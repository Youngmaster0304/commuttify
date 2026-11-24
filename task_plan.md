# Commuttify Backend — Task Plan

Delhi Transport Stack Hackathon 2026, Problem 1: real-time bus traffic model + journey planner.
Project root: `C:\Users\Abhinav\commuttify`

## Decisions (confirmed with user)

| Decision | Value |
|---|---|
| Historical data | `C:\Users\Abhinav\Downloads\delhi_buses_dataset\bus_movements_YYYY_MM_DD.db` (11 days, Oct 1-11 2026, ~34 GB, table `vehicle_feed`) |
| Live GTFS-RT | `https://dts-backend.transportstack.in/api/dataset/otd/get-file?agency=delhi-buses&category=realtime_gtfs&filename=VehiclePositions.pb`, header `x-api-key`, poll every 10 s |
| Static GTFS | NOT on disk yet. User downloads full ZIP from delhi.transportstack.in portal -> drop into `data/gtfs/`. Smoke tests use `data/gtfs_sample/` (TransportStack sample, id-space verified against GPS). |
| DB | Docker: PostGIS + pgRouting (`Dockerfile.db`), Redis 7 |
| First run | Smoke test with `--limit`, then full 11-day background run |
| Name | commuttify (bus-only, derived from commutify) |

## Phases

- [x] P0 Research: dataset schema, live feed key test (HTTP 200, 4587 vehicles), static GTFS id-space alignment check
- [x] P1 Scaffold: docker-compose, .env, requirements (README pending)
- [x] P2 Prompt 1: `sql/001_schema.sql`, `backend/models.py`, `backend/ingest_gtfs.py`
- [x] P3 Infra up: containers healthy (db :5433, redis :6380 — 5432/6379 taken by samanvay), schema applied, sample GTFS ingest verified (35 segments, 36 nodes)
- [x] P3.5 Recommendation engine: `backend/recommend.py` + `GET /api/search/autocomplete` (metro commutify parity, rapidfuzz tiers, tested over HTTP)
- [ ] P4 Prompt 2: `backend/process_historical.py` (chunked, snap, dow/hour, `--limit`) — code written, not yet smoke-tested
- [x] P5 Prompt 3: `backend/live_feed_worker.py` (async poll, snap, Redis TTL 900 s) — synthetic test PASS (150.4s vs 150 expected, TTL 900), real `--once` poll OK (5465 vehicles, 1.0s)
- [x] P6 Prompt 4: `backend/routing.py` + `GET /journeys` (3 options, live -> historical -> schedule) — time-dependent Dijkstra, presets dedup, smoke PASS; `backend/main.py` has health/autocomplete/journeys/graph-refresh
- [ ] P7 Chatbot: `backend/chatbot.py` + `POST /chat`
- [ ] P8 Prompt 6: `backend/validate_model.py` (30 OD pairs, Google Maps, CSV + scatter)
- [ ] P9 Smoke test end-to-end; report full-run commands

## Blockers

- Full static GTFS missing (portal download by user) — sample GTFS unblocks all development.
- Google Maps API key not provided — `validate_model.py` runs in no-Google mode until `GOOGLE_MAPS_API_KEY` is set.

## Verification checklist

1. `docker compose up -d` healthy (PostGIS image; pgRouting dropped — topology is pure PostGIS in `sql/010_topology.sql`)
2. Ingest sample: `stops/routes/trips/stop_times/shape_geoms/route_segments` non-empty
3. `process_historical.py --limit 100000` writes `historical_segment_speeds` rows
4. `live_feed_worker.py --once` writes `live:seg:*` keys with TTL
5. `GET /journeys?...` returns 3 options with legs + ETA
6. `validate_model.py --skip-google` writes `outputs/validation_report.csv`
