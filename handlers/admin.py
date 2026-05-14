import asyncio
import logging
from aiogram import Dispatcher, types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.exceptions import BotBlocked, UserDeactivated

from config import ADMIN_IDS, VIDEOS
from storage import state_store, video_stats
from services import sheets

logger = logging.getLogger(__name__)

PAGE_SIZE = 10  # Sahifada nechta user ko'rsatilsin

# ── FSM States ────────────────────────────────────────────────────────────────

class BroadcastStates(StatesGroup):
    SELECT_AUDIENCE = State()
    GET_CONTENT = State()
    GET_BUTTON = State()
    CONFIRM = State()

class DirectMessageStates(StatesGroup):
    SELECT_USER = State()
    GET_MESSAGE = State()
    CONFIRM = State()

class DeleteUserStates(StatesGroup):
    SELECT_USER = State()
    CONFIRM = State()

# ── Keyboards ─────────────────────────────────────────────────────────────────

def _admin_main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton("📢 Xabar yuborish"), KeyboardButton("👤 Alohida xabar")],
            [KeyboardButton("📊 Statistika"), KeyboardButton("🎬 Video statistika")],
            [KeyboardButton("📋 Ro'yxatdan o'tganlar"), KeyboardButton("⏳ Ro'yxatdan o'tmaganlar")],
            [KeyboardButton("🗑 Foydalanuvchini o'chirish")],
        ],
        resize_keyboard=True
    )

def _audience_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Barchaga", callback_data="target_all")],
        [InlineKeyboardButton(text="❌ Ro'yxatdan o'tmaganlarga", callback_data="target_unregistered")],
        [InlineKeyboardButton(text="✅ Ro'yxatdan o'tganlarga", callback_data="target_registered")],
        [InlineKeyboardButton(text="⏳ Eski ro'yxatdan o'tganlarga", callback_data="target_old_registered")],
        [InlineKeyboardButton(text="🚫 Bekor qilish", callback_data="cancel_broadcast")],
    ])

def _confirm_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Tasdiqlash", callback_data="confirm_broadcast")],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_broadcast")],
    ])

def _pagination_keyboard(page: int, total_pages: int, prefix: str) -> InlineKeyboardMarkup:
    """Back | sahifa N/M | Next tugmalari."""
    buttons = []
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️ Back", callback_data=f"{prefix}_page_{page - 1}"))
    nav.append(InlineKeyboardButton(text=f"📄 {page + 1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="Next ▶️", callback_data=f"{prefix}_page_{page + 1}"))
    buttons.append(nav)
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_combined_users():
    """Merge local state with Google Sheets data."""
    users = state_store.get_all()
    registered_ids = sheets.get_all_registered_ids()
    for tid in registered_ids:
        if tid not in users:
            users[tid] = {"state": state_store.REGISTERED}
        else:
            users[tid]["state"] = state_store.REGISTERED
    return users


async def _get_all_registered_list() -> list:
    """
    Barcha registered userlarni (uid, name, phone, grade) ro'yxat sifatida qaytaradi.
    Local profile'dan olinadi, yo'q bo'lsa Google Sheets'dan.
    """
    local_profiles = state_store.get_all_registered_profiles()
    sheet_profiles = sheets.get_all_registered_profiles()

    ordered_ids = list(sheet_profiles.keys())
    for uid in local_profiles.keys():
        if uid not in sheet_profiles:
            ordered_ids.append(uid)

    result = []
    for uid in ordered_ids:
        loc = local_profiles.get(uid, {})
        sht = sheet_profiles.get(uid, {})
        
        name = loc.get("name") if loc.get("name", "—") != "—" else sht.get("name", "—")
        phone = loc.get("phone") if loc.get("phone", "—") != "—" else sht.get("phone", "—")
        grade = loc.get("grade") if loc.get("grade", "—") != "—" else sht.get("grade", "—")
        district = loc.get("district") if loc.get("district", "—") != "—" else sht.get("district", "—")

        result.append({
            "uid": uid,
            "name": name,
            "phone": phone,
            "grade": grade,
            "district": district,
        })
    return result[::-1]


def _format_users_page(users_list: list, page: int) -> str:
    """10 talik sahifani formatlaydi."""
    start = page * PAGE_SIZE
    end = min(start + PAGE_SIZE, len(users_list))
    chunk = users_list[start:end]

    lines = [f"📋 <b>Ro'yxatdan o'tganlar ({start + 1}–{end} / {len(users_list)}):</b>\n"]
    for i, u in enumerate(chunk, start + 1):
        lines.append(
            f"<b>{i}.</b> 👤 {u['name']}\n"
            f"   📱 {u['phone']}  |  🎓 {u['grade']}\n"
            f"   🆔 <code>{u['uid']}</code>\n"
        )
    return "\n".join(lines)

# ── Admin Main ────────────────────────────────────────────────────────────────

async def cmd_admin(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    await message.answer("👋 Admin panelga xush kelibsiz!", reply_markup=_admin_main_keyboard())

# ── Statistics ────────────────────────────────────────────────────────────────

async def show_stats(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    await message.answer("⌛ Statistika hisoblanmoqda...")
    all_users = await _get_combined_users()
    total = len(all_users)
    registered = sum(1 for u in all_users.values() if u.get("state") == state_store.REGISTERED)
    blocked = sum(1 for u in all_users.values() if u.get("blocked") is True)
    text = (
        "📊 <b>Bot Statistikasi:</b>\n\n"
        f"👥 Umumiy foydalanuvchilar: {total}\n"
        f"✅ Ro'yxatdan o'tganlar: {registered}\n"
        f"⏳ Ro'yxatdan o'tmaganlar: {total - registered}\n"
        f"🚫 Botni bloklaganlar: {blocked}"
    )
    await message.answer(text, parse_mode="HTML")


async def show_video_stats(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    stats = video_stats.get_all()
    if not stats:
        await message.answer("📊 Hali hech kim video tanlamagan.")
        return
    sorted_stats = sorted(stats.items(), key=lambda x: x[1], reverse=True)
    total_views = sum(stats.values())
    lines = ["🎬 <b>Video Ko'rish Statistikasi:</b>\n"]
    for rank, (idx, count) in enumerate(sorted_stats, 1):
        title = VIDEOS.get(idx, {}).get("title", f"Video {idx}")
        bar_len = int((count / total_views) * 15) if total_views > 0 else 0
        bar = "█" * bar_len + "░" * (15 - bar_len)
        medal = ["🥇", "🥈", "🥉"][rank - 1] if rank <= 3 else f"#{rank}"
        lines.append(f"{medal} <b>{title[:35]}</b>\n   {bar} {count} marta\n")
    lines.append(f"\n📈 Jami ko'rishlar: <b>{total_views}</b>")
    await message.answer("\n".join(lines), parse_mode="HTML")

# ── Registered Users List with Pagination ────────────────────────────────────

async def show_registered_users(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    await message.answer("⌛ Yuklanmoqda...")
    users_list = await _get_all_registered_list()
    if not users_list:
        await message.answer("📋 Hali hech kim ro'yxatdan o'tmagan.")
        return

    total_pages = max(1, (len(users_list) + PAGE_SIZE - 1) // PAGE_SIZE)
    text = _format_users_page(users_list, 0)
    markup = _pagination_keyboard(0, total_pages, "reglist") if total_pages > 1 else None
    await message.answer(text, parse_mode="HTML", reply_markup=markup)


async def registered_pagination(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer()
        return
    if callback.data == "noop":
        await callback.answer()
        return

    page = int(callback.data.split("_page_")[1])
    users_list = await _get_all_registered_list()
    total_pages = max(1, (len(users_list) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))

    text = _format_users_page(users_list, page)
    markup = _pagination_keyboard(page, total_pages, "reglist")
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=markup)
    except Exception:
        pass
    await callback.answer()

# ── Unregistered Users List with Pagination ────────────────────────────────────

async def _format_unregistered_page(bot, unreg_ids: list, page: int) -> str:
    start = page * PAGE_SIZE
    end = min(start + PAGE_SIZE, len(unreg_ids))
    chunk = unreg_ids[start:end]

    lines = [f"⏳ <b>Ro'yxatdan o'tmaganlar ({start + 1}–{end} / {len(unreg_ids)}):</b>\n"]
    for i, uid in enumerate(chunk, start + 1):
        name = "Noma'lum"
        try:
            chat = await bot.get_chat(uid)
            name = chat.first_name or name
            if chat.last_name:
                name += f" {chat.last_name}"
            if chat.username:
                name += f" (@{chat.username})"
        except Exception:
            pass
        
        lines.append(f"<b>{i}.</b> 👤 <a href='tg://user?id={uid}'>{name}</a>\n   🆔 <code>{uid}</code>\n")
    return "\n".join(lines)

async def show_unregistered_users(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    await message.answer("⌛ Yuklanmoqda...")
    all_users = await _get_combined_users()
    unreg_ids = [uid for uid, info in all_users.items() if info.get("state") != state_store.REGISTERED][::-1]
    
    if not unreg_ids:
        await message.answer("📋 Barcha ro'yxatdan o'tgan.")
        return
        
    total_pages = max(1, (len(unreg_ids) + PAGE_SIZE - 1) // PAGE_SIZE)
    text = await _format_unregistered_page(message.bot, unreg_ids, 0)
    markup = _pagination_keyboard(0, total_pages, "unreglist") if total_pages > 1 else None
    await message.answer(text, parse_mode="HTML", reply_markup=markup)

async def unregistered_pagination(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer()
        return
    if callback.data == "noop":
        await callback.answer()
        return

    page = int(callback.data.split("_page_")[1])
    all_users = await _get_combined_users()
    unreg_ids = [uid for uid, info in all_users.items() if info.get("state") != state_store.REGISTERED][::-1]
    
    total_pages = max(1, (len(unreg_ids) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))

    text = await _format_unregistered_page(callback.bot, unreg_ids, page)
    markup = _pagination_keyboard(page, total_pages, "unreglist")
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=markup)
    except Exception:
        pass
    await callback.answer()

# ── Broadcast Flow ────────────────────────────────────────────────────────────

async def start_broadcast(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    await BroadcastStates.SELECT_AUDIENCE.set()
    await message.answer("🎯 Kimlarga xabar yubormoqchisiz?", reply_markup=_audience_keyboard())


async def set_target(callback: types.CallbackQuery, state: FSMContext):
    if callback.data == "cancel_broadcast":
        await state.finish()
        await callback.message.edit_text("❌ Bekor qilindi.")
        return
    target_map = {
        "target_all": "all",
        "target_registered": "registered",
        "target_unregistered": "unregistered",
        "target_old_registered": "old_registered",
    }
    target = target_map.get(callback.data, "all")
    await state.update_data(target=target)
    await BroadcastStates.GET_CONTENT.set()
    await callback.message.edit_text("📝 Yubormoqchi bo'lgan xabaringizni yuboring (matn, rasm, video va h.k.):")


async def get_content(message: types.Message, state: FSMContext):
    await state.update_data(message_id=message.message_id, chat_id=message.chat.id)
    await BroadcastStates.GET_BUTTON.set()
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏭ Tugmasiz yuborish", callback_data="skip_button")]
    ])
    await message.answer(
        "🔗 Tugma qo'shishni xohlaysizmi?\n\n"
        "Format: <code>Tugma matni | Link</code>\n"
        "Masalan: <code>Bizning kanal | https://t.me/...</code>",
        parse_mode="HTML",
        reply_markup=markup
    )


async def get_button(message: types.Message, state: FSMContext):
    if "|" not in message.text:
        await message.answer("❌ Noto'g'ri format. Qaytadan urinib ko'ring yoki pastdagi tugmani bosing.")
        return
    text, url = message.text.split("|", 1)
    await state.update_data(btn_text=text.strip(), btn_url=url.strip())
    await BroadcastStates.CONFIRM.set()
    await _show_preview(message, state)


async def skip_button(callback: types.CallbackQuery, state: FSMContext):
    await BroadcastStates.CONFIRM.set()
    await _show_preview(callback.message, state)


async def _show_preview(message: types.Message, state: FSMContext):
    data = await state.get_data()
    await message.answer("👀 <b>Xabar ko'rinishi (Preview):</b>", parse_mode="HTML")
    markup = None
    if data.get("btn_text") and data.get("btn_url"):
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=data["btn_text"], url=data["btn_url"])]
        ])
    await message.bot.copy_message(
        chat_id=message.chat.id,
        from_chat_id=data["chat_id"],
        message_id=data["message_id"],
        reply_markup=markup
    )
    target_labels = {
        "all": "Barchaga",
        "registered": "Ro'yxatdan o'tganlarga",
        "unregistered": "Ro'yxatdan o'tmaganlarga",
        "old_registered": "Eski ro'yxatdan o'tganlarga (Holati noma'lum)",
    }
    target_text = target_labels.get(data.get("target", "all"), "Barchaga")
    await message.answer(
        f"⬆️ Xabar yuqoridagidek ko'rinadi.\n🎯 Maqsadli auditoriya: <b>{target_text}</b>\n\nTasdiqlaysizmi?",
        parse_mode="HTML",
        reply_markup=_confirm_keyboard()
    )


async def execute_broadcast(callback: types.CallbackQuery, state: FSMContext):
    if callback.data == "cancel_broadcast":
        await state.finish()
        await callback.message.edit_text("❌ Bekor qilindi.")
        return
    data = await state.get_data()
    await state.finish()
    await callback.message.edit_text("🚀 Yuborish boshlandi...")
    all_users = await _get_combined_users()
    target = data.get("target", "all")
    markup = None
    if data.get("btn_text") and data.get("btn_url"):
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=data["btn_text"], url=data["btn_url"])]
        ])
    count = 0
    failed = 0
    error_msg = ""
    for user_id, info in all_users.items():
        user_state = info.get("state")
        if target == "unregistered" and user_state == state_store.REGISTERED:
            continue
        if target == "registered" and user_state != state_store.REGISTERED:
            continue
        if target == "old_registered":
            if user_state != state_store.REGISTERED:
                continue
            profile = state_store.get_profile(user_id) or {}
            school_val = profile.get("school", "")
            if school_val in ("✅", "❌", "Ha o'qiydi", "Yo'q o'qimaydi"):
                continue
        try:
            await callback.bot.copy_message(
                chat_id=user_id,
                from_chat_id=data["chat_id"],
                message_id=data["message_id"],
                reply_markup=markup
            )
            count += 1
            if count % 20 == 0:
                await asyncio.sleep(0.5)
        except BotBlocked:
            logger.warning("Bot was blocked by user %s", user_id)
            state_store.set_metadata(user_id, "blocked", True)
            failed += 1
            error_msg = "Foydalanuvchi botni bloklagan"
        except UserDeactivated:
            logger.warning("User %s is deactivated", user_id)
            failed += 1
            error_msg = "Foydalanuvchi akkaunti o'chirilgan"
        except Exception as e:
            logger.error("Failed to send broadcast to %s: %s", user_id, e)
            failed += 1
            error_msg = str(e)
    final_text = (
        f"✅ <b>Xabar yuborildi!</b>\n\n"
        f"👤 Qabul qildi: {count}\n"
        f"❌ Xatolik: {failed}"
    )
    if failed > 0:
        final_text += f"\n\n⚠️ Oxirgi xatolik: <code>{error_msg}</code>"
    await callback.message.answer(final_text, parse_mode="HTML", reply_markup=_admin_main_keyboard())

# ── Direct Message with Pagination ───────────────────────────────────────────

async def start_direct_message(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    await message.answer("⌛ Yuklanmoqda...")
    users_list = await _get_all_registered_list()
    if not users_list:
        await message.answer("📋 Hali hech kim ro'yxatdan o'tmagan.")
        return

    await _send_dm_selector(message, users_list, page=0, edit=False)
    await DirectMessageStates.SELECT_USER.set()
    await state.update_data(dm_page=0)


def _dm_user_keyboard(users_list: list, page: int) -> InlineKeyboardMarkup:
    """10 talik sahifada user tugmalari + pagination."""
    start = page * PAGE_SIZE
    end = min(start + PAGE_SIZE, len(users_list))
    total_pages = max(1, (len(users_list) + PAGE_SIZE - 1) // PAGE_SIZE)

    buttons = []
    for u in users_list[start:end]:
        label = f"👤 {u['name'][:18]} | 📱 {u['phone']}"
        buttons.append([InlineKeyboardButton(text=label, callback_data=f"dmsel_{u['uid']}")])

    # Pagination row
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️ Back", callback_data=f"dmpage_{page - 1}"))
    nav.append(InlineKeyboardButton(text=f"📄 {page + 1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="Next ▶️", callback_data=f"dmpage_{page + 1}"))
    if nav:
        buttons.append(nav)

    buttons.append([InlineKeyboardButton(text="🚫 Bekor qilish", callback_data="dm_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def _send_dm_selector(message: types.Message, users_list: list, page: int, edit: bool = False):
    total_pages = max(1, (len(users_list) + PAGE_SIZE - 1) // PAGE_SIZE)
    text = (
        f"👤 <b>Qaysi foydalanuvchiga xabar yubormoqchisiz?</b>\n"
        f"<i>Sahifa {page + 1}/{total_pages} — Jami {len(users_list)} ta</i>"
    )
    markup = _dm_user_keyboard(users_list, page)
    if edit:
        try:
            await message.edit_text(text, parse_mode="HTML", reply_markup=markup)
        except Exception:
            await message.answer(text, parse_mode="HTML", reply_markup=markup)
    else:
        await message.answer(text, parse_mode="HTML", reply_markup=markup)


async def dm_page_callback(callback: types.CallbackQuery, state: FSMContext):
    """DM sahifani almashtirish."""
    if callback.data == "noop":
        await callback.answer()
        return
    if callback.data == "dm_cancel":
        await state.finish()
        await callback.message.edit_text("❌ Bekor qilindi.")
        return

    page = int(callback.data.split("_")[1])
    users_list = await _get_all_registered_list()
    await state.update_data(dm_page=page)
    await _send_dm_selector(callback.message, users_list, page, edit=True)
    await callback.answer()


async def dm_select_user(callback: types.CallbackQuery, state: FSMContext):
    """Foydalanuvchi tanlandi."""
    if callback.data == "dm_cancel":
        await state.finish()
        await callback.message.edit_text("❌ Bekor qilindi.")
        return

    user_id = int(callback.data.split("_")[1])
    # Profile olish
    users_list = await _get_all_registered_list()
    user_info = next((u for u in users_list if u["uid"] == user_id), None)
    name = user_info["name"] if user_info else f"ID: {user_id}"

    await state.update_data(target_user_id=user_id, target_user_name=name)
    await DirectMessageStates.GET_MESSAGE.set()
    await callback.message.edit_text(
        f"✉️ <b>{name}</b> ga yubormoqchi bo'lgan xabaringizni yozing:\n\n"
        "<i>(Matn, rasm, video yoki audio yuborishingiz mumkin)</i>\n"
        "<i>Bekor qilish: /cancel</i>",
        parse_mode="HTML"
    )


async def dm_get_message(message: types.Message, state: FSMContext):
    if message.text and message.text.startswith("/cancel"):
        await state.finish()
        await message.answer("❌ Bekor qilindi.", reply_markup=_admin_main_keyboard())
        return

    await state.update_data(dm_message_id=message.message_id, dm_chat_id=message.chat.id)
    data = await state.get_data()
    name = data.get("target_user_name", "Foydalanuvchi")

    await DirectMessageStates.CONFIRM.set()
    await message.answer(f"👀 <b>Preview — {name} ga yuboriladigan xabar:</b>", parse_mode="HTML")
    await message.bot.copy_message(chat_id=message.chat.id, from_chat_id=message.chat.id, message_id=message.message_id)

    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Yuborish", callback_data="dm_confirm")],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="dm_cancel_confirm")],
    ])
    await message.answer(
        f"⬆️ Yuqoridagi xabar <b>{name}</b> ga yuboriladimi?",
        parse_mode="HTML",
        reply_markup=markup
    )


async def dm_confirm(callback: types.CallbackQuery, state: FSMContext):
    if callback.data == "dm_cancel_confirm":
        await state.finish()
        await callback.message.edit_text("❌ Bekor qilindi.")
        await callback.message.answer("🏠 Admin panel:", reply_markup=_admin_main_keyboard())
        return

    data = await state.get_data()
    await state.finish()
    target_id = data["target_user_id"]
    name = data.get("target_user_name", "Foydalanuvchi")

    try:
        await callback.bot.copy_message(
            chat_id=target_id,
            from_chat_id=data["dm_chat_id"],
            message_id=data["dm_message_id"]
        )
        await callback.message.edit_text(
            f"✅ Xabar <b>{name}</b> (<code>{target_id}</code>) ga muvaffaqiyatli yuborildi!",
            parse_mode="HTML"
        )
    except BotBlocked:
        state_store.set_metadata(target_id, "blocked", True)
        await callback.message.edit_text(
            f"❌ Xabar yuborishda xatolik: <b>{name}</b> botni bloklagan.",
            parse_mode="HTML"
        )
    except UserDeactivated:
        await callback.message.edit_text(
            f"❌ Xabar yuborishda xatolik: <b>{name}</b> o'z akkauntini o'chirgan.",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error("Failed to send DM to %s: %s", target_id, e)
        await callback.message.edit_text(
            f"❌ Xabar yuborishda xatolik: <code>{e}</code>",
            parse_mode="HTML"
        )
    await callback.message.answer("🏠 Admin panel:", reply_markup=_admin_main_keyboard())

# ── Delete User with Pagination ─────────────────────────────────────────────

def _del_user_keyboard(users_list: list, page: int) -> InlineKeyboardMarkup:
    """10 talik sahifada user tugmalari + pagination for deleting."""
    start = page * PAGE_SIZE
    end = min(start + PAGE_SIZE, len(users_list))
    total_pages = max(1, (len(users_list) + PAGE_SIZE - 1) // PAGE_SIZE)

    buttons = []
    for u in users_list[start:end]:
        label = f"🗑 {u['name'][:18]} | 📱 {u['phone']}"
        buttons.append([InlineKeyboardButton(text=label, callback_data=f"delsel_{u['uid']}")])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️ Back", callback_data=f"delpage_{page - 1}"))
    nav.append(InlineKeyboardButton(text=f"📄 {page + 1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="Next ▶️", callback_data=f"delpage_{page + 1}"))
    if nav:
        buttons.append(nav)

    buttons.append([InlineKeyboardButton(text="🚫 Bekor qilish", callback_data="del_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def _send_del_selector(message: types.Message, users_list: list, page: int, edit: bool = False):
    total_pages = max(1, (len(users_list) + PAGE_SIZE - 1) // PAGE_SIZE)
    text = (
        f"🗑 <b>Qaysi foydalanuvchini o'chirmoqchisiz?</b>\n"
        f"<i>Sahifa {page + 1}/{total_pages} — Jami {len(users_list)} ta</i>"
    )
    markup = _del_user_keyboard(users_list, page)
    if edit:
        try:
            await message.edit_text(text, parse_mode="HTML", reply_markup=markup)
        except Exception:
            await message.answer(text, parse_mode="HTML", reply_markup=markup)
    else:
        await message.answer(text, parse_mode="HTML", reply_markup=markup)


async def start_delete_user(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    await message.answer("⌛ Yuklanmoqda...")
    users_list = await _get_all_registered_list()
    if not users_list:
        await message.answer("📋 Hali hech kim ro'yxatdan o'tmagan.")
        return

    await _send_del_selector(message, users_list, page=0, edit=False)
    await DeleteUserStates.SELECT_USER.set()
    await state.update_data(del_page=0)


async def del_page_callback(callback: types.CallbackQuery, state: FSMContext):
    if callback.data == "noop":
        await callback.answer()
        return
    if callback.data == "del_cancel":
        await state.finish()
        await callback.message.edit_text("❌ Bekor qilindi.")
        return

    page = int(callback.data.split("_")[1])
    users_list = await _get_all_registered_list()
    await state.update_data(del_page=page)
    await _send_del_selector(callback.message, users_list, page, edit=True)
    await callback.answer()


async def del_select_user(callback: types.CallbackQuery, state: FSMContext):
    if callback.data == "del_cancel":
        await state.finish()
        await callback.message.edit_text("❌ Bekor qilindi.")
        return

    user_id = int(callback.data.split("_")[1])
    users_list = await _get_all_registered_list()
    user_info = next((u for u in users_list if u["uid"] == user_id), None)
    name = user_info["name"] if user_info else f"ID: {user_id}"

    await state.update_data(target_user_id=user_id, target_user_name=name)
    await DeleteUserStates.CONFIRM.set()
    
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Ha, o'chirish", callback_data="del_confirm")],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="del_cancel_confirm")],
    ])
    await callback.message.edit_text(
        f"⚠️ <b>Diqqat!</b>\n\n"
        f"Siz rostana ham <b>{name}</b> (<code>{user_id}</code>) ni o'chirib tashlamoqchimisiz?\n"
        f"Bu amalni ortga qaytarib bo'lmaydi!",
        parse_mode="HTML",
        reply_markup=markup
    )


async def del_confirm(callback: types.CallbackQuery, state: FSMContext):
    if callback.data == "del_cancel_confirm":
        await state.finish()
        await callback.message.edit_text("❌ Bekor qilindi.")
        await callback.message.answer("🏠 Admin panel:", reply_markup=_admin_main_keyboard())
        return

    data = await state.get_data()
    await state.finish()
    target_id = data["target_user_id"]
    name = data.get("target_user_name", "Foydalanuvchi")

    await callback.message.edit_text("⌛ O'chirilmoqda...")

    # Bazadan o'chirish
    state_store.delete_user(target_id)
    sheets.delete_row_by_tid(target_id)

    await callback.message.edit_text(
        f"✅ <b>{name}</b> (<code>{target_id}</code>) muvaffaqiyatli o'chirildi!",
        parse_mode="HTML"
    )
    await callback.message.answer("🏠 Admin panel:", reply_markup=_admin_main_keyboard())

# ── Registration ───────────────────────────────────────────────────────────────

def register_admin_handlers(dp: Dispatcher):
    dp.register_message_handler(cmd_admin, commands=["admin"], state="*")
    dp.register_message_handler(show_stats, lambda m: m.text == "📊 Statistika", state="*")
    dp.register_message_handler(show_video_stats, lambda m: m.text == "🎬 Video statistika", state="*")
    dp.register_message_handler(show_registered_users, lambda m: m.text == "📋 Ro'yxatdan o'tganlar", state="*")
    dp.register_message_handler(show_unregistered_users, lambda m: m.text == "⏳ Ro'yxatdan o'tmaganlar", state="*")
    dp.register_message_handler(start_broadcast, lambda m: m.text == "📢 Xabar yuborish", state="*")
    dp.register_message_handler(start_direct_message, lambda m: m.text == "👤 Alohida xabar", state="*")
    dp.register_message_handler(start_delete_user, lambda m: m.text == "🗑 Foydalanuvchini o'chirish", state="*")

    # Broadcast FSM
    dp.register_callback_query_handler(set_target, state=BroadcastStates.SELECT_AUDIENCE)
    dp.register_message_handler(get_content, content_types=types.ContentType.ANY, state=BroadcastStates.GET_CONTENT)
    dp.register_callback_query_handler(skip_button, lambda c: c.data == "skip_button", state=BroadcastStates.GET_BUTTON)
    dp.register_message_handler(get_button, state=BroadcastStates.GET_BUTTON)
    dp.register_callback_query_handler(execute_broadcast, state=BroadcastStates.CONFIRM)

    dp.register_callback_query_handler(
        registered_pagination,
        lambda c: c.data and (c.data.startswith("reglist_page_") or c.data == "noop"),
        state="*",
    )
    
    # Unregistered list pagination
    dp.register_callback_query_handler(
        unregistered_pagination,
        lambda c: c.data and c.data.startswith("unreglist_page_"),
        state="*",
    )

    # Direct Message FSM — pagination
    dp.register_callback_query_handler(
        dm_page_callback,
        lambda c: c.data and (c.data.startswith("dmpage_") or c.data in ("dm_cancel", "noop")),
        state=DirectMessageStates.SELECT_USER,
    )
    # Direct Message FSM — user tanlash
    dp.register_callback_query_handler(
        dm_select_user,
        lambda c: c.data and c.data.startswith("dmsel_"),
        state=DirectMessageStates.SELECT_USER,
    )
    dp.register_message_handler(dm_get_message, content_types=types.ContentType.ANY, state=DirectMessageStates.GET_MESSAGE)
    dp.register_callback_query_handler(dm_confirm, lambda c: c.data in ("dm_confirm", "dm_cancel_confirm"), state=DirectMessageStates.CONFIRM)

    # Delete User FSM
    dp.register_callback_query_handler(
        del_page_callback,
        lambda c: c.data and (c.data.startswith("delpage_") or c.data in ("del_cancel", "noop")),
        state=DeleteUserStates.SELECT_USER,
    )
    dp.register_callback_query_handler(
        del_select_user,
        lambda c: c.data and c.data.startswith("delsel_"),
        state=DeleteUserStates.SELECT_USER,
    )
    dp.register_callback_query_handler(del_confirm, lambda c: c.data in ("del_confirm", "del_cancel_confirm"), state=DeleteUserStates.CONFIRM)
