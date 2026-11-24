import type { Day, StopId } from "@/lib/transit/data";
import type { Journey, LatLng, Place } from "@/lib/transit/model";
import type { TweetData } from "@/lib/api";

export type PickTarget = "origin" | "destination";

export interface TransitMapProps {
  day: Day;
  minutes: number;
  origin: Place | null;
  destination: Place | null;
  journeys: Journey[];
  selectedId: string | null;
  showTraffic: boolean;
  showFleet: boolean;
  showTweets?: boolean;
  tweets?: TweetData[];
  focusedTweet?: TweetData | null;
  onSelectTweet?: (tweet: TweetData) => void;
  pickMode: PickTarget | null;
  onPickPoint: (p: LatLng) => void;
  onPickStop: (id: StopId) => void;
  onSelectJourney: (id: string) => void;
}
