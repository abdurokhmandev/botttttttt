import json
import threading
import os
from config import BASE_DIR

_PODCASTS_FILE = os.path.join(BASE_DIR, "data", "podcasts.json")
_lock = threading.Lock()

# { index (int): { "title": str, "description": str, "audio": str, "url": str } }
_podcasts: dict[int, dict] = {}

def _load() -> None:
    global _podcasts
    try:
        if os.path.exists(_PODCASTS_FILE):
            with open(_PODCASTS_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)
                # JSON keys are strings, convert to int
                _podcasts = {int(k): v for k, v in raw.items()}
    except (FileNotFoundError, json.JSONDecodeError):
        _podcasts = {}

def _save() -> None:
    os.makedirs(os.path.dirname(_PODCASTS_FILE), exist_ok=True)
    with open(_PODCASTS_FILE, "w", encoding="utf-8") as f:
        json.dump(_podcasts, f, ensure_ascii=False, indent=2)

def save_podcast(index: int, data: dict) -> None:
    with _lock:
        _podcasts[index] = data
        _save()

def get_all_podcasts() -> dict[int, dict]:
    with _lock:
        return dict(_podcasts)

def delete_podcast(index: int) -> None:
    with _lock:
        if index in _podcasts:
            del _podcasts[index]
            _save()

_load()
