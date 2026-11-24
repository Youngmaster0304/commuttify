-- ============================================================================
-- Commuttify schema (Prompt 1): GTFS + PostGIS + model tables
--
-- How to enable the extensions (run as superuser, e.g. `postgres`):
--   PostGIS: CREATE EXTENSION IF NOT EXISTS postgis;
--      (bundled in the postgis/postgis Docker image; on bare Debian/Ubuntu:
--       apt-get install postgresql-16-postgis-3)
-- No pgRouting required: the graph topology (route_nodes + source/target)
-- is built by sql/010_topology.sql in pure PostGIS (run by ingest_gtfs.py
-- step 6; safe to re-run at any time).
-- This script is idempotent: every object uses IF NOT EXISTS.
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS postgis;

-- ----------------------------------------------------------------------------
-- Standard GTFS tables (ids stored as TEXT to preserve leading zeros)
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS agency (
    agency_id       TEXT PRIMARY KEY,
    agency_name     TEXT,
    agency_url      TEXT,
    agency_timezone TEXT,
    agency_lang     TEXT,
    agency_phone    TEXT
);

CREATE TABLE IF NOT EXISTS calendar (
    service_id TEXT PRIMARY KEY,
    monday     SMALLINT NOT NULL,
    tuesday    SMALLINT NOT NULL,
    wednesday  SMALLINT NOT NULL,
    thursday   SMALLINT NOT NULL,
    friday     SMALLINT NOT NULL,
    saturday   SMALLINT NOT NULL,
    sunday     SMALLINT NOT NULL,
    start_date DATE NOT NULL,
    end_date   DATE NOT NULL
);

CREATE TABLE IF NOT EXISTS calendar_dates (
    service_id     TEXT NOT NULL,
    date           DATE NOT NULL,
    exception_type SMALLINT NOT NULL,
    PRIMARY KEY (service_id, date)
);

CREATE TABLE IF NOT EXISTS stops (
    stop_id        TEXT PRIMARY KEY,
    stop_code      TEXT,
    stop_name      TEXT NOT NULL,
    stop_lat       DOUBLE PRECISION NOT NULL,
    stop_lon       DOUBLE PRECISION NOT NULL,
    zone_id        TEXT,
    location_type  SMALLINT DEFAULT 0,
    parent_station TEXT,
    -- PostGIS point column required by the challenge (EPSG:4326 = WGS84 lon/lat order
    -- when constructed with ST_MakePoint(lon, lat))
    geom           GEOMETRY(Point, 4326)
);

CREATE TABLE IF NOT EXISTS routes (
    route_id         TEXT PRIMARY KEY,
    agency_id        TEXT,
    route_short_name TEXT,
    route_long_name  TEXT,
    route_desc       TEXT,
    route_type       SMALLINT,
    route_url        TEXT,
    route_color      TEXT,
    route_text_color TEXT
);

CREATE TABLE IF NOT EXISTS trips (
    route_id        TEXT NOT NULL REFERENCES routes (route_id),
    service_id      TEXT,
    trip_id         TEXT PRIMARY KEY,
    trip_headsign   TEXT,
    trip_short_name TEXT,
    direction_id    SMALLINT DEFAULT 0,
    block_id        TEXT,
    shape_id        TEXT,
    wheelchair_accessible TEXT,
    bikes_allowed   TEXT
);

CREATE TABLE IF NOT EXISTS stop_times (
    trip_id        TEXT NOT NULL,
    arrival_time   TEXT,
    departure_time TEXT,
    stop_id        TEXT NOT NULL,
    stop_sequence  INTEGER NOT NULL,
    stop_headsign  TEXT,
    pickup_type    SMALLINT,
    drop_off_type  SMALLINT,
    shape_dist_traveled DOUBLE PRECISION,
    PRIMARY KEY (trip_id, stop_sequence)
);

-- Raw shape points, plus a derived LineString per shape_id (built by ingest_gtfs.py)
CREATE TABLE IF NOT EXISTS shapes (
    shape_id             TEXT NOT NULL,
    shape_pt_lat         DOUBLE PRECISION NOT NULL,
    shape_pt_lon         DOUBLE PRECISION NOT NULL,
    shape_pt_sequence    INTEGER NOT NULL,
    shape_dist_traveled  DOUBLE PRECISION,
    PRIMARY KEY (shape_id, shape_pt_sequence)
);

CREATE TABLE IF NOT EXISTS shape_geoms (
    shape_id TEXT PRIMARY KEY,
    geom     GEOMETRY(LineString, 4326) NOT NULL,
    n_points INTEGER,
    length_m DOUBLE PRECISION
);

-- ----------------------------------------------------------------------------
-- route_segments: the EDGES of the routing graph (challenge requirement #3)
-- One row per consecutive stop pair along a representative trip of each
-- (route, direction). geom is the sliced shape LineString between the stops.
-- base_travel_time = schedule seconds (falls back to length/default speed).
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS route_segments (
    segment_id      BIGSERIAL PRIMARY KEY,
    route_id        TEXT NOT NULL,
    direction_id    SMALLINT NOT NULL DEFAULT 0,
    from_stop_id    TEXT NOT NULL,
    to_stop_id      TEXT NOT NULL,
    from_stop_seq   INTEGER NOT NULL,
    to_stop_seq     INTEGER NOT NULL,
    from_stop_name  TEXT,
    to_stop_name    TEXT,
    shape_id        TEXT,
    -- GEOMETRY(LineString, 4326) required by the challenge
    geom            GEOMETRY(LineString, 4326) NOT NULL,
    length_m        DOUBLE PRECISION NOT NULL,
    base_travel_time DOUBLE PRECISION NOT NULL,  -- seconds
    time_source     TEXT NOT NULL DEFAULT 'schedule',  -- 'schedule' | 'default'
    -- topology node ids at each endpoint (built by sql/010_topology.sql)
    source          BIGINT,
    target          BIGINT,
    UNIQUE (route_id, direction_id, from_stop_seq, to_stop_id)
);

CREATE INDEX IF NOT EXISTS idx_route_segments_geom    ON route_segments USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_route_segments_route   ON route_segments (route_id, direction_id);
CREATE INDEX IF NOT EXISTS idx_route_segments_from    ON route_segments (from_stop_id);
CREATE INDEX IF NOT EXISTS idx_route_segments_to      ON route_segments (to_stop_id);

-- Topology (route_nodes + source/target) is built by sql/010_topology.sql
-- after route_segments exist — see ingest_gtfs.py step 6.

CREATE TABLE IF NOT EXISTS route_nodes (
    node_id BIGSERIAL PRIMARY KEY,
    stop_id TEXT NOT NULL UNIQUE,
    geom    GEOMETRY(Point, 4326)
);
CREATE INDEX IF NOT EXISTS idx_route_nodes_geom ON route_nodes USING GIST (geom);

CREATE INDEX IF NOT EXISTS idx_route_segments_source ON route_segments (source);
CREATE INDEX IF NOT EXISTS idx_route_segments_target ON route_segments (target);

-- ----------------------------------------------------------------------------
-- historical_segment_speeds: aggregated GPS travel times (challenge: Prompt 2)
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS historical_segment_speeds (
    segment_id       BIGINT NOT NULL REFERENCES route_segments (segment_id) ON DELETE CASCADE,
    day_of_week      SMALLINT NOT NULL CHECK (day_of_week BETWEEN 0 AND 6),  -- 0 = Monday
    hour_of_day      SMALLINT NOT NULL CHECK (hour_of_day BETWEEN 0 AND 23), -- IST
    avg_time_seconds DOUBLE PRECISION NOT NULL,
    sample_count     INTEGER NOT NULL DEFAULT 0,
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (segment_id, day_of_week, hour_of_day)
);

CREATE INDEX IF NOT EXISTS idx_hist_dow_hour ON historical_segment_speeds (day_of_week, hour_of_day);

-- ----------------------------------------------------------------------------
-- Optional helper: live speeds live in Redis (keys live:seg:<segment_id>),
-- no table needed. This view gives the router a single-place fallback check.
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW segment_lookup AS
SELECT s.segment_id,
       s.route_id,
       s.from_stop_id,
       s.to_stop_id,
       s.length_m,
       s.base_travel_time,
       h.day_of_week,
       h.hour_of_day,
       h.avg_time_seconds AS historical_time,
       h.sample_count
FROM route_segments s
LEFT JOIN historical_segment_speeds h ON h.segment_id = s.segment_id;
