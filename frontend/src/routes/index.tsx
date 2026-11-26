import { ClientOnly, createFileRoute } from "@tanstack/react-router";
import { Suspense, lazy, useEffect, useMemo, useState } from "react";
import {
  AlertCircle,
  ArrowLeft,
  ArrowUpDown,
  Bus,
  BusFront,
  ChevronDown,
  Crosshair,
  MessageSquare,
  Radio,
  Route as RouteIcon,
  Sparkles,
  X,
} from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { PlaceInput } from "@/components/transit/PlaceInput";
import { TimeControls } from "@/components/transit/TimeControls";
import { JourneyCard } from "@/components/transit/JourneyCard";
import { Legend, NetworkStatus } from "@/components/transit/MapOverlay";
import { LiveTweetsFeed } from "@/components/transit/LiveTweetsFeed";
import { ChatbotDrawer } from "@/components/transit/ChatbotDrawer";
import { ShowcaseLanding } from "@/components/showcase/ShowcaseLanding";
import type { PickTarget } from "@/components/transit/map-types";
import { PRESETS, STOP_BY_ID, type Day, type StopId } from "@/lib/transit/data";
import { placeFromStop, planJourneys, type Journey, type LatLng, type Place } from "@/lib/transit/model";
import { departAtIso, mapBackendJourneys } from "@/lib/transit/backendJourneys";
import { fetchBackendJourneys, fetchLiveTweets, type TweetData } from "@/lib/api";
import { cn } from "@/lib/utils";

const TransitMap = lazy(() => import("@/components/transit/TransitMap"));

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Commuttify — Delhi Bus Traffic Model & Journey Planner" },
      {
        name: "description",
        content: "Real-time Delhi bus traffic model, journey planner, and live geolocated commuter tweets.",
      },
      { property: "og:title", content: "Commuttify — Delhi Bus Traffic Model & Live Tweets" },
      {
        property: "og:description",
        content: "Compare live-traffic bus journey times across Delhi and monitor real-time road incident tweets.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Index,
});

const DEFAULT = PRESETS[0]!;

function MapFallback() {
  return (
    <div className="grid h-full w-full place-items-center bg-muted text-sm text-muted-foreground">
      <span className="flex items-center gap-2">
        <BusFront className="size-4 animate-pulse" /> Loading Delhi bus traffic map…
      </span>
    </div>
  );
}

function Index() {
  const [viewMode, setViewMode] = useState<"showcase" | "map">("showcase");
  const [activeTab, setActiveTab] = useState<"planner" | "tweets">("planner");
  const [sheetOpen, setSheetOpen] = useState(false);
  const [origin, setOrigin] = useState<Place | null>(() => placeFromStop(DEFAULT.origin));
  const [destination, setDestination] = useState<Place | null>(() => placeFromStop(DEFAULT.destination));
  const [day, setDay] = useState<Day>(DEFAULT.day);
  const [minutes, setMinutes] = useState(DEFAULT.minutes);
  const [activePreset, setActivePreset] = useState<string | null>(DEFAULT.id);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [showTraffic, setShowTraffic] = useState(true);
  const [showFleet, setShowFleet] = useState(true);
  const [showTweets, setShowTweets] = useState(true);
  const [tweets, setTweets] = useState<TweetData[]>([]);
  const [focusedTweet, setFocusedTweet] = useState<TweetData | null>(null);
  const [pickMode, setPickMode] = useState<PickTarget | null>(null);
  const [backendLive, setBackendLive] = useState(false);

  useEffect(() => {
    fetchLiveTweets()
      .then((data) => setTweets(data))
      .catch(() => {});
  }, []);

  // Real backend (PostGIS routing) drives the planner; the bundled local
  // model is the offline fallback when the API is unreachable.
  const [remoteJourneys, setRemoteJourneys] = useState<Journey[] | null>(null);

  useEffect(() => {
    if (!origin || !destination) {
      setRemoteJourneys(null);
      setBackendLive(false);
      return;
    }
    let active = true;
    fetchBackendJourneys(
      origin.lat,
      origin.lng,
      destination.lat,
      destination.lng,
      departAtIso(day, minutes),
    )
      .then((data) => {
        if (!active) return;
        if (!data || !Array.isArray(data.options)) {
          setBackendLive(false);
          setRemoteJourneys(null);
          return;
        }
        setBackendLive(true);
        setRemoteJourneys(mapBackendJourneys(data, minutes));
      })
      .catch(() => {
        if (!active) return;
        setBackendLive(false);
        setRemoteJourneys(null);
      });
    return () => {
      active = false;
    };
  }, [origin, destination, day, minutes]);

  const localJourneys = useMemo(
    () => (origin && destination ? planJourneys(origin, destination, day, minutes) : []),
    [origin, destination, day, minutes],
  );
  const journeys = remoteJourneys ?? localJourneys;

  const selected = journeys.find((j) => j.id === selectedId) ?? journeys[0] ?? null;
  const fastestId = journeys.reduce<string | null>(
    (best, j) => (best === null || j.totalMin < journeys.find((x) => x.id === best)!.totalMin ? j.id : best),
    null,
  );

  const applyPreset = (id: string) => {
    const p = PRESETS.find((x) => x.id === id)!;
    setOrigin(placeFromStop(p.origin));
    setDestination(placeFromStop(p.destination));
    setDay(p.day);
    setMinutes(p.minutes);
    setActivePreset(p.id);
    setSelectedId(null);
    setPickMode(null);
    setActiveTab("planner");
  };

  const clearPreset = () => setActivePreset(null);

  const setPlace = (target: PickTarget, p: Place) => {
    if (target === "origin") setOrigin(p);
    else setDestination(p);
    setSelectedId(null);
    clearPreset();
  };

  const onPickPoint = (ll: LatLng) => {
    if (!pickMode) return;
    setPlace(pickMode, { ...ll, label: `Pinned ${ll.lat.toFixed(4)}, ${ll.lng.toFixed(4)}` });
    toast.success(`${pickMode === "origin" ? "Start" : "Destination"} pinned on the map`);
    setPickMode(null);
  };

  const onPickStop = (id: StopId) => {
    if (!pickMode) return;
    setPlace(pickMode, placeFromStop(id));
    toast.success(`${pickMode === "origin" ? "Start" : "Destination"} set to ${STOP_BY_ID[id]!.name}`);
    setPickMode(null);
  };

  const swap = () => {
    const prevO = origin;
    setOrigin(destination);
    setDestination(prevO);
    setSelectedId(null);
    clearPreset();
  };

  const handleSelectTweet = (tweet: TweetData) => {
    setFocusedTweet(tweet);
    toast.info(`Focusing alert: ${tweet.location_name}`);
  };

  const handleLaunchPlanner = (presetOrig?: string, presetDest?: string) => {
    if (presetOrig && presetDest) {
      const match = PRESETS.find((p) => p.id.includes(presetOrig) || p.origin.includes(presetOrig));
      if (match) applyPreset(match.id);
    }
    setViewMode("map");
  };

  // If in Showcase Landing view mode, render ShowcaseLanding
  if (viewMode === "showcase") {
    return (
      <>
        <ShowcaseLanding
          onLaunchPlanner={handleLaunchPlanner}
          onOpenAlerts={() => {
            setActiveTab("tweets");
            setViewMode("map");
          }}
          activeAlertsCount={tweets.length}
        />
        <ChatbotDrawer />
      </>
    );
  }

  // Interactive Map & Journey Planner View Mode
  return (
    <div className="flex h-[100dvh] w-full flex-col overflow-hidden bg-background">
      {/* Top Bar with Showcase Return */}
      <header className="h-14 bg-[#121214] text-white px-4 sm:px-6 flex items-center justify-between gap-2 sm:gap-3 border-b border-neutral-800 z-50 shrink-0">
        <button
          type="button"
          onClick={() => setViewMode("showcase")}
          className="flex shrink-0 items-center gap-2 text-xs font-medium text-neutral-300 hover:text-white transition-colors bg-neutral-800 hover:bg-neutral-700 px-3 py-1.5 rounded-full cursor-pointer"
        >
          <ArrowLeft className="size-3.5" />
          <span className="hidden sm:inline">Back to Showcase</span>
        </button>

        <div className="flex min-w-0 items-center gap-2">
          <div className="size-7 shrink-0 rounded-lg bg-black text-amber-400 flex items-center justify-center font-bold text-xs border border-neutral-700">
            <Bus className="size-4" />
          </div>
          <span className="truncate font-display font-black text-base tracking-tight text-white">Commuttify</span>
          <span className="hidden sm:inline-block px-1.5 py-0.5 rounded bg-neutral-800 text-[10px] font-mono text-neutral-400">
            DELHI BUSWAY
          </span>
        </div>

        <div className="flex shrink-0 items-center gap-2">
          <Button
            size="sm"
            variant="outline"
            onClick={() => setActiveTab(activeTab === "planner" ? "tweets" : "planner")}
            className="h-8 text-xs rounded-full border-neutral-700 text-neutral-200 hover:text-white hover:bg-neutral-800 cursor-pointer"
          >
            {activeTab === "planner" ? (
              <>
                <span className="sm:hidden">Tweets ({tweets.length})</span>
                <span className="hidden sm:inline">View Tweets ({tweets.length})</span>
              </>
            ) : (
              <>
                <span className="sm:hidden">Planner</span>
                <span className="hidden sm:inline">Journey Planner</span>
              </>
            )}
          </Button>
        </div>
      </header>

      {/* Main Workspace: Left Controls / Tweets Feed & Right Map */}
      <main className="relative flex flex-1 flex-col overflow-hidden lg:flex-row">
        {/* Planner pane — bottom sheet on mobile, left sidebar on desktop */}
        <aside
          className={cn(
            "scrollbar-thin flex w-full flex-col border-t border-border bg-card shadow-float overflow-hidden",
            // mobile: Google-Maps-style bottom sheet over the map
            "absolute inset-x-0 bottom-0 z-[600] rounded-t-2xl transition-[max-height] duration-300 ease-out",
            sheetOpen ? "max-h-[65dvh] overflow-y-auto" : "max-h-[7rem]",
            // desktop: original left sidebar
            "lg:static lg:z-10 lg:h-full lg:w-[440px] lg:shrink-0 lg:max-h-none lg:overflow-y-auto lg:rounded-none lg:border-t-0 lg:border-r lg:border-b-0 lg:transition-none",
          )}
          aria-label="Journey planning and live feeds"
        >
          {/* mobile grab handle */}
          <button
            type="button"
            onClick={() => setSheetOpen((v) => !v)}
            aria-expanded={sheetOpen}
            className="sticky top-0 z-10 flex w-full cursor-pointer flex-col items-center gap-1.5 rounded-t-2xl bg-card px-4 pt-2.5 pb-1 lg:hidden"
          >
            <span className="h-1 w-10 rounded-full bg-border" />
            <span className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
              {sheetOpen
                ? "Hide panel"
                : activeTab === "planner"
                  ? "Plan a journey"
                  : "Live tweets & alerts"}
              <ChevronDown className={cn("size-3.5 transition-transform", sheetOpen && "rotate-180")} />
            </span>
          </button>
          {/* Segmented Mode Switcher */}
          <div className="p-3 border-b border-border bg-secondary/30">
            <div className="grid grid-cols-2 p-1 bg-secondary rounded-xl text-xs font-medium">
              <button
                type="button"
                onClick={() => setActiveTab("planner")}
                className={cn(
                  "py-2 px-3 rounded-lg transition-all font-semibold flex items-center justify-center gap-2 cursor-pointer",
                  activeTab === "planner"
                    ? "bg-card text-foreground shadow-xs"
                    : "text-muted-foreground hover:text-foreground",
                )}
              >
                <RouteIcon className="size-4 text-primary" />
                <span>Journey Planner</span>
              </button>
              <button
                type="button"
                onClick={() => setActiveTab("tweets")}
                className={cn(
                  "py-2 px-3 rounded-lg transition-all font-semibold flex items-center justify-center gap-2 cursor-pointer relative",
                  activeTab === "tweets"
                    ? "bg-card text-foreground shadow-xs"
                    : "text-muted-foreground hover:text-foreground",
                )}
              >
                <Radio className="size-4 text-rose-500 animate-pulse" />
                <span>Live Tweets & Alerts</span>
                {tweets.length > 0 && (
                  <span className="px-1.5 py-0.2 rounded-full bg-rose-500/10 text-rose-600 text-[10px] font-mono font-bold">
                    {tweets.length}
                  </span>
                )}
              </button>
            </div>
          </div>

          {/* TAB 1: Journey Planner Content */}
          {activeTab === "planner" && (
            <div className="flex-1 flex flex-col">
              <section className="space-y-4 p-4 border-b border-border/60" aria-label="Route Presets">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-mono font-medium uppercase tracking-wider text-muted-foreground">
                    Common Delhi Corridors
                  </span>
                  {origin && destination ? (
                    <button
                      type="button"
                      onClick={() => {
                        setOrigin(null);
                        setDestination(null);
                        setActivePreset(null);
                        setSelectedId(null);
                      }}
                      className="text-[11px] font-mono text-blue-600 hover:underline cursor-pointer flex items-center gap-1 font-semibold"
                    >
                      <X className="size-3" /> Clear · Show All Lines
                    </button>
                  ) : (
                    <span className="text-[11px] font-mono text-muted-foreground">All Lines Visible</span>
                  )}
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {PRESETS.map((p) => {
                    const active = activePreset === p.id;
                    return (
                      <button
                        key={p.id}
                        type="button"
                        onClick={() => applyPreset(p.id)}
                        className={cn(
                          "cursor-pointer rounded-full border px-2.5 py-1 text-xs transition-colors",
                          active
                            ? "border-primary bg-primary text-primary-foreground font-semibold"
                            : "border-border bg-secondary/60 text-foreground hover:bg-secondary",
                        )}
                      >
                        {p.label}
                      </button>
                    );
                  })}
                </div>
              </section>

              <section className="relative space-y-3 p-4" aria-label="Trip planning inputs">
                <div className="relative space-y-2 pr-10">
                  <PlaceInput
                    label="Origin / Start Stop"
                    target="origin"
                    value={origin}
                    onSelect={(p) => setPlace("origin", p)}
                    onClear={() => {
                      setOrigin(null);
                      clearPreset();
                    }}
                    onPickOnMap={() => setPickMode(pickMode === "origin" ? null : "origin")}
                    picking={pickMode === "origin"}
                  />

                  <PlaceInput
                    label="Destination / End Stop"
                    target="destination"
                    value={destination}
                    onSelect={(p) => setPlace("destination", p)}
                    onClear={() => {
                      setDestination(null);
                      clearPreset();
                    }}
                    onPickOnMap={() => setPickMode(pickMode === "destination" ? null : "destination")}
                    picking={pickMode === "destination"}
                  />

                  <Button
                    type="button"
                    variant="mapControl"
                    size="icon"
                    onClick={swap}
                    aria-label="Swap start and destination"
                    className="absolute top-1/2 right-3 size-8 -translate-y-1/2 rounded-full shadow-xs cursor-pointer"
                  >
                    <ArrowUpDown className="size-4" />
                  </Button>
                </div>

                <TimeControls
                  day={day}
                  minutes={minutes}
                  onDay={(d) => {
                    setDay(d);
                    clearPreset();
                  }}
                  onMinutes={(m) => {
                    setMinutes(m);
                    clearPreset();
                  }}
                />
              </section>

              <section className="space-y-3 px-4 pb-6 flex-1" aria-live="polite">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <h2 className="flex items-center gap-1.5 text-base font-bold">
                      <RouteIcon className="size-4 text-primary" /> Journey options
                    </h2>
                    {backendLive && (
                      <span className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-600 text-[10px] font-mono font-medium border border-emerald-500/20">
                        <span className="size-1.5 rounded-full bg-emerald-500 animate-pulse" />
                        Backend Live ⚡
                      </span>
                    )}
                  </div>
                  <span className="text-xs text-muted-foreground">{journeys.length} found</span>
                </div>
                {journeys.length === 0 ? (
                  <div className="rounded-xl border border-dashed border-border p-6 text-center text-sm text-muted-foreground">
                    {origin && destination
                      ? "No bus connection found nearby. Try a stop closer to a main road."
                      : "Choose a start and destination to see options."}
                  </div>
                ) : (
                  journeys.map((j, i) => (
                    <JourneyCard
                      key={j.id}
                      journey={j}
                      index={i}
                      selected={selected?.id === j.id}
                      fastest={j.id === fastestId && journeys.length > 1}
                      onSelect={() => setSelectedId(j.id)}
                    />
                  ))
                )}
              </section>
            </div>
          )}

          {/* TAB 2: Live Tweets Feed */}
          {activeTab === "tweets" && (
            <div className="flex-1 flex flex-col h-full">
              <LiveTweetsFeed
                selectedTweetId={focusedTweet?.id ?? null}
                onSelectTweet={handleSelectTweet}
                className="flex-1"
              />
            </div>
          )}
        </aside>

        {/* Right Pane: Interactive Map */}
        <section className="relative min-h-0 flex-1 lg:h-auto" aria-label="Delhi bus traffic map">
          <ClientOnly fallback={<MapFallback />}>
            <Suspense fallback={<MapFallback />}>
              <TransitMap
                day={day}
                minutes={minutes}
                origin={origin}
                destination={destination}
                journeys={journeys}
                selectedId={selected?.id ?? null}
                showTraffic={showTraffic}
                showFleet={showFleet}
                showTweets={showTweets}
                tweets={tweets}
                focusedTweet={focusedTweet}
                onSelectTweet={handleSelectTweet}
                pickMode={pickMode}
                onPickPoint={onPickPoint}
                onPickStop={onPickStop}
                onSelectJourney={setSelectedId}
              />
            </Suspense>
          </ClientOnly>

          {/* Map Overlay Controls */}
          <div className="pointer-events-none absolute inset-0 z-[500] p-3 pb-32 lg:pb-3">
            <div className="flex h-full flex-col justify-between gap-3">
              <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                <div className="pointer-events-auto">
                  <NetworkStatus
                    day={day}
                    minutes={minutes}
                    showTraffic={showTraffic}
                    showFleet={showFleet}
                    showTweets={showTweets}
                    tweetCount={tweets.length}
                    hasRoute={Boolean(origin && destination)}
                    onClearRoute={() => {
                      setOrigin(null);
                      setDestination(null);
                      setActivePreset(null);
                      setSelectedId(null);
                    }}
                    onTraffic={setShowTraffic}
                    onFleet={setShowFleet}
                    onTweets={setShowTweets}
                    onToggleTweetsPanel={() => setActiveTab("tweets")}
                  />
                </div>
                {pickMode && (
                  <div className="pointer-events-auto fade-swap flex items-center gap-2 rounded-full bg-header px-3 py-2 text-xs text-header-foreground shadow-float">
                    <Crosshair className="size-4 text-accent" />
                    Click the map or a stop to set your {pickMode === "origin" ? "start" : "destination"}
                    <button
                      type="button"
                      onClick={() => setPickMode(null)}
                      aria-label="Cancel picking"
                      className="rounded-full p-0.5 hover:bg-header-chip"
                    >
                      <X className="size-3.5" />
                    </button>
                  </div>
                )}
              </div>

              <div className="flex flex-col items-start gap-2 pr-12 sm:flex-row sm:items-end sm:justify-between">
                <div className="pointer-events-auto hidden sm:block">
                  <Legend showFleet={showFleet} />
                </div>
              </div>
            </div>
          </div>
        </section>
      </main>

      {/* Floating AI Bus Assistant */}
      <ChatbotDrawer />
    </div>
  );
}
