"""Prompt 4 — Journey planner (Google Maps-like) over the route_segments graph.

Time-dependent Dijkstra where a state is (stop, route, direction):

  * edge weight  = live (Redis, TTL 900 s)
                 → historical (day-of-week x hour-of-day IST)
                 → schedule base_travel_time,
  * evaluated at the time the bus is boarded (FIFO, so standard Dijkstra holds),
  * transfer penalty is added when changing route/direction (presets below),
  * access/egress walking to stops <= config.MAX_WALK_M at WALK_SPEED_MPS.

Three journey options are produced by re-running the search with different
transfer penalties (fastest / balanced / fewest transfers) and de-duplicating
by bus-leg signature.
"""

from __future__ import annotations

import heapq
import math
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np
from sqlalchemy import text

from . import config, db

IST = ZoneInfo("Asia/Kolkata")
EARTH_R_M = 6_371_000.0

SOURCE_PRIORITY = {"live": 3, "historical": 2, "schedule": 1}
OPTION_PRESETS = (
    ("fastest", 60.0),
    ("balanced", config.TRANSFER_PENALTY_S),
    ("fewest_transfers", 600.0),
)


# --------------------------------------------------------------------------- #
# graph
# --------------------------------------------------------------------------- #

@dataclass(frozen=True, slots=True)
class Edge:
    seg_id: int
    route_id: str
    direction: int
    to_stop: str
    length_m: float
    base_s: float


@dataclass
class Graph:
    stop_names: dict[str, str]                 # stop_id -> name
    stop_lats: dict[str, float]
    stop_lons: dict[str, float]
    out: dict[str, list[Edge]]                 # from_stop -> edges
    # vectorised arrays for nearby() lookups
    _ids: list[str] = field(default_factory=list)
    _lats: np.ndarray = field(default_factory=lambda: np.empty(0))
    _lons: np.ndarray = field(default_factory=lambda: np.empty(0))

    @classmethod
    def load(cls) -> "Graph":
        engine = db.get_engine()
        with engine.connect() as conn:
            seg_rows = conn.execute(text(
                "SELECT segment_id, route_id, direction_id, from_stop_id, "
                "       to_stop_id, length_m, base_travel_time "
                "FROM route_segments"
            )).fetchall()
            stop_rows = conn.execute(text(
                "SELECT stop_id, stop_name, ST_Y(geom), ST_X(geom) "
                "FROM stops WHERE geom IS NOT NULL"
            )).fetchall()
        if not seg_rows:
            raise ValueError("route_segments is empty — run ingest_gtfs.py first")
        g = cls(stop_names={}, stop_lats={}, stop_lons={}, out={})
        for sid, name, lat, lon in stop_rows:
            g.stop_names[sid] = name or sid
            g.stop_lats[sid] = float(lat)
            g.stop_lons[sid] = float(lon)
        for seg_id, route_id, direction, f, t, length_m, base_s in seg_rows:
            if f not in g.stop_lats or t not in g.stop_lats:
                continue
            g.out.setdefault(f, []).append(Edge(
                seg_id=int(seg_id), route_id=str(route_id),
                direction=int(direction or 0), to_stop=str(t),
                length_m=float(length_m or 0.0),
                base_s=float(base_s or config.DEFAULT_BUS_SPEED_MPS),
            ))
        g._ids = list(g.stop_names)
        g._lats = np.array([g.stop_lats[i] for i in g._ids])
        g._lons = np.array([g.stop_lons[i] for i in g._ids])
        return g

    def nearby(self, lat: float, lon: float,
               max_m: float = config.MAX_WALK_M) -> list[tuple[str, float]]:
        """[(stop_id, walk_seconds)] for stops within max_m (haversine)."""
        if not self._ids:
            return []
        la = np.radians(self._lats)
        lo = np.radians(self._lons)
        dlat = la - math.radians(lat)
        dlon = lo - math.radians(lon)
        a = (np.sin(dlat / 2) ** 2
             + math.cos(math.radians(lat)) * np.cos(la) * np.sin(dlon / 2) ** 2)
        d = 2 * EARTH_R_M * np.arcsin(np.sqrt(a))
        out = []
        for i in np.nonzero(d <= max_m)[0]:
            out.append((self._ids[int(i)], float(d[int(i)]) / config.WALK_SPEED_MPS))
        out.sort(key=lambda x: x[1])
        return out


# --------------------------------------------------------------------------- #
# time-dependent edge costs
# --------------------------------------------------------------------------- #

class HistCache:
    """Lazily loads historical_segment_speeds, batched by route."""

    def __init__(self) -> None:
        self.data: dict[int, dict[tuple[int, int], float]] = {}
        self.routes: set[str] = set()

    def clear(self) -> None:
        self.data.clear()
        self.routes.clear()

    def ensure(self, route_ids: set[str]) -> None:
        missing = {r for r in route_ids if r not in self.routes}
        if not missing:
            return
        with db.get_engine().connect() as conn:
            rows = conn.execute(text(
                "SELECT h.segment_id, h.day_of_week, h.hour_of_day, "
                "       h.avg_time_seconds "
                "FROM historical_segment_speeds h "
                "JOIN route_segments rs ON rs.segment_id = h.segment_id "
                "WHERE rs.route_id = ANY(:routes)"
            ), {"routes": sorted(missing)}).fetchall()
        for seg_id, dow, hour, tt in rows:
            self.data.setdefault(int(seg_id), {})[(int(dow), int(hour))] = float(tt)
        self.routes |= missing


def _ist_parts(t_epoch: float) -> tuple[int, int]:
    d = datetime.fromtimestamp(t_epoch, IST)
    return d.weekday(), d.hour


def edge_seconds(edge: Edge, t_board: float, live: dict[int, float],
                 hist: HistCache) -> tuple[float, str]:
    tt = live.get(edge.seg_id)
    if tt is not None:
        return min(tt, config.MAX_EDGE_TIME_S), "live"
    dow, hour = _ist_parts(t_board)
    h = hist.data.get(edge.seg_id, {}).get((dow, hour))
    if h is not None:
        return min(h, config.MAX_EDGE_TIME_S), "historical"
    return min(edge.base_s, config.MAX_EDGE_TIME_S), "schedule"


# --------------------------------------------------------------------------- #
# search
# --------------------------------------------------------------------------- #

State = tuple[str, str, int]  # (stop_id, route_id, direction); route "" = walked in


def _search(graph: Graph, origin: tuple[float, float],
            dest: tuple[float, float], depart: float, penalty: float,
            live: dict[int, float], hist: HistCache,
            access: list[tuple[str, float]], egress: dict[str, float],
            direct_walk_s: float | None) -> dict | None:
    INF = float("inf")
    dist: dict[State, float] = {}
    prev: dict[State, tuple[State, Edge, float, float]] = {}
    pq: list[tuple[float, State]] = []
    best: tuple[float, State] | None = None

    if direct_walk_s is not None:
        best = (depart + direct_walk_s, ("", "", -1))

    for stop_id, walk_s in access:
        st: State = (stop_id, "", -1)
        t = depart + walk_s
        if t < dist.get(st, INF):
            dist[st] = t
            heapq.heappush(pq, (t, st))

    while pq:
        t, state = heapq.heappop(pq)
        if t > dist.get(state, INF):
            continue
        stop_id, route_id, direction = state
        if best is not None and t >= best[0]:
            break  # FIFO: nothing left can beat the best arrival
        eg = egress.get(stop_id)
        if eg is not None and stop_id != "":
            arrival = t + eg
            if best is None or arrival < best[0]:
                best = (arrival, state)
        edges = graph.out.get(stop_id)
        if not edges:
            continue
        hist.ensure({e.route_id for e in edges})
        for e in edges:
            pen = 0.0 if (route_id == "" or (route_id == e.route_id
                                             and direction == e.direction)) \
                else penalty
            t_board = t + pen
            cost, _ = edge_seconds(e, t_board, live, hist)
            t2 = t_board + cost
            if best is not None and t2 >= best[0]:
                continue
            st2: State = (e.to_stop, e.route_id, e.direction)
            if t2 < dist.get(st2, INF):
                dist[st2] = t2
                prev[st2] = (state, e, t_board, t2)
                heapq.heappush(pq, (t2, st2))

    if best is None:
        return None
    arrival, final_state = best
    if final_state == ("", "", -1):
        return {"arrival": arrival, "chain": [], "egress_walk": direct_walk_s}

    # reconstruct transition chain
    chain: list[tuple[State, Edge, float, float]] = []
    st = final_state
    while st in prev:
        parent, e, t_board, t_arrive = prev[st]
        chain.append((parent, e, t_board, t_arrive))
        st = parent
    chain.reverse()
    return {"arrival": arrival, "chain": chain,
            "access_stop": st[0], "final_state": final_state}


# --------------------------------------------------------------------------- #
# leg assembly
# --------------------------------------------------------------------------- #

def _iso(t_epoch: float) -> str:
    return datetime.fromtimestamp(t_epoch, IST).isoformat()


def _dominant_source(sources: list[str]) -> str:
    counts = {s: sources.count(s) for s in ("live", "historical", "schedule")}
    return max(counts, key=lambda s: (counts[s], SOURCE_PRIORITY[s]))


def _assemble(graph: Graph, origin: tuple[float, float],
              dest: tuple[float, float], depart: float, result: dict,
              label: str, live: dict[int, float], hist: HistCache) -> dict:
    chain: list[tuple[State, Edge, float, float]] = result["chain"]
    legs: list[dict] = []

    if not chain:
        # walk-only: origin -> stop (access) -> dest (egress), or direct
        walk_total = result["arrival"] - depart
        legs.append({
            "type": "walk",
            "from": "origin", "to": "destination",
            "depart": _iso(depart), "arrive": _iso(result["arrival"]),
            "duration_min": round(walk_total / 60, 1),
            "distance_m": round(walk_total * config.WALK_SPEED_MPS),
        })
        return _option(legs, depart, result["arrival"], label)

    # access walk: origin -> first boarding stop
    first_parent, first_edge, t_board0, _ = chain[0]
    access_stop = first_parent[0]
    legs.append({
        "type": "walk",
        "from": "origin", "to": graph.stop_names.get(access_stop, access_stop),
        "depart": _iso(depart), "arrive": _iso(t_board0),
        "duration_min": round((t_board0 - depart) / 60, 1),
        "distance_m": round((t_board0 - depart) * config.WALK_SPEED_MPS),
    })

    # group consecutive transitions that share (route, direction)
    groups: list[list[tuple[State, Edge, float, float]]] = []
    for item in chain:
        _, e, _, _ = item
        if groups:
            _, pe, _, _ = groups[-1][0]
            if pe.route_id == e.route_id and pe.direction == e.direction:
                groups[-1].append(item)
                continue
        groups.append([item])

    for g in groups:
        _, e0, t_dep, _ = g[0]
        t_arr = g[-1][3]
        from_stop = g[0][0][0]
        to_stop = g[-1][1].to_stop
        sources = [edge_seconds(e, tb, live, hist)[1]
                   for (_, e, tb, _) in g]
        legs.append({
            "type": "bus",
            "route": e0.route_id,
            "direction": e0.direction,
            "from": graph.stop_names.get(from_stop, from_stop),
            "to": graph.stop_names.get(to_stop, to_stop),
            "depart": _iso(t_dep), "arrive": _iso(t_arr),
            "duration_min": round((t_arr - t_dep) / 60, 1),
            "stops": len(g),
            "distance_m": round(sum(e.length_m for _, e, _, _ in g)),
            "source": _dominant_source(sources),
        })

    # egress walk: last stop -> destination
    final_stop = chain[-1][1].to_stop
    t_last = chain[-1][3]
    legs.append({
        "type": "walk",
        "from": graph.stop_names.get(final_stop, final_stop),
        "to": "destination",
        "depart": _iso(t_last), "arrive": _iso(result["arrival"]),
        "duration_min": round((result["arrival"] - t_last) / 60, 1),
        "distance_m": round((result["arrival"] - t_last) * config.WALK_SPEED_MPS),
    })
    return _option(legs, depart, result["arrival"], label)


def _option(legs: list[dict], depart: float, arrival: float,
            label: str) -> dict:
    bus_legs = [l for l in legs if l["type"] == "bus"]
    walk_min = sum(l["duration_min"] for l in legs if l["type"] == "walk")
    return {
        "label": label,
        "departure": _iso(depart),
        "arrival": _iso(arrival),
        "duration_min": round((arrival - depart) / 60, 1),
        "transfers": max(0, len(bus_legs) - 1),
        "walk_min": round(walk_min, 1),
        "legs": legs,
    }


def _signature(option: dict) -> tuple:
    return tuple(
        (l.get("route"), l["from"], l["to"])
        for l in option["legs"] if l["type"] == "bus"
    ) or (("walk",),)


# --------------------------------------------------------------------------- #
# public API
# --------------------------------------------------------------------------- #

_graph: Graph | None = None
_hist = HistCache()
_warmed = False


def get_graph() -> Graph:
    global _graph
    if _graph is None:
        _graph = Graph.load()
    return _graph


def refresh() -> None:
    """Drop cached graph + historical data (call after re-ingest)."""
    global _graph, _warmed
    _graph = None
    _hist.clear()
    _warmed = False


def warm() -> None:
    """Preload the graph + historical speeds for every route.

    Run in a background thread at startup / on /health so the first
    journey after a cold start does not pay the cross-region DB cost.
    """
    global _warmed
    g = get_graph()
    routes = {e.route_id for edges in g.out.values() for e in edges}
    _hist.ensure(routes)
    _warmed = True
    print(f"[warm] graph ready; historical speeds for {len(routes)} routes")


def is_warmed() -> bool:
    return _warmed


def _parse_depart(s: str | None) -> float:
    if not s:
        return time.time()
    s = s.strip()
    try:
        if ":" in s and "T" not in s and "-" not in s:  # HH:MM[:SS] -> today IST
            parts = [int(p) for p in s.split(":")]
            now_ist = datetime.now(IST)
            return now_ist.replace(hour=parts[0], minute=parts[1],
                                   second=parts[2] if len(parts) > 2 else 0,
                                   microsecond=0).timestamp()
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=IST)
        return dt.timestamp()
    except (ValueError, IndexError) as exc:
        raise ValueError(
            f"invalid depart_at {s!r} (use ISO-8601 or HH:MM)") from exc


def plan_journeys(from_lat: float, from_lon: float,
                  to_lat: float, to_lon: float,
                  depart_at: str | None = None) -> dict:
    for name, v in (("from_lat", from_lat), ("from_lon", from_lon),
                    ("to_lat", to_lat), ("to_lon", to_lon)):
        if not math.isfinite(v):
            raise ValueError(f"{name} must be a finite number")
    depart = _parse_depart(depart_at)
    graph = get_graph()

    access = graph.nearby(from_lat, from_lon)
    egress = dict(graph.nearby(to_lat, to_lon))
    if not access:
        raise ValueError(
            f"no stops within {int(config.MAX_WALK_M)} m of the origin")
    if not egress:
        raise ValueError(
            f"no stops within {int(config.MAX_WALK_M)} m of the destination")

    # direct walk when origin and destination are close
    direct = None
    if access and egress:
        d = math.hypot((from_lat - to_lat) * 111_000,
                       (from_lon - to_lon) * 95_000)
        if d <= config.MAX_WALK_M:
            direct = d / config.WALK_SPEED_MPS

    try:
        live = _live_times()
    except Exception:  # noqa: BLE001 — Redis optional
        live = {}

    options: list[dict] = []
    seen: set[tuple] = set()
    for label, penalty in OPTION_PRESETS:
        res = _search(graph, (from_lat, from_lon), (to_lat, to_lon),
                      depart, penalty, live, _hist, access, egress, direct)
        if res is None:
            continue
        opt = _assemble(graph, (from_lat, from_lon), (to_lat, to_lon),
                        depart, res, label, live, _hist)
        sig = _signature(opt)
        if sig in seen:
            continue
        seen.add(sig)
        options.append(opt)

    if not options:
        raise ValueError("no journey found between these points")
    options.sort(key=lambda o: o["duration_min"])
    return {
        "from": {"lat": from_lat, "lon": from_lon},
        "to": {"lat": to_lat, "lon": to_lon},
        "depart_at": _iso(depart),
        "options": options,
    }


def _live_times() -> dict[int, float]:
    from .live_feed_worker import LiveStore  # local import: avoids cycles
    return LiveStore(config.REDIS_URL).live_travel_times()
