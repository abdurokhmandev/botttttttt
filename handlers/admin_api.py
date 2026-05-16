import logging
import asyncio
import time
import io
import csv
from aiohttp import web
from aiogram import Bot, types
from aiogram.utils import exceptions

from config import ADMIN_PASSWORD, VIDEOS, PODCASTS
from storage import state_store, video_stats
from storage.podcast_store import delete_podcast, save_podcast
from storage.settings_store import get_settings, save_settings
from storage.broadcast_history import add_broadcast, get_history
from storage.click_store import get_broadcast_clicks
from handlers.admin import _get_combined_users, _get_all_registered_list

logger = logging.getLogger(__name__)

async def admin_stats_api_handler(request: web.Request, bot: Bot) -> web.Response:
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "Invalid JSON"}, status=400)

    password = data.get("password")
    if not password or password != ADMIN_PASSWORD:
        return web.json_response({"ok": False, "error": "Unauthorized"}, status=401)

    action = data.get("action", "stats")

    # --- ACTION: BROADCAST ---
    if action == "broadcast":
        message_text = data.get("text")
        target = data.get("target", "all")
        buttons = data.get("buttons", [])
        
        if not message_text:
            return web.json_response({"ok": False, "error": "Message text is required"}, status=400)
            
        all_users = await _get_combined_users()
        target_ids = []
        if target == "all":
            target_ids = list(all_users.keys())
        elif target == "registered":
            target_ids = [uid for uid, u in all_users.items() if u.get("state") == state_store.REGISTERED]
        elif target == "unregistered":
            target_ids = [uid for uid, u in all_users.items() if u.get("state") != state_store.REGISTERED]
            
        b_id = str(int(time.time()))
        base_url = f"{request.scheme}://{request.host}/go"

        add_broadcast(b_id, message_text, target, len(buttons))

        async def run_broadcast():
            success = 0
            fail = 0
            for uid in target_ids:
                try:
                    kb = None
                    if buttons:
                        kb = types.InlineKeyboardMarkup()
                        for btn in buttons:
                            tracked_url = f"{base_url}?b={b_id}&u={uid}&url={btn['url']}"
                            kb.add(types.InlineKeyboardButton(text=btn['text'], url=tracked_url))
                    
                    await bot.send_message(uid, message_text, reply_markup=kb, parse_mode="HTML")
                    success += 1
                except exceptions.BotBlocked:
                    fail += 1
                except Exception as e:
                    logger.error(f"Broadcast error for {uid}: {e}")
                    fail += 1
                await asyncio.sleep(0.05)
            logger.info(f"Broadcast {b_id} finished: {success} success, {fail} failed")

        asyncio.create_task(run_broadcast())
        return web.json_response({"ok": True, "broadcast_id": b_id, "target_count": len(target_ids)})

    # --- ACTION: GET BROADCAST HISTORY ---
    elif action == "get_broadcast_history":
        return web.json_response({"ok": True, "history": get_history()})

    # --- ACTION: GET CLICK STATS ---
    elif action == "get_click_stats":
        b_id = data.get("broadcast_id")
        if not b_id:
            return web.json_response({"ok": False, "error": "Missing broadcast_id"}, status=400)
        
        clicks = get_broadcast_clicks(b_id)
        all_users = await _get_combined_users()
        detailed_clicks = []
        for uid, ts in clicks.items():
            u = all_users.get(int(uid), {})
            detailed_clicks.append({
                "user_id": uid,
                "name": u.get("name", "Noma'lum"),
                "phone": u.get("phone", "—"),
                "time": ts
            })
        return web.json_response({"ok": True, "clicks": detailed_clicks})

    # --- ACTION: GET STATS ---
    elif action == "stats":
        all_users = await _get_combined_users()
        total_users = len(all_users)
        registered = sum(1 for u in all_users.values() if u.get("state") == state_store.REGISTERED)
        blocked = sum(1 for u in all_users.values() if u.get("blocked") is True)
        unregistered = total_users - registered

        user_stats = {
            "total": total_users,
            "registered": registered,
            "unregistered": unregistered,
            "blocked": blocked
        }

        stats = video_stats.get_all()
        video_labels = []
        video_views = []
        for idx in sorted(VIDEOS.keys()):
            title = VIDEOS.get(idx, {}).get("title", f"Video {idx}")
            if len(title) > 25:
                title = title[:25] + "..."
            video_labels.append(title)
            video_views.append(stats.get(str(idx)) or stats.get(idx) or 0)

        video_data = {"labels": video_labels, "views": video_views}
        users_list = await _get_all_registered_list()
        recent_users = users_list[:20] 

        district_counts = {}
        grade_counts = {}
        for u in users_list:
            d = u.get("district") or "Noma'lum"
            district_counts[d] = district_counts.get(d, 0) + 1
            g = u.get("grade") or "Noma'lum"
            grade_counts[g] = grade_counts.get(g, 0) + 1

        return web.json_response({
            "ok": True,
            "data": {
                "user_stats": user_stats,
                "video_stats": video_data,
                "recent_users": recent_users,
                "district_stats": {"labels": list(district_counts.keys()), "data": list(district_counts.values())},
                "grade_stats": {"labels": list(grade_counts.keys()), "data": list(grade_counts.values())}
            }
        })

    # --- ACTION: GET PODCASTS ---
    elif action == "get_podcasts":
        podcasts_list = []
        for idx in sorted(PODCASTS.keys(), reverse=True):
            p = PODCASTS[idx].copy()
            p["id"] = idx
            podcasts_list.append(p)
        return web.json_response({"ok": True, "podcasts": podcasts_list})

    # --- ACTION: UPDATE PODCAST ---
    elif action == "update_podcast":
        p_id = data.get("id")
        p_data = data.get("podcast_data")
        if not p_id or not p_data:
            return web.json_response({"ok": False, "error": "Missing ID or data"}, status=400)
        idx = int(p_id)
        existing = PODCASTS.get(idx, {})
        existing.update(p_data)
        PODCASTS[idx] = existing
        save_podcast(idx, existing)
        return web.json_response({"ok": True})

    # --- ACTION: DELETE PODCAST ---
    elif action == "delete_podcast":
        p_id = data.get("id")
        if not p_id:
            return web.json_response({"ok": False, "error": "Missing ID"}, status=400)
        idx = int(p_id)
        if idx in PODCASTS:
            del PODCASTS[idx]
            delete_podcast(idx)
        return web.json_response({"ok": True})

    # --- ACTION: GET SETTINGS ---
    elif action == "get_settings":
        return web.json_response({"ok": True, "settings": get_settings()})

    # --- ACTION: UPDATE SETTINGS ---
    elif action == "update_settings":
        new_settings = data.get("settings")
        if not new_settings:
            return web.json_response({"ok": False, "error": "Missing settings"}, status=400)
        save_settings(new_settings)
        return web.json_response({"ok": True})

    # --- ACTION: EXPORT USERS ---
    elif action == "export_users":
        users_list = await _get_all_registered_list()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Ism Familiya", "Telefon", "Sinf", "Hudud", "Telegram ID"])
        for u in users_list:
            writer.writerow([u.get("name"), u.get("phone"), u.get("grade"), u.get("district"), u.get("id")])
        return web.Response(
            body=output.getvalue(),
            content_type='text/csv',
            headers={'Content-Disposition': 'attachment; filename="users.csv"'}
        )

    return web.json_response({"ok": False, "error": "Unknown action"}, status=400)
