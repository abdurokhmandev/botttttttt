import json
import threading
import os
from config import BASE_DIR

_STATS_FILE = os.path.join(BASE_DIR, "data", "video_stats.json")
_lock = threading.Lock()

# { video_index (int): count (int) }
_stats: dict[int, int] = {}


def _load() -> None:
    global _stats
    try:
        with open(_STATS_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
            _stats = {int(k): int(v) for k, v in raw.items()}
    except (FileNotFoundError, json.JSONDecodeError):
        _stats = {}


def _save() -> None:
    os.makedirs(os.path.dirname(_STATS_FILE), exist_ok=True)
    with open(_STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(_stats, f, ensure_ascii=False, indent=2)


_load()


def increment(video_index: int) -> None:
    """Video bosilganda hisoblagichni oshiradi."""
    with _lock:
        _stats[video_index] = _stats.get(video_index, 0) + 1
        _save()


def get_all() -> dict[int, int]:
    """Barcha video statistikasini qaytaradi."""
    with _lock:
        return dict(_stats)


def reset(video_index: "int | None" = None) -> None:
    """Statistikani nolga qaytaradi. None bo'lsa hammasi reset qilinadi."""
    with _lock:
        if video_index is None:
            _stats.clear()
        else:
            _stats.pop(video_index, None)
        _save()
