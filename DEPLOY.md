# Deployment guide (Render + Vercel + Upstash)

Stack: **Vercel** (frontend) · **Render** (API + inline live worker) ·
**Render Postgres/Supabase** (PostGIS) · **Upstash** (Redis) ·
**UptimeRobot** (keeps the Render free service awake).

## 0. What the repo already provides

| File | Purpose |
|---|---|
| `Dockerfile` | API image (uvicorn on `$PORT`) |
| `render.yaml` | Render blueprint — web service, health check `/health`, `INLINE_WORKER=1` |
| `vercel.json` | Vercel framework config (tanstack-start) |
| `backend/main.py` lifespan | starts the GTFS-RT poller in-process when `INLINE_WORKER=1` |
| `.env.example` | full variable list (keys empty) |

## 1. Database (do first — everything needs its URL)

**Option A — Render Postgres (one dashboard with the API):**
1. Render → New → **Postgres** → free instance → database `commuttify`.
2. Copy **Internal URL** (looks like `postgres://…:…@…`).
3. Enable PostGIS in the SQL editor:
   ```sql
   CREATE EXTENSION IF NOT EXISTS postgis;
   ```
4. SSL: append `?sslmode=require` when used as `postgresql+psycopg2://…`.

**Option B — Supabase:** create project → enable `postgis` extension →
copy Connection string (Session mode, pooler) → `?sslmode=require`.

## 2. Load the data (from your machine, one time)

The cloud DB must hold GTFS + topology + historical cells:

```powershell
# full DB (schema, GTFS, topology, historical cells) to Render/Supabase URL
$CLOUD = "postgresql+psycopg2://USER:PASSWORD@HOST:5432/commuttify?sslmode=require"
docker exec -i commuttify-db pg_dump -U commuttify --no-owner commuttify |
  docker run --rm -i postgres:16 psql "$CLOUD"
```

(Alternatively re-run `ingest_gtfs` + `process_historical` pointing
`DATABASE_URL` at the cloud DB — slower over the network.)

Verify: `SELECT count(*) FROM route_segments;` → ~80,861.

## 3. Redis (Upstash)

1. Upstash → create DB (free, region close to Render) → copy
   **Redis URL** (`rediss://default:…@…:6380` — TLS, works with `redis-py`).
2. Render env `REDIS_URL` = that URL.

## 4. Backend on Render

1. Render → **New → Blueprint** (or Web Service → repo) → select this repo —
   `render.yaml` is auto-detected (Docker, free, `/health` check).
2. Paste env vars (dashboard → Environment):
   `DATABASE_URL`, `REDIS_URL`, `GTFS_RT_KEY` (from local `.env`), and
   optional `CHATBOT_LLM_*` / `CHATBOT_FALLBACK_*`.
3. Deploy → wait for `https://commuttify-api.onrender.com/health`
   → `{"status":"ok","db":true,"redis":true}`.
4. Test live data: the Render logs should show
   `[inline-worker] GTFS-RT polling every 10s` + `poll ok: {entities: …}`.

## 5. Keep it awake (UptimeRobot)

1. [uptimerobot.com](https://uptimerobot.com) → Add monitor →
   **HTTP(s)** → `https://commuttify-api.onrender.com/health` → 5 min interval.
2. Render free services sleep after ~15 min idle; the ping prevents that,
   so the inline GTFS-RT worker never stops.

## 6. Frontend on Vercel

1. Vercel → **Import** repo `Youngmaster0304/commuttify` (framework auto:
   tanstack-start; if it asks for a root directory, use `frontend`).
2. Env var: **`VITE_API_BASE`** = `https://commuttify-api.onrender.com`.
3. Deploy → open the `.vercel.app` URL → search a place, plan a journey,
   send a chatbot message.

## 7. Smoke checklist

- [ ] `GET …/health` → `ok, db: true, redis: true`
- [ ] Render logs → inline worker `poll ok` every ~10 s
- [ ] `GET …/journeys?from_lat=…` → 3 options, legs with `source`
- [ ] `GET …/api/search/autocomplete?q=rohini` → 10 places
- [ ] `POST …/api/chat` → reply (or refusal if off-topic)
- [ ] Vercel site renders map + journey card against prod API
- [ ] UptimeRobot monitor green

## Notes

- CORS is open (`*`) — fine for the demo; tighten to the Vercel domain later.
- Local dev unchanged: `docker compose up -d` + `uvicorn … --port 8010`,
  `.env` stays local and untracked.
- Render free Postgres expires after 90 days (fine for the hackathon);
  Supabase free is longer-lived if you prefer Option B.
