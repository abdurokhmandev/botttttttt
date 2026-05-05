import asyncio
import logging
from aiogram import Dispatcher, types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

from config import ADMIN_IDS, VIDEOS
from storage import state_store, video_stats
from services import sheets

logger = logging.getLogger(__name__)

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

# ── Keyboards ─────────────────────────────────────────────────────────────────

def _admin_main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton("📢 Xabar yuborish"), KeyboardButton("👤 Alohida xabar")],
            [KeyboardButton("📊 Statistika"), KeyboardButton("🎬 Video statistika")],
            [KeyboardButton("📋 Ro'yxatdan o'tganlar")],
        ],
        resize_keyboard=True
    )

def _audience_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Barchaga", callback_data="target_all")],
        [InlineKeyboardButton(text="❌ Ro'yxatdan o'tmaganlarga", callback_data="target_unregistered")],
        [InlineKeyboardButton(text="✅ Ro'yxatdan o'tganlarga", callback_data="target_registered")],
        [InlineKeyboardButton(text="🚫 Bekor qilish", callback_data="cancel_broadcast")],
    ])

def _confirm_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Tasdiqlash", callback_data="confirm_broadcast")],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_broadcast")],
    ])

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

# ── Admin Main ────────────────────────────────────────────────────────────────

async def cmd_admin(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return

    await message.answer(
        "👋 Admin panelga xush kelibsiz!",
        reply_markup=_admin_main_keyboard()
    )

# ── Statistics ────────────────────────────────────────────────────────────────

async def show_stats(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return

    await message.answer("⌛ Statistika hisoblanmoqda...")
    all_users = await _get_combined_users()
    total = len(all_users)
    registered = sum(1 for u in all_users.values() if u.get("state") == state_store.REGISTERED)

    text = (
        "📊 <b>Bot Statistikasi:</b>\n\n"
        f"👥 Umumiy foydalanuvchilar: {total}\n"
        f"✅ Ro'yxatdan o'tganlar: {registered}\n"
        f"⏳ Ro'yxatdan o'tmaganlar: {total - registered}"
    )
    await message.answer(text, parse_mode="HTML")


async def show_video_stats(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return

    stats = video_stats.get_all()
    if not stats:
        await message.answer("📊 Hali hech kim video tanlamagan.")
        return

    # Sort by count descending
    sorted_stats = sorted(stats.items(), key=lambda x: x[1], reverse=True)

    lines = ["🎬 <b>Video Ko'rish Statistikasi:</b>\n"]
    total_views = sum(stats.values())

    for rank, (idx, count) in enumerate(sorted_stats, 1):
        title = VIDEOS.get(idx, {}).get("title", f"Video {idx}")
        bar_len = int((count / total_views) * 15) if total_views > 0 else 0
        bar = "█" * bar_len + "░" * (15 - bar_len)
        medal = ["🥇", "🥈", "🥉"][rank - 1] if rank <= 3 else f"#{rank}"
        lines.append(f"{medal} <b>{title[:35]}</b>\n   {bar} {count} marta\n")

    lines.append(f"\n📈 Jami ko'rishlar: <b>{total_views}</b>")
    await message.answer("\n".join(lines), parse_mode="HTML")

# ── Registered Users List ─────────────────────────────────────────────────────

async def show_registered_users(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return

    await message.answer("⌛ Ro'yxatdan o'tganlar yuklanmoqda...")

    # Avval local cache dan olamiz
    local_profiles = state_store.get_all_registered_profiles()

    # Agar local bo'sh bo'lsa, Google Sheets'dan olamiz
    if not local_profiles:
        sheet_ids = sheets.get_all_registered_ids()
        if not sheet_ids:
            await message.answer("📋 Hali hech kim ro'yxatdan o'tmagan.")
            return

        lines = ["📋 <b>Ro'yxatdan o'tganlar (Google Sheets):</b>\n"]
        for i, tid in enumerate(sheet_ids, 1):
            lines.append(f"{i}. <code>{tid}</code>")
        lines.append(f"\n✅ Jami: {len(sheet_ids)} ta")
        await message.answer("\n".join(lines), parse_mode="HTML")
        return

    lines = ["📋 <b>Ro'yxatdan o'tganlar:</b>\n"]
    for i, (uid, info) in enumerate(local_profiles.items(), 1):
        name = info.get("name", "—")
        phone = info.get("phone", "—")
        grade = info.get("grade", "—")
        district = info.get("district", "—")
        lines.append(
            f"{i}. 👤 <b>{name}</b>\n"
            f"   📱 {phone} | 🎓 {grade} | 📍 {district}\n"
            f"   🆔 <code>{uid}</code>\n"
        )

    lines.append(f"✅ Jami: {len(local_profiles)} ta")

    # Telegram message 4096 belgi bilan cheklangan
    text = "\n".join(lines)
    if len(text) > 4000:
        # Bo'lib yuboramiz
        chunks = []
        current = ""
        for line in lines:
            if len(current) + len(line) > 3800:
                chunks.append(current)
                current = line + "\n"
            else:
                current += line + "\n"
        if current:
            chunks.append(current)
        for chunk in chunks:
            await message.answer(chunk, parse_mode="HTML")
    else:
        await message.answer(text, parse_mode="HTML")

# ── Broadcast Flow ────────────────────────────────────────────────────────────

async def start_broadcast(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return

    await BroadcastStates.SELECT_AUDIENCE.set()
    await message.answer(
        "🎯 Kimlarga xabar yubormoqchisiz?",
        reply_markup=_audience_keyboard()
    )

async def set_target(callback: types.CallbackQuery, state: FSMContext):
    if callback.data == "cancel_broadcast":
        await state.finish()
        await callback.message.edit_text("❌ Bekor qilindi.")
        return

    if callback.data == "target_all":
        target = "all"
    elif callback.data == "target_registered":
        target = "registered"
    else:
        target = "unregistered"

    await state.update_data(target=target)

    await BroadcastStates.GET_CONTENT.set()
    await callback.message.edit_text(
        "📝 Yubormoqchi bo'lgan xabaringizni yuboring (matn, rasm, video va h.k.):"
    )

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

    await callback.message.answer(
        final_text,
        parse_mode="HTML",
        reply_markup=_admin_main_keyboard()
    )

# ── Direct Message (Alohida xabar) ───────────────────────────────────────────

async def start_direct_message(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return

    # Ro'yxatdan o'tganlar ro'yxatini ko'rsat
    local_profiles = state_store.get_all_registered_profiles()
    sheet_ids = sheets.get_all_registered_ids()

    # Barcha registered IDlarni birlashtirish
    all_reg_ids = set(local_profiles.keys()) | set(sheet_ids)

    if not all_reg_ids:
        await message.answer("📋 Hali hech kim ro'yxatdan o'tmagan.")
        return

    # Inline keyboard yasaymiz (har biri alohida tugma)
    buttons = []
    for uid in list(all_reg_ids)[:50]:  # Max 50 ta
        profile = local_profiles.get(uid, {})
        name = profile.get("name", f"ID: {uid}")
        btn_label = f"👤 {name[:20]} ({uid})"
        buttons.append([InlineKeyboardButton(text=btn_label, callback_data=f"dm_{uid}")])

    buttons.append([InlineKeyboardButton(text="🚫 Bekor qilish", callback_data="dm_cancel")])
    markup = InlineKeyboardMarkup(inline_keyboard=buttons)

    await DirectMessageStates.SELECT_USER.set()
    await message.answer(
        "👤 Qaysi o'quvchiga xabar yubormoqchisiz?\n\n"
        f"<i>Jami {len(all_reg_ids)} ta ro'yxatdan o'tgan foydalanuvchi</i>",
        parse_mode="HTML",
        reply_markup=markup
    )

async def dm_select_user(callback: types.CallbackQuery, state: FSMContext):
    if callback.data == "dm_cancel":
        await state.finish()
        await callback.message.edit_text("❌ Bekor qilindi.")
        return

    user_id = int(callback.data.split("_")[1])
    profile = state_store.get_profile(user_id)
    name = profile.get("name", f"ID: {user_id}") if profile else f"ID: {user_id}"

    await state.update_data(target_user_id=user_id, target_user_name=name)
    await DirectMessageStates.GET_MESSAGE.set()

    await callback.message.edit_text(
        f"✉️ <b>{name}</b> ga yubormoqchi bo'lgan xabaringizni yozing:\n\n"
        "<i>(Matn, rasm, video yoki audio yuborishingiz mumkin)</i>",
        parse_mode="HTML"
    )

async def dm_get_message(message: types.Message, state: FSMContext):
    await state.update_data(
        dm_message_id=message.message_id,
        dm_chat_id=message.chat.id
    )

    data = await state.get_data()
    name = data.get("target_user_name", "Foydalanuvchi")

    await DirectMessageStates.CONFIRM.set()

    # Preview
    await message.answer(f"👀 <b>Preview — {name} ga yuboriladigan xabar:</b>", parse_mode="HTML")
    await message.bot.copy_message(
        chat_id=message.chat.id,
        from_chat_id=message.chat.id,
        message_id=message.message_id
    )

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
            f"✅ Xabar <b>{name}</b> ga muvaffaqiyatli yuborildi!",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error("Failed to send DM to %s: %s", target_id, e)
        await callback.message.edit_text(
            f"❌ Xabar yuborishda xatolik: <code>{e}</code>",
            parse_mode="HTML"
        )

    await callback.message.answer("🏠 Admin panel:", reply_markup=_admin_main_keyboard())

# ── Registration ───────────────────────────────────────────────────────────────

def register_admin_handlers(dp: Dispatcher):
    dp.register_message_handler(cmd_admin, commands=["admin"], state="*")
    dp.register_message_handler(show_stats, lambda m: m.text == "📊 Statistika", state="*")
    dp.register_message_handler(show_video_stats, lambda m: m.text == "🎬 Video statistika", state="*")
    dp.register_message_handler(show_registered_users, lambda m: m.text == "📋 Ro'yxatdan o'tganlar", state="*")
    dp.register_message_handler(start_broadcast, lambda m: m.text == "📢 Xabar yuborish", state="*")
    dp.register_message_handler(start_direct_message, lambda m: m.text == "👤 Alohida xabar", state="*")

    # Broadcast FSM
    dp.register_callback_query_handler(set_target, state=BroadcastStates.SELECT_AUDIENCE)
    dp.register_message_handler(get_content, content_types=types.ContentType.ANY, state=BroadcastStates.GET_CONTENT)
    dp.register_callback_query_handler(skip_button, lambda c: c.data == "skip_button", state=BroadcastStates.GET_BUTTON)
    dp.register_message_handler(get_button, state=BroadcastStates.GET_BUTTON)
    dp.register_callback_query_handler(execute_broadcast, state=BroadcastStates.CONFIRM)

    # Direct Message FSM
    dp.register_callback_query_handler(dm_select_user, lambda c: c.data.startswith("dm_"), state=DirectMessageStates.SELECT_USER)
    dp.register_message_handler(dm_get_message, content_types=types.ContentType.ANY, state=DirectMessageStates.GET_MESSAGE)
    dp.register_callback_query_handler(dm_confirm, lambda c: c.data in ("dm_confirm", "dm_cancel_confirm"), state=DirectMessageStates.CONFIRM)
