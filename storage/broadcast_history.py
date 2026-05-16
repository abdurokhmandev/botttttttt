import json
import os
import threading
from datetime import datetime
from config import BASE_DIR

HISTORY_FILE = os.path.join(BASE_DIR, "data", "broadcast_history.json")
_lock = threading.Lock()
_history = []

def _load():
    global _history
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                _history = json.load(f)
        except:
            _history = []

def add_broadcast(b_id, text, target, buttons_count):
    with _lock:
        _history.insert(0, {
            "id": b_id,
            "text": text[:100] + "..." if len(text) > 100 else text,
            "target": target,
            "buttons": buttons_count,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        # Keep last 50
        _history = _history[:50]
        _save()

def get_history():
    with _lock:
        return list(_history)

def _save():
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(_history, f, indent=4)

_load()
