import { useState } from "react";
import { ArrowUpRight, Bus, MapPin, Navigation, Radio, ShieldAlert } from "lucide-react";
import { Button } from "@/components/ui/button";

interface NetworkCorridorsProps {
  onSelectCorridor: (corridorId: string) => void;
  onLaunchPlanner: () => void;
  onOpenAlerts: () => void;
}

interface CorridorInfo {
  id: string;
  name: string;
  status: "ACTIVE" | "CONGESTED" | "MODERATE";
  colorHex: string;
  routes: string[];
  avgSpeed: string;
  description: string;
  delayMin: number;
}

const CORRIDORS: CorridorInfo[] = [
  {
    id: "ring-road",
    name: "Ring Road Express",
    status: "ACTIVE",
    colorHex: "#10b981", // Green
    routes: ["419", "534", "TMS", "729"],
    avgSpeed: "24 km/h",
    description: "Arterial circular corridor connecting AIIMS, Moolchand, Ashram, and Kashmere Gate.",
    delayMin: 4,
  },
  {
    id: "outer-ring",
    name: "Outer Ring Road",
    status: "ACTIVE",
    colorHex: "#3b82f6", // Blue
    routes: ["764", "883", "990"],
    avgSpeed: "28 km/h",
    description: "Wide perimeter corridor serving Hauz Khas, Munirka, Dhaula Kuan, and Janakpuri.",
    delayMin: 2,
  },
  {
    id: "vikas-marg",
    name: "Vikas Marg & Yamuna",
    status: "MODERATE",
    colorHex: "#f97316", // Orange
    routes: ["85", "522", "39"],
    avgSpeed: "16 km/h",
    description: "Primary link between Central Delhi (ITO) and Trans-Yamuna (Laxmi Nagar, Anand Vihar).",
    delayMin: 9,
  },
  {
    id: "ashram-mathura",
    name: "Mathura Road & Ashram",
    status: "CONGESTED",
    colorHex: "#ef4444", // Red
    routes: ["419", "534", "MS"],
    avgSpeed: "9 km/h",
    description: "Heavy bottleneck near Ashram chowk & Sarai Kale Khan flyover. Severe bus delays.",
    delayMin: 18,
  },
  {
    id: "dhaula-kuan",
    name: "Dhaula Kuan & NH-48",
    status: "ACTIVE",
    colorHex: "#eab308", // Yellow
    routes: ["729", "764", "Airport Exp"],
    avgSpeed: "21 km/h",
    description: "South-West corridor connecting Central Secretariat to Gurgaon border & IGI Airport.",
    delayMin: 5,
  },
  {
    id: "rohtak-road",
    name: "Rohtak Road Corridor",
    status: "ACTIVE",
    colorHex: "#a855f7", // Purple
    routes: ["990", "778", "85"],
    avgSpeed: "22 km/h",
    description: "West Delhi arterial serving Punjabi Bagh, Peeragarhi, Nangloi and Tikri border.",
    delayMin: 3,
  },
  {
    id: "mb-road",
    name: "Mehrauli-Badarpur (MB)",
    status: "ACTIVE",
    colorHex: "#06b6d4", // Teal
    routes: ["505", "534", "419"],
    avgSpeed: "19 km/h",
    description: "Southern cross-corridor connecting Saket, Khanpur, Hamdard, and Badarpur border.",
    delayMin: 6,
  },
  {
    id: "gt-karnal",
    name: "GT Karnal Road",
    status: "ACTIVE",
    colorHex: "#ec4899", // Pink
    routes: ["103", "120", "131"],
    avgSpeed: "25 km/h",
    description: "North Delhi gateway from Azadpur wholesale mandi to Narela and Singhu border.",
    delayMin: 4,
  },
];

export function NetworkCorridors({ onSelectCorridor, onLaunchPlanner, onOpenAlerts }: NetworkCorridorsProps) {
  const [activeTab, setActiveTab] = useState<"planner" | "fleets" | "fares" | "alerts">("planner");

  return (
    <section id="corridors" className="py-16 bg-white border-t border-neutral-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Secondary Sub-Navigation Segmented Bar */}
        <div className="flex items-center justify-start sm:justify-center overflow-x-auto pb-4 mb-10 border-b border-neutral-200 scrollbar-none">
          <div className="inline-flex p-1 rounded-xl bg-neutral-100 border border-neutral-200 text-xs font-medium">
            <button
              type="button"
              onClick={() => {
                setActiveTab("planner");
                onLaunchPlanner();
              }}
              className="px-4 py-2 rounded-lg bg-white text-black font-semibold shadow-sm transition-all flex items-center gap-1.5 cursor-pointer whitespace-nowrap"
            >
              <span>🗺️ Bus Planner</span>
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("fleets")}
              className="px-4 py-2 rounded-lg text-neutral-600 hover:text-black transition-all flex items-center gap-1.5 cursor-pointer whitespace-nowrap"
            >
              <span>🚌 DTC & Cluster Fleets</span>
            </button>
            <button
              type="button"
              onClick={() => {
                const el = document.getElementById("fare-calculator");
                el?.scrollIntoView({ behavior: "smooth" });
              }}
              className="px-4 py-2 rounded-lg text-neutral-600 hover:text-black transition-all flex items-center gap-1.5 cursor-pointer whitespace-nowrap"
            >
              <span>🎫 Fare Calculator</span>
            </button>
            <button
              type="button"
              onClick={onOpenAlerts}
              className="px-4 py-2 rounded-lg text-neutral-600 hover:text-black transition-all flex items-center gap-1.5 cursor-pointer whitespace-nowrap"
            >
              <span>🚨 Live Alerts</span>
            </button>
          </div>
        </div>

        {/* Delhi Bus Commute Planner Callout Card */}
        <div className="mb-16 border-2 border-black rounded-2xl overflow-hidden shadow-hard-lg bg-neutral-50">
          <div className="bg-[#121214] text-white px-6 py-4 flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-neutral-800">
            <div className="flex items-center gap-2.5">
              <Bus className="size-5 text-amber-400" />
              <h2 className="font-display font-bold text-base text-white">Delhi Bus Commute Planner</h2>
            </div>
            <span className="text-[11px] font-mono text-neutral-400">
              Real-Time Speeds & Delay Prediction
            </span>
          </div>
          <div className="p-6 sm:p-8 text-center max-w-2xl mx-auto">
            <p className="text-sm text-neutral-600 leading-relaxed mb-6">
              Use the Boarding Pass calculator in the Hero section above to find routes, or launch our real-time traffic
              model to view congestion heatmaps, fleet locations, and live delays across Delhi.
            </p>
            <Button
              onClick={onLaunchPlanner}
              className="h-11 px-6 rounded-full bg-black text-white hover:bg-neutral-800 font-bold text-xs uppercase tracking-wider shadow transition-all hover:scale-105 cursor-pointer"
            >
              Open Route Planner Form ↗
            </Button>
          </div>
        </div>

        {/* Section Header */}
        <div className="mb-10">
          <div className="text-xs font-mono font-medium text-neutral-500 uppercase tracking-widest mb-1.5">
            § 02 — NETWORK
          </div>
          <h2 className="text-3xl sm:text-4xl font-display font-black text-neutral-900 tracking-tight">
            Major Corridors. One city.
          </h2>
          <p className="text-sm text-neutral-600 mt-2 max-w-xl">
            Live bus telemetry continuously feeds our travel-time model along major arterial routes. Select any
            corridor to view speed trends and delays.
          </p>
        </div>

        {/* 8-Card Responsive Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {CORRIDORS.map((corridor) => (
            <div
              key={corridor.id}
              onClick={() => onSelectCorridor(corridor.id)}
              className="group p-5 bg-white border border-neutral-200 hover:border-black rounded-xl transition-all duration-200 hover:shadow-hard cursor-pointer relative overflow-hidden flex flex-col justify-between"
            >
              {/* Left Color Strip */}
              <div
                className="absolute left-0 top-0 bottom-0 w-1.5"
                style={{ backgroundColor: corridor.colorHex }}
              />

              <div>
                <div className="flex items-center justify-between mb-2">
                  <h3 className="font-display font-bold text-base text-neutral-900 group-hover:text-amber-600 transition-colors">
                    {corridor.name}
                  </h3>
                  <span
                    className={`text-[10px] font-mono px-2 py-0.5 rounded-full font-bold uppercase ${
                      corridor.status === "ACTIVE"
                        ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                        : corridor.status === "CONGESTED"
                        ? "bg-rose-50 text-rose-700 border border-rose-200"
                        : "bg-amber-50 text-amber-700 border border-amber-200"
                    }`}
                  >
                    {corridor.status}
                  </span>
                </div>

                <p className="text-xs text-neutral-500 line-clamp-2 leading-relaxed mb-4">
                  {corridor.description}
                </p>
              </div>

              <div className="pt-3 border-t border-neutral-100 flex items-center justify-between text-xs">
                <div className="flex items-center gap-1 font-mono text-neutral-700 font-semibold">
                  <span>{corridor.avgSpeed}</span>
                  {corridor.delayMin > 10 && (
                    <span className="text-[10px] text-rose-600 font-normal">
                      (+{corridor.delayMin}m delay)
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-1 text-[11px] font-mono text-neutral-500 group-hover:text-black">
                  <span>Explore</span>
                  <ArrowUpRight className="size-3" />
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
