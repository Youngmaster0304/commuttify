import React, { useState, useEffect } from "react";
import {
  AlertTriangle,
  Flame,
  Info,
  MapPin,
  MessageCircle,
  PlusCircle,
  RefreshCw,
  Share2,
  ThumbsUp,
  TrendingUp,
  X,
  CheckCircle2,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { fetchLiveTweets, submitIncidentTweet, type TweetData } from "@/lib/api";
import { STOPS } from "@/lib/transit/data";
import { cn } from "@/lib/utils";
import { toast } from "sonner";

interface Props {
  selectedTweetId: string | null;
  onSelectTweet: (tweet: TweetData) => void;
  className?: string;
}

const CATEGORIES = [
  { id: "all", label: "All Alerts" },
  { id: "congestion", label: "Congestion" },
  { id: "breakdown", label: "Breakdowns" },
  { id: "diversion", label: "Diversions" },
  { id: "waterlogging", label: "Waterlogging" },
  { id: "accident", label: "Accidents" },
];

export function LiveTweetsFeed({ selectedTweetId, onSelectTweet, className }: Props) {
  const [tweets, setTweets] = useState<TweetData[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeCategory, setActiveCategory] = useState("all");
  const [isReportOpen, setIsReportOpen] = useState(false);

  // New report form state
  const [reportText, setReportText] = useState("");
  const [reportCategory, setReportCategory] = useState<string>("congestion");
  const [reportSeverity, setReportSeverity] = useState<string>("medium");
  const [reportLocation, setReportLocation] = useState("");
  const [reportRoutes, setReportRoutes] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const loadTweets = async () => {
    setLoading(true);
    try {
      const data = await fetchLiveTweets(activeCategory);
      setTweets(data);
    } catch {
      toast.error("Failed to refresh live alerts");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTweets();
  }, [activeCategory]);

  const handleCreateReport = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!reportText.trim()) {
      toast.error("Please enter the incident details");
      return;
    }

    setSubmitting(true);
    try {
      // Find matching stop coordinates or default to central Delhi
      const matchedStop = STOPS.find((s) => s.name.toLowerCase().includes(reportLocation.toLowerCase()));
      const lat = matchedStop ? matchedStop.lat : 28.6139;
      const lng = matchedStop ? matchedStop.lng : 77.209;

      const routesArray = reportRoutes
        .split(",")
        .map((r) => r.trim())
        .filter(Boolean);

      const newTweet = await submitIncidentTweet({
        text: reportText,
        category: reportCategory,
        severity: reportSeverity,
        location_name: reportLocation || "Delhi Bus Corridor",
        lat,
        lng,
        affected_routes: routesArray,
        user: "Commuter (You)",
        handle: "@delhi_commuter",
      });

      setTweets((prev) => [newTweet, ...prev]);
      toast.success("Traffic alert posted! Pinned to live map.");
      setIsReportOpen(false);
      setReportText("");
      setReportRoutes("");
      setReportLocation("");
      onSelectTweet(newTweet);
    } catch {
      toast.error("Could not post traffic alert");
    } finally {
      setSubmitting(false);
    }
  };

  const getCategoryBadgeClass = (category: string) => {
    switch (category.toLowerCase()) {
      case "breakdown":
        return "bg-rose-500/15 text-rose-600 dark:text-rose-400 border-rose-500/30";
      case "congestion":
        return "bg-amber-500/15 text-amber-600 dark:text-amber-400 border-amber-500/30";
      case "diversion":
        return "bg-blue-500/15 text-blue-600 dark:text-blue-400 border-blue-500/30";
      case "waterlogging":
        return "bg-cyan-500/15 text-cyan-600 dark:text-cyan-400 border-cyan-500/30";
      case "accident":
        return "bg-red-500/15 text-red-600 dark:text-red-400 border-red-500/30";
      default:
        return "bg-muted text-muted-foreground border-border";
    }
  };

  return (
    <div className={cn("flex h-full flex-col bg-card border-border", className)}>
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border p-3.5">
        <div className="flex items-center gap-2">
          <span className="relative flex size-2.5">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
            <span className="relative inline-flex size-2.5 rounded-full bg-emerald-500" />
          </span>
          <div>
            <h3 className="text-sm font-bold flex items-center gap-1.5 leading-none">
              Live Delhi Traffic Tweets
            </h3>
            <span className="text-[11px] text-muted-foreground">
              Real-time road incidents & bus corridor status
            </span>
          </div>
        </div>

        <div className="flex items-center gap-1.5">
          <Button
            variant="ghost"
            size="icon"
            onClick={loadTweets}
            disabled={loading}
            className="size-7 rounded-full text-muted-foreground hover:text-foreground"
            title="Refresh tweets"
          >
            <RefreshCw className={cn("size-3.5", loading && "animate-spin")} />
          </Button>

          <Dialog open={isReportOpen} onOpenChange={setIsReportOpen}>
            <DialogTrigger asChild>
              <Button size="sm" variant="default" className="h-7 text-xs gap-1 px-2.5 font-medium">
                <PlusCircle className="size-3.5" /> Report
              </Button>
            </DialogTrigger>
            <DialogContent className="sm:max-w-[460px]">
              <DialogHeader>
                <DialogTitle className="flex items-center gap-2 text-base">
                  <AlertTriangle className="size-4 text-amber-500" /> Report Delhi Bus / Traffic Incident
                </DialogTitle>
              </DialogHeader>
              <form onSubmit={handleCreateReport} className="space-y-3.5 pt-2">
                <div>
                  <label className="block text-xs font-semibold mb-1 text-foreground">Incident Description</label>
                  <Textarea
                    placeholder="e.g. Bus breakdown on Ring Road near AIIMS causing 15 min delay; route 419 diverted."
                    value={reportText}
                    onChange={(e) => setReportText(e.target.value)}
                    className="text-xs resize-none h-20"
                    required
                  />
                </div>

                <div className="grid grid-cols-2 gap-2.5">
                  <div>
                    <label className="block text-xs font-semibold mb-1 text-foreground">Category</label>
                    <Select value={reportCategory} onValueChange={setReportCategory}>
                      <SelectTrigger className="h-8 text-xs">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="congestion">Congestion / Jam</SelectItem>
                        <SelectItem value="breakdown">Bus Breakdown</SelectItem>
                        <SelectItem value="diversion">Route Diversion</SelectItem>
                        <SelectItem value="waterlogging">Waterlogging</SelectItem>
                        <SelectItem value="accident">Accident / Collision</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold mb-1 text-foreground">Severity</label>
                    <Select value={reportSeverity} onValueChange={setReportSeverity}>
                      <SelectTrigger className="h-8 text-xs">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="high">High (Major delay)</SelectItem>
                        <SelectItem value="medium">Medium (Slow moving)</SelectItem>
                        <SelectItem value="low">Low (Minor hindrance)</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-2.5">
                  <div>
                    <label className="block text-xs font-semibold mb-1 text-foreground">Nearest Stop / Area</label>
                    <Input
                      placeholder="e.g. AIIMS or Ashram"
                      value={reportLocation}
                      onChange={(e) => setReportLocation(e.target.value)}
                      className="h-8 text-xs"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold mb-1 text-foreground">Affected Routes</label>
                    <Input
                      placeholder="e.g. 419, 729, 534"
                      value={reportRoutes}
                      onChange={(e) => setReportRoutes(e.target.value)}
                      className="h-8 text-xs"
                    />
                  </div>
                </div>

                <div className="flex justify-end gap-2 pt-2">
                  <Button type="button" variant="outline" size="sm" onClick={() => setIsReportOpen(false)}>
                    Cancel
                  </Button>
                  <Button type="submit" size="sm" disabled={submitting}>
                    {submitting ? "Posting…" : "Post to Live Map"}
                  </Button>
                </div>
              </form>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {/* Category filters */}
      <div className="scrollbar-thin flex gap-1.5 overflow-x-auto border-b border-border/70 px-3 py-2 bg-muted/30">
        {CATEGORIES.map((cat) => (
          <button
            key={cat.id}
            type="button"
            onClick={() => setActiveCategory(cat.id)}
            className={cn(
              "shrink-0 rounded-full px-2.5 py-1 text-[11px] font-medium transition-colors",
              activeCategory === cat.id
                ? "bg-primary text-primary-foreground font-semibold shadow-xs"
                : "bg-background text-muted-foreground hover:bg-muted hover:text-foreground border border-border/60"
            )}
          >
            {cat.label}
          </button>
        ))}
      </div>

      {/* Tweet feed list */}
      <div className="scrollbar-thin flex-1 overflow-y-auto divide-y divide-border/60 p-1">
        {loading ? (
          <div className="py-12 text-center text-xs text-muted-foreground animate-pulse">
            Fetching verified Delhi traffic tweets…
          </div>
        ) : tweets.length === 0 ? (
          <div className="py-12 text-center text-xs text-muted-foreground">
            No active alerts in this category. Traffic is moving smoothly!
          </div>
        ) : (
          tweets.map((tweet) => {
            const isSelected = selectedTweetId === tweet.id;
            return (
              <article
                key={tweet.id}
                onClick={() => onSelectTweet(tweet)}
                className={cn(
                  "group relative cursor-pointer p-3 transition-colors hover:bg-muted/40",
                  isSelected && "bg-primary/5 ring-1 ring-primary/40 rounded-lg"
                )}
              >
                {/* Author Info */}
                <div className="flex items-start justify-between gap-2 mb-1.5">
                  <div className="flex items-center gap-2">
                    <img
                      src={tweet.avatar}
                      alt={tweet.user}
                      className="size-7 rounded-full object-cover border border-border"
                      onError={(e) => {
                        (e.currentTarget as HTMLImageElement).src =
                          "https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?w=100";
                      }}
                    />
                    <div className="leading-tight">
                      <div className="flex items-center gap-1">
                        <span className="text-xs font-bold text-foreground group-hover:text-primary transition-colors">
                          {tweet.user}
                        </span>
                        {tweet.verified && (
                          <CheckCircle2 className="size-3 text-sky-500 fill-sky-500/20" />
                        )}
                      </div>
                      <span className="text-[10px] text-muted-foreground">{tweet.handle}</span>
                    </div>
                  </div>
                  <span className="text-[10px] text-muted-foreground tabular-nums shrink-0">
                    {tweet.timestamp}
                  </span>
                </div>

                {/* Tweet text */}
                <p className="text-xs text-foreground/90 leading-relaxed mb-2">
                  {tweet.text}
                </p>

                {/* Affected routes and category tags */}
                <div className="flex flex-wrap items-center gap-1.5 mb-2">
                  <Badge variant="outline" className={cn("text-[10px] py-0 px-1.5 uppercase font-bold", getCategoryBadgeClass(tweet.category))}>
                    {tweet.category}
                  </Badge>

                  {tweet.affected_routes && tweet.affected_routes.length > 0 && (
                    <div className="flex items-center gap-1">
                      <span className="text-[10px] text-muted-foreground font-medium">Buses:</span>
                      {tweet.affected_routes.map((rt) => (
                        <span
                          key={rt}
                          className="inline-block rounded bg-primary/10 text-primary font-mono font-bold text-[10px] px-1.5 py-0.2"
                        >
                          {rt}
                        </span>
                      ))}
                    </div>
                  )}
                </div>

                {/* Location pin footer */}
                <div className="flex items-center justify-between text-[11px] text-muted-foreground pt-1 border-t border-border/40">
                  <div className="flex items-center gap-1 font-medium text-foreground/75 truncate">
                    <MapPin className="size-3 text-rose-500 shrink-0" />
                    <span className="truncate">{tweet.location_name}</span>
                  </div>
                  <span className="text-[10px] text-primary font-semibold group-hover:underline flex items-center gap-0.5 shrink-0">
                    Pin on map →
                  </span>
                </div>
              </article>
            );
          })
        )}
      </div>
    </div>
  );
}
