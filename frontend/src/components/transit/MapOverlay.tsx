import { useEffect, useState } from "react";
import { Activity, AlertCircle, Bus, Layers, MessageSquare, X } from "lucide-react";

import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { useTween } from "@/hooks/use-tween";
import type { Day } from "@/lib/transit/data";
import { SPEED_BANDS, cityStats, formatClock } from "@/lib/transit/model";
import { cn } from "@/lib/utils";

const BAND_BG = {
  fast: "bg-traffic-fast",
  moderate: "bg-traffic-moderate",
  heavy: "bg-traffic-heavy",
  severe: "bg-traffic-severe",
} as const;

interface Props {
  day: Day;
  minutes: number;
  showTraffic: boolean;
  showFleet: boolean;
  showTweets?: boolean;
  tweetCount?: number;
  hasRoute?: boolean;
  onClearRoute?: () => void;
  onTraffic: (v: boolean) => void;
  onFleet: (v: boolean) => void;
  onTweets?: (v: boolean) => void;
  onToggleTweetsPanel?: () => void;
}

export function NetworkStatus({
  day,
  minutes,
  showTraffic,
  showFleet,
  showTweets = true,
  tweetCount = 8,
  hasRoute = false,
  onClearRoute,
  onTraffic,
  onFleet,
  onTweets,
  onToggleTweetsPanel,
}: Props) {
  const stats = cityStats(day, minutes);
  const avg = useTween(stats.avgSpeed);
  const label = SPEED_BANDS.find((b) => b.band === stats.band)?.label;
  // null = first paint / SSR: CSS decides (hidden on phones, shown on desktop)
  const [collapsed, setCollapsed] = useState<boolean | null>(null);

  useEffect(() => {
    setCollapsed(window.matchMedia("(max-width: 767px)").matches);
  }, []);

  return (
    <>
      {/* compact pill — shown only while the card is hidden */}
      <button
        type="button"
        onClick={() => setCollapsed(false)}
        title="Show network status"
        className={cn(
          "items-center gap-2 rounded-full border border-border bg-card py-2 pl-3 pr-3.5 shadow-float cursor-pointer",
          collapsed === true ? "flex" : "hidden",
        )}
      >
        <span className="live-dot" />
        <span className="text-xs font-semibold tabular">{Math.round(avg)} km/h</span>
        <span className={cn("rounded px-1.5 py-0.5 text-[10px] font-semibold text-primary-foreground", BAND_BG[stats.band])}>
          {label}
        </span>
        {tweetCount > 0 && <span className="text-[10px] font-medium text-rose-600">{tweetCount} alerts</span>}
      </button>

      <div
        className={cn(
          "w-[245px] max-w-[calc(100vw-1.5rem)] rounded-xl border border-border bg-card p-3 shadow-float md:max-w-none",
          collapsed === null ? "hidden md:block" : collapsed ? "hidden" : "block",
        )}
      >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
          <span className="live-dot" /> Modeled network
        </div>
        <div className="flex items-center gap-1.5">
          {onToggleTweetsPanel && (
            <button
              onClick={onToggleTweetsPanel}
              type="button"
              className="flex items-center gap-1 rounded bg-rose-500/10 text-rose-600 dark:text-rose-400 font-semibold px-1.5 py-0.5 text-[10px] hover:bg-rose-500/20 transition-colors"
            >
              <AlertCircle className="size-3" /> {tweetCount} Alerts
            </button>
          )}
          <button
            type="button"
            onClick={() => setCollapsed(true)}
            aria-label="Hide network status card"
            title="Hide"
            className="rounded p-0.5 text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
          >
            <X className="size-3.5" />
          </button>
        </div>
      </div>

      <div className="mt-1 flex items-baseline gap-1.5">
        <span className="tabular text-2xl font-semibold">{Math.round(avg)}</span>
        <span className="text-xs text-muted-foreground">km/h avg</span>
        <span className={cn("ml-auto rounded px-1.5 py-0.5 text-[10px] font-semibold text-primary-foreground", BAND_BG[stats.band])}>{label}</span>
      </div>
      <div className="mt-0.5 text-xs text-muted-foreground">
        {day} {formatClock(minutes)} · {Math.round(stats.congestedShare * 100)}% of corridors congested
      </div>
      <div className="mt-3 space-y-2 border-t border-border pt-3">
        <div className="flex items-center justify-between">
          <Label htmlFor="traffic-toggle" className="flex items-center gap-1.5 text-xs font-medium cursor-pointer">
            <Layers className="size-3.5 text-amber-500" /> Traffic speeds
          </Label>
          <Switch id="traffic-toggle" checked={showTraffic} onCheckedChange={onTraffic} />
        </div>
        <div className="flex items-center justify-between">
          <Label htmlFor="fleet-toggle" className="flex items-center gap-1.5 text-xs font-medium cursor-pointer">
            <Bus className="size-3.5 text-sky-500" /> Live bus fleet
          </Label>
          <Switch id="fleet-toggle" checked={showFleet} onCheckedChange={onFleet} />
        </div>
        {onTweets && (
          <div className="flex items-center justify-between">
            <Label htmlFor="tweets-toggle" className="flex items-center gap-1.5 text-xs font-medium cursor-pointer">
              <AlertCircle className="size-3.5 text-rose-500" /> Live tweets & alerts
            </Label>
            <Switch id="tweets-toggle" checked={showTweets} onCheckedChange={onTweets} />
          </div>
        )}
      </div>

      {hasRoute && (
        <div className="mt-2.5 pt-2 border-t border-border flex items-center justify-between">
          <span className="text-[10px] font-semibold text-blue-600 dark:text-blue-400 flex items-center gap-1">
            <span className="size-1.5 rounded-full bg-blue-600 animate-pulse" />
            Route Active (Other lines faded)
          </span>
          {onClearRoute && (
            <button
              type="button"
              onClick={onClearRoute}
              className="text-[10px] text-muted-foreground hover:text-foreground underline cursor-pointer"
            >
              Show all lines
            </button>
          )}
        </div>
      )}
      </div>
    </>
  );
}

export function Legend({ showFleet }: { showFleet: boolean }) {
  return (
    <div className="rounded-xl border border-border bg-card px-3 py-2.5 text-[11px] shadow-float">
      <div className="mb-1.5 flex items-center gap-1.5 font-medium text-muted-foreground">
        <Activity className="size-3.5" /> Bus speed
      </div>
      <div className="grid grid-cols-2 gap-x-3 gap-y-1">
        {SPEED_BANDS.map((b) => (
          <span key={b.band} className="flex items-center gap-1.5">
            <span className={cn("h-1.5 w-4 rounded-full", BAND_BG[b.band])} />
            {b.label}
            <span className="tabular text-muted-foreground">{b.min > 0 ? `${b.min}+` : "<11"}</span>
          </span>
        ))}
      </div>
      {showFleet && (
        <div className="mt-2 flex gap-2 border-t border-border pt-2">
          <span className="flex items-center gap-1"><span className="size-2 rounded-full bg-fleet-ac" />AC</span>
          <span className="flex items-center gap-1"><span className="size-2 rounded-full bg-fleet-cng" />CNG</span>
          <span className="flex items-center gap-1"><span className="size-2 rounded-full bg-fleet-electric" />e-Bus</span>
        </div>
      )}
    </div>
  );
}
