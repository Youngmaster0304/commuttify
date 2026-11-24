"""Central configuration for commuttify (reads .env, falls back to defaults)."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, "") or default)
    except ValueError:
        return default


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://commuttify:commuttify@localhost:5433/commuttify",
)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6380/0")

GTFS_DIR = Path(os.getenv("GTFS_DIR", str(PROJECT_ROOT / "data" / "gtfs")))
GTFS_SAMPLE_DIR = Path(
    os.getenv("GTFS_SAMPLE_DIR", str(PROJECT_ROOT / "data" / "gtfs_sample"))
)
SQL_DIR = Path(os.getenv("SQL_DIR", str(PROJECT_ROOT / "sql")))
HIST_DIR = Path(
    os.getenv("HIST_DIR", r"C:\Users\Abhinav\Downloads\delhi_buses_dataset")
)

GTFS_RT_URL = os.getenv(
    "GTFS_RT_URL",
    "https://dts-backend.transportstack.in/api/dataset/otd/get-file"
    "?agency=delhi-buses&category=realtime_gtfs&filename=VehiclePositions.pb",
)
GTFS_RT_KEY = os.getenv("GTFS_RT_KEY", "")
GTFS_RT_KEY_HEADER = os.getenv("GTFS_RT_KEY_HEADER", "x-api-key")
GTFS_RT_POLL_SECONDS = _int("GTFS_RT_POLL_SECONDS", 10)

GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")

# Chatbot LLM endpoints: primary OpenAI-compatible, then FreeLLMAPI fallback
# (https://github.com/tashfeenahmed/freellmapi — self-hosted router on
#  http://localhost:3001/v1, unified key from its dashboard)
CHATBOT_LLM_URL = os.getenv("CHATBOT_LLM_URL", "")
CHATBOT_LLM_MODEL = os.getenv("CHATBOT_LLM_MODEL", "gpt-4o-mini")
CHATBOT_LLM_KEY = os.getenv("CHATBOT_LLM_KEY", "")
CHATBOT_FALLBACK_URL = os.getenv(
    "CHATBOT_FALLBACK_URL", "http://localhost:3001/v1/chat/completions")
CHATBOT_FALLBACK_MODEL = os.getenv("CHATBOT_FALLBACK_MODEL", "auto")
CHATBOT_FALLBACK_KEY = os.getenv("CHATBOT_FALLBACK_KEY", "")

# Routing model constants (seconds / metres)
WALK_SPEED_MPS = 1.2          # ~4.3 km/h comfortable urban walking
MAX_WALK_M = 800.0            # do not walk farther than this to a stop
TRANSFER_PENALTY_S = 240.0    # default penalty when changing routes
LIVE_TTL_S = 900              # GTFS-RT live speed is trusted for 15 minutes
DEFAULT_BUS_SPEED_MPS = 4.17  # fallback ~15 km/h when no schedule/history
MAX_EDGE_TIME_S = 1800.0      # sanity cap for a single segment

# Delhi bounding box (sanity filter for GPS points)
DELHI_BBOX = (28.40, 76.80, 29.05, 77.60)  # min_lat, min_lon, max_lat, max_lon
