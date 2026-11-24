"""Place recommendation engine (port of metro commutify's autocomplete).

Metro used Elasticsearch's completion suggester (prefix + fuzziness AUTO).
Here the same behaviour runs in-process over the stops table:

    tier 1  exact name match            score 1000
    tier 2  name starts with query      score  800
    tier 3  any word starts with query  score  700
    tier 4  query is a substring        score  600
    tier 5  fuzzy (rapidfuzz >= 75)     score  400..500

Top `limit` results after ranking (score desc, shorter name first),
deduplicated by name. The place list is cached in memory (TTL 5 min)
and can be force-refreshed after a re-ingest via refresh().
"""

from __future__ import annotations

import time

from rapidfuzz import fuzz, process
from sqlalchemy import text

from . import db

_CACHE_TTL_S = 300.0
_FUZZY_CUTOFF = 75.0

_places: list[dict] = []
_loaded_at = 0.0


def load_places(force: bool = False) -> list[dict]:
    """Return [{stop_id, name, lat, lon}] for every named stop (cached)."""
    global _places, _loaded_at
    if not force and _places and time.time() - _loaded_at < _CACHE_TTL_S:
        return _places
    with db.get_engine().connect() as conn:
        rows = conn.execute(text(
            "SELECT stop_id, stop_name, ST_Y(geom) AS lat, ST_X(geom) AS lon "
            "FROM stops "
            "WHERE stop_name IS NOT NULL AND stop_name <> '' AND geom IS NOT NULL"
        )).mappings().all()
    _places = [
        {
            "stop_id": str(r["stop_id"]),
            "name": str(r["stop_name"]),
            "lat": float(r["lat"]),
            "lon": float(r["lon"]),
        }
        for r in rows
    ]
    _loaded_at = time.time()
    return _places


def refresh() -> None:
    """Drop the cache (call after re-ingesting GTFS)."""
    load_places(force=True)


def _tier_score(q: str, name: str) -> float | None:
    nl = name.lower()
    if nl == q:
        return 1000.0
    if nl.startswith(q):
        return 800.0
    if any(w.startswith(q) for w in nl.replace("-", " ").split()):
        return 700.0
    if q in nl:
        return 600.0
    return None


def recommend(q: str, limit: int = 10) -> list[dict]:
    """Top `limit` place suggestions for a typed word (metro-parity API)."""
    q = (q or "").strip().lower()
    if not q:
        return []
    places = load_places()
    if not places:
        return []

    names = [p["name"] for p in places]
    hits: list[tuple[float, int]] = []  # (score, index into places)

    for i, p in enumerate(places):
        s = _tier_score(q, p["name"])
        if s is not None:
            hits.append((s, i))

    if len(hits) < limit:
        # fuzzy tier: same idea as ES completion fuzziness: AUTO
        seen = {i for _, i in hits}
        fuzzy = process.extract(
            q, names, scorer=fuzz.partial_ratio,
            limit=limit * 3, score_cutoff=_FUZZY_CUTOFF,
        )
        for name, score, idx in fuzzy:
            if idx in seen:
                continue
            hits.append((400.0 + float(score), idx))  # 475..500 band
            seen.add(idx)

    hits.sort(key=lambda t: (-t[0], len(names[t[1]]), names[t[1]]))

    out: list[dict] = []
    seen_names: set[str] = set()
    for score, i in hits:
        p = places[i]
        key = p["name"].lower()
        if key in seen_names:
            continue
        seen_names.add(key)
        out.append({**p, "score": round(score, 1), "type": "stop"})
        if len(out) >= limit:
            break
    return out
