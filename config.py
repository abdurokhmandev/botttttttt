import os
from dotenv import load_dotenv

load_dotenv()


def _require(key: str) -> str:
    val = os.getenv(key)
    if not val:
        raise RuntimeError(f"Missing required environment variable: {key}")
    return val


# ── Core ─────────────────────────────────────────────────────────────────────
BOT_TOKEN: str = _require("BOT_TOKEN")
SHEETS_ID: str = _require("SHEETS_ID")
WEBAPP_URL: str = _require("WEBAPP_URL")

# ── School ───────────────────────────────────────────────────────────────────
SCHOOL_INFO: str = os.getenv(
    "SCHOOL_INFO",
    "🏫 Rahimov School\n\nContact us for more information.",
).replace("\\n", "\n")

# ── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ── Videos ───────────────────────────────────────────────────────────────────
VIDEOS: dict[int, dict] = {
    1: {
        "photo": os.path.join(BASE_DIR, "static", "aka.png"),
        "title": "Aka-uka va opa-singillar o'rtasidagi muammo 📹",
        "url": "https://youtu.be/ApLGhoQCuMw?si=zIYyOYpBaogyYJQo"
    },
    2: {
        "photo": os.path.join(BASE_DIR, "static", "otalar.png"),
        "title": "Ota va o'g'il munosabati haqida gaplashamiz 📹",
        "url": "https://youtu.be/JzofE9oMaV8?si=iTHzQwIyIMVh4vNK"
    },
    3: {
        "photo": os.path.join(BASE_DIR, "static", "band.png"),
        "title": "Tarbiya uchun vaqt yo'q  📹",
        "url": "https://youtu.be/xbfkK7xV7SI?si=LaMetMjOgkfVtJDz"
    },
    4: {
        "photo": os.path.join(BASE_DIR, "static", "kasb.png"),
        "title": "Farzandim bloger bo'lmoqchi  📹",
        "url": "https://youtu.be/PxOoZDJTpZM?si=UDa6H2vVTZlujkm4"
    },
    5: {
        "photo": os.path.join(BASE_DIR, "static", "farzandim.png"),
        "title": "Bola bilan do'stlashing  📹",
        "url": "https://youtu.be/8-6Wcy9DE_c?si=3qqCa4v2fjF0F_k8"
    },
}

CREDENTIALS_PATH = os.path.join(BASE_DIR, "credentials.json")
STATE_FILE_PATH = os.path.join(BASE_DIR, "state.json")