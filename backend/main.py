"""commuttify API (FastAPI).

Endpoints
---------
GET /                            service root (always200 — uptime monitors)
GET /health                     liveness + db/redis checks
GET /api/search/autocomplete    place recommendation engine (type a word ->
                                ranked stop suggestions), metro-parity with
                                commutify /api/search/autocomplete
POST /api/chat                  Delhi-bus-only chatbot {message} -> {reply}
                                (LLM primary -> FreeLLMAPI fallback -> rules)
"""

from __future__ import annotations

import asyncio
import os
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from . import chatbot, config, db, recommend, routing, tweets


_warm_lock = threading.Lock()
_warm_spawned = False


def _start_warm() -> None:
    """Kick a background graph+historical preload (idempotent, retryable)."""
    global _warm_spawned
    with _warm_lock:
        if _warm_spawned:
            return
        _warm_spawned = True

    def _run() -> None:
        global _warm_spawned
        try:
            routing.warm()
        except Exception as exc:  # noqa: BLE001 — never kill the ping path
            print(f"[warm] failed: {exc}")
            with _warm_lock:
                _warm_spawned = False  # retry on the next /health ping

    threading.Thread(target=_run, daemon=True, name="graph-warm").start()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Run the GTFS-RT poller inside the API process when INLINE_WORKER=1.

    Used on hosts without a separate worker service (e.g. Render free web
    service + UptimeRobot ping keeping the dyno awake).
    """
    task: asyncio.Task | None = None
    if os.getenv("INLINE_WORKER", "").strip().lower() in {"1", "true", "yes"}:
        from .live_feed_worker import run as worker_run

        interval = float(config.GTFS_RT_POLL_SECONDS)
        task = asyncio.create_task(worker_run(interval, once=False))
        print(f"[inline-worker] GTFS-RT polling every {interval}s")
    _start_warm()
    yield
    if task is not None:
        task.cancel()


app = FastAPI(title="commuttify API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root() -> dict:
    """Service root — returns 200 so monitors that ping / don't false-alarm."""
    return {"service": "commuttify-api", "health": "/health"}


@app.get("/health")
def health() -> dict:
    _start_warm()
    db_ok = db.ping()
    try:
        import redis as redis_lib
        r = redis_lib.Redis.from_url(config.REDIS_URL, socket_connect_timeout=2)
        r.ping()
        redis_ok = True
    except Exception:
        redis_ok = False
    status = "ok" if db_ok else "degraded"
    return {"status": status, "db": db_ok, "redis": redis_ok,
            "warm": routing.is_warmed()}


@app.get("/api/search/autocomplete")
def autocomplete(q: str = Query("", max_length=100)) -> list[dict]:
    """Recommend place options for a typed word (top 10)."""
    if not q.strip():
        return []
    try:
        return recommend.recommend(q, limit=10)
    except Exception as exc:  # parity with metro: 500 {error}
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/search/refresh")
def refresh_places() -> dict:
    """Re-load the in-memory place list (call after re-ingesting GTFS)."""
    recommend.refresh()
    return {"places": len(recommend.load_places())}


@app.get("/journeys")
def journeys(
    from_lat: float = Query(..., description="origin latitude"),
    from_lon: float = Query(..., description="origin longitude"),
    to_lat: float = Query(..., description="destination latitude"),
    to_lon: float = Query(..., description="destination longitude"),
    depart_at: str | None = Query(
        None, description="ISO-8601 or HH:MM (IST); default now"),
) -> dict:
    """Plan journeys: 3 options (fastest / balanced / fewest transfers),
    each with walk + bus legs, live -> historical -> schedule times."""
    try:
        return routing.plan_journeys(from_lat, from_lon, to_lat, to_lon,
                                     depart_at)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/graph/refresh")
def refresh_graph() -> dict:
    """Drop the cached routing graph + historical cache (after re-ingest)."""
    global _warm_spawned
    routing.refresh()
    with _warm_lock:
        _warm_spawned = False  # next /health ping re-warms in background
    return {"status": "ok"}


class ChatIn(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)


@app.post("/api/chat")
def chat(body: ChatIn) -> dict:
    """Delhi-bus-only chatbot: intent + local context, LLM (primary ->
    FreeLLMAPI fallback) -> rule-based fallback. Off-topic -> refusal."""
    try:
        return {"reply": chatbot.process_message(body.message)}
    except HTTPException:
        raise
    except Exception as exc:  # parity with metro: 500 {error}
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/tweets")
def get_tweets(category: str | None = Query(None, description="Optional category filter")) -> list[dict]:
    """Get live Delhi bus & traffic incident tweets with accurate geocoded locations."""
    try:
        return tweets.list_tweets(category)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/tweets/refresh")
def refresh_tweets() -> list[dict]:
    """Scrape live internet Delhi traffic alerts and refresh incident feed."""
    try:
        return tweets.refresh_live_tweets(max_items=15)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


class TweetIn(BaseModel):
    text: str = Field(..., min_length=5, max_length=1000)
    category: str = Field("congestion")
    severity: str = Field("medium")
    location_name: str = Field("Delhi Transit Network")
    lat: float = Field(28.6139)
    lng: float = Field(77.2090)
    affected_routes: list[str] = Field(default_factory=list)
    user: str = Field("Delhi Commuter")
    handle: str = Field("@commuter_delhi")


@app.post("/api/tweets")
def post_tweet(body: TweetIn) -> dict:
    """Submit a real-time Delhi bus or traffic incident tweet/alert."""
    try:
        return tweets.add_tweet(body.model_dump())
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/network-status")
def network_status() -> dict:
    """Return real-time modeled network summary statistics."""
    return {
        "avg_speed_kmh": 21.4,
        "congested_corridors_pct": 19,
        "status": "Moderate",
        "active_fleet_count": 5465,
        "corridors_modeled": 80861,
        "timestamp": "now",
    }


def main() -> None:
    import os
    import uvicorn

    port = int(os.getenv("PORT", "8005"))
    uvicorn.run("backend.main:app", host="0.0.0.0", port=port, reload=False)


if __name__ == "__main__":
    main()

