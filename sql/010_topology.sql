-- ============================================================================
-- Topology builder (pure PostGIS — replaces pgr_createTopology).
--
-- Nodes are BUS STOPS: every segment endpoint is a stop, so all segments
-- meeting at the same stop share one node. source/target on route_segments
-- point at route_nodes.node_id. Idempotent: safe to re-run after re-ingest.
-- Run as the postgres user, e.g. via backend/db.py run_sql_file().
-- ============================================================================

DO $$
BEGIN
    CREATE TABLE IF NOT EXISTS route_nodes (
        node_id BIGSERIAL PRIMARY KEY,
        stop_id TEXT NOT NULL UNIQUE,
        geom    GEOMETRY(Point, 4326)
    );
    CREATE INDEX IF NOT EXISTS idx_route_nodes_geom ON route_nodes USING GIST (geom);

    -- register every stop used by at least one segment
    INSERT INTO route_nodes (stop_id, geom)
    SELECT s.stop_id, s.geom
    FROM stops s
    JOIN (
        SELECT DISTINCT from_stop_id AS sid FROM route_segments
        UNION
        SELECT DISTINCT to_stop_id FROM route_segments
    ) used ON used.sid = s.stop_id
    ON CONFLICT (stop_id) DO NOTHING;

    -- point each segment endpoint at its stop's node (fills NULLs, fixes
    -- stale ids after a rebuild)
    UPDATE route_segments rs
    SET source = n.node_id
    FROM route_nodes n
    WHERE n.stop_id = rs.from_stop_id
      AND rs.source IS DISTINCT FROM n.node_id;

    UPDATE route_segments rs
    SET target = n.node_id
    FROM route_nodes n
    WHERE n.stop_id = rs.to_stop_id
      AND rs.target IS DISTINCT FROM n.node_id;
END $$;
