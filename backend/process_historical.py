"""Prompt 2 — Historical travel-time model from daily SQLite GPS databases.

Processes the October 2026 DTC bus GPS dump (one SQLite file per day,
table `vehicle_feed`, ~31M rows/day, NO indexes) in a memory-bounded way:

  * streams each database with a server-side cursor (fetchmany, never LOAD ALL),
  * filters GPS noise (speed > 80 km/h, out-of-bbox, bad coords),
  * snaps every point to the nearest `route_segment` of its own route
    (per-route shapely STRtree, vectorised, max snap distance ~165 m),
  * identifies dwell (speed == 0 within 30 m of a stop) for reporting,
  * reconstructs per-vehicle segment traversals (first-seen timestamps,
    bridged across chunks) and aggregates travel time by
    day-of-week (0=Mon) x hour-of-day (IST),
  * upserts into `historical_segment_speeds`
    (segment_id, day_of_week, hour_of_day, avg_time_seconds, sample_count).

Usage:
    python -m backend.process_historical --limit 100000        # smoke test
    python -m backend.process_historical                       # all days, all rows
    python -m backend.process_historical --days 2026_10_01     # one day
    python -m backend.process_historical --dry-run             # no DB writes
"""

from __future__ import annotations

import argparse
import datetime as dt
import math
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import shapely
from shapely import STRtree
from sqlalchemy import text

from . import config, db

MAX_SPEED_KMH = 80.0          # drop GPS anomalies above this
DWELL_SPEED_MS = 0.0          # speed == 0 identifies dwell
DWELL_STOP_M = 30.0           # ...when within 30 m of a stop
MAX_SNAP_DEG = 0.0015         # ~165 m: farther snaps are treated as noise
MAX_TRANSIT_S = 900.0         # a segment traversal longer than 15 min is a gap
MIN_TRANSIT_S = 0.5           # sub-second jumps are GPS noise
CHUNK_DEFAULT = 500_000
PROGRESS_EVERY = 2_000_000

# column order of vehicle_feed
SQL_COLS = ("vehicle_id", "lat", "lng", "speed", "route_id", "trip_id",
            "timestamp", "date", "time")


# --------------------------------------------------------------------------- #
# segment + stop geometries loaded once from Postgres
# --------------------------------------------------------------------------- #

class SnapIndex:
    """Per-route STRtree over route_segments (built lazily per route)."""

    def __init__(self) -> None:
        self.seg_ids: np.ndarray = np.empty(0, dtype=np.int64)
        self.seg_route: np.ndarray = np.empty(0, dtype=np.int64)
        self._geoms: list = []
        self._route_pos: dict[int, list[int]] = {}
        self._trees: dict[int, tuple[STRtree, np.ndarray]] = {}

    def load(self) -> None:
        engine = db.get_engine()
        with engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT segment_id, route_id, ST_AsText(geom) FROM route_segments"
            )).fetchall()
        if not rows:
            sys.exit("ERROR: route_segments is empty — run ingest_gtfs.py first.")
        self.seg_ids = np.array([r[0] for r in rows], dtype=np.int64)
        self._geoms = [shapely.from_wkt(r[2]) for r in rows]
        for i, r in enumerate(rows):
            self._route_pos.setdefault(int(r[1]), []).append(i)
        print(f"  snap index: {len(rows):,} segments across "
              f"{len(self._route_pos):,} routes")

    def _tree(self, route: int) -> tuple[STRtree, np.ndarray] | None:
        t = self._trees.get(route)
        if t is not None:
            return t
        pos = self._route_pos.get(route)
        if not pos:
            self._trees[route] = None  # type: ignore[assignment]
            return None
        geoms = [self._geoms[i] for i in pos]
        tree = STRtree(geoms)
        ids = self.seg_ids[np.array(pos, dtype=np.int64)]
        self._trees[route] = (tree, ids)
        return self._trees[route]  # type: ignore[return-value]

    def snap(self, lon: np.ndarray, lat: np.ndarray,
             route: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Returns (segment_id per point or -1, snap distance in degrees)."""
        n = len(lon)
        out_ids = np.full(n, -1, dtype=np.int64)
        out_dist = np.full(n, np.nan, dtype=np.float64)
        pts = shapely.points(lon, lat)
        for rt in np.unique(route):
            if np.isnan(rt):
                continue
            mask = route == rt
            entry = self._tree(int(rt))
            if entry is None:
                continue
            tree, ids = entry
            res = tree.query_nearest(
                pts[mask], all_matches=False, max_distance=MAX_SNAP_DEG,
                return_distance=True,
            )
            if res is None or len(res) == 0:
                continue
            # shapely >=2 returns (indices(2,n), distances) or (2,n) array
            if isinstance(res, tuple):
                idx, dist = res
            else:
                idx, dist = res
                # shape (2, n): row0 input idx, row1 tree idx
            in_idx = idx[0] if idx.ndim == 2 else idx
            tree_idx = idx[1] if idx.ndim == 2 else idx
            m = np.where(mask)[0]
            out_ids[m[in_idx]] = ids[tree_idx]
            out_dist[m[in_idx]] = dist
        return out_ids, out_dist


class StopIndex:
    """Global STRtree over stops for dwell detection."""

    def __init__(self) -> None:
        self.ids: list[str] = []
        self.lon = np.empty(0)
        self.lat = np.empty(0)
        self._tree: STRtree | None = None

    def load(self) -> None:
        with db.get_engine().connect() as conn:
            rows = conn.execute(text(
                "SELECT stop_id, stop_lon, stop_lat FROM stops"
            )).fetchall()
        self.ids = [r[0] for r in rows]
        self.lon = np.array([float(r[1]) for r in rows])
        self.lat = np.array([float(r[2]) for r in rows])
        if rows:
            self._tree = STRtree(shapely.points(self.lon, self.lat))

    def near(self, lon: np.ndarray, lat: np.ndarray,
             max_m: float) -> np.ndarray:
        """Boolean mask: point is within max_m metres of its nearest stop."""
        if self._tree is None or len(lon) == 0:
            return np.zeros(len(lon), dtype=bool)
        res = self._tree.query_nearest(
            shapely.points(lon, lat), all_matches=False,
            max_distance=max_m / 111_000.0, return_distance=True,
        )
        if res is None or len(res) == 0:
            return np.zeros(len(lon), dtype=bool)
        idx, dist = res if isinstance(res, tuple) else (res, None)
        in_idx = idx[0] if idx.ndim == 2 else idx
        mask = np.zeros(len(lon), dtype=bool)
        mask[in_idx] = True
        return mask


# --------------------------------------------------------------------------- #
# chunk processing
# --------------------------------------------------------------------------- #

def prepare_chunk(raw: pd.DataFrame) -> pd.DataFrame | None:
    """Type-cast + noise filter. Returns None when nothing survives."""
    df = raw.copy()
    df.columns = SQL_COLS
    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df["lng"] = pd.to_numeric(df["lng"], errors="coerce")
    df["speed"] = pd.to_numeric(df["speed"], errors="coerce")
    df["route_id"] = pd.to_numeric(df["route_id"], errors="coerce")
    df["ts"] = pd.to_numeric(df["timestamp"], errors="coerce")

    min_lat, min_lon, max_lat, max_lon = config.DELHI_BBOX
    ok = (
        df["lat"].between(min_lat, max_lat)
        & df["lng"].between(min_lon, max_lon)
        & df["ts"].notna() & (df["ts"] > 0)
        & df["speed"].notna()
        & (df["speed"] <= MAX_SPEED_KMH)     # drop >80 km/h GPS anomalies
        & (df["speed"] >= 0)
        & df["route_id"].notna()
        & df["vehicle_id"].notna()
    )
    df = df[ok]
    if df.empty:
        return None

    df["ts"] = df["ts"].astype(np.int64)
    df["route"] = df["route_id"].astype(np.int64)
    # day/hour come from the IST date/time strings (no timezone math needed)
    dates = pd.to_datetime(df["date"], errors="coerce")
    df["dow"] = dates.dt.weekday.fillna(0).astype(np.int8)      # 0 = Monday
    df["hour"] = (
        pd.to_numeric(df["time"].str.slice(0, 2), errors="coerce")
        .fillna(0).clip(0, 23).astype(np.int8)
    )
    df["key"] = df["vehicle_id"].astype(str) + "\x00" + df["trip_id"].astype(str)
    df["speed_ms"] = df["speed"] / 3.6
    return df


def process_day(path: Path, snap: SnapIndex, stops: StopIndex,
                limit: int | None, chunksize: int, dry_run: bool,
                counter: dict) -> dict[tuple[int, int, int], list[float]]:
    """Stream one SQLite day file -> {(seg,dow,hour): [sum_s, n]} aggregates."""
    import sqlite3

    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    con.execute("PRAGMA query_only=1")
    cur = con.cursor()
    cur.arraysize = chunksize
    cur.execute(
        f"SELECT {', '.join(SQL_COLS)} FROM vehicle_feed"
    )

    aggregates: dict[tuple[int, int, int], list[float]] = {}
    carry: pd.DataFrame | None = None   # first row of each key's open visit
    rows_read = 0
    t_start = time.time()

    while True:
        raw = cur.fetchmany(chunksize)
        if not raw:
            break
        rows_read += len(raw)
        if limit is not None and counter["rows"] >= limit:
            break

        chunk = pd.DataFrame(raw, columns=list(SQL_COLS))
        df = prepare_chunk(chunk)
        if df is None:
            continue

        # ---- snap to route_segments (per route) ----
        lon = df["lng"].to_numpy()
        lat = df["lat"].to_numpy()
        route = df["route"].to_numpy(dtype=float)
        seg_ids, seg_dist = snap.snap(lon, lat, route)
        df["seg"] = seg_ids
        n_pts = len(df)
        n_snapped = int((df["seg"] >= 0).sum())
        counter["rows"] += n_pts
        counter["snapped"] += n_snapped

        # ---- dwell identification (speed == 0 near a stop) ----
        dwell_mask = (df["speed_ms"] <= DWELL_SPEED_MS).to_numpy()
        if dwell_mask.any():
            near = stops.near(lon[dwell_mask], lat[dwell_mask], DWELL_STOP_M)
            counter["dwell"] += int(near.sum())

        # keep only points that landed on a segment
        df = df[df["seg"] >= 0]
        if df.empty:
            continue

        # ---- bridge across chunks: prepend the open visits from last chunk ----
        if carry is not None and not carry.empty:
            df = pd.concat([carry, df], ignore_index=True)

        df = df.sort_values(["key", "ts"], kind="stable")

        # ---- visit segmentation: a new visit starts whenever seg changes ----
        g = df.groupby("key", sort=False)
        prev_seg = g["seg"].shift(1)
        prev_route = g["route"].shift(1)
        is_new_visit = prev_seg.isna() | (df["seg"] != prev_seg)
        df["visit"] = g.cumcount() * 0  # placeholder to keep column order stable
        df["visit"] = is_new_visit.groupby(df["key"], sort=False).cumsum() - 1

        # first row of every visit = segment entry (first-seen timestamp)
        entry_mask = df.groupby(["key", "visit"], sort=False).cumcount() == 0
        entries = df[entry_mask]
        ge = entries.groupby("key", sort=False)
        entries = entries.assign(
            prev_seg=ge["seg"].shift(1),
            prev_route=ge["route"].shift(1),
            prev_ts=ge["ts"].shift(1),
            prev_dow=ge["dow"].shift(1),
            prev_hour=ge["hour"].shift(1),
        )
        dt_s = entries["ts"] - entries["prev_ts"]
        valid = (
            entries["prev_seg"].notna()
            & (entries["seg"] != entries["prev_seg"])
            & (entries["route"] == entries["prev_route"])
            & dt_s.between(MIN_TRANSIT_S, MAX_TRANSIT_S)
        )
        rec = entries[valid]
        for seg, dow, hour, secs in zip(
            rec["prev_seg"].astype(np.int64),
            rec["prev_dow"].astype(np.int8),
            rec["prev_hour"].astype(np.int8),
            dt_s[valid].astype(float),
        ):
            k = (int(seg), int(dow), int(hour))
            agg = aggregates.get(k)
            if agg is None:
                aggregates[k] = [secs, 1.0]
            else:
                agg[0] += secs
                agg[1] += 1.0
        counter["transitions"] += int(valid.sum())

        # ---- new carry: first row of each key's currently open visit ----
        last_visit = int(df["visit"].max()) if len(df) else -1
        starts = df[is_new_visit.reindex(df.index, fill_value=False)]
        # keep the LATEST visit-start per key (the open one)
        carry = starts.groupby("key", sort=False).tail(1)

        if counter["rows"] // PROGRESS_EVERY != counter.get("last_progress", -1):
            counter["last_progress"] = counter["rows"] // PROGRESS_EVERY
            rate = counter["rows"] / max(time.time() - t_start, 1e-9)
            print(f"  [{path.name}] {counter['rows']:,} rows | "
                  f"{counter['snapped']:,} snapped | "
                  f"{counter['transitions']:,} traversals | "
                  f"{rate:,.0f} rows/s")

    con.close()
    counter["day_rows"] = rows_read
    return aggregates


def flush(aggregates: dict[tuple[int, int, int], list[float]]) -> int:
    """Upsert aggregates into historical_segment_speeds (weighted average).

    Uses psycopg2 execute_values — the previous SQLAlchemy executemany ran
    row-by-row (~220 cells/s) and made the flush the bottleneck.
    """
    if not aggregates:
        return 0
    engine = db.get_engine()
    items = [
        (k[0], k[1], k[2], v[0] / v[1], int(v[1]))
        for k, v in aggregates.items()
    ]
    sql = """
        INSERT INTO historical_segment_speeds
            (segment_id, day_of_week, hour_of_day, avg_time_seconds, sample_count)
        VALUES %s
        ON CONFLICT (segment_id, day_of_week, hour_of_day) DO UPDATE SET
            avg_time_seconds =
                (historical_segment_speeds.sample_count
                     * historical_segment_speeds.avg_time_seconds
                 + EXCLUDED.sample_count * EXCLUDED.avg_time_seconds)
                / NULLIF(historical_segment_speeds.sample_count + EXCLUDED.sample_count, 0),
            sample_count = historical_segment_speeds.sample_count + EXCLUDED.sample_count,
            updated_at = now()
    """
    from psycopg2.extras import execute_values

    raw = engine.raw_connection()
    try:
        cur = raw.cursor()
        execute_values(cur, sql, items, page_size=1000)
        raw.commit()
    finally:
        raw.close()
    return len(items)


def main() -> None:
    ap = argparse.ArgumentParser(description="Historical travel-time aggregation")
    ap.add_argument("--hist-dir", default=str(config.HIST_DIR))
    ap.add_argument("--limit", type=int, default=None,
                    help="stop after N rows total (testing), e.g. 100000")
    ap.add_argument("--chunksize", type=int, default=CHUNK_DEFAULT)
    ap.add_argument("--days", nargs="*", default=None,
                    help="subset of day suffixes, e.g. 2026_10_01")
    ap.add_argument("--dry-run", action="store_true",
                    help="compute but do not write to Postgres")
    args = ap.parse_args()

    hist_dir = Path(args.hist_dir)
    files = sorted(hist_dir.glob("bus_movements_*.db"))
    if args.days:
        files = [f for f in files if any(d in f.name for d in args.days)]
    if not files:
        sys.exit(f"ERROR: no bus_movements_*.db found in {hist_dir}")

    print(f"[1/3] loading snap index from Postgres")
    snap = SnapIndex()
    snap.load()
    stops = StopIndex()
    stops.load()
    print(f"  stop index: {len(stops.ids):,} stops")

    print(f"[2/3] processing {len(files)} day file(s) from {hist_dir}")
    counter = {"rows": 0, "snapped": 0, "transitions": 0, "dwell": 0}
    total_written = 0
    for i, path in enumerate(files, 1):
        limit_left = None
        if args.limit is not None:
            limit_left = max(args.limit - counter["rows"], 0)
            if limit_left == 0:
                break
        print(f"  day {i}/{len(files)}: {path.name} "
              f"({path.stat().st_size / 1e9:.1f} GB)")
        t0 = time.time()
        aggs = process_day(path, snap, stops, limit_left,
                           args.chunksize, args.dry_run, counter)
        if args.dry_run:
            n = len(aggs)
            print(f"    {n:,} aggregate cells (dry-run, not written)")
        else:
            n = flush(aggs)
            total_written += n
            print(f"    upserted {n:,} cells in {time.time() - t0:.1f}s")

    print("[3/3] summary")
    rows = counter["rows"]
    print(f"  rows read        : {rows:,}")
    print(f"  snapped          : {counter['snapped']:,} "
          f"({100 * counter['snapped'] / max(rows, 1):.1f}%)")
    print(f"  traversals       : {counter['transitions']:,}")
    print(f"  dwell points     : {counter['dwell']:,} (speed=0 near a stop)")
    if not args.dry_run:
        with db.get_engine().connect() as conn:
            cells = conn.execute(text(
                "SELECT count(*), count(DISTINCT segment_id), sum(sample_count) "
                "FROM historical_segment_speeds"
            )).fetchone()
        print(f"  historical_segment_speeds: {cells[0]:,} cells over "
              f"{cells[1]:,} segments, {int(cells[2] or 0):,} samples total "
              f"(+{total_written:,} this run)")


if __name__ == "__main__":
    main()
