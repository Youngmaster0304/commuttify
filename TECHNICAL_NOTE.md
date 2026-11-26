# Technical note — commuttify

**Delhi Transport Stack Hackathon 2026** — real-time bus traffic model +
Google-Maps-like journey API for Delhi. Brief: method, assumptions,
limitations.

## Method

1. **Graph** — official portal GTFS (static) is ingested into PostGIS;
   route shapes are exploded into **80,861 directed road segments** over
   6,862 stops (pure-PostGIS topology, no pgRouting).
2. **Historical model** — the provided GPS day files
   (`bus_movements_*.db`) are streamed in 100 k-row chunks, filtered
   (>80 km/h anomalies dropped, dwell = speed 0), snapped to segments, and
   aggregated into **segment × day-of-week × hour** average travel times
   → `historical_segment_speeds` (4.7 M cells from 30 days).
3. **Live model** — GTFS-RT vehicle positions are polled every 10 s,
   snapped to segments and converted to edge speeds; a live speed is
   trusted for **15 minutes** (Redis `live:seg:*`, in-process TTL cache
   when Redis is absent).
4. **Journey API** — `GET /journeys` runs a time-dependent Dijkstra with
   three presets (fastest / balanced / fewest transfers). Each edge
   resolves **live → historical → schedule** at the departure time;
   walking access/egress ≤ 800 m at 1.2 m/s; scheduled waits at
   boarding/transfer stops are included. **No Google Directions calls in
   the serving path** — every leg reports its time source
   (`live | historical | schedule`).
5. **Validation** — `backend/validate_model.py` compares predicted
   stop→stop times against observed GPS times for 30 origin–destination
   pairs (MAPE), optionally against Google Maps **offline only**.

## Assumptions

- Segment travel time depends only on (day-of-week, hour); no weather,
  holiday or incident modelling beyond the 15-minute live window.
- Edges with neither live nor historical data fall back to a schedule
  default speed (~15 km/h).
- Walking is straight-line at 1.2 m/s, max 800 m to reach a stop.
- GPS points belong to the nearest route segment after snapping; the
  provided day files represent normal operations.
- The static GTFS schedule is a valid base timetable for waits and
  first-bus times.

## Limitations

- **Buses only** — coverage equals the portal GTFS (no metro/rail);
  journeys may include walking legs only as access/egress.
- The live layer exists only while the worker polls; on the free
  Render tier the service sleeps between pings (cold start), and the
  web service (Oregon) talks to the database (Singapore) over the
  public internet, adding latency to uncached queries.
- day-of-week × hour averages smooth out unusual days; the validation
  report is generated locally (`outputs/validation_report.csv`) and is
  not committed.
- The chatbot is deliberately scoped to Delhi bus topics (keyword gate +
  prompt); replies are LLM-phrased with Groq, falling back to rules when
  no key is configured.
