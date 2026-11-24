import { useState, useEffect } from "react";
import { Bus, Check, Crosshair, Loader2, MapPin, Navigation, Star, X } from "lucide-react";

import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from "@/components/ui/command";
import { STOPS } from "@/lib/transit/data";
import { placeFromStop, type Place } from "@/lib/transit/model";
import { fetchAutocompleteStops } from "@/lib/api";
import { cn } from "@/lib/utils";

const COORD_RE = /^\s*(-?\d{1,2}(?:\.\d+)?)\s*[, ]\s*(-?\d{1,3}(?:\.\d+)?)\s*$/;

interface Props {
  label: string;
  marker?: "A" | "B" | string;
  target?: string;
  value: Place | null;
  onChange?: (p: Place) => void;
  onSelect?: (p: Place) => void;
  onClear?: () => void;
  onPickOnMap: () => void;
  picking: boolean;
}

export function PlaceInput({
  label,
  marker,
  target,
  value,
  onChange,
  onSelect,
  onClear,
  onPickOnMap,
  picking,
}: Props) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [remotePlaces, setRemotePlaces] = useState<Place[]>([]);
  const [loadingRemote, setLoadingRemote] = useState(false);

  const displayMarker = marker ?? (target === "origin" ? "A" : "B");
  const coord = query.match(COORD_RE);
  const popular = STOPS.filter((s) => s.popular);

  // Query live backend autocomplete API when user types
  useEffect(() => {
    const trimmed = query.trim();
    if (trimmed.length < 2) {
      setRemotePlaces([]);
      setLoadingRemote(false);
      return;
    }

    let active = true;
    setLoadingRemote(true);

    const timer = setTimeout(() => {
      fetchAutocompleteStops(trimmed)
        .then((stops) => {
          if (!active) return;
          const mapped: Place[] = stops.map((s) => ({
            lat: s.lat,
            lng: s.lon,
            label: s.name,
          }));
          setRemotePlaces(mapped);
        })
        .catch(() => {})
        .finally(() => {
          if (active) setLoadingRemote(false);
        });
    }, 150);

    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [query]);

  const choose = (p: Place) => {
    if (onChange) onChange(p);
    if (onSelect) onSelect(p);
    setOpen(false);
    setQuery("");
  };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          className={cn(
            "group flex w-full items-center gap-3 rounded-lg border border-input bg-card px-3 py-2.5 text-left transition-colors hover:border-foreground/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring cursor-pointer",
            picking && "border-amber-500 ring-2 ring-amber-500/50",
          )}
        >
          <span
            className={cn(
              "grid size-6 shrink-0 place-items-center rounded-full font-display text-xs font-bold",
              displayMarker === "A" ? "bg-foreground text-background" : "bg-amber-400 text-black",
            )}
          >
            {displayMarker}
          </span>
          <span className="min-w-0 flex-1">
            <span className="block text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
              {label}
            </span>
            <span className={cn("block truncate text-sm font-semibold", !value && "text-muted-foreground font-normal")}>
              {picking ? "Click a point on the map…" : (value?.label ?? "Choose a stop or landmark")}
            </span>
          </span>
          {value && onClear && (
            <span
              onClick={(e) => {
                e.stopPropagation();
                onClear();
              }}
              className="p-1 text-muted-foreground hover:text-foreground rounded-full hover:bg-secondary cursor-pointer"
              title="Clear selection"
            >
              <X className="size-3.5" />
            </span>
          )}
        </button>
      </PopoverTrigger>
      <PopoverContent className="w-[--radix-popover-trigger-width] min-w-[320px] p-0 shadow-hard-lg border-2 border-black rounded-xl bg-white z-[700]" align="start">
        <Command shouldFilter={remotePlaces.length === 0}>
          <div className="relative">
            <CommandInput
              placeholder="Search stops (e.g. AIIMS, Kashmere Gate)..."
              value={query}
              onValueChange={setQuery}
              className="h-10 text-sm"
            />
            {loadingRemote && (
              <Loader2 className="size-4 animate-spin absolute right-3 top-3 text-neutral-400 pointer-events-none" />
            )}
          </div>
          <CommandList className="scrollbar-thin max-h-72 p-1">
            <CommandEmpty>No stop found. Try coordinates like 28.61, 77.21.</CommandEmpty>

            {coord && (
              <CommandGroup heading="Custom location">
                <CommandItem
                  value={`coords ${query}`}
                  onSelect={() => {
                    const lat = Number(coord[1]);
                    const lng = Number(coord[2]);
                    choose({ lat, lng, label: `Pinned ${lat.toFixed(4)}, ${lng.toFixed(4)}` });
                  }}
                  onPointerDown={(e) => {
                    e.preventDefault();
                    const lat = Number(coord[1]);
                    const lng = Number(coord[2]);
                    choose({ lat, lng, label: `Pinned ${lat.toFixed(4)}, ${lng.toFixed(4)}` });
                  }}
                  className="cursor-pointer"
                >
                  <Navigation className="size-4 text-primary mr-2" />
                  <span>Use {Number(coord[1]).toFixed(4)}, {Number(coord[2]).toFixed(4)}</span>
                </CommandItem>
              </CommandGroup>
            )}

            <CommandGroup>
              <CommandItem
                value="pick on map choose point"
                onSelect={() => {
                  setOpen(false);
                  onPickOnMap();
                }}
                onPointerDown={(e) => {
                  e.preventDefault();
                  setOpen(false);
                  onPickOnMap();
                }}
                className="cursor-pointer text-amber-700 font-medium"
              >
                <Crosshair className="size-4 text-amber-600 mr-2" />
                <span>Pick a point on the map</span>
              </CommandItem>
            </CommandGroup>

            <CommandSeparator />

            {/* Remote Backend Autocomplete Results */}
            {remotePlaces.length > 0 && (
              <CommandGroup heading="Delhi Transit Stops (Live Search)">
                {remotePlaces.map((p, idx) => (
                  <CommandItem
                    key={`remote-${p.label}-${idx}`}
                    value={`${p.label} ${p.lat} ${p.lng}`}
                    onSelect={() => choose(p)}
                    onPointerDown={(e) => {
                      e.preventDefault();
                      choose(p);
                    }}
                    onClick={() => choose(p)}
                    className="cursor-pointer flex items-center justify-between py-2 px-2.5 rounded-lg hover:bg-neutral-100 aria-selected:bg-amber-100"
                  >
                    <div className="flex items-center gap-2">
                      <Bus className="size-4 text-emerald-600 shrink-0" />
                      <span className="font-medium text-neutral-900">{p.label}</span>
                    </div>
                    <span className="text-[10px] font-mono text-neutral-400">
                      {p.lat.toFixed(3)}, {p.lng.toFixed(3)}
                    </span>
                  </CommandItem>
                ))}
              </CommandGroup>
            )}

            {/* Popular Delhi Stops */}
            <CommandGroup heading="Popular Delhi Hubs">
              {popular.map((s) => {
                const isSelected = value?.label?.toLowerCase().includes(s.name.toLowerCase());
                return (
                  <CommandItem
                    key={`p-${s.id}`}
                    value={`popular ${s.name} ${s.area}`}
                    onSelect={() => choose(placeFromStop(s.id))}
                    onPointerDown={(e) => {
                      e.preventDefault();
                      choose(placeFromStop(s.id));
                    }}
                    onClick={() => choose(placeFromStop(s.id))}
                    className="cursor-pointer flex items-center justify-between py-2 px-2.5 rounded-lg hover:bg-neutral-100 aria-selected:bg-amber-100"
                  >
                    <div className="flex items-center gap-2">
                      <Star className="size-3.5 fill-amber-400 text-amber-400 shrink-0" />
                      <span className="font-medium text-neutral-900">{s.name}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-muted-foreground">{s.area}</span>
                      {isSelected && <Check className="size-3.5 text-emerald-600" />}
                    </div>
                  </CommandItem>
                );
              })}
            </CommandGroup>

            {/* All Remaining Delhi Stops */}
            <CommandGroup heading="All Delhi Bus Stops">
              {STOPS.filter((s) => !s.popular).map((s) => {
                const isSelected = value?.label?.toLowerCase().includes(s.name.toLowerCase());
                return (
                  <CommandItem
                    key={s.id}
                    value={`${s.name} ${s.area}`}
                    onSelect={() => choose(placeFromStop(s.id))}
                    onPointerDown={(e) => {
                      e.preventDefault();
                      choose(placeFromStop(s.id));
                    }}
                    onClick={() => choose(placeFromStop(s.id))}
                    className="cursor-pointer flex items-center justify-between py-2 px-2.5 rounded-lg hover:bg-neutral-100 aria-selected:bg-amber-100"
                  >
                    <div className="flex items-center gap-2">
                      <MapPin className="size-3.5 text-neutral-400 shrink-0" />
                      <span className="font-medium text-neutral-900">{s.name}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-muted-foreground">{s.area}</span>
                      {isSelected && <Check className="size-3.5 text-emerald-600" />}
                    </div>
                  </CommandItem>
                );
              })}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
