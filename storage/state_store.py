import json
import os
import time
import threading
from typing import Optional
from config import STATE_FILE_PATH

PROFILES_FILE_PATH = os.path.join(os.path.dirname(STATE_FILE_PATH), "profiles.json")

# ── States ───────────────────────────────────────────────────────────────────
STARTED       = "STARTED"
REGISTERED    = "REGISTERED"

# ── Funnel workflow states ───────────────────────────────────────────────────────
PODCAST_SELECTED      = "PODCAST_SELECTED"

# ── Video funnel states ───────────────────────────────────────────────────────────
VIDEO_SENT            = "VIDEO_SENT"           # Video yuborildi, 30 daqiqa kutilmoqda
VIDEO_WATCHED_ASKED   = "VIDEO_WATCHED_ASKED"  # "Ko'rdingizmi?" savoli yuborildi
WANT_MORE_ASKED       = "WANT_MORE_ASKED"      # Podkast ro'yxati ko'rsatildi
LIKE_ASKED            = "LIKE_ASKED"           # "Yoqdimi?" savoli yuborildi
REGISTER_OFFERED      = "REGISTER_OFFERED"     # Ro'yxatga taklif yuborildi
SCHOOL_ASKED          = "SCHOOL_ASKED"         # Maktab haqida savol yuborildi
SNOOZE_15             = "SNOOZE_15"            # 10-15 daqiqada eslatish
SNOOZE_60             = "SNOOZE_60"            # 1 soatda eslatish
SNOOZE_TOMORROW       = "SNOOZE_TOMORROW"      # Ertaga eslatish

# ── Registered users profile store: {user_id: {name, phone, grade, ...}} ─────
_profiles: dict[int, dict] = {}


def _load_profiles() -> None:
    """Load persisted profiles from disk on startup."""
    global _profiles
    try:
        with open(PROFILES_FILE_PATH, "r", encoding="utf-8") as f:
            raw = json.load(f)
            _profiles = {int(k): v for k, v in raw.items()}
    except (FileNotFoundError, json.JSONDecodeError):
        _profiles = {}


def _save_profiles() -> None:
    """Persist profiles to disk (call while holding _lock)."""
    os.makedirs(os.path.dirname(PROFILES_FILE_PATH), exist_ok=True)
    with open(PROFILES_FILE_PATH, "w", encoding="utf-8") as f:
        json.dump(_profiles, f, ensure_ascii=False, indent=2)

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
    import os
    os.makedirs(os.path.dirname(STATE_FILE_PATH), exist_ok=True)
    with open(STATE_FILE_PATH, "w", encoding="utf-8") as f:
        json.dump(_store, f, ensure_ascii=False, indent=2)


# Load on module import
_load()
_load_profiles()


# ── Public API ────────────────────────────────────────────────────────────────

def set_state(user_id: int, state: str) -> None:
    with _lock:
        if user_id not in _store:
            _store[user_id] = {}
        _store[user_id]["state"] = state
        _store[user_id]["ts"] = time.time()
        _save()


def set_metadata(user_id: int, key: str, value: any) -> None:
    with _lock:
        if user_id not in _store:
            _store[user_id] = {"state": None, "ts": time.time()}
        _store[user_id][key] = value
        _save()


def get_metadata(user_id: int, key: str) -> any:
    with _lock:
        entry = _store.get(user_id)
        return entry.get(key) if entry else None


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


def clear_funnel_progress(user_id: int) -> None:
    """Clear pending funnel/reminder metadata without changing registration state."""
    with _lock:
        if user_id not in _store:
            return
        for key in (
            "funnel_state",
            "video_sent_ts",
            "snooze_ts",
            "last_video_idx",
            "podcast_selected_ts",
        ):
            _store[user_id].pop(key, None)
        _save()


def save_profile(user_id: int, name: str, phone: str, grade: str, district: str = "", school: str = "") -> None:
    """Ro'yxatdan o'tgan foydalanuvchi profilini saqlaydi."""
    with _lock:
        _profiles[user_id] = {
            "name": name,
            "phone": phone,
            "grade": grade,
            "district": district,
            "school": school,
        }
        _save_profiles()


def get_profile(user_id: int) -> Optional[dict]:
    """Foydalanuvchi profilini qaytaradi."""
    with _lock:
        return _profiles.get(user_id)


def get_all_registered_profiles() -> dict[int, dict]:
    """Barcha ro'yxatdan o'tgan foydalanuvchilar profilini qaytaradi."""
    with _lock:
        registered = {
            uid: info for uid, info in _store.items()
            if info.get("state") == REGISTERED
        }
        result = {}
        for uid in registered:
            profile = _profiles.get(uid, {})
            result[uid] = {
                **registered[uid],
                "name": profile.get("name", "—"),
                "phone": profile.get("phone", "—"),
                "grade": profile.get("grade", "—"),
                "district": profile.get("district", "—"),
                "school": profile.get("school", "—"),
            }
        return result


def delete_user(user_id: int) -> None:
    """Foydalanuvchini local bazadan o'chiradi."""
    with _lock:
        deleted = False
        if user_id in _store:
            del _store[user_id]
            deleted = True
        if user_id in _profiles:
            del _profiles[user_id]
            deleted = True
        
        if deleted:
            _save()
            _save_profiles()
