import { ArrowRight, Bus } from "lucide-react";
import { Button } from "@/components/ui/button";

interface BottomBannerProps {
  onPlanJourney: () => void;
  onOpenAuth: () => void;
}

export function BottomBanner({ onPlanJourney, onOpenAuth }: BottomBannerProps) {
  return (
    <>
      {/* Ready When You Are CTA Section */}
      <section className="py-20 sm:py-28 bg-[#F3F3F3] border-t border-neutral-200 text-center">
        <div className="max-w-4xl mx-auto px-4 sm:px-6">
          <div className="text-xs font-mono font-medium text-neutral-500 uppercase tracking-widest mb-3">
            ✦ READY WHEN YOU ARE
          </div>

          <h2 className="text-4xl sm:text-6xl font-display font-black text-neutral-950 tracking-tight leading-[1.1] mb-8">
            Board smarter. <br />
            <span className="font-serif italic font-normal text-neutral-800">Travel</span> lighter.
          </h2>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
            <Button
              onClick={onPlanJourney}
              className="h-12 px-8 rounded-full bg-black text-white hover:bg-neutral-800 font-bold text-sm shadow-md transition-all hover:scale-105 flex items-center gap-2 cursor-pointer"
            >
              <span>Launch Journey Planner</span>
              <span>↗</span>
            </Button>
            <Button
              variant="outline"
              onClick={onOpenAuth}
              className="h-12 px-6 rounded-full border-2 border-neutral-300 hover:border-black bg-white text-neutral-800 font-medium text-sm transition-all cursor-pointer"
            >
              Create free account
            </Button>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-white border-t border-neutral-200 py-8">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex items-center justify-between gap-4 text-xs text-neutral-500 font-mono">
          <div className="flex items-center gap-2">
            <div className="size-6 rounded-lg bg-black text-white flex items-center justify-center font-bold text-[10px]">
              <Bus className="size-3.5 text-amber-400" />
            </div>
            <span className="font-display font-bold text-neutral-900">Commuttify © 2026</span>
          </div>
        </div>
      </footer>
    </>
  );
}
