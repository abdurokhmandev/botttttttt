import json
import os
import threading
import time
from datetime import datetime
from typing import Any

from config import BASE_DIR

EVENTS_FILE = os.path.join(BASE_DIR, "data", "user_events.json")
MAX_EVENTS_PER_USER = 500

_lock = threading.Lock()
_events: dict[str, list[dict[str, Any]]] = {}


def _now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _load() -> None:
    global _events
    try:
        with open(EVENTS_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
            _events = {str(k): list(v) for k, v in raw.items()}
    except (FileNotFoundError, json.JSONDecodeError, TypeError):
        _events = {}


def _save() -> None:
    os.makedirs(os.path.dirname(EVENTS_FILE), exist_ok=True)
    with open(EVENTS_FILE, "w", encoding="utf-8") as f:
        json.dump(_events, f, ensure_ascii=False, indent=2)


def log_event(
    user_id: int | str | None,
    event: str,
    label: str = "",
    details: dict[str, Any] | None = None,
    duration_sec: float | None = None,
) -> None:
    if not user_id:
        return

    item = {
        "event": event,
        "label": label,
        "time": _now_text(),
        "ts": time.time(),
        "details": details or {},
    }
    if duration_sec is not None:
        item["duration_sec"] = round(max(0, duration_sec), 1)

    key = str(user_id)
    with _lock:
        bucket = _events.setdefault(key, [])
        bucket.append(item)
        if len(bucket) > MAX_EVENTS_PER_USER:
            _events[key] = bucket[-MAX_EVENTS_PER_USER:]
        _save()


def get_events(user_id: int | str) -> list[dict[str, Any]]:
    with _lock:
        return list(_events.get(str(user_id), []))


def get_all_events() -> dict[str, list[dict[str, Any]]]:
    with _lock:
        return {uid: list(items) for uid, items in _events.items()}


def get_last_event(user_id: int | str) -> dict[str, Any] | None:
    with _lock:
        items = _events.get(str(user_id), [])
        return items[-1] if items else None


_load()
