"""Synthetic GTFS-RT test for the live feed worker (no network needed).

Builds a FeedMessage with one vehicle on sample route "1", pre-seeds its
previous position 40% along the segment (30 s ago), places it now at 60%,
and verifies:
  * snap + forward-motion delta -> travel_time_s stored,
  * expected travel time = 30 s / 0.2 = 150 s for the full segment,
  * Redis TTL <= 900 s,
  * unknown-route vehicle is counted but not snapped.
"""

import time

import shapely
from google.transit import gtfs_realtime_pb2
from sqlalchemy import text

from backend import config, db
from backend.live_feed_worker import (
    SEG_INDEX,
    SEG_KEY,
    VEH_HASH,
    LiveStore,
    SegmentSnapIndex,
    process_feed,
)


def main() -> None:
    snap = SegmentSnapIndex()
    snap.load()
    store = LiveStore(config.REDIS_URL)
    assert store.redis is not None, "test expects real Redis up"

    with db.get_engine().connect() as conn:
        row = conn.execute(text(
            "SELECT segment_id, ST_AsText(geom), length_m FROM route_segments "
            "WHERE route_id = '1' ORDER BY segment_id LIMIT 1"
        )).fetchone()
    seg_id, wkt, length_m = int(row[0]), row[1], float(row[2])
    geom = shapely.from_wkt(wkt)
    p40 = geom.interpolate(0.40, normalized=True)
    p60 = geom.interpolate(0.60, normalized=True)
    dist = lambda p: geom.project(p) / geom.length * length_m  # noqa: E731

    now = int(time.time())
    store.save_vehicles({"TEST1": {
        "lat": p40.y, "lon": p40.x, "ts": now - 30,
        "seg": seg_id, "dist": round(dist(p40), 2),
    }}, now)

    feed = gtfs_realtime_pb2.FeedMessage()
    feed.header.gtfs_realtime_version = "2.0"
    feed.header.timestamp = now
    ent = feed.entity.add()
    ent.id = "TEST1"
    ent.vehicle.trip.route_id = "1"
    ent.vehicle.trip.trip_id = "1_06_05"
    ent.vehicle.timestamp = now
    ent.vehicle.vehicle.id = "TEST1"
    ent.vehicle.position.latitude = p60.y
    ent.vehicle.position.longitude = p60.x
    # unknown-route vehicle (sample feed has no route 999999)
    ent2 = feed.entity.add()
    ent2.id = "GHOST"
    ent2.vehicle.trip.route_id = "999999"
    ent2.vehicle.timestamp = now
    ent2.vehicle.vehicle.id = "GHOST"
    ent2.vehicle.position.latitude = p60.y
    ent2.vehicle.position.longitude = p60.x

    stats = process_feed(feed.SerializeToString(), snap, store, now)
    print("stats:", stats)
    assert stats["entities"] == 2, stats
    assert stats["snapped"] == 1, stats
    assert stats["updated"] == 1, stats
    assert stats["unknown_route"] == 1, stats

    times = store.live_travel_times()
    assert seg_id in times, times
    expected = 30.0 / 0.2  # 0.4 -> 0.6 in 30 s, full segment in 150 s
    got = times[seg_id]
    print(f"segment {seg_id}: travel_time={got}s (expected ~{expected}s)")
    assert abs(got - expected) < 5, (got, expected)

    ttl = store.redis.ttl(SEG_KEY.format(seg_id))
    print(f"redis TTL: {ttl}s")
    assert 0 < ttl <= config.LIVE_TTL_S, ttl

    # forward-only guard: same position again must NOT update
    stats2 = process_feed(feed.SerializeToString(), snap, store, now + 5)
    assert stats2["updated"] == 0, stats2

    # cleanup test keys
    store.redis.delete(SEG_KEY.format(seg_id))
    store.redis.srem(SEG_INDEX, str(seg_id))
    store.redis.delete(VEH_HASH)
    print("PASS: live worker synthetic test")


if __name__ == "__main__":
    main()
