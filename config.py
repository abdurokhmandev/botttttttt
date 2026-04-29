import json
import os
from dotenv import load_dotenv

load_dotenv()


def _require(key: str) -> str:
    val = os.getenv(key)
    if not val:
        raise RuntimeError(f"Missing required environment variable: {key}")
    return val


def _load_video(key: str) -> dict:
    raw = os.getenv(key, "{}")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"title": key, "url": "", "photo": "", "video": ""}


# ── Core ─────────────────────────────────────────────────────────────────────
BOT_TOKEN: str = _require("BOT_TOKEN")
SHEETS_ID: str = _require("SHEETS_ID")
WEBAPP_URL: str = _require("WEBAPP_URL")

# ── School ───────────────────────────────────────────────────────────────────
SCHOOL_INFO: str = os.getenv(
    "SCHOOL_INFO",
    "🏫 Rahimov School\n\nContact us for more information.",
).replace("\\n", "\n")

# ── Videos ───────────────────────────────────────────────────────────────────
VIDEOS: dict[int, dict] = {
    1: _load_video("VIDEO_1"),
    2: _load_video("VIDEO_2"),
    3: _load_video("VIDEO_3"),
    4: _load_video("VIDEO_4"),
    5: _load_video("VIDEO_5"),
}

# ── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_PATH = os.path.join(BASE_DIR, "credentials.json")
STATE_FILE_PATH = os.path.join(BASE_DIR, "state.json")
