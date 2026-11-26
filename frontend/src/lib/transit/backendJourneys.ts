// Maps FastAPI /journeys responses into the UI's local Journey shape so the
// planner can use the real PostGIS routing engine (with the bundled local
// model as an offline fallback).
import type { BusRoute, Stop } from "./data";
import type { Day, Journey, Leg } from "./model";

interface BackendWalkLeg {
  type: "walk";
  from: string;
  to: string;
  depart: string;
  arrive: string;
  duration_min: number;
  distance_m?: number;
  from_lat?: number;
  from_lon?: number;
  to_lat?: number;
  to_lon?: number;
}

interface BackendBusLeg {
  type: "bus";
  route: string;
  route_name?: string;
  direction?: number;
  from: string;
  to: string;
  from_id?: string;
  to_id?: string;
  from_lat?: number;
  from_lon?: number;
  to_lat?: number;
  to_lon?: number;
  stop_ids?: string[];
  stop_names?: string[];
  coords?: [number, number][];
  depart: string;
  arrive: string;
  duration_min: number;
  stops: number;
  distance_m?: number;
  source?: "live" | "historical" | "schedule";
}

interface BackendOption {
  label: string;
  departure: string;
  arrival: string;
  duration_min: number;
  transfers: number;
  walk_min: number;
  legs: (BackendWalkLeg | BackendBusLeg)[];
}

const DAY_IDX: Record<Day, number> = { Sun: 0, Mon: 1, Tue: 2, Wed: 3, Thu: 4, Fri: 5, Sat: 6 };
const FLEETS = ["cng", "ac", "electric"] as const;

const pad = (n: number) => String(n).padStart(2, "0");

/** ISO-8601 departure (+05:30) for the next occurrence of `day` at `minutes`. */
export function departAtIso(day: Day, minutes: number): string {
  const now = new Date();
  const d = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  for (let i = 0; i < 7 && d.getDay() !== DAY_IDX[day]; i++) d.setDate(d.getDate() + 1);
  const h = Math.floor(minutes / 60) % 24;
  const m = minutes % 60;
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(h)}:${pad(m)}:00+05:30`;
}

/** Minutes-of-day from a backend ISO timestamp (emitted in IST). */
function isoMinutes(iso: string): number {
  const m = /T(\d{2}):(\d{2})/.exec(iso);
  return m ? Number(m[1]) * 60 + Number(m[2]) : 0;
}

function synthRoute(routeId: string, name?: string): BusRoute {
  const display = name || routeId;
  let h = 0;
  for (const ch of routeId) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return {
    id: routeId,
    number: display,
    name: display,
    corridor: "arterial",
    fleet: FLEETS[h % FLEETS.length],
    stops: [],
    headway: { peak: 10, offpeak: 15, night: 30 },
  };
}

function synthStop(id: string | undefined, name: string, lat?: number, lon?: number): Stop {
  return { id: id ?? name, name, area: "", lat: lat ?? 0, lng: lon ?? 0, hotspot: 1 };
}

/** Convert a /journeys response into local-model Journey objects. */
export function mapBackendJourneys(data: unknown, departMin: number): Journey[] {
  const opts = (data as { options?: BackendOption[] } | null)?.options;
  if (!Array.isArray(opts)) return [];

  const out: Journey[] = [];
  for (const opt of opts) {
    let clock = departMin;
    const legs: Leg[] = [];
    let walkKm = 0;
    let busKm = 0;

    for (const bl of opt.legs) {
      if (bl.type === "walk") {
        const distKm = (bl.distance_m ?? 0) / 1000;
        const purpose: Extract<Leg, { kind: "walk" }>["purpose"] =
          opt.legs.length === 1
            ? "direct"
            : legs.length === 0
              ? "access"
              : bl.to === "destination"
                ? "egress"
                : "transfer";
        legs.push({
          kind: "walk",
          from: { lat: bl.from_lat ?? 0, lng: bl.from_lon ?? 0, label: bl.from },
          to: { lat: bl.to_lat ?? 0, lng: bl.to_lon ?? 0, label: bl.to },
          distanceKm: distKm,
          minutes: bl.duration_min,
          startMin: clock,
          purpose,
        });
        walkKm += distKm;
        clock += bl.duration_min;
        continue;
      }

      const waitMin = Math.max(0, isoMinutes(bl.depart) - clock);
      const rideMin = bl.duration_min;
      const distKm = (bl.distance_m ?? 0) / 1000;
      legs.push({
        kind: "bus",
        route: synthRoute(bl.route, bl.route_name),
        from: synthStop(bl.from_id, bl.from, bl.from_lat, bl.from_lon),
        to: synthStop(bl.to_id, bl.to, bl.to_lat, bl.to_lon),
        stops: bl.stop_ids ?? [],
        stopNames: bl.stop_names,
        coords: bl.coords,
        source: bl.source,
        waitMin,
        headway: 0,
        rideMin,
        distanceKm: distKm,
        avgSpeed: rideMin > 0 ? distKm / (rideMin / 60) : 0,
        boardMin: clock + waitMin,
        alightMin: clock + waitMin + rideMin,
      });
      busKm += distKm;
      clock += waitMin + rideMin;
    }

    const totalMin = clock - departMin;
    const hasBus = legs.some((l) => l.kind === "bus");
    out.push({
      id: opt.label,
      type: !hasBus ? "walk" : opt.transfers === 0 ? "direct" : "transfer",
      legs,
      departMin,
      arriveMin: clock,
      totalMin,
      quietMin: totalMin,
      quietAtMin: departMin,
      timetableMin: totalMin,
      trafficDelayMin: 0,
      walkKm,
      busKm,
      transfers: opt.transfers,
    });
  }
  return out;
}
