import { useState } from "react";
import { Check, Heart, Shield, Ticket, Zap } from "lucide-react";
import { Slider } from "@/components/ui/slider";

export function FareCalculator() {
  const [distanceKm, setDistanceKm] = useState(12);

  // DTC Standard Fare Matrix
  const nonAcFare = distanceKm <= 4 ? 5 : distanceKm <= 10 ? 10 : 15;
  const acFare = distanceKm <= 4 ? 10 : distanceKm <= 8 ? 15 : distanceKm <= 12 ? 20 : 25;

  return (
    <section id="fare-calculator" className="py-16 bg-[#FAFAFA] border-t border-neutral-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center max-w-2xl mx-auto mb-12">
          <div className="text-xs font-mono font-medium text-neutral-500 uppercase tracking-widest mb-1.5">
            § 03 — FARES & PASSES
          </div>
          <h2 className="text-3xl sm:text-4xl font-display font-black text-neutral-900 tracking-tight">
            Affordable. Transparent. Zero Guesswork.
          </h2>
          <p className="text-sm text-neutral-600 mt-2">
            Calculate exact DTC and Cluster fares based on official Delhi Government transit tariffs.
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          {/* Interactive Distance Estimator */}
          <div className="lg:col-span-7 bg-white border-2 border-black rounded-2xl p-6 sm:p-8 shadow-hard">
            <h3 className="font-display font-bold text-xl text-neutral-900 mb-2">
              Trip Distance Estimator
            </h3>
            <p className="text-xs text-neutral-500 mb-6">
              Drag the slider to adjust your commute distance and see live pricing across all vehicle classes.
            </p>

            {/* Slider */}
            <div className="space-y-4 mb-8">
              <div className="flex justify-between items-baseline">
                <span className="text-sm font-mono text-neutral-600">DISTANCE</span>
                <span className="text-2xl font-display font-black text-neutral-900">
                  {distanceKm} <span className="text-sm font-normal text-neutral-500">km</span>
                </span>
              </div>
              <Slider
                value={[distanceKm]}
                onValueChange={(vals) => setDistanceKm(vals[0] ?? 1)}
                min={1}
                max={40}
                step={1}
                className="cursor-pointer"
              />
              <div className="flex justify-between text-[11px] font-mono text-neutral-400">
                <span>1 km (Local)</span>
                <span>20 km (Cross-city)</span>
                <span>40 km (NCR / Outskirts)</span>
              </div>
            </div>

            {/* Fare Breakdown Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div className="p-4 rounded-xl border border-neutral-200 bg-neutral-50">
                <div className="text-[11px] font-mono text-neutral-500 uppercase">Non-AC Standard</div>
                <div className="text-3xl font-display font-black text-neutral-900 mt-1">₹{nonAcFare}</div>
                <div className="text-[11px] text-neutral-500 mt-1">CNG / Green bus</div>
              </div>

              <div className="p-4 rounded-xl border-2 border-black bg-amber-50">
                <div className="text-[11px] font-mono text-amber-800 uppercase font-bold">AC & e-Bus</div>
                <div className="text-3xl font-display font-black text-amber-950 mt-1">₹{acFare}</div>
                <div className="text-[11px] text-amber-800 mt-1">Red & Blue electric fleet</div>
              </div>

              <div className="p-4 rounded-xl border border-rose-200 bg-rose-50/70">
                <div className="text-[11px] font-mono text-rose-700 uppercase font-bold flex items-center gap-1">
                  <Heart className="size-3 fill-rose-500 text-rose-500" />
                  Pink Ticket
                </div>
                <div className="text-3xl font-display font-black text-rose-700 mt-1">₹0</div>
                <div className="text-[11px] text-rose-600 mt-1">Free for all female commuters</div>
              </div>
            </div>
          </div>

          {/* Daily Passes & Smart Cards */}
          <div className="lg:col-span-5 space-y-4">
            <div className="p-6 bg-white border border-neutral-200 rounded-2xl shadow-sm">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <Ticket className="size-5 text-amber-500" />
                  <h4 className="font-display font-bold text-base text-neutral-900">DTC All-Route Daily Pass</h4>
                </div>
                <span className="font-mono text-xs font-bold px-2 py-0.5 rounded bg-neutral-100">
                  ₹50 / Day
                </span>
              </div>
              <p className="text-xs text-neutral-600 leading-relaxed mb-4">
                Unlimited rides on any DTC AC, Non-AC, and Cluster electric bus until midnight. Valid across Delhi NCR.
              </p>
              <ul className="text-xs text-neutral-500 space-y-1.5 font-mono">
                <li className="flex items-center gap-1.5">
                  <Check className="size-3 text-emerald-600" /> Non-AC Daily Pass: ₹40
                </li>
                <li className="flex items-center gap-1.5">
                  <Check className="size-3 text-emerald-600" /> AC All-Fleet Pass: ₹50
                </li>
                <li className="flex items-center gap-1.5">
                  <Check className="size-3 text-emerald-600" /> Available via One Delhi & Chartr apps
                </li>
              </ul>
            </div>

            <div className="p-6 bg-neutral-900 text-white border border-neutral-800 rounded-2xl shadow-sm">
              <div className="flex items-center gap-2 mb-2">
                <Zap className="size-4 text-amber-400" />
                <h4 className="font-display font-bold text-sm text-white">National Common Mobility Card (NCMC)</h4>
              </div>
              <p className="text-xs text-neutral-400 leading-relaxed">
                Delhi Metro Smart Cards and RuPay NCMC cards are accepted on all DTC electronic ticketing machines with
                a 10% discount on standard fares.
              </p>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
