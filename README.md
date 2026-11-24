# commuttify — Real-time Bus Traffic Model & Journey Planner (Delhi)

Hackathon entry for **Problem 1 — Delhi Transport Stack Hackathon 2026**:
a traffic model built from real-time + historical Delhi bus GPS data, and a
Google-Maps-like **journey planning API that computes ETAs itself** — no
Google Directions calls in the serving path.

## What it does

- **Own routing API** — `GET /journeys` plans walk + bus journeys between any
  two coordinates in Delhi with a time-dependent Dijkstra over the GTFS road
  graph (fastest / balanced / fewest-transfers options).
- **ETA math is ours** — edge travel times resolve **live → historical →
  schedule**: real-time GTFS-RT speeds (10 s polls, 15 min trust window),
  historical day-of-week × hour averages from 11 days of GPS traces
  (~34 GB SQLite), then GTFS schedule as the base.
- **Recommendation engine** — `GET /api/search/autocomplete?q=` (type a word →
  top-10 places, fuzzy tiers, metro-parity with commutify).
- **Chatbot** — `POST /api/chat` Delhi-bus-only assistant: intent detection +
  local engine context, LLM (primary OpenAI-compatible endpoint →
  [FreeLLMAPI](https://github.com/tashfeenahmed/freellmapi) fallback → rules).
- **Validation** — `backend/validate_model.py` checks predictions against
  observed GPS travel times and (optionally, offline only) Google Maps.

## Architecture

```
data/gtfs (static, portal)──► ingest_gtfs.py ──► PostgreSQL/PostGIS
historical *.db (11 days) ──► process_historical.py ──► historical_segment_speeds
GTFS-RT (your API key) ────► live_feed_worker.py ──► Redis live:seg:* ─┐
                                                                       ▼
                                     routing.py (time-dependent Dijkstra) ──► FastAPI
recommend.py (places)  ┐
chatbot.py (LLM chain) ┘──► FastAPI /api/search/* , /api/chat
```

Docker provides **PostGIS (:5433)** and **Redis (:6380)** (ports remapped to
avoid clashes with other local projects).

## Quick start

```powershell
# 1. infra
docker compose up -d

# 2. Python deps
pip install -r requirements.txt

# 3. static GTFS — download from delhi.transportstack.in (portal),
#    unzip the .txt files into data\gtfs\
python -m backend.ingest_gtfs --gtfs-dir data\gtfs --rebuild

# 4. historical model (11 day files; run 2 at a time — memory bound)
python -m backend.process_historical --days 2026_10_01 --chunksize 100000
#    ... repeat per day, or run outputs\run_hist_waves.ps1

# 5. live worker (needs GTFS_RT_KEY in .env)
python -m backend.live_feed_worker

# 6. API
python -m uvicorn backend.main:app --port 8010
```

Copy `.env.example` → `.env` first and fill in `GTFS_RT_KEY`
(verified working: ~5.2k vehicle entities / poll).

## API

| Endpoint | Purpose |
|---|---|
| `GET /health` | db/redis liveness |
| `GET /journeys?from_lat=&from_lon=&to_lat=&to_lon=&depart_at=` | 3 journey options (fastest/balanced/fewest), walk + bus legs, per-leg time source |
| `GET /api/search/autocomplete?q=rohini` | top-10 place suggestions |
| `POST /api/search/refresh` | reload place cache after re-ingest |
| `POST /api/graph/refresh` | drop routing graph + historical cache |
| `POST /api/chat` `{"message": "..."}` | Delhi-bus-only chatbot `{"reply": "..."}` |

Example:

```powershell
curl "http://localhost:8010/journeys?from_lat=28.71797&from_lon=77.06390&to_lat=28.70060&to_lon=77.09380"
# -> 14.1 min, bus 1189, walk 1.2 min (legs carry source: live|historical|schedule)
```

## Validation (success criterion)

```powershell
# actual stop->stop times from raw GPS (one day) -> outputs/observed_actuals.json
python -m backend.validate_model --observe --observe-day 2026_10_02

# predictions vs observed (+ Google if GOOGLE_MAPS_API_KEY set)
python -m backend.validate_model --skip-google
```

Writes `outputs/validation_report.csv` (30 OD pairs: predicted vs observed vs
Google, MAPE columns) and `outputs/validation_scatter.png`.

**Google Maps policy:** used only offline in `validate_model.py` for the
comparison the judging criteria ask for. The serving API never calls Google —
routes and ETAs are computed from Delhi's own data.

## Layout

```
backend/          FastAPI app, routing, ingest, live worker, chatbot, validation
sql/              001_schema.sql (PostGIS), 010_topology.sql (pure-PostGIS graph)
data/gtfs/        static GTFS (drop portal download here; not committed)
outputs/          run logs, validation report, observed actuals cache
docker-compose.yml, Dockerfile.db, requirements.txt, .env.example
```

## Chatbot LLM endpoints

1. `CHATBOT_LLM_URL/_MODEL/_KEY` — primary OpenAI-compatible endpoint
2. `CHATBOT_FALLBACK_URL/_MODEL/_KEY` — defaults to a local FreeLLMAPI router
   (`http://localhost:3001/v1/chat/completions`, unified key from its dashboard)
3. rule-based fallback — always works with no keys configured

Scope is enforced: off-topic questions get a refusal pointing back to Delhi
bus topics (both in the system prompt and a pre-LLM keyword gate).
