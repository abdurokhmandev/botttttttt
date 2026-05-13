import logging
from aiohttp import web
from config import ADMIN_PASSWORD, VIDEOS
from storage import state_store, video_stats
from handlers.admin import _get_combined_users, _get_all_registered_list

logger = logging.getLogger(__name__)

async def admin_stats_api_handler(request: web.Request) -> web.Response:
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "Invalid JSON"}, status=400)

    password = data.get("password")
    if not password or password != ADMIN_PASSWORD:
        return web.json_response({"ok": False, "error": "Unauthorized"}, status=401)

    # 1. User stats
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

    # 2. Video stats
    stats = video_stats.get_all()
    video_labels = []
    video_views = []
    for idx in sorted(VIDEOS.keys()):
        title = VIDEOS.get(idx, {}).get("title", f"Video {idx}")
        if len(title) > 25:
            title = title[:25] + "..."
        video_labels.append(title)
        video_views.append(stats.get(str(idx)) or stats.get(idx) or 0)

    video_data = {
        "labels": video_labels,
        "views": video_views
    }

    # 3. Recent registered users
    users_list = await _get_all_registered_list()
    # List is already newest first
    recent_users = users_list[:20] 

    # 4. District and Grade stats
    district_counts = {}
    grade_counts = {}
    for u in users_list:
        d = u.get("district")
        if not d or d == "—":
            d = "Noma'lum"
        district_counts[d] = district_counts.get(d, 0) + 1

        g = u.get("grade")
        if not g or g == "—":
            g = "Noma'lum"
        grade_counts[g] = grade_counts.get(g, 0) + 1

    return web.json_response({
        "ok": True,
        "data": {
            "user_stats": user_stats,
            "video_stats": video_data,
            "recent_users": recent_users,
            "district_stats": {
                "labels": list(district_counts.keys()),
                "data": list(district_counts.values())
            },
            "grade_stats": {
                "labels": list(grade_counts.keys()),
                "data": list(grade_counts.values())
            }
        }
    })
