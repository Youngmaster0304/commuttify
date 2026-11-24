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
- **Frontend** — React + Vite showcase: transit map, journey cards, live
  tweets feed, fare calculator, chatbot drawer.
- **Validation** — `backend/validate_model.py` checks predictions against
  observed GPS travel times and (optionally, offline only) Google Maps.

## Architecture

```mermaid
flowchart LR
    subgraph Sources
        A1["Static GTFS<br/>(delhi.transportstack.in)"]
        A2["Historical GPS<br/>11 SQLite days (~34 GB)"]
        A3["GTFS-RT live feed<br/>(10 s polls)"]
    end

    subgraph Ingest
        B1["ingest_gtfs.py<br/>stops · routes · trips<br/>stop_times · shapes"]
        B2["process_historical.py<br/>snap → speed cells<br/>day × hour averages"]
        B3["live_feed_worker.py<br/>SegmentSnapIndex<br/>speed decay 15 min"]
    end

    subgraph Storage
        C1[("PostgreSQL / PostGIS<br/>:5433")]
        C2[("Redis<br/>live:seg:*")]
    end

    subgraph Engine
        D1["routing.py<br/>time-dependent Dijkstra<br/>3 presets: fastest/<br/>balanced/fewest"]
        D2["recommend.py<br/>fuzzy place search"]
        D3["chatbot.py<br/>LLM chain + rules"]
    end

    subgraph Serving
        E1["FastAPI backend.main<br/>:8010 · /journeys · /api/*"]
        E2["frontend/ (React + Vite)<br/>map · cards · chatbot"]
    end

    A1 --> B1 --> C1
    A2 --> B2 --> C1
    A3 --> B3 --> C2
    C1 --> D1
    C2 --> D1
    C1 --> D2
    C1 --> D3
    D1 --> E1
    D2 --> E1
    D3 --> E1
    E1 <--> E2
```

Docker provides **PostGIS (:5433)** and **Redis (:6380)** (ports remapped to
avoid clashes with other local projects).

## Data workflow

```mermaid
flowchart TD
    S1["GTFS download (portal)"] --> I1["ingest_gtfs.py --rebuild"]
    I1 --> T1["schema 001_schema.sql<br/>stops · routes · trips ·<br/>stop_times · shapes"]
    T1 --> T2["topology 010_topology.sql<br/>shape → route_segments<br/>80,861 edges + nodes"]
    S2["11 × bus_movements_*.db"] --> H1["process_historical.py<br/>--chunksize 100000<br/>(2 workers/week — RAM bound)"]
    H1 --> H2["historical_segment_speeds<br/>4.7 M samples →<br/>71,676 segment cells"]
    S3["GTFS-RT API key"] --> W1["live_feed_worker"]
    W1 --> W2["Redis live:seg:*<br/>trust window 15 min"]
    T2 --> G["GraphCache (in-proc)<br/>route_nodes + route_segments"]
    H2 --> G
    W2 --> G
    G --> R["GET /journeys<br/>time-dependent Dijkstra"]
    R --> V["validate_model.py<br/>30 OD pairs vs observed GPS"]
```

Historical pipeline memory note: each worker holds pandas chunks of the
~31 M-row `vehicle_feed`; run **2 workers max** on a 16 GB machine
(`outputs/run_hist_waves.ps1` orchestrates waves of 2 with a free-RAM gate).

## Journey request sequence

```mermaid
sequenceDiagram
    participant C as Client
    participant API as FastAPI /journeys
    participant R as routing.py
    participant Redis as Redis live:seg:*
    participant DB as PostGIS historical + schedule

    C->>API: from/to lat-lon, depart_at, option
    API->>R: plan_journeys(depart_at, preset)
    R->>R: snap endpoints → nearest route_nodes
    loop each edge on candidate path
        R->>Redis: live speed (age < 15 min?)
        alt live hit
            Redis-->>R: live speed → source=live
        else
            R->>DB: day-of-week × hour average
            alt historical hit
                DB-->>R: avg speed → source=historical
            else
                DB-->>R: GTFS schedule speed → source=schedule
            end
        end
        R->>R: weight = length / speed (+ wait at stops)
    end
    R->>R: time-dependent Dijkstra (3 presets)
    API-->>C: 3 options: walk legs, bus legs,<br/>total min, transfers, per-leg source
```

Every leg in the response carries `source: live | historical | schedule` —
the ETA math is fully inspectable.

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| API | FastAPI + Uvicorn, Pydantic | typed contracts, OpenAPI for free |
| DB | PostgreSQL 16 + PostGIS 3.4 | spatial joins, pure-PostGIS routing (no pgRouting needed) |
| Cache / live | Redis | 10 s GTFS-RT writes, O(1) edge lookups |
| Live feed | httpx polling, `x-api-key` header | portal GTFS-RT every 10 s |
| Routing | pure-Python time-dependent Dijkstra | fastest/balanced/fewest presets, no external solver |
| Historical | pandas + SQLite readers → `psycopg2.execute_values` | 34 GB day files streamed in 100 k-row chunks |
| Search | rapidfuzz over place index | type-2 fuzzy tiers, top-10 autocomplete |
| Chatbot | OpenAI-compatible chain → FreeLLMAPI → rules | works with zero keys configured |
| Validation | pandas + matplotlib (scatter) | observed GPS vs predicted vs Google (offline) |
| Frontend | React 19, Vite, TanStack Router, Tailwind/shadcn | showcase map UI |
| Infra | Docker Compose (db + redis) | one-command up |

## Data model (core tables)

| Table | Contents |
|---|---|
| `stops` | 6,862 GTFS stops (name, lat/lon) |
| `routes` | 2,574 routes (long_name, agency) |
| `trips` | 80,357 trips (direction, shape, service) |
| `stop_times` | 2,737,136 stop-time rows |
| `route_segments` | 80,861 directed edges: geometry, length_m, source/target node ids |
| `route_nodes` | 6,862 junction nodes (degree ≥ 1, snapped stop endpoints) |
| `shape_geoms` | 3,498 decoded shapes |
| `historical_segment_speeds` | segment × dow × hour: avg speed, sample count (from 11-day GPS) |

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

# 7. frontend (separate terminal)
cd frontend && npm install && npm run dev
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

## Frontend

`frontend/` — React 19 + Vite + TanStack Router showcase:

- **ShowcaseLanding** — hero, network corridors, fare calculator, ticker tape
- **TransitMap** (MapLibre) — routes, stops, live vehicles, journey overlay
- **JourneyCard / TimeControls** — 3-option results, depart-at picker
- **ChatbotDrawer** — talks to `POST /api/chat`
- **LiveTweetsFeed / AuthModal** — social proof + sign-in

Run it with `npm run dev` after the backend is up (API base in
`frontend/src/lib/api.ts`).

## Layout

```
backend/          FastAPI app, routing, ingest, live worker, chatbot, validation
frontend/         React showcase (separately owned)
sql/              001_schema.sql (PostGIS), 010_topology.sql (pure-PostGIS graph)
data/gtfs/        static GTFS (drop portal download here; not committed)
data/gtfs_sample/ tiny sample feed for tests
outputs/          run logs, validation report, observed actuals cache (not committed)
docker-compose.yml, Dockerfile.db, requirements.txt, .env.example, README.md
```

## Chatbot LLM endpoints

1. `CHATBOT_LLM_URL/_MODEL/_KEY` — primary OpenAI-compatible endpoint
2. `CHATBOT_FALLBACK_URL/_MODEL/_KEY` — defaults to a local FreeLLMAPI router
   (`http://localhost:3001/v1/chat/completions`, unified key from its dashboard)
3. rule-based fallback — always works with no keys configured

Scope is enforced: off-topic questions get a refusal pointing back to Delhi
bus topics (both in the system prompt and a pre-LLM keyword gate).

## Hackathon criteria mapping

| Criterion | Where |
|---|---|
| Real-time bus traffic model | `live_feed_worker.py` + `historical_segment_speeds` (live → historical → schedule) |
| Google-Maps-like journey API | `GET /journeys` — own Dijkstra, no Google in serving path |
| ETA accuracy | per-edge speeds from 11-day GPS + 10 s live feed; validated by `validate_model.py` |
| Recommendation / search | `/api/search/autocomplete` fuzzy top-10 |
| Assistant | `/api/chat` scoped Delhi-bus chatbot with LLM chain |
| Data honesty | ingests the official portal GTFS + provided GPS day files |
