import { STOPS, type Stop } from "./transit/data";
import { planJourneys, type Day, type Journey, type Place } from "./transit/model";

export const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8005";

export interface TweetData {
  id: string;
  user: string;
  handle: string;
  avatar: string;
  verified: boolean;
  timestamp: string;
  text: string;
  category: "congestion" | "breakdown" | "diversion" | "waterlogging" | "accident";
  severity: "high" | "medium" | "low";
  location_name: string;
  lat: number;
  lng: number;
  affected_routes: string[];
  likes: number;
  retweets: number;
}

export const FALLBACK_TWEETS: TweetData[] = [
  {
    id: "tw-101",
    user: "Delhi Traffic Police",
    handle: "@dtptraffic",
    avatar: "https://images.unsplash.com/photo-1544620347-c4fd4a3d5957?w=100&auto=format&fit=crop&q=60",
    verified: true,
    timestamp: "4 min ago",
    text: "Traffic Alert: Ring Road corridor from Moolchand toward AIIMS is heavily congested due to a broken-down DTC electric bus near Andrews Ganj flyover. Recovery van deployed.",
    category: "breakdown",
    severity: "high",
    location_name: "AIIMS - Moolchand Ring Road",
    lat: 28.5672,
    lng: 77.222,
    affected_routes: ["419", "729", "MS", "505"],
    likes: 84,
    retweets: 32,
  },
  {
    id: "tw-102",
    user: "Delhi Traffic Police",
    handle: "@dtptraffic",
    avatar: "https://images.unsplash.com/photo-1544620347-c4fd4a3d5957?w=100&auto=format&fit=crop&q=60",
    verified: true,
    timestamp: "12 min ago",
    text: "Traffic Advisory: Slow moving traffic at Kashmere Gate ISBT intersection due to heavy inter-state and DTC cluster bus volume. Commuters heading to Old Delhi please allow extra 15 mins.",
    category: "congestion",
    severity: "medium",
    location_name: "Kashmere Gate ISBT",
    lat: 28.6675,
    lng: 77.228,
    affected_routes: ["534", "419", "990"],
    likes: 56,
    retweets: 19,
  },
  {
    id: "tw-103",
    user: "Delhi Commuters Forum",
    handle: "@DelhiCommuters",
    avatar: "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=100&auto=format&fit=crop&q=60",
    verified: false,
    timestamp: "18 min ago",
    text: "Ashram Underpass and Chowk completely blocked towards Sarai Kale Khan. Bus route 534 and 85 held up for over 25 minutes. Take Barapullah if possible!",
    category: "congestion",
    severity: "high",
    location_name: "Ashram Chowk",
    lat: 28.5713,
    lng: 77.2589,
    affected_routes: ["534", "85", "MS"],
    likes: 112,
    retweets: 47,
  },
  {
    id: "tw-104",
    user: "DTC Updates",
    handle: "@dtc_delhi",
    avatar: "https://images.unsplash.com/photo-1570125909232-eb263c188f7e?w=100&auto=format&fit=crop&q=60",
    verified: true,
    timestamp: "25 min ago",
    text: "Diversion Alert: Water pipeline maintenance work near ITO Vikas Marg junction. Buses on routes 522 and 534 temporarily diverted via Bahadur Shah Zafar Marg.",
    category: "diversion",
    severity: "medium",
    location_name: "ITO Junction",
    lat: 28.6289,
    lng: 77.2405,
    affected_routes: ["522", "534"],
    likes: 42,
    retweets: 15,
  },
  {
    id: "tw-105",
    user: "Rohan Malhotra",
    handle: "@rohan_delhi",
    avatar: "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=100&auto=format&fit=crop&q=60",
    verified: false,
    timestamp: "34 min ago",
    text: "Waterlogging near Dhaula Kuan underpass causing buses on route 764 to crawl at under 8 km/h. Traffic police on spot clearing the drain.",
    category: "waterlogging",
    severity: "medium",
    location_name: "Dhaula Kuan Underpass",
    lat: 28.5918,
    lng: 77.1617,
    affected_routes: ["764", "990", "MS"],
    likes: 67,
    retweets: 21,
  },
  {
    id: "tw-106",
    user: "Delhi Transit Live",
    handle: "@delhi_transit",
    avatar: "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=100&auto=format&fit=crop&q=60",
    verified: false,
    timestamp: "42 min ago",
    text: "Minor collision between two vehicles near Connaught Place Outer Circle / Regal cinema. One lane blocked, buses experiencing 5-8 min minor delays.",
    category: "accident",
    severity: "low",
    location_name: "Connaught Place (Regal)",
    lat: 28.6292,
    lng: 77.2167,
    affected_routes: ["522", "729", "505"],
    likes: 38,
    retweets: 8,
  },
  {
    id: "tw-107",
    user: "Delhi Traffic Police",
    handle: "@dtptraffic",
    avatar: "https://images.unsplash.com/photo-1544620347-c4fd4a3d5957?w=100&auto=format&fit=crop&q=60",
    verified: true,
    timestamp: "50 min ago",
    text: "Smooth Flow: Peeragarhi towards Janakpuri West stretch on Outer Ring Road is now clear for transit buses. Speed normalized to ~28 km/h.",
    category: "congestion",
    severity: "low",
    location_name: "Janakpuri West / Ring Rd",
    lat: 28.6295,
    lng: 77.078,
    affected_routes: ["778"],
    likes: 95,
    retweets: 14,
  },
  {
    id: "tw-108",
    user: "Pooja Verma",
    handle: "@pooja_v_trans",
    avatar: "https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=100&auto=format&fit=crop&q=60",
    verified: false,
    timestamp: "1 hr ago",
    text: "Anand Vihar ISBT bus bays are packed this evening. Took 20 min just for route 85 to exit terminal. Plan accordingly if commuting to Noida/Ghaziabad.",
    category: "congestion",
    severity: "medium",
    location_name: "Anand Vihar ISBT",
    lat: 28.6469,
    lng: 77.316,
    affected_routes: ["85", "522"],
    likes: 73,
    retweets: 24,
  },
];

export async function fetchAutocompleteStops(q: string): Promise<Array<{ id?: string; name: string; stop_name?: string; area?: string; lat: number; lng?: number; stop_lat?: number; stop_lon?: number }>> {
  if (!q.trim()) return [];
  try {
    const res = await fetch(`${API_BASE}/api/search/autocomplete?q=${encodeURIComponent(q)}`, { signal: AbortSignal.timeout(3000) });
    if (res.ok) {
      const data = await res.json();
      if (Array.isArray(data) && data.length > 0) {
        return data.map((item: any) => ({
          id: item.stop_id || item.id || item.stop_name,
          name: item.stop_name || item.name,
          area: item.area || "Delhi Stop",
          lat: item.stop_lat ?? item.lat ?? 28.6139,
          lng: item.stop_lon ?? item.lng ?? item.lon ?? 77.209,
        }));
      }
    }
  } catch {
    // backend offline or timeout: fall back gracefully
  }

  // Client-side fallback search across STOPS
  const lower = q.toLowerCase();
  return STOPS.filter((s) => s.name.toLowerCase().includes(lower) || s.area.toLowerCase().includes(lower))
    .slice(0, 10)
    .map((s) => ({
      id: s.id,
      name: s.name,
      area: s.area,
      lat: s.lat,
      lng: s.lng,
    }));
}

export async function fetchLiveTweets(category?: string): Promise<TweetData[]> {
  try {
    const url = category && category !== "all" ? `${API_BASE}/api/tweets?category=${encodeURIComponent(category)}` : `${API_BASE}/api/tweets`;
    const res = await fetch(url, { signal: AbortSignal.timeout(3000) });
    if (res.ok) {
      const data = await res.json();
      if (Array.isArray(data) && data.length > 0) {
        return data;
      }
    }
  } catch {
    // fallback
  }

  if (category && category !== "all") {
    return FALLBACK_TWEETS.filter((t) => t.category.toLowerCase() === category.toLowerCase());
  }
  return FALLBACK_TWEETS;
}

export async function submitIncidentTweet(payload: {
  text: string;
  category: string;
  severity: string;
  location_name: string;
  lat: number;
  lng: number;
  affected_routes?: string[];
  user?: string;
  handle?: string;
}): Promise<TweetData> {
  try {
    const res = await fetch(`${API_BASE}/api/tweets`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: AbortSignal.timeout(4000),
    });
    if (res.ok) {
      return await res.json();
    }
  } catch {
    // fallback local addition
  }

  const localItem: TweetData = {
    id: `tw-${Date.now().toString(36)}`,
    user: payload.user || "Delhi Commuter",
    handle: payload.handle || "@commuter_delhi",
    avatar: "https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?w=100&auto=format&fit=crop&q=60",
    verified: false,
    timestamp: "Just now",
    text: payload.text,
    category: (payload.category as any) || "congestion",
    severity: (payload.severity as any) || "medium",
    location_name: payload.location_name,
    lat: payload.lat,
    lng: payload.lng,
    affected_routes: payload.affected_routes || [],
    likes: 1,
    retweets: 0,
  };
  return localItem;
}

export async function sendChatMessage(message: string): Promise<string> {
  try {
    const res = await fetch(`${API_BASE}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
      signal: AbortSignal.timeout(8000),
    });
    if (res.ok) {
      const data = await res.json();
      if (data.reply) return data.reply;
    }
  } catch {
    // fallback
  }

  const msg = message.toLowerCase();
  if (msg.includes("aiims") && msg.includes("kashmere")) {
    return "From Kashmere Gate to AIIMS, direct route 419 is the best option (~28 min in quiet hours, ~37 min in peak traffic). Alternatively take route 534 to Central Secretariat and transfer to 729.";
  }
  if (msg.includes("fare") || msg.includes("ticket") || msg.includes("cost")) {
    return "Standard DTC non-AC bus fares are ₹5, ₹10, and ₹15. DTC AC buses are ₹10, ₹15, ₹20, and ₹25. Women travel free on DTC and cluster buses with Pink Tickets.";
  }
  if (msg.includes("ashram") || msg.includes("ring road") || msg.includes("traffic")) {
    return "Currently Ashram Chowk and the Moolchand-AIIMS Ring Road stretch are experiencing heavy congestion (average bus speeds down to ~11-14 km/h). Expect an extra 10-15 minutes delay.";
  }
  return "I'm your Commuttify Delhi Bus Assistant. You can ask me about bus route numbers, schedules, transfer points, or current road congestion across Delhi's corridors!";
}
