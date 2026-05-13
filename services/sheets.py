import json
import logging
import os
from datetime import datetime
from typing import Optional

import gspread
from oauth2client.service_account import ServiceAccountCredentials

from config import SHEETS_ID

logger = logging.getLogger(__name__)

_SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]

HEADERS = ["Date", "Full Name", "Phone", "Grade", "District", "Source", "Telegram ID", "Rahimov School"]

_client: Optional[gspread.Client] = None
_sheet: Optional[gspread.Worksheet] = None


def _get_sheet() -> gspread.Worksheet:
    """Lazy-init the gspread client and worksheet."""
    global _client, _sheet
    if _sheet is not None:
        return _sheet

    # Railway: GOOGLE_CREDENTIALS env var dan o'qi
    raw = os.getenv("GOOGLE_CREDENTIALS")
    if raw:
        creds_dict = json.loads(raw)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, _SCOPES)
    else:
        # Local: credentials.json fayldan o'qi
        from config import CREDENTIALS_PATH
        creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_PATH, _SCOPES)

    _client = gspread.authorize(creds)
    spreadsheet = _client.open_by_key(SHEETS_ID)
    _sheet = spreadsheet.sheet1

    if not _sheet.row_values(1):
        _sheet.append_row(HEADERS)

    return _sheet


def append_row(data: dict) -> None:
    """
    Append a registration row to Google Sheets.

    Expected keys in data:
        name, phone, grade, district, source, telegram_id
    """
    try:
        sheet = _get_sheet()
        row = [
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            data.get("name", ""),
            data.get("phone", ""),
            data.get("grade", ""),
            data.get("district", ""),
            data.get("source", ""),
            str(data.get("telegram_id", "")),
        ]
        sheet.append_row(row)
        logger.info("✅ Row appended for user %s", data.get("telegram_id"))
    except Exception:
        logger.exception("❌ Failed to append row to Google Sheets")


def get_all_registered_ids() -> list[int]:
    """Fetch all Telegram IDs from the Google Sheet."""
    try:
        sheet = _get_sheet()
        # Telegram ID is in column 7 (HEADERS index 6)
        records = sheet.get_all_records()
        ids = []
        for row in records:
            tid = row.get("Telegram ID")
            if tid and str(tid).isdigit():
                ids.append(int(tid))
        return list(set(ids)) # Unique IDs
    except Exception:
        logger.exception("❌ Failed to fetch IDs from Google Sheets")
        return []

def get_all_registered_profiles() -> dict[int, dict]:
    """Fetch all Telegram IDs and profiles from the Google Sheet."""
    try:
        sheet = _get_sheet()
        records = sheet.get_all_records()
        profiles = {}
        for row in records:
            tid = row.get("Telegram ID")
            if tid and str(tid).isdigit():
                uid = int(tid)
                profiles[uid] = {
                    "name": str(row.get("Full Name", "—")),
                    "phone": str(row.get("Phone", "—")),
                    "grade": str(row.get("Grade", "—")),
                    "district": str(row.get("District", "—")),
                }
        return profiles
    except Exception:
        logger.exception("❌ Failed to fetch profiles from Google Sheets")
        return {}

def delete_row_by_tid(tid: int) -> bool:
    """Delete a user's row from Google Sheets by Telegram ID."""
    try:
        sheet = _get_sheet()
        # The first column is 1. Telegram ID is the 7th column (index 7 in gspread 1-based indexing)
        cell = sheet.find(str(tid), in_column=7)
        if cell:
            sheet.delete_rows(cell.row)
            logger.info("✅ Row deleted from Sheets for user %s", tid)
            return True
    except gspread.exceptions.CellNotFound:
        # User not found in Google Sheets, which is fine
        pass
    except Exception:
        logger.exception("❌ Failed to delete row from Google Sheets for user %s", tid)
    return False

def update_school_status(tid: int, status: str) -> bool:
    """Update the Rahimov School status for a given Telegram ID."""
    try:
        sheet = _get_sheet()
        # The first column is 1. Telegram ID is the 7th column
        cell = sheet.find(str(tid), in_column=7)
        if cell:
            # Rahimov School is the 8th column
            sheet.update_cell(cell.row, 8, status)
            logger.info("✅ School status updated in Sheets for user %s", tid)
            return True
    except gspread.exceptions.CellNotFound:
        pass
    except Exception:
        logger.exception("❌ Failed to update school status in Google Sheets for user %s", tid)
    return False
