"""Prompt 3 — GTFS-RT live feed worker.

Polls the TransportStack VehiclePositions.pb endpoint (default every 10 s),
snaps each vehicle to the `route_segment` of its own route, derives a
segment travel time from two consecutive observations on the SAME segment
(forward motion only), and stores it in Redis:

    live:seg:{segment_id}  JSON {travel_time_s, speed_mps, vehicle_id, ts}
                           with TTL = config.LIVE_TTL_S (900 s)
    live:seg:index         SET of live segment ids (router lookup)
    live:vehicles          hash of per-vehicle state for the next delta

If Redis is down, an in-process TTL cache with the same semantics is used
(so the API still serves live data).

Usage:
    python -m backend.live_feed_worker --once     # single poll, then exit
    python -m backend.live_feed_worker            # poll forever (Ctrl-C stops)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time

import httpx
import numpy as np
import shapely
from google.transit import gtfs_realtime_pb2
from shapely import STRtree
from sqlalchemy import text

from . import config, db

SEG_KEY = "live:seg:{}"         # value: JSON payload, TTL = LIVE_TTL_S
SEG_INDEX = "live:seg:index"    # SET of ids currently live
VEH_HASH = "live:vehicles"      # vehicle_id -> JSON state
VEH_TTL_S = 3600                # hash expiry (refreshed every poll)
VEH_STATE_MAX_AGE_S = 1800      # drop vehicle state older than 30 min

MIN_SPEED_MPS = 0.3             # below this it is not meaningful motion
MAX_SPEED_MPS = 25.0            # sanity cap (~90 km/h)
MIN_DT_S = 1                    # need at least 1 s between observations
MAX_DT_S = 120                  # older than 2 min: re-baseline, no update
MAX_SNAP_DEG = 0.0015           # ~165 m, same tolerance as the historical model


# --------------------------------------------------------------------------- #
# segment snap index (per-route STRtree over route_segments)
# --------------------------------------------------------------------------- #

class SegmentSnapIndex:
    """Snaps a (route_id, lon, lat) to the nearest segment of that route and
    returns the distance ALONG the segment in metres."""

    def __init__(self) -> None:
        self._ids: list[int] = []
        self._id_pos: dict[int, int] = {}
        self._route_pos: dict[str, list[int]] = {}
        self._geoms: list = []
        self._lengths: list[float] = []
        self._trees: dict[str, tuple[STRtree, np.ndarray] | None] = {}

    @property
    def route_ids(self) -> set[str]:
        return set(self._route_pos)

    def load(self) -> None:
        with db.get_engine().connect() as conn:
            rows = conn.execute(text(
                "SELECT segment_id, route_id, ST_AsText(geom), length_m "
                "FROM route_segments"
            )).fetchall()
        if not rows:
            raise SystemExit(
                "ERROR: route_segments is empty — run ingest_gtfs.py first.")
        for seg_id, route_id, wkt, length_m in rows:
            self._id_pos[int(seg_id)] = len(self._ids)
            self._ids.append(int(seg_id))
            self._route_pos.setdefault(str(route_id), []).append(len(self._geoms))
            self._geoms.append(shapely.from_wkt(wkt))
            self._lengths.append(float(length_m))
        print(f"  live snap index: {len(rows):,} segments across "
              f"{len(self._route_pos):,} routes")

    def length_of(self, seg_id: int) -> float:
        pos = self._id_pos.get(int(seg_id))
        return self._lengths[pos] if pos is not None else 0.0

    def _tree(self, route_id: str):
        t = self._trees.get(route_id)
        if t is not None:
            return t
        pos = self._route_pos.get(route_id)
        if not pos:
            self._trees[route_id] = None
            return None
        tree = STRtree([self._geoms[i] for i in pos])
        ids = np.array([self._ids[i] for i in pos], dtype=np.int64)
        entry = (tree, ids, np.array(pos, dtype=np.int64))
        self._trees[route_id] = entry
        return entry

    def snap(self, route_id: str, lon: float, lat: float) -> tuple[int, float] | None:
        entry = self._tree(route_id)
        if entry is None:
            return None
        tree, ids, pos = entry
        pt = shapely.Point(lon, lat)
        res = tree.query_nearest(pt, all_matches=False,
                                 max_distance=MAX_SNAP_DEG)
        if res is None:
            return None
        arr = np.asarray(res).ravel()
        if arr.size == 0:          # nothing within MAX_SNAP_DEG
            return None
        local = int(arr[0])
        gi = int(pos[local])
        geom = self._geoms[gi]
        length_deg = geom.length
        along_m = 0.0
        if length_deg > 0:
            along_m = geom.project(pt) / length_deg * self._lengths[gi]
        return int(ids[local]), float(along_m)


# --------------------------------------------------------------------------- #
# Redis store (with in-process fallback)
# --------------------------------------------------------------------------- #

class LiveStore:
    def __init__(self, redis_url: str) -> None:
        self.redis = None
        try:
            import redis as redis_lib
            r = redis_lib.Redis.from_url(
                redis_url, socket_connect_timeout=2, socket_timeout=5)
            r.ping()
            self.redis = r
        except Exception as exc:  # noqa: BLE001 — any failure -> fallback
            print(f"  redis unavailable ({exc}); using in-process TTL cache")
        self._mem_seg: dict[str, tuple[float, dict]] = {}
        self._mem_veh: dict[str, tuple[float, dict]] = {}

    # --- segment speeds -----------------------------------------------------
    def set_seg(self, seg_id: int, payload: dict) -> None:
        if self.redis is not None:
            pipe = self.redis.pipeline()
            pipe.set(SEG_KEY.format(seg_id), json.dumps(payload),
                     ex=config.LIVE_TTL_S)
            pipe.sadd(SEG_INDEX, str(seg_id))
            pipe.execute()
        else:
            self._mem_seg[str(seg_id)] = (time.time() + config.LIVE_TTL_S,
                                          payload)

    def live_travel_times(self) -> dict[int, float]:
        """{segment_id: travel_time_s} for currently-live segments (router API)."""
        out: dict[int, float] = {}
        if self.redis is not None:
            ids = self.redis.smembers(SEG_INDEX)
            if not ids:
                return out
            pipe = self.redis.pipeline()
            for sid in ids:
                pipe.get(SEG_KEY.format(sid.decode()))
            for sid, blob in zip(ids, pipe.execute()):
                if blob is None:
                    self.redis.srem(SEG_INDEX, sid)   # lazy index cleanup
                    continue
                try:
                    out[int(sid)] = float(
                        json.loads(blob)["travel_time_s"])
                except (ValueError, KeyError, json.JSONDecodeError):
                    continue
            return out
        now = time.time()
        for sid, (exp, payload) in list(self._mem_seg.items()):
            if exp <= now:
                del self._mem_seg[sid]
                continue
            out[int(sid)] = float(payload["travel_time_s"])
        return out

    # --- vehicle states -----------------------------------------------------
    def load_vehicles(self) -> dict[str, dict]:
        if self.redis is not None:
            raw = self.redis.hgetall(VEH_HASH)
            out: dict[str, dict] = {}
            for k, v in raw.items():
                try:
                    out[k.decode()] = json.loads(v)
                except json.JSONDecodeError:
                    continue
            return out
        now = time.time()
        for k, (exp, st) in list(self._mem_veh.items()):
            if exp <= now:
                del self._mem_veh[k]
        return {k: st for k, (_, st) in self._mem_veh.items()}

    def save_vehicles(self, states: dict[str, dict], now: int) -> None:
        fresh = {k: v for k, v in states.items()
                 if now - int(v.get("ts", 0)) <= VEH_STATE_MAX_AGE_S}
        if self.redis is not None:
            pipe = self.redis.pipeline()
            pipe.delete(VEH_HASH)
            for vid, st in fresh.items():
                pipe.hset(VEH_HASH, vid, json.dumps(st))
            pipe.expire(VEH_HASH, VEH_TTL_S)
            pipe.execute()
        else:
            self._mem_veh = {k: (now + VEH_TTL_S, v)
                             for k, v in fresh.items()}


# --------------------------------------------------------------------------- #
# feed processing (pure: bytes in -> stats out; unit-testable)
# --------------------------------------------------------------------------- #

def process_feed(feed_bytes: bytes, snap: SegmentSnapIndex,
                 store: LiveStore, now: int) -> dict:
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(feed_bytes)

    states = store.load_vehicles()
    stats = {"entities": 0, "snapped": 0, "updated": 0, "unknown_route": 0}
    known_routes = snap.route_ids

    for ent in feed.entity:
        if not ent.HasField("vehicle"):
            continue
        v = ent.vehicle
        if not v.HasField("position"):
            continue
        stats["entities"] += 1
        lat = float(v.position.latitude)
        lon = float(v.position.longitude)
        if not (config.DELHI_BBOX[0] <= lat <= config.DELHI_BBOX[2]
                and config.DELHI_BBOX[1] <= lon <= config.DELHI_BBOX[3]):
            continue
        route_id = str(v.trip.route_id or "")
        if route_id not in known_routes:
            stats["unknown_route"] += 1
            continue
        vid = v.vehicle.id or ent.id or f"{lat:.5f},{lon:.5f}"
        ts = int(v.timestamp) if v.timestamp else now

        snapped = snap.snap(route_id, lon, lat)
        if snapped is None:
            continue
        seg_id, dist_m = snapped
        stats["snapped"] += 1

        prev = states.get(vid)
        if prev is not None and prev.get("seg") == seg_id:
            dt = ts - int(prev["ts"])
            dd = dist_m - float(prev["dist"])
            if MIN_DT_S <= dt <= MAX_DT_S and dd > 0:
                speed = dd / dt
                if MIN_SPEED_MPS <= speed <= MAX_SPEED_MPS:
                    travel_s = snap.length_of(seg_id) / speed
                    store.set_seg(seg_id, {
                        "travel_time_s": round(travel_s, 1),
                        "speed_mps": round(speed, 3),
                        "vehicle_id": vid,
                        "ts": ts,
                    })
                    stats["updated"] += 1

        states[vid] = {"lat": lat, "lon": lon, "ts": ts,
                       "seg": seg_id, "dist": round(dist_m, 2)}

    store.save_vehicles(states, now)
    return stats


# --------------------------------------------------------------------------- #
# polling loop
# --------------------------------------------------------------------------- #

async def poll_once(client: httpx.AsyncClient, snap: SegmentSnapIndex,
                    store: LiveStore) -> dict:
    t0 = time.time()
    resp = await client.get(
        config.GTFS_RT_URL,
        headers={config.GTFS_RT_KEY_HEADER: config.GTFS_RT_KEY},
    )
    resp.raise_for_status()
    stats = process_feed(resp.content, snap, store, int(time.time()))
    stats["elapsed_s"] = round(time.time() - t0, 2)
    return stats


async def run(interval: float, once: bool) -> None:
    snap = SegmentSnapIndex()
    snap.load()
    store = LiveStore(config.REDIS_URL)
    print(f"  polling {config.GTFS_RT_URL.split('?')[0]} every {interval}s "
          f"(redis={'on' if store.redis else 'fallback'})")
    async with httpx.AsyncClient(timeout=httpx.Timeout(15.0)) as client:
        while True:
            try:
                stats = await poll_once(client, snap, store)
                print(f"  poll ok: {stats}")
            except Exception as exc:  # noqa: BLE001 — keep polling
                print(f"  poll failed: {exc}")
            if once:
                return
            await asyncio.sleep(interval)


def main() -> None:
    ap = argparse.ArgumentParser(description="GTFS-RT live feed worker")
    ap.add_argument("--once", action="store_true",
                    help="poll once and exit (smoke test)")
    ap.add_argument("--interval", type=float,
                    default=float(config.GTFS_RT_POLL_SECONDS),
                    help="poll interval in seconds")
    args = ap.parse_args()
    try:
        asyncio.run(run(args.interval, args.once))
    except KeyboardInterrupt:
        print("\nstopped")


if __name__ == "__main__":
    main()
