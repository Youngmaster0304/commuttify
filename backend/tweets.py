"""Commuttify Live Tweets & Incident Service.

Aggregates, parses, and provides real-time traffic tweets and crowdsourced
commuter reports for Delhi bus routes and arterial corridors.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from .live_crawler import fetch_live_traffic_alerts


class TweetItem(BaseModel):
    id: str
    user: str
    handle: str
    avatar: str
    verified: bool = False
    timestamp: str
    text: str
    category: str
    severity: str
    location_name: str
    lat: float
    lng: float
    affected_routes: List[str] = Field(default_factory=list)
    likes: int = 0
    retweets: int = 0
    is_live_scraped: bool = False


INITIAL_TWEETS: List[Dict[str, Any]] = [
    {
        "id": "tw-101",
        "user": "Delhi Traffic Police",
        "handle": "@dtptraffic",
        "avatar": "https://images.unsplash.com/photo-1544620347-c4fd4a3d5957?w=100&auto=format&fit=crop&q=60",
        "verified": True,
        "timestamp": "4 min ago",
        "text": "Traffic Alert: Ring Road corridor from Moolchand toward AIIMS is heavily congested due to a broken-down DTC electric bus near Andrews Ganj flyover. Recovery van deployed.",
        "category": "breakdown",
        "severity": "high",
        "location_name": "AIIMS - Moolchand Ring Road",
        "lat": 28.5672,
        "lng": 77.2220,
        "affected_routes": ["419", "729", "MS", "505"],
        "likes": 84,
        "retweets": 32,
    },
    {
        "id": "tw-102",
        "user": "Delhi Traffic Police",
        "handle": "@dtptraffic",
        "avatar": "https://images.unsplash.com/photo-1544620347-c4fd4a3d5957?w=100&auto=format&fit=crop&q=60",
        "verified": True,
        "timestamp": "12 min ago",
        "text": "Traffic Advisory: Slow moving traffic at Kashmere Gate ISBT intersection due to heavy inter-state and DTC cluster bus volume. Commuters heading to Old Delhi please allow extra 15 mins.",
        "category": "congestion",
        "severity": "medium",
        "location_name": "Kashmere Gate ISBT",
        "lat": 28.6675,
        "lng": 77.2280,
        "affected_routes": ["534", "419", "990"],
        "likes": 56,
        "retweets": 19,
    },
    {
        "id": "tw-103",
        "user": "Delhi Commuters Forum",
        "handle": "@DelhiCommuters",
        "avatar": "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=100&auto=format&fit=crop&q=60",
        "verified": False,
        "timestamp": "18 min ago",
        "text": "Ashram Underpass and Chowk completely blocked towards Sarai Kale Khan. Bus route 534 and 85 held up for over 25 minutes. Take Barapullah if possible!",
        "category": "congestion",
        "severity": "high",
        "location_name": "Ashram Chowk",
        "lat": 28.5713,
        "lng": 77.2589,
        "affected_routes": ["534", "85", "MS"],
        "likes": 112,
        "retweets": 47,
    },
    {
        "id": "tw-104",
        "user": "DTC Updates",
        "handle": "@dtc_delhi",
        "avatar": "https://images.unsplash.com/photo-1570125909232-eb263c188f7e?w=100&auto=format&fit=crop&q=60",
        "verified": True,
        "timestamp": "25 min ago",
        "text": "Diversion Alert: Water pipeline maintenance work near ITO Vikas Marg junction. Buses on routes 522 and 534 temporarily diverted via Bahadur Shah Zafar Marg.",
        "category": "diversion",
        "severity": "medium",
        "location_name": "ITO Junction",
        "lat": 28.6289,
        "lng": 77.2405,
        "affected_routes": ["522", "534"],
        "likes": 42,
        "retweets": 15,
    },
    {
        "id": "tw-105",
        "user": "Rohan Malhotra",
        "handle": "@rohan_delhi",
        "avatar": "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=100&auto=format&fit=crop&q=60",
        "verified": False,
        "timestamp": "34 min ago",
        "text": "Waterlogging near Dhaula Kuan underpass causing buses on route 764 to crawl at under 8 km/h. Traffic police on spot clearing the drain.",
        "category": "waterlogging",
        "severity": "medium",
        "location_name": "Dhaula Kuan Underpass",
        "lat": 28.5918,
        "lng": 77.1617,
        "affected_routes": ["764", "990", "MS"],
        "likes": 67,
        "retweets": 21,
    },
    {
        "id": "tw-106",
        "user": "Delhi Transit Live",
        "handle": "@delhi_transit",
        "avatar": "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=100&auto=format&fit=crop&q=60",
        "verified": False,
        "timestamp": "42 min ago",
        "text": "Minor collision between two vehicles near Connaught Place Outer Circle / Regal cinema. One lane blocked, buses experiencing 5-8 min minor delays.",
        "category": "accident",
        "severity": "low",
        "location_name": "Connaught Place (Regal)",
        "lat": 28.6292,
        "lng": 77.2167,
        "affected_routes": ["522", "729", "505"],
        "likes": 38,
        "retweets": 8,
    },
    {
        "id": "tw-107",
        "user": "Delhi Traffic Police",
        "handle": "@dtptraffic",
        "avatar": "https://images.unsplash.com/photo-1544620347-c4fd4a3d5957?w=100&auto=format&fit=crop&q=60",
        "verified": True,
        "timestamp": "50 min ago",
        "text": "Smooth Flow: Peeragarhi towards Janakpuri West stretch on Outer Ring Road is now clear for transit buses. Speed normalized to ~28 km/h.",
        "category": "congestion",
        "severity": "low",
        "location_name": "Janakpuri West / Ring Rd",
        "lat": 28.6295,
        "lng": 77.0780,
        "affected_routes": ["778"],
        "likes": 95,
        "retweets": 14,
    },
    {
        "id": "tw-108",
        "user": "Pooja Verma",
        "handle": "@pooja_v_trans",
        "avatar": "https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=100&auto=format&fit=crop&q=60",
        "verified": False,
        "timestamp": "1 hr ago",
        "text": "Anand Vihar ISBT bus bays are packed this evening. Took 20 min just for route 85 to exit terminal. Plan accordingly if commuting to Noida/Ghaziabad.",
        "category": "congestion",
        "severity": "medium",
        "location_name": "Anand Vihar ISBT",
        "lat": 28.6469,
        "lng": 77.3160,
        "affected_routes": ["85", "522"],
        "likes": 73,
        "retweets": 24,
    },
]

_STORE: List[Dict[str, Any]] = list(INITIAL_TWEETS)
_INITIAL_CRAWL_DONE: bool = False


def refresh_live_tweets(max_items: int = 15) -> List[Dict[str, Any]]:
    """Crawl live Delhi traffic alerts from public real-time RSS feeds and prepend to _STORE."""
    global _INITIAL_CRAWL_DONE
    try:
        scraped = fetch_live_traffic_alerts(max_items=max_items)
        existing_ids = {t["id"] for t in _STORE}
        existing_texts = {t["text"][:50].lower() for t in _STORE}

        added = []
        for item in reversed(scraped):
            if item["id"] not in existing_ids and item["text"][:50].lower() not in existing_texts:
                _STORE.insert(0, item)
                existing_ids.add(item["id"])
                existing_texts.add(item["text"][:50].lower())
                added.append(item)
        _INITIAL_CRAWL_DONE = True
        print(f"[tweets] Scraped {len(scraped)} live items, inserted {len(added)} new alerts into feed.")
    except Exception as exc:
        print(f"[tweets] Error crawling live alerts: {exc}")
    return list(_STORE)


def list_tweets(category: Optional[str] = None) -> List[Dict[str, Any]]:
    """Return all tweets, optionally filtered by category. Trigger initial crawl if needed."""
    global _INITIAL_CRAWL_DONE
    if not _INITIAL_CRAWL_DONE:
        refresh_live_tweets(max_items=12)

    if not category or category.lower() == "all":
        return list(_STORE)
    cat_lower = category.lower()
    return [t for t in _STORE if t["category"].lower() == cat_lower]


def add_tweet(tweet_data: Dict[str, Any]) -> Dict[str, Any]:
    """Add a new commuter tweet / traffic report."""
    item = {
        "id": f"tw-{uuid.uuid4().hex[:6]}",
        "user": tweet_data.get("user", "Delhi Commuter"),
        "handle": tweet_data.get("handle", "@commuter_delhi"),
        "avatar": tweet_data.get(
            "avatar",
            "https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?w=100&auto=format&fit=crop&q=60",
        ),
        "verified": False,
        "timestamp": "Just now",
        "text": tweet_data["text"],
        "category": tweet_data.get("category", "congestion"),
        "severity": tweet_data.get("severity", "medium"),
        "location_name": tweet_data.get("location_name", "Delhi Transit Network"),
        "lat": float(tweet_data.get("lat", 28.6139)),
        "lng": float(tweet_data.get("lng", 77.2090)),
        "affected_routes": tweet_data.get("affected_routes", []),
        "likes": 1,
        "retweets": 0,
    }
    _STORE.insert(0, item)
    return item
