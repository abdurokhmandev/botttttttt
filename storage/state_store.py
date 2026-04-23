import json
import time
import threading
from typing import Optional
from config import STATE_FILE_PATH

# ── States ───────────────────────────────────────────────────────────────────
STARTED       = "STARTED"
REGISTERED    = "REGISTERED"
REMINDER_SENT = "REMINDER_SENT"

_lock = threading.Lock()

# ── Internal storage: {user_id (int): {"state": str, "ts": float}} ───────────
_store: dict[int, dict] = {}


def _load() -> None:
    """Load persisted state from disk on startup."""
    global _store
    try:
        with open(STATE_FILE_PATH, "r", encoding="utf-8") as f:
            raw = json.load(f)
            # JSON keys are always strings — convert back to int
            _store = {int(k): v for k, v in raw.items()}
    except (FileNotFoundError, json.JSONDecodeError):
        _store = {}


def _save() -> None:
    """Persist current state to disk (call while holding _lock)."""
    with open(STATE_FILE_PATH, "w", encoding="utf-8") as f:
        json.dump(_store, f, ensure_ascii=False, indent=2)


# Load on module import
_load()


# ── Public API ────────────────────────────────────────────────────────────────

def set_state(user_id: int, state: str) -> None:
    with _lock:
        _store[user_id] = {"state": state, "ts": time.time()}
        _save()


def get_state(user_id: int) -> Optional[str]:
    with _lock:
        entry = _store.get(user_id)
        return entry["state"] if entry else None


def get_timestamp(user_id: int) -> Optional[float]:
    with _lock:
        entry = _store.get(user_id)
        return entry["ts"] if entry else None


def get_all() -> dict[int, dict]:
    """Return a shallow copy of the full state store (thread-safe)."""
    with _lock:
        return dict(_store)
