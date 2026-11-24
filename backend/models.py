"""SQLAlchemy models for the commuttify schema (metadata mirrors sql/001_schema.sql).

Geometry columns (stops.geom, shape_geoms.geom, route_segments.geom) are managed
with explicit PostGIS SQL (ST_SetSRID / ST_GeomFromText / ST_MakeLine) rather than
GeoAlchemy2, so plain SQLAlchemy Core inserts stay fast and dependency-light.
"""

from __future__ import annotations

from sqlalchemy import (
    BIGINT,
    DATE,
    DOUBLE_PRECISION,
    INTEGER,
    SMALLINT,
    TEXT,
    Column,
    MetaData,
    Table,
)

metadata = MetaData(naming_convention={"ix": "ix_%(table_name)s_%(column_0_name)s"})

agency = Table(
    "agency", metadata,
    Column("agency_id", TEXT, primary_key=True),
    Column("agency_name", TEXT),
    Column("agency_url", TEXT),
    Column("agency_timezone", TEXT),
    Column("agency_lang", TEXT),
    Column("agency_phone", TEXT),
)

calendar = Table(
    "calendar", metadata,
    Column("service_id", TEXT, primary_key=True),
    Column("monday", SMALLINT, nullable=False),
    Column("tuesday", SMALLINT, nullable=False),
    Column("wednesday", SMALLINT, nullable=False),
    Column("thursday", SMALLINT, nullable=False),
    Column("friday", SMALLINT, nullable=False),
    Column("saturday", SMALLINT, nullable=False),
    Column("sunday", SMALLINT, nullable=False),
    Column("start_date", DATE, nullable=False),
    Column("end_date", DATE, nullable=False),
)

stops = Table(
    "stops", metadata,
    Column("stop_id", TEXT, primary_key=True),
    Column("stop_code", TEXT),
    Column("stop_name", TEXT, nullable=False),
    Column("stop_lat", DOUBLE_PRECISION, nullable=False),
    Column("stop_lon", DOUBLE_PRECISION, nullable=False),
    Column("zone_id", TEXT),
    Column("location_type", SMALLINT, default=0),
    Column("parent_station", TEXT),
    # geom GEOMETRY(Point, 4326) — created by raw SQL in ingest_gtfs.py
)

routes = Table(
    "routes", metadata,
    Column("route_id", TEXT, primary_key=True),
    Column("agency_id", TEXT),
    Column("route_short_name", TEXT),
    Column("route_long_name", TEXT),
    Column("route_desc", TEXT),
    Column("route_type", SMALLINT),
    Column("route_url", TEXT),
    Column("route_color", TEXT),
    Column("route_text_color", TEXT),
)

trips = Table(
    "trips", metadata,
    Column("route_id", TEXT, nullable=False),
    Column("service_id", TEXT),
    Column("trip_id", TEXT, primary_key=True),
    Column("trip_headsign", TEXT),
    Column("trip_short_name", TEXT),
    Column("direction_id", SMALLINT, default=0),
    Column("block_id", TEXT),
    Column("shape_id", TEXT),
    Column("wheelchair_accessible", TEXT),
    Column("bikes_allowed", TEXT),
)

stop_times = Table(
    "stop_times", metadata,
    Column("trip_id", TEXT, nullable=False, primary_key=True),
    Column("arrival_time", TEXT),
    Column("departure_time", TEXT),
    Column("stop_id", TEXT, nullable=False),
    Column("stop_sequence", INTEGER, nullable=False, primary_key=True),
    Column("stop_headsign", TEXT),
    Column("pickup_type", SMALLINT),
    Column("drop_off_type", SMALLINT),
    Column("shape_dist_traveled", DOUBLE_PRECISION),
)

shapes = Table(
    "shapes", metadata,
    Column("shape_id", TEXT, nullable=False, primary_key=True),
    Column("shape_pt_lat", DOUBLE_PRECISION, nullable=False, primary_key=True),
    Column("shape_pt_lon", DOUBLE_PRECISION, nullable=False, primary_key=True),
    Column("shape_pt_sequence", INTEGER, nullable=False, primary_key=True),
    Column("shape_dist_traveled", DOUBLE_PRECISION),
)

shape_geoms = Table(
    "shape_geoms", metadata,
    Column("shape_id", TEXT, primary_key=True),
    # geom GEOMETRY(LineString, 4326) — raw SQL
    Column("n_points", INTEGER),
    Column("length_m", DOUBLE_PRECISION),
)

route_segments = Table(
    "route_segments", metadata,
    Column("segment_id", BIGINT, primary_key=True, autoincrement=True),
    Column("route_id", TEXT, nullable=False),
    Column("direction_id", SMALLINT, nullable=False, default=0),
    Column("from_stop_id", TEXT, nullable=False),
    Column("to_stop_id", TEXT, nullable=False),
    Column("from_stop_seq", INTEGER, nullable=False),
    Column("to_stop_seq", INTEGER, nullable=False),
    Column("from_stop_name", TEXT),
    Column("to_stop_name", TEXT),
    Column("shape_id", TEXT),
    # geom GEOMETRY(LineString, 4326) — raw SQL
    Column("length_m", DOUBLE_PRECISION, nullable=False),
    Column("base_travel_time", DOUBLE_PRECISION, nullable=False),
    Column("time_source", TEXT, nullable=False, default="schedule"),
    Column("source", BIGINT),
    Column("target", BIGINT),
)

historical_segment_speeds = Table(
    "historical_segment_speeds", metadata,
    Column("segment_id", BIGINT, primary_key=True, nullable=False),
    Column("day_of_week", SMALLINT, primary_key=True, nullable=False),
    Column("hour_of_day", SMALLINT, primary_key=True, nullable=False),
    Column("avg_time_seconds", DOUBLE_PRECISION, nullable=False),
    Column("sample_count", INTEGER, nullable=False, default=0),
    # updated_at TIMESTAMPTZ DEFAULT now() — server side
)
