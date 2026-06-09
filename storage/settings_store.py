import json
import os
import threading
from config import BASE_DIR

SETTINGS_FILE = os.path.join(BASE_DIR, "data", "bot_settings.json")
_lock = threading.Lock()

DEFAULT_SETTINGS = {
    "maktab_haqida": "🏫 <b>Rahimov School haqida</b>\n\nMaktabimiz haqida batafsil ma'lumot olish uchun quyidagi tugmalardan foydalanishingiz mumkin yoki ushbu matnni o'zgartiring.",
    "phone": "+998781130005",
    "instagram": "instagram.com/rahimovschool",
    "telegram": "t.me/rahimovschool",
    "youtube": "youtube.com/@rahimovschool",
    "test_accounts": []
}

def get_settings():
    with _lock:
        if not os.path.exists(SETTINGS_FILE):
            return DEFAULT_SETTINGS.copy()
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Merge with defaults in case new settings were added
                merged = DEFAULT_SETTINGS.copy()
                merged.update(data)
                return merged
        except Exception:
            return DEFAULT_SETTINGS.copy()

def save_settings(settings):
    with _lock:
        os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=4, ensure_ascii=False)
