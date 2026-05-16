import json
import os
import threading
from datetime import datetime
from config import BASE_DIR

CLICKS_FILE = os.path.join(BASE_DIR, "data", "clicks.json")
_lock = threading.Lock()

# Format: { "broadcast_id": { "user_id": "timestamp" } }
_clicks = {}

def _load():
    global _clicks
    if os.path.exists(CLICKS_FILE):
        try:
            with open(CLICKS_FILE, 'r', encoding='utf-8') as f:
                _clicks = json.load(f)
        except:
            _clicks = {}

def log_click(broadcast_id: str, user_id: str):
    with _lock:
        if broadcast_id not in _clicks:
            _clicks[broadcast_id] = {}
        _clicks[broadcast_id][str(user_id)] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        _save()

def get_broadcast_clicks(broadcast_id: str):
    with _lock:
        return _clicks.get(broadcast_id, {})

def _save():
    os.makedirs(os.path.dirname(CLICKS_FILE), exist_ok=True)
    with open(CLICKS_FILE, 'w', encoding='utf-8') as f:
        json.dump(_clicks, f, indent=4)

_load()
