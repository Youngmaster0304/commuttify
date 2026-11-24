import { ArrowRight, Bus, Clock, ShieldCheck, Sparkles, TrendingDown } from "lucide-react";
import { Button } from "@/components/ui/button";

interface HeroSectionProps {
  onPlanJourney: (originId?: string, destId?: string) => void;
  onExploreFeatures: () => void;
}

export function HeroSection({ onPlanJourney, onExploreFeatures }: HeroSectionProps) {
  return (
    <section className="relative overflow-hidden pt-12 pb-16 md:pt-20 md:pb-24 bg-[#FAFAFA]">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 lg:gap-8 items-center">
          {/* Left Column: Headline and CTAs */}
          <div className="lg:col-span-7 space-y-6">
            <h1 className="text-4xl sm:text-6xl md:text-7xl font-display font-black tracking-tight text-neutral-950 leading-[1.08]">
              Delhi Buses, <br />
              <span className="font-serif italic font-normal text-neutral-800">solved for</span>{" "}
              <span className="relative inline-block bg-[#FACC15] px-3.5 py-1 rounded-lg text-black font-extrabold shadow-sm border-2 border-black">
                commuters.
              </span>
            </h1>

            <p className="text-base sm:text-lg text-neutral-600 max-w-xl leading-relaxed">
              Plan stop-to-stop journeys, compare real-time traffic speeds against static timetables, dodge bottleneck
              choke-points, and ask our AI transit assistant — all in one place.
            </p>

            <div className="flex flex-wrap items-center gap-3 pt-2">
              <Button
                onClick={() => onPlanJourney()}
                className="h-12 px-7 rounded-full bg-black text-white hover:bg-neutral-800 font-bold text-sm shadow-md transition-all hover:scale-[1.02] flex items-center gap-2 cursor-pointer"
              >
                <span>Plan a journey</span>
                <span>↗</span>
              </Button>
              <Button
                variant="outline"
                onClick={onExploreFeatures}
                className="h-12 px-6 rounded-full border-2 border-neutral-300 hover:border-black bg-white text-neutral-800 font-medium text-sm transition-all cursor-pointer"
              >
                Explore corridors
              </Button>
            </div>

            {/* Network Quick Stats */}
            <div className="grid grid-cols-3 gap-6 pt-6 border-t border-neutral-200 max-w-md">
              <div>
                <div className="text-2xl sm:text-3xl font-display font-black text-neutral-900">5,465+</div>
                <div className="text-[11px] font-mono tracking-wider text-neutral-500 uppercase mt-0.5">
                  FLEET BUSES
                </div>
              </div>
              <div>
                <div className="text-2xl sm:text-3xl font-display font-black text-neutral-900">450+</div>
                <div className="text-[11px] font-mono tracking-wider text-neutral-500 uppercase mt-0.5">
                  ACTIVE ROUTES
                </div>
              </div>
              <div>
                <div className="text-2xl sm:text-3xl font-display font-black text-neutral-900">₹5–25</div>
                <div className="text-[11px] font-mono tracking-wider text-neutral-500 uppercase mt-0.5">
                  FARE RANGE
                </div>
              </div>
            </div>
          </div>

          {/* Right Column: Retro Boarding Pass Ticket */}
          <div className="lg:col-span-5 flex justify-center">
            <div className="relative w-full max-w-md bg-white border-2 border-black rounded-2xl p-6 sm:p-7 shadow-hard-lg transition-transform hover:-translate-y-1">
              {/* Yellow Corner Ribbon */}
              <div className="absolute top-0 right-0 overflow-hidden size-24 rounded-tr-xl pointer-events-none">
                <div className="absolute transform rotate-45 bg-[#FACC15] text-black font-mono font-bold text-[10px] py-1 right-[-35px] top-[20px] w-[130px] text-center border-y border-black shadow-sm">
                  SAMPLE
                </div>
              </div>

              {/* Pass Header */}
              <div className="flex items-center justify-between border-b-2 border-dashed border-neutral-200 pb-4 mb-5">
                <div className="flex items-center gap-2">
                  <div className="size-6 rounded bg-black text-white flex items-center justify-center font-bold text-[10px]">
                    DTC
                  </div>
                  <span className="font-mono text-xs font-semibold text-neutral-600 tracking-wider">
                    BOARDING PASS
                  </span>
                </div>
                <span className="font-mono text-xs text-neutral-400 pr-10">CMFT-3545</span>
              </div>

              {/* Route Endpoints */}
              <div className="space-y-4 mb-6">
                <div>
                  <div className="text-[10px] font-mono tracking-widest text-neutral-400 uppercase">FROM</div>
                  <div className="flex items-baseline justify-between mt-0.5">
                    <span className="text-xl font-display font-bold text-neutral-900">Kashmere Gate ISBT</span>
                    <span className="text-xs font-mono px-2 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200 font-semibold">
                      Route 419
                    </span>
                  </div>
                </div>

                <div className="flex items-center gap-3 text-neutral-300">
                  <div className="h-px flex-1 bg-neutral-200" />
                  <ArrowRight className="size-4 text-neutral-400" />
                  <div className="h-px flex-1 bg-neutral-200" />
                </div>

                <div>
                  <div className="text-[10px] font-mono tracking-widest text-neutral-400 uppercase">TO</div>
                  <div className="flex items-baseline justify-between mt-0.5">
                    <span className="text-xl font-display font-bold text-neutral-900">AIIMS Ring Road</span>
                    <span className="text-xs font-mono px-2 py-0.5 rounded bg-blue-50 text-blue-700 border border-blue-200 font-semibold">
                      South Corridor
                    </span>
                  </div>
                </div>
              </div>

              {/* Ticket Metrics */}
              <div className="grid grid-cols-3 gap-2 py-4 px-3 bg-neutral-50 rounded-xl border border-neutral-200 text-center mb-5">
                <div>
                  <div className="text-lg font-display font-black text-neutral-900">₹20</div>
                  <div className="text-[10px] font-mono tracking-wider text-neutral-500 uppercase">FARE</div>
                </div>
                <div className="border-x border-neutral-200">
                  <div className="text-lg font-display font-black text-emerald-600 flex items-center justify-center gap-1">
                    <span>38 min</span>
                  </div>
                  <div className="text-[10px] font-mono tracking-wider text-neutral-500 uppercase flex items-center justify-center gap-0.5">
                    <TrendingDown className="size-2.5 text-emerald-600" /> LIVE TIME
                  </div>
                </div>
                <div>
                  <div className="text-lg font-display font-black text-neutral-900">1</div>
                  <div className="text-[10px] font-mono tracking-wider text-neutral-500 uppercase">CHANGE</div>
                </div>
              </div>

              {/* Spectrum Color Bar */}
              <div className="h-2 w-full rounded-full flex overflow-hidden mb-5">
                <div className="flex-1 bg-rose-500" title="AC Fleet" />
                <div className="flex-1 bg-emerald-500" title="CNG Fleet" />
                <div className="flex-1 bg-blue-500" title="Electric e-Bus" />
                <div className="flex-1 bg-purple-500" title="Express Corridors" />
                <div className="flex-1 bg-amber-500" title="Cluster Fleet" />
                <div className="flex-1 bg-cyan-500" title="Metro Feeder" />
              </div>

              {/* Ticket Action Button */}
              <Button
                onClick={() => onPlanJourney("kashmere-gate", "aiims")}
                className="w-full h-11 bg-black text-white hover:bg-neutral-800 rounded-xl font-bold text-xs uppercase tracking-wider transition-all shadow cursor-pointer"
              >
                Click to Plan a journey
              </Button>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
