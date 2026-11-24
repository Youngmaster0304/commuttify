"""Prompt 1 — Static GTFS ingestion into PostgreSQL/PostGIS/pgRouting.

Reads unzipped GTFS .txt files with Pandas, bulk-loads them with psycopg2 COPY,
builds PostGIS geometry columns, then derives `route_segments` (the routing-graph
edges) by slicing each route's shape between consecutive stops.

Usage:
    python -m backend.ingest_gtfs --gtfs-dir data/gtfs_sample --rebuild
    python -m backend.ingest_gtfs --gtfs-dir data/gtfs          # full feed

Comments in sql/001_schema.sql explain how the PostGIS/pgRouting extensions
are enabled; this script assumes the schema has already been applied.
"""

from __future__ import annotations

import argparse
import io
import math
import sys
import time
from pathlib import Path

import pandas as pd
from shapely.geometry import LineString, Point
from shapely.ops import substring
from sqlalchemy import text

from . import config, db, models

REQUIRED_FILES = ("stops.txt", "routes.txt", "trips.txt", "stop_times.txt")
OPTIONAL_FILES = ("shapes.txt", "calendar.txt", "agency.txt", "feed_info.txt")

COPY_TABLES = [
    "agency", "calendar", "stops", "routes", "trips", "stop_times", "shapes",
]

DEFAULT_SPEED_MPS = config.DEFAULT_BUS_SPEED_MPS
MAX_LEG_SCHEDULE_S = 7200.0  # a single stop-to-stop leg longer than 2 h is bogus


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

def read_gtfs(gtfs_dir: Path) -> dict[str, pd.DataFrame]:
    missing = [f for f in REQUIRED_FILES if not (gtfs_dir / f).exists()]
    if missing:
        sys.exit(
            f"ERROR: missing GTFS files in {gtfs_dir}: {', '.join(missing)}\n"
            "Download the full 'Delhi Buses: GTFS Static Data' ZIP from "
            "https://delhi.transportstack.in/data-services (dataset id 1), unzip it "
            "so the .txt files sit directly in data/gtfs/, then re-run."
        )
    frames: dict[str, pd.DataFrame] = {}
    for name in REQUIRED_FILES + OPTIONAL_FILES:
        path = gtfs_dir / name
        if not path.exists():
            continue
        df = pd.read_csv(
            path,
            dtype=str,
            keep_default_na=False,
            na_values=[],
            low_memory=False,
        )
        frames[name.replace(".txt", "")] = df
        print(f"  read {name:16s} {len(df):>10,} rows")
    return frames


def copy_df(conn, table: str, df: pd.DataFrame) -> None:
    """Fast bulk load: psycopg2 COPY FROM STDIN (CSV, empty field = NULL)."""
    if df.empty:
        return
    buf = io.StringIO()
    df.to_csv(buf, index=False, header=False, na_rep="")
    buf.seek(0)
    cols = ", ".join(f'"{c}"' for c in df.columns)
    conn.copy_expert(
        f"COPY {table} ({cols}) FROM STDIN WITH (FORMAT csv, NULL '')", buf
    )


def parse_hhmmss(value: str) -> float | None:
    """GTFS times may exceed 24:00:00. Returns seconds or None."""
    if not value:
        return None
    parts = value.split(":")
    if len(parts) != 3:
        return None
    try:
        h, m, s = (int(p) for p in parts)
    except ValueError:
        return None
    return h * 3600 + m * 60 + s


def haversine_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def line_length_m(coords) -> float:
    return sum(
        haversine_m(coords[i][0], coords[i][1], coords[i + 1][0], coords[i + 1][1])
        for i in range(len(coords) - 1)
    )


def wkt_linestring(coords) -> str:
    pts = ", ".join(f"{lon:.7f} {lat:.7f}" for lon, lat in coords)
    return f"LINESTRING ({pts})"


# --------------------------------------------------------------------------- #
# geometry builders
# --------------------------------------------------------------------------- #

def build_shape_geoms(shapes_df: pd.DataFrame) -> dict[str, LineString]:
    """shapes.txt -> {shape_id: shapely LineString} ordered by sequence."""
    out: dict[str, LineString] = {}
    df = shapes_df.copy()
    df["shape_pt_sequence"] = df["shape_pt_sequence"].astype(int)
    df = df.sort_values(["shape_id", "shape_pt_sequence"])
    for shape_id, grp in df.groupby("shape_id", sort=False):
        coords = list(zip(grp["shape_pt_lon"].astype(float), grp["shape_pt_lat"].astype(float)))
        if len(coords) >= 2:
            out[str(shape_id)] = LineString(coords)
    return out


def slice_shape(
    shape: LineString | None,
    stop_a: tuple[float, float],
    stop_b: tuple[float, float],
) -> list[tuple[float, float]]:
    """LineString of the shape between the projections of stop_a and stop_b.

    Endpoints are replaced by the exact stop coordinates so pgRouting nodes
    coincide at shared stops. Falls back to a straight stop-to-stop line when
    the shape is missing or the projection is degenerate.
    """
    straight = [stop_a, stop_b]
    if shape is None or shape.is_empty:
        return straight
    pa = shape.project(Point(stop_a))
    pb = shape.project(Point(stop_b))
    if pb < pa:  # stop order runs against shape direction
        pa, pb = pb, pa
    if pb - pa < 1.0:  # projections collapse (<1 m apart): use straight line
        return straight
    piece = substring(shape, pa, pb)
    coords = list(piece.coords)
    if len(coords) < 2:
        return straight
    coords[0] = stop_a
    coords[-1] = stop_b
    # de-duplicate consecutive identical points (endpoint replacement can create them)
    cleaned = [coords[0]]
    for c in coords[1:]:
        if c != cleaned[-1]:
            cleaned.append(c)
    return cleaned if len(cleaned) >= 2 else straight


# --------------------------------------------------------------------------- #
# main ingestion
# --------------------------------------------------------------------------- #

def ingest(gtfs_dir: Path, rebuild: bool, skip_topology: bool) -> None:
    t0 = time.time()
    print(f"[1/6] reading GTFS from {gtfs_dir}")
    frames = read_gtfs(gtfs_dir)

    engine = db.get_engine()

    if rebuild:
        print("[2/6] clearing existing GTFS data")
        with engine.begin() as conn:
            # child tables first (route_segments/hist reference GTFS ids)
            for tbl in (
                "historical_segment_speeds", "route_segments", "route_nodes",
                "shape_geoms",
                "stop_times", "trips", "shapes", "calendar_dates", "calendar",
                "routes", "stops", "agency",
            ):
                conn.execute(text(f"TRUNCATE {tbl} RESTART IDENTITY CASCADE"))
    else:
        print("[2/6] appending (use --rebuild to start clean)")

    print("[3/6] bulk loading GTFS tables via COPY")
    raw = engine.raw_connection()
    try:
        conn = raw.cursor()
        # normalise column sets to what the tables expect
        colmap = {
            "agency": ["agency_id", "agency_name", "agency_url", "agency_timezone",
                       "agency_lang", "agency_phone"],
            "calendar": ["service_id", "monday", "tuesday", "wednesday", "thursday",
                         "friday", "saturday", "sunday", "start_date", "end_date"],
            "stops": ["stop_id", "stop_code", "stop_name", "stop_lat", "stop_lon",
                      "zone_id", "location_type", "parent_station"],
            "routes": ["route_id", "agency_id", "route_short_name", "route_long_name",
                       "route_desc", "route_type", "route_url", "route_color",
                       "route_text_color"],
            "trips": ["route_id", "service_id", "trip_id", "trip_headsign",
                      "trip_short_name", "direction_id", "block_id", "shape_id",
                      "wheelchair_accessible", "bikes_allowed"],
            "stop_times": ["trip_id", "arrival_time", "departure_time", "stop_id",
                           "stop_sequence", "stop_headsign", "pickup_type",
                           "drop_off_type", "shape_dist_traveled"],
            "shapes": ["shape_id", "shape_pt_lat", "shape_pt_lon",
                       "shape_pt_sequence", "shape_dist_traveled"],
        }
        for table in COPY_TABLES:
            if table not in frames:
                continue
            df = frames[table]
            wanted = colmap[table]
            for c in wanted:
                if c not in df.columns:
                    df[c] = ""
            df = df[wanted]
            # numeric coercion: non-numeric -> NULL (empty)
            for c in df.columns:
                if c.endswith(("_lat", "_lon", "_sequence", "_type")) or c in (
                    "route_type", "direction_id", "stop_sequence",
                    "shape_pt_sequence", "monday", "tuesday", "wednesday",
                    "thursday", "friday", "saturday", "sunday",
                ):
                    df[c] = pd.to_numeric(df[c], errors="coerce")
            copy_df(conn, table, df)
            print(f"  copied {table:12s} {len(df):>10,} rows")
        raw.commit()
    finally:
        raw.close()

    print("[4/6] building PostGIS geometry columns")
    with engine.begin() as conn:
        conn.execute(text(
            "UPDATE stops SET geom = ST_SetSRID(ST_MakePoint(stop_lon, stop_lat), 4326) "
            "WHERE geom IS NULL"
        ))
        n_stops = conn.execute(text(
            "SELECT count(*) FROM stops WHERE geom IS NOT NULL"
        )).scalar()
        print(f"  stops.geom set on {n_stops:,} rows")

    # shape_geoms
    shapes_df = frames.get("shapes")
    shape_map: dict[str, LineString] = {}
    if shapes_df is not None and not shapes_df.empty:
        print("  building shape LineStrings from shapes.txt")
        shape_map = build_shape_geoms(shapes_df)
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM shape_geoms"))
            rows = [
                {
                    "shape_id": sid,
                    "wkt": wkt_linestring(list(geom.coords)),
                    "n_points": len(geom.coords),
                    "length_m": line_length_m(list(geom.coords)),
                }
                for sid, geom in shape_map.items()
            ]
            conn.execute(
                text(
                    "INSERT INTO shape_geoms (shape_id, geom, n_points, length_m) "
                    "VALUES (:shape_id, ST_GeomFromText(:wkt, 4326), :n_points, :length_m)"
                ),
                rows,
            )
            print(f"  shape_geoms: {len(rows):,} LineStrings")

    print("[5/6] deriving route_segments (graph edges)")
    trips_df = frames["trips"].copy()
    stops_df = frames["stops"].copy()
    # free the big frames: stop_times (2.7M rows) is re-read from Postgres
    # below as a stream — copying it in pandas OOM'd on this feed
    frames.pop("stop_times", None)
    frames.pop("shapes", None)

    trips_df["direction_id"] = pd.to_numeric(
        trips_df.get("direction_id", pd.Series(dtype=float)), errors="coerce"
    ).fillna(0).astype(int)
    stops_df["stop_lat"] = stops_df["stop_lat"].astype(float)
    stops_df["stop_lon"] = stops_df["stop_lon"].astype(float)

    stop_pos = {
        str(r.stop_id): (float(r.stop_lon), float(r.stop_lat), r.stop_name)
        for r in stops_df.itertuples(index=False)
    }
    trip_route = {
        str(k): str(v)
        for k, v in zip(trips_df["trip_id"], trips_df["route_id"])
    }
    trip_shape = {
        str(k): (str(v) if pd.notna(v) else "")
        for k, v in zip(trips_df["trip_id"],
                        trips_df.get("shape_id", pd.Series(dtype=str)))
    }
    trip_dir = {
        str(k): int(v)
        for k, v in zip(trips_df["trip_id"], trips_df["direction_id"])
    }

    # stream stop_times per trip (already COPY-loaded), no pandas copy
    trip_stops: dict[str, list] = {}
    with engine.connect() as conn:
        result = conn.execution_options(stream_results=True).execute(text(
            "SELECT trip_id, stop_id, arrival_time, departure_time "
            "FROM stop_times WHERE stop_sequence IS NOT NULL "
            "ORDER BY trip_id, stop_sequence"
        ))
        cur_tid: str | None = None
        seq: list = []
        for tid, sid, arr, dep in result:
            tid = str(tid)
            if tid != cur_tid:
                if cur_tid is not None:
                    trip_stops[cur_tid] = seq
                cur_tid = tid
                seq = []
            seq.append((str(sid), arr, dep))
        if cur_tid is not None:
            trip_stops[cur_tid] = seq

    # representative trip per (route, direction) = the one with most stops
    rep_trip: dict[tuple[str, int], str] = {}
    for tid, stops_seq in trip_stops.items():
        route = trip_route.get(tid)
        if route is None:
            continue
        key = (str(route), int(trip_dir.get(tid, 0)))
        if key not in rep_trip or len(stops_seq) > len(trip_stops[rep_trip[key]]):
            rep_trip[key] = tid

    seg_rows: list[dict] = []
    for (route_id, direction_id), tid in sorted(rep_trip.items()):
        seq = trip_stops[tid]
        shape = shape_map.get(str(trip_shape.get(tid, "") or ""))
        for i in range(len(seq) - 1):
            (sid_a, arr_a, dep_a), (sid_b, arr_b, dep_b) = seq[i], seq[i + 1]
            pa, pb = stop_pos.get(sid_a), stop_pos.get(sid_b)
            if pa is None or pb is None:
                continue
            coords = slice_shape(shape, (pa[0], pa[1]), (pb[0], pb[1]))
            length_m = line_length_m(coords)

            sched = None
            t_dep = parse_hhmmss(str(dep_a))
            t_arr = parse_hhmmss(str(arr_b))
            if t_dep is not None and t_arr is not None and t_arr > t_dep:
                delta = t_arr - t_dep
                if delta <= MAX_LEG_SCHEDULE_S:
                    sched = delta
            if sched is not None:
                base, src = sched, "schedule"
            else:
                base, src = length_m / DEFAULT_SPEED_MPS, "default"

            seg_rows.append({
                "route_id": route_id,
                "direction_id": direction_id,
                "from_stop_id": str(sid_a),
                "to_stop_id": str(sid_b),
                "from_stop_seq": i + 1,
                "to_stop_seq": i + 2,
                "from_stop_name": pa[2],
                "to_stop_name": pb[2],
                "shape_id": str(trip_shape.get(tid, "") or "") or None,
                "wkt": wkt_linestring(coords),
                "length_m": round(length_m, 2),
                "base_travel_time": round(base, 1),
                "time_source": src,
            })

    with engine.begin() as conn:
        n = conn.execute(text("SELECT count(*) FROM route_segments")).scalar()
        if n and not rebuild:
            print(f"  route_segments already has {n:,} rows; pass --rebuild to replace")
        else:
            conn.execute(text("DELETE FROM route_segments"))
            for chunk_start in range(0, len(seg_rows), 2000):
                chunk = seg_rows[chunk_start:chunk_start + 2000]
                conn.execute(
                    text(
                        "INSERT INTO route_segments "
                        "(route_id, direction_id, from_stop_id, to_stop_id, "
                        " from_stop_seq, to_stop_seq, from_stop_name, to_stop_name, "
                        " shape_id, geom, length_m, base_travel_time, time_source) "
                        "VALUES "
                        "(:route_id, :direction_id, :from_stop_id, :to_stop_id, "
                        " :from_stop_seq, :to_stop_seq, :from_stop_name, :to_stop_name, "
                        " :shape_id, ST_GeomFromText(:wkt, 4326), :length_m, "
                        " :base_travel_time, :time_source)"
                    ),
                    chunk,
                )
            print(f"  route_segments: {len(seg_rows):,} edges "
                  f"({len(rep_trip):,} representative trips)")

    print("[6/6] building graph topology (route_nodes + source/target)")
    if skip_topology:
        print("  skipped (--skip-topology)")
    else:
        db.run_sql_file(str(config.SQL_DIR / "010_topology.sql"))
        with engine.connect() as conn:
            n_nodes = conn.execute(text(
                "SELECT count(*) FROM route_nodes"
            )).scalar()
            n_null = conn.execute(text(
                "SELECT count(*) FROM route_segments WHERE source IS NULL OR target IS NULL"
            )).scalar()
        print(f"  route_nodes: {n_nodes:,}")
        if n_null:
            print(f"  WARNING: {n_null} segments without topology nodes")

    with engine.connect() as conn:
        counts = {
            t: conn.execute(text(f"SELECT count(*) FROM {t}")).scalar()
            for t in ("stops", "routes", "trips", "stop_times", "shape_geoms",
                      "route_segments")
        }
    print(f"done in {time.time() - t0:.1f}s -> " +
          ", ".join(f"{k}={v:,}" for k, v in counts.items()))


def main() -> None:
    ap = argparse.ArgumentParser(description="Ingest static GTFS into PostgreSQL")
    ap.add_argument("--gtfs-dir", default=str(config.GTFS_DIR),
                    help="directory containing the unzipped GTFS .txt files")
    ap.add_argument("--rebuild", action="store_true",
                    help="TRUNCATE existing GTFS tables first")
    ap.add_argument("--skip-topology", action="store_true",
                    help="do not build route_nodes / source / target topology")
    args = ap.parse_args()
    ingest(Path(args.gtfs_dir), args.rebuild, args.skip_topology)


if __name__ == "__main__":
    main()
