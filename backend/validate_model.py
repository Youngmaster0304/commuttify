"""Prompt 6 — validation: predicted vs observed vs Google Maps.

Success criterion check: "journey options with estimated travel times that
hold up against known actual travel times and against Google Maps".

    # 1) derive ACTUAL stop->stop times from raw GPS (one historical day)
    python -m backend.validate_model --observe --observe-day 2026_10_02

    # 2) predict with the journey API and write the report
    python -m backend.validate_model --skip-google        # no Maps key
    python -m backend.validate_model                      # with Maps key

Outputs:
    outputs/validation_report.csv     one row per OD pair
    outputs/validation_scatter.png    predicted vs observed (+ Google)
    outputs/observed_actuals.json     cache from --observe

Google Maps is used ONLY here for offline comparison — never in the serving
API (hackathon rule: the deliverable must not wrap Google Directions).
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

import httpx
import numpy as np
import pandas as pd
import shapely
from shapely import STRtree
from sqlalchemy import text

from . import config, db, routing

N_PAIRS = 30
SEED = 42
OBS_MIN_S = 60.0          # A->B faster than this = GPS noise
OBS_MAX_S = 7200.0        # slower than this = gap / detour, drop
STOP_SNAP_M = 100.0       # GPS point counts as "at stop" within 100 m
OUT_DIR = Path("outputs")
REPORT_CSV = OUT_DIR / "validation_report.csv"
SCATTER_PNG = OUT_DIR / "validation_scatter.png"
OBS_JSON = OUT_DIR / "observed_actuals.json"


# --------------------------------------------------------------------------- #
# 30 deterministic same-route OD pairs
# --------------------------------------------------------------------------- #

def select_pairs() -> pd.DataFrame:
    """30 stop pairs along distinct routes (4-12 segments apart), seed=42."""
    with db.get_engine().connect() as conn:
        segs = pd.DataFrame(conn.execute(text(
            "SELECT segment_id, route_id, direction_id, from_stop_id, "
            "       to_stop_id, from_stop_name, to_stop_name, from_stop_seq "
            "FROM route_segments"
        )).fetchall(), columns=[
            "segment_id", "route_id", "direction_id", "from_stop_id",
            "to_stop_id", "from_stop_name", "to_stop_name", "from_stop_seq"])
        stops = pd.DataFrame(conn.execute(text(
            "SELECT stop_id, stop_name, stop_lat, stop_lon FROM stops"
        )).fetchall(), columns=["stop_id", "stop_name", "lat", "lon"])

    segs["route_id"] = segs["route_id"].astype(str)
    segs = segs.sort_values(["route_id", "direction_id", "from_stop_seq"])

    # build ordered stop chains per (route, direction)
    chains: list[tuple[str, str, list[str]]] = []
    for (route, _dir), grp in segs.groupby(["route_id", "direction_id"],
                                           sort=False):
        chain = [str(grp.iloc[0]["from_stop_id"])]
        for sid in grp["to_stop_id"]:
            chain.append(str(sid))
        if len(chain) >= 6:
            chains.append((route, str(grp.iloc[0]["direction_id"]), chain))

    rng = np.random.default_rng(SEED)
    rng.shuffle(chains)

    pos = {str(r.stop_id): (float(r.lat), float(r.lon), r.stop_name)
           for r in stops.itertuples(index=False)}
    rows = []
    for route, direction, chain in chains:
        if len(rows) >= N_PAIRS:
            break
        span = int(rng.integers(4, min(12, len(chain) - 1) + 1))
        i = int(rng.integers(0, len(chain) - span))
        a, b = chain[i], chain[i + span]
        if a not in pos or b not in pos or a == b:
            continue
        rows.append({
            "pair_id": f"P{len(rows)+1:02d}",
            "route_id": route,
            "direction_id": direction,
            "from_stop_id": a, "to_stop_id": b,
            "from_stop": pos[a][2], "to_stop": pos[b][2],
            "from_lat": pos[a][0], "from_lon": pos[a][1],
            "to_lat": pos[b][0], "to_lon": pos[b][1],
        })
    pairs = pd.DataFrame(rows)
    if len(pairs) < N_PAIRS:
        print(f"  WARNING: only {len(pairs)} pairs available (want {N_PAIRS})")
    return pairs


# --------------------------------------------------------------------------- #
# observed actuals from raw GPS
# --------------------------------------------------------------------------- #

def observe_day(pairs: pd.DataFrame, day_suffix: str) -> dict[str, dict]:
    """Actual stop->stop bus times from one historical SQLite day file."""
    import sqlite3

    hist_dir = Path(config.HIST_DIR)
    files = sorted(hist_dir.glob(f"bus_movements_*{day_suffix}*.db"))
    if not files:
        sys.exit(f"ERROR: no bus_movements_*{day_suffix}*.db in {hist_dir}")
    path = files[0]

    routes = sorted({float(r) for r in pairs["route_id"]})
    route_set = set(routes)
    print(f"[observe] {path.name}  routes={len(routes)}  pairs={len(pairs)}")

    with db.get_engine().connect() as conn:
        coords = conn.execute(text(
            "SELECT stop_id, stop_lon, stop_lat FROM stops")).fetchall()
    stop_ids = [str(c[0]) for c in coords]
    lon = np.array([float(c[1]) for c in coords])
    lat = np.array([float(c[2]) for c in coords])
    tree = STRtree(shapely.points(lon, lat))

    # events: (route, vehicle, stop_idx, ts)
    ev_route: list[np.ndarray] = []
    ev_veh: list[np.ndarray] = []
    ev_stop: list[np.ndarray] = []
    ev_ts: list[np.ndarray] = []

    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    con.execute("PRAGMA query_only=1")
    cur = con.cursor()
    cur.arraysize = 100_000
    cur.execute("SELECT vehicle_id, lat, lng, route_id, timestamp "
                "FROM vehicle_feed")
    rows_read = 0
    t0 = time.time()
    while True:
        raw = cur.fetchmany(100_000)
        if not raw:
            break
        rows_read += len(raw)
        df = pd.DataFrame(raw, columns=["veh", "lat", "lng", "route", "ts"])
        for c in ("lat", "lng", "route", "ts"):
            df[c] = pd.to_numeric(df[c], errors="coerce")
        df = df.dropna(subset=["lat", "lng", "route", "ts"])
        df = df[df["route"].isin(route_set)]
        if df.empty:
            continue
        pts = shapely.points(df["lng"].to_numpy(), df["lat"].to_numpy())
        res = tree.query_nearest(pts, all_matches=False,
                                 max_distance=STOP_SNAP_M / 111_000.0)
        if res is None:
            continue
        res = np.asarray(res)
        if res.ndim != 2 or res.size == 0:
            continue
        in_idx = res[0].astype(np.int64)      # input rows with a match
        tree_idx = res[1].astype(np.int64)    # matching stop indices
        if in_idx.size == 0:
            continue
        f = df.iloc[in_idx]
        ev_route.append(f["route"].to_numpy())
        ev_veh.append(f["veh"].astype(str).to_numpy())
        ev_stop.append(tree_idx)
        ev_ts.append(f["ts"].to_numpy(dtype=np.int64))
        if rows_read % 2_000_000 < 100_000:
            print(f"  {rows_read:,} rows | events "
                  f"{sum(len(e) for e in ev_stop):,} | "
                  f"{time.time()-t0:.0f}s", flush=True)
    con.close()

    if not ev_route:
        sys.exit("ERROR: no stop-proximity events captured")
    routes_a = np.concatenate(ev_route)
    veh_a = np.concatenate(ev_veh)
    stop_a = np.concatenate(ev_stop)
    ts_a = np.concatenate(ev_ts)
    print(f"[observe] {rows_read:,} rows -> {len(ts_a):,} stop events "
          f"in {time.time()-t0:.0f}s")

    # per (route, vehicle) chronological events
    order = np.lexsort((ts_a, veh_a, routes_a))
    routes_a, veh_a, stop_a, ts_a = (routes_a[order], veh_a[order],
                                     stop_a[order], ts_a[order])
    key_change = (routes_a[1:] != routes_a[:-1]) | (veh_a[1:] != veh_a[:-1])
    bounds = np.flatnonzero(key_change) + 1
    groups = np.split(np.arange(len(ts_a)), bounds)

    # stop index lookup per pair
    stop_pos = {s: i for i, s in enumerate(stop_ids)}
    results: dict[str, dict] = {}
    for _, p in pairs.iterrows():
        a_i = stop_pos.get(str(p["from_stop_id"]))
        b_i = stop_pos.get(str(p["to_stop_id"]))
        if a_i is None or b_i is None:
            continue
        route_f = float(p["route_id"])
        deltas: list[float] = []
        for g in groups:
            if routes_a[g[0]] != route_f:
                continue
            g_stops, g_ts = stop_a[g], ts_a[g]
            pending_a: int | None = None
            for s, t in zip(g_stops, g_ts):
                if s == a_i:
                    pending_a = int(t)
                elif s == b_i and pending_a is not None:
                    d = int(t) - pending_a
                    if OBS_MIN_S <= d <= OBS_MAX_S:
                        deltas.append(d / 60.0)
                    pending_a = None
        if deltas:
            results[p["pair_id"]] = {
                "n": len(deltas),
                "median_min": round(statistics.median(deltas), 1),
                "p25_min": round(float(np.percentile(deltas, 25)), 1),
                "p75_min": round(float(np.percentile(deltas, 75)), 1),
            }
        print(f"  {p['pair_id']} {p['from_stop'][:22]:22s} -> "
              f"{p['to_stop'][:22]:22s}  n={len(deltas):4d}  "
              f"median={results.get(p['pair_id'], {}).get('median_min', '-')}")
    return results


# --------------------------------------------------------------------------- #
# predictions + google
# --------------------------------------------------------------------------- #

def predict(pairs: pd.DataFrame) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for _, p in pairs.iterrows():
        try:
            res = routing.plan_journeys(p["from_lat"], p["from_lon"],
                                        p["to_lat"], p["to_lon"])
        except ValueError as exc:
            print(f"  {p['pair_id']}: plan failed ({exc})")
            continue
        opt = res["options"][0]
        bus_s = sum(l["duration_min"] * 60 for l in opt["legs"]
                    if l["type"] == "bus")
        out[p["pair_id"]] = {
            "total_min": opt["duration_min"],
            "bus_min": round(bus_s / 60.0, 1),
            "transfers": opt["transfers"],
            "sources": sorted({l.get("source", "-") for l in opt["legs"]
                               if l["type"] == "bus"}),
        }
    return out


def google_minutes(pairs: pd.DataFrame, mode: str) -> dict[str, dict]:
    key = config.GOOGLE_MAPS_API_KEY
    if not key:
        return {}
    out: dict[str, dict] = {}
    with httpx.Client(timeout=20.0) as client:
        for _, p in pairs.iterrows():
            try:
                r = client.get(
                    "https://maps.googleapis.com/maps/api/directions/json",
                    params={"origin": f"{p['from_lat']},{p['from_lon']}",
                            "destination": f"{p['to_lat']},{p['to_lon']}",
                            "mode": mode, "key": key})
                data = r.json()
                leg = data["routes"][0]["legs"][0]
                out[p["pair_id"]] = {
                    "min": round(leg["duration"]["value"] / 60.0, 1),
                    "distance_km": round(leg["distance"]["value"] / 1000, 2),
                }
            except Exception as exc:  # noqa: BLE001
                print(f"  {p['pair_id']}: google failed ({exc})")
            time.sleep(0.15)   # stay under Directions QPS limits
    return out


# --------------------------------------------------------------------------- #
# report
# --------------------------------------------------------------------------- #

def write_report(pairs: pd.DataFrame, pred: dict, obs: dict,
                 gmap: dict) -> None:
    rows = []
    for _, p in pairs.iterrows():
        pid = p["pair_id"]
        pr = pred.get(pid, {})
        ob = obs.get(pid, {})
        gm = gmap.get(pid, {})
        obs_m = ob.get("median_min")
        bus = pr.get("bus_min")
        total = pr.get("total_min")
        row = {
            "pair_id": pid,
            "route_id": p["route_id"],
            "from_stop": p["from_stop"],
            "to_stop": p["to_stop"],
            "observed_n": ob.get("n", 0),
            "predicted_total_min": total,
            "predicted_bus_min": bus,
            "observed_median_min": obs_m,
            "google_min": gm.get("min"),
            "err_bus_vs_obs_pct": (
                round(abs(bus - obs_m) / obs_m * 100, 1)
                if bus and obs_m else None),
            "err_total_vs_obs_pct": (
                round(abs(total - obs_m) / obs_m * 100, 1)
                if total and obs_m else None),
            "err_bus_vs_google_pct": (
                round(abs(bus - gm["min"]) / gm["min"] * 100, 1)
                if bus and gm.get("min") else None),
            "time_sources": "|".join(pr.get("sources", [])),
        }
        rows.append(row)
    df = pd.DataFrame(rows)
    OUT_DIR.mkdir(exist_ok=True)
    df.to_csv(REPORT_CSV, index=False)

    n_obs = df["observed_median_min"].notna().sum()
    mape_obs = (df["err_bus_vs_obs_pct"].dropna().mean()
                if n_obs else float("nan"))
    mape_g = df["err_bus_vs_google_pct"].dropna().mean() \
        if df["err_bus_vs_google_pct"].notna().any() else float("nan")
    print(f"\nreport: {REPORT_CSV}  ({len(df)} pairs, "
          f"{n_obs} with GPS actuals)")
    print(f"  MAPE bus-vs-observed : {mape_obs:.1f}%" if n_obs else
          "  MAPE bus-vs-observed : n/a (run --observe first)")
    if not np.isnan(mape_g):
        print(f"  MAPE bus-vs-google   : {mape_g:.1f}%")

    # scatter: predicted bus time vs observed (and vs google)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(7, 7))
    o = df["observed_median_min"]
    b = df["predicted_bus_min"]
    ok = o.notna() & b.notna()
    if ok.any():
        ax.scatter(o[ok], b[ok], s=45, color="#1a73e8",
                   label=f"vs GPS actual (n={int(ok.sum())})")
    g = df["google_min"]
    okg = g.notna() & b.notna()
    if okg.any():
        ax.scatter(g[okg], b[okg], s=45, color="#34a853", alpha=0.75,
                   marker="s", label=f"vs Google Maps (n={int(okg.sum())})")
    vals = df[["observed_median_min", "predicted_bus_min",
               "google_min"]].max()
    top = vals.max()
    lim = 10.0 if pd.isna(top) or top <= 0 else float(top) * 1.05
    ax.plot([0, lim], [0, lim], "--", color="#999", label="perfect fit")
    ax.set_xlabel("reference travel time (min)")
    ax.set_ylabel("predicted bus time (min)")
    ax.set_title("commuttify validation: predicted vs actual")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(SCATTER_PNG, dpi=140)
    print(f"  scatter: {SCATTER_PNG}")


# --------------------------------------------------------------------------- #

def main() -> None:
    ap = argparse.ArgumentParser(description="Validate journey predictions "
                                             "vs observed GPS and Google")
    ap.add_argument("--observe", action="store_true",
                    help="derive actuals from a raw GPS day file first")
    ap.add_argument("--observe-day", default="2026_10_02",
                    help="day suffix for --observe, e.g. 2026_10_02")
    ap.add_argument("--skip-google", action="store_true",
                    help="do not call Google Maps (comparison only)")
    ap.add_argument("--google-mode", default="driving",
                    choices=["driving", "transit"],
                    help="Google Directions mode for the comparison")
    ap.add_argument("--use-cache", action="store_true",
                    help="reuse outputs/observed_actuals.json if present")
    args = ap.parse_args()

    print("[1/4] selecting 30 OD pairs (seed=42)")
    pairs = select_pairs()
    print(f"  {len(pairs)} pairs over {pairs['route_id'].nunique()} routes")

    obs: dict[str, dict] = {}
    if args.observe:
        print(f"[2/4] observing actuals from day {args.observe_day}")
        obs = observe_day(pairs, args.observe_day)
        OUT_DIR.mkdir(exist_ok=True)
        OBS_JSON.write_text(json.dumps(obs, indent=1), encoding="utf-8")
        print(f"  cached -> {OBS_JSON}")
    elif args.use_cache and OBS_JSON.exists():
        obs = json.loads(OBS_JSON.read_text(encoding="utf-8"))
        print(f"[2/4] loaded {len(obs)} cached observations")
    else:
        print("[2/4] skipping observe (use --observe or --use-cache)")

    print("[3/4] predicting with the journey API")
    pred = predict(pairs)
    print(f"  predicted {len(pred)}/{len(pairs)} pairs")

    gmap: dict[str, dict] = {}
    if not args.skip_google and config.GOOGLE_MAPS_API_KEY:
        print(f"[4/4] comparing against Google Maps ({args.google_mode})")
        gmap = google_minutes(pairs, args.google_mode)
    else:
        print("[4/4] --skip-google (or no GOOGLE_MAPS_API_KEY)")

    write_report(pairs, pred, obs, gmap)


if __name__ == "__main__":
    main()
