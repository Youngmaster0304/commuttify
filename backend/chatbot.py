"""Prompt 7 — chatbot (port of metro commutify chatbot/chatbot.js flow):

    detect intent -> build LOCAL context from the engines
                  -> if an OpenAI-compatible LLM is configured
                     (CHATBOT_LLM_URL / _MODEL / _KEY) let it phrase the reply
                  -> otherwise return the rule-based fallback.

Context sources: recommendation engine (places), journey planner (routing),
live feed worker (Redis live segment times).
"""

from __future__ import annotations

import re

import httpx
from sqlalchemy import text

from . import config, db, recommend, routing
from .live_feed_worker import LiveStore

GREETINGS = ("hi", "hello", "hey", "namaste", "good morning", "good evening")
HELP_KEYS = ("help", "what can you do", "features", "commands")

SYSTEM_PROMPT = (
    "You are Commuttify AI, a Delhi DTC bus transit assistant built for the "
    "commuttify project (Delhi Transport Stack Hackathon 2026).\n"
    "STRICT SCOPE — answer ONLY questions about Delhi bus travel: DTC bus "
    "routes and journeys, bus stops and stations, live bus traffic and "
    "delays, journey duration and transfers, and Delhi places/stops as they "
    "relate to bus travel.\n"
    "If a question is outside this scope (other cities or countries, metro/"
    "train/flight travel, coding, general knowledge, creative writing, "
    "personal advice, etc.), refuse politely in ONE sentence and steer the "
    "user back to Delhi bus topics. Never answer off-topic questions, even "
    "when asked directly.\n"
    "CRITICAL FORMATTING RULES:\n"
    "1. NEVER use LaTeX math syntax; use plain Unicode arrows (→).\n"
    "2. Use only plain Markdown: **bold**, bullet lists with '- ', numbered lists.\n"
    "3. Prioritize facts from the local context below when it matches the query.\n"
    "4. Keep answers friendly, concise, informative; emojis are welcome.\n"
    "5. If the local context is empty, say you could not find that in the data "
    "instead of inventing routes."
)


# --------------------------------------------------------------------------- #
# intent + place extraction
# --------------------------------------------------------------------------- #

def detect_intent(message: str) -> str:
    lower = message.lower().strip()
    if any(lower == g or lower.startswith(g) for g in GREETINGS):
        return "greeting"
    if any(k in lower for k in HELP_KEYS):
        return "help"
    if any(w in lower for w in ("live", "running now", "right now",
                                "traffic", "delay")):
        return "live"
    if any(w in lower for w in ("route", "from ", " to ", "go to",
                                "how to reach", "how do i get", "direction",
                                "journey", "travel", "time", "how long",
                                "duration")):
        return "route"
    if any(w in lower for w in ("stop", "station", "tell me about",
                                "info about", "where is")):
        return "stop_info"
    return "general"


def _resolve(fragment: str) -> dict | None:
    """Best place match for a text fragment (recommendation engine)."""
    fragment = fragment.strip(" ?.,!")
    if not fragment:
        return None
    hits = recommend.recommend(fragment, limit=1)
    return hits[0] if hits else None


def _extract_places(message: str) -> list[dict]:
    """Known stop names present in the message (longest match first)."""
    places = recommend.load_places()
    remaining = message.lower()
    found: list[dict] = []
    for p in sorted(places, key=lambda x: -len(x["name"])):
        nl = p["name"].lower()
        if nl and nl in remaining:
            found.append(p)
            remaining = remaining.replace(nl, " ")
            if len(found) >= 3:
                break
    return found


def _two_places(message: str) -> tuple[dict, dict] | None:
    m = re.search(r"\bfrom\s+(.+?)\s+to\s+(.+?)(?:[?.!]|$)",
                  message, flags=re.IGNORECASE)
    if m:
        a, b = _resolve(m.group(1)), _resolve(m.group(2))
        if a and b and a["stop_id"] != b["stop_id"]:
            return a, b
    found = _extract_places(message)
    if len(found) >= 2:
        return found[0], found[1]
    return None


# --------------------------------------------------------------------------- #
# bus-only scope gate (Delhi bus project)
# --------------------------------------------------------------------------- #

BUS_KEYWORDS = (
    "bus", "dtc", "delhi", "route", "stop", "station", "journey", "travel",
    "fare", "live", "traffic", "delay", "walk", "transfer", "terminal",
    "transport", "commute", "how do i get", "how to reach", "direction",
    "get to", "reach", "time", "how long", "minutes", "hours", "km",
    "near me", "first bus", "last bus", "frequency", "timing",
)

OUT_OF_SCOPE = (
    "🚫 I only answer questions about **Delhi bus travel** — DTC routes, "
    "stops, live traffic, and journey times. "
    "Try: \"Route from Rohini Sec 22 Terminal to Azadpur Terminal\" or "
    "\"Tell me about Lakhhi Ram Park\"."
)


def _is_bus_related(message: str) -> bool:
    lower = message.lower()
    if any(k in lower for k in BUS_KEYWORDS):
        return True
    # a known stop/place name counts as on-topic even without keywords
    return bool(_extract_places(message))


# --------------------------------------------------------------------------- #
# context builders
# --------------------------------------------------------------------------- #

def _journey_text(res: dict) -> str:
    lines = ["🚌 **Journey options**"]
    for i, opt in enumerate(res["options"][:3], 1):
        lines.append(
            f"{i}. **{opt['label']}** — {opt['duration_min']} min, "
            f"{opt['transfers']} transfer(s), walk {opt['walk_min']} min")
        for leg in opt["legs"]:
            if leg["type"] == "walk":
                lines.append(f"   - walk {leg['from']} → {leg['to']} "
                             f"({leg['duration_min']} min)")
            else:
                lines.append(
                    f"   - 🚌 route {leg['route']}: {leg['from']} → {leg['to']} "
                    f"({leg['duration_min']} min, {leg['stops']} segments, "
                    f"{leg['source']} times)")
    if len(res["options"]) > 1:
        lines.append(f"_({len(res['options'])} distinct options shown)_")
    return "\n".join(lines)


def _route_context(message: str) -> str | None:
    pair = _two_places(message)
    if pair is None:
        return None
    a, b = pair
    try:
        res = routing.plan_journeys(a["lat"], a["lon"], b["lat"], b["lon"])
    except ValueError:
        return None
    return (f"**Route: {a['name']} → {b['name']}**\n"
            + _journey_text(res))


def _stop_context(message: str) -> str | None:
    found = _extract_places(message)
    place = found[0] if found else None
    if place is None:
        cleaned = re.sub(
            r"(tell me about|info about|where is|stop|station)", " ",
            message, flags=re.IGNORECASE).strip(" ?.,!")
        place = _resolve(cleaned) if cleaned else None
    if place is None:
        return None
    with db.get_engine().connect() as conn:
        rows = conn.execute(text(
            "SELECT DISTINCT route_id FROM route_segments "
            "WHERE from_stop_id = :s OR to_stop_id = :s LIMIT 30"
        ), {"s": place["stop_id"]}).fetchall()
    routes = sorted(str(r[0]) for r in rows)
    lines = [f"**{place['name']}**",
             f"- Coordinates: {place['lat']:.5f}, {place['lon']:.5f}",
             f"- Routes serving this stop: {', '.join(routes) or 'none in graph'}"]
    return "\n".join(lines)


def _live_context() -> str:
    store = LiveStore(config.REDIS_URL)
    tts = store.live_travel_times()
    if not tts:
        return ("🔴 No live bus segments right now — the live worker may not "
                "be running, or data is older than 15 minutes.")
    sample = sorted(tts.items())[:5]
    examples = ", ".join(f"seg {sid}≈{int(tt)}s" for sid, tt in sample)
    return (f"🟢 {len(tts)} road segments currently have live traffic data "
            f"(updated every 10 s, valid 15 min). Examples: {examples}.")


# --------------------------------------------------------------------------- #
# optional LLM: primary endpoint, then FreeLLMAPI fallback
# --------------------------------------------------------------------------- #

def _chat_once(url: str, model: str, key: str,
               context: str, message: str) -> str | None:
    if not url:
        return None
    # accept base URLs like .../v1 or .../v1/chat/completions
    if not url.rstrip("/").endswith("chat/completions"):
        url = url.rstrip("/") + "/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT
             + "\n\nLocal context:\n" + (context or "No local context matched.")},
            {"role": "user", "content": message},
        ],
        "temperature": 0.4,
    }
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    try:
        r = httpx.post(url, json=payload, headers=headers, timeout=30.0)
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"]
        return content if content and content.strip() else None
    except Exception:  # noqa: BLE001 — next endpoint / rule fallback
        return None


def _llm_reply(context: str, message: str) -> str | None:
    reply = _chat_once(config.CHATBOT_LLM_URL, config.CHATBOT_LLM_MODEL,
                       config.CHATBOT_LLM_KEY, context, message)
    if reply:
        return reply
    return _chat_once(config.CHATBOT_FALLBACK_URL,
                      config.CHATBOT_FALLBACK_MODEL,
                      config.CHATBOT_FALLBACK_KEY, context, message)


# --------------------------------------------------------------------------- #
# rule-based fallback
# --------------------------------------------------------------------------- #

def _fallback(intent: str, message: str, context: str | None) -> str:
    if intent == "greeting":
        return ("👋 Namaste! I'm the Commuttify bus assistant. I can help with:\n"
                "- 🗺️ **Journeys** — \"Route from Rohini Sec 22 to Azadpur\"\n"
                "- 🚩 **Stop info** — \"Tell me about Lakhhi Ram Park\"\n"
                "- 🔴 **Live traffic** — \"Any live delays right now?\"\n"
                "- Try: \"How do I get from X to Y?\"")
    if intent == "help":
        return ("Try asking naturally:\n"
                "- \"Route from Rohini Sec 22 Terminal to Azadpur Terminal\"\n"
                "- \"Tell me about Lakhhi Ram Park\"\n"
                "- \"Is there live traffic data right now?\"")
    if intent in ("route", "time") and context:
        return context
    if intent in ("route", "time"):
        return ("I couldn't identify both places. Try: "
                "\"Route from Rohini Sec 22 Terminal to Azadpur Terminal\"")
    if intent == "stop_info" and context:
        return context
    if intent == "stop_info":
        return "Which stop? Try: \"Tell me about Lakhhi Ram Park\""
    if intent == "live":
        return context or _live_context()
    if context:
        return context
    return ("I'm here to help you navigate Delhi buses! Ask me about routes, "
            "stops, or live traffic.")


# --------------------------------------------------------------------------- #
# public entry point
# --------------------------------------------------------------------------- #

def process_message(message: str) -> str:
    intent = detect_intent(message)

    # bus-only scope: refuse clearly off-topic questions before any LLM call
    if intent not in ("greeting", "help") and not _is_bus_related(message):
        return OUT_OF_SCOPE

    context: str | None = None
    try:
        if intent in ("route", "time"):
            context = _route_context(message)
        elif intent == "stop_info":
            context = _stop_context(message)
        elif intent == "live":
            context = _live_context()
    except Exception:  # noqa: BLE001 — never break the chat on engine errors
        context = None

    reply = _llm_reply(context or "", message)
    if reply:
        return reply
    return _fallback(intent, message, context)
