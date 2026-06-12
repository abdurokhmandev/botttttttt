import logging

from aiogram import Dispatcher, types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import ADMIN_IDS, PODCASTS, WEBAPP_URL

from storage.podcast_store import save_podcast

logger = logging.getLogger(__name__)


# ── FSM ───────────────────────────────────────────────────────────────────────

class AddPodcastStates(StatesGroup):
    GET_FILE     = State()   # Audio, Video yoki URL
    GET_TITLE    = State()   # Sarlavha
    GET_URL      = State()   # Tashqi havola (ixtiyoriy)
    GET_DESC     = State()   # Tavsif (ixtiyoriy)
    CONFIRM      = State()   # Tasdiqlash

# ── Keyboards ─────────────────────────────────────────────────────────────────

def _podcast_list_text() -> str:
    """Suhbatlar ro'yxati matni."""
    if not PODCASTS:
        return "📹 Hozircha suhbatlar mavjud emas."
    lines = []
    for idx in sorted(PODCASTS.keys()):
        item = PODCASTS[idx]
        title = item.get("title", f"Suhbat {idx}")
        media_type = item.get("type", "audio")
        emoji = "📹" if media_type == "video" else "🎧"
        lines.append(f"<b>{idx}.</b> {emoji} {title}")
    return "\n".join(lines)


def _podcast_list_keyboard() -> InlineKeyboardMarkup:
    """Suhbatlar uchun raqamli tugmalar."""
    if not PODCASTS:
        return InlineKeyboardMarkup(inline_keyboard=[])
    
    buttons = []
    for idx in sorted(PODCASTS.keys()):
        buttons.append(InlineKeyboardButton(text=str(idx), callback_data=f"podcast_{idx}"))
    
    # Har bir qatorda 5 tadan tugma
    rows = [buttons[i:i + 5] for i in range(0, len(buttons), 5)]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _podcast_action_keyboard(idx: int) -> InlineKeyboardMarkup:
    """Suhbat yuborilgandan keyin chiqadigan tugmalar."""
    rows = []
    url = PODCASTS.get(idx, {}).get("url", "").strip()
    if url:
        rows.append([InlineKeyboardButton(text="🔗 To'liq ko'rish", url=url)])
    rows.append([InlineKeyboardButton(text="🏫 Rahimov School", callback_data="school_info")])
    rows.append([InlineKeyboardButton(text="◀️ Suhbatlar ro'yxati", callback_data="podcasts_back_list")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _confirm_add_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Qo'shish", callback_data="podcast_add_confirm")],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="podcast_add_cancel")],
    ])

# ── User Handlers ─────────────────────────────────────────────────────────────

async def show_podcast_list(message: types.Message) -> None:
    """Foydalanuvchi 📹 Rahimov Suhbatlari tugmasini bosganida."""
    if not PODCASTS:
        await message.answer("📹 Hozircha suhbatlar mavjud emas. Tez orada qo'shiladi!")
        return
    
    text = (
        "🎧 <b>Qaysi darsni tinglamoqchisiz?</b>\n\n"
        f"{_podcast_list_text()}"
    )
    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=_podcast_list_keyboard()
    )


async def handle_podcast_callback(callback: types.CallbackQuery) -> None:
    """Suhbat tanlanganda audio/video yuborish + avtomatik tugmalar."""
    await callback.answer()

    if callback.data == "podcasts_back_list":
        if not PODCASTS:
            await callback.message.edit_text("📹 Hozircha suhbatlar mavjud emas.")
            return
        await callback.message.edit_text(
            "📹 <b>Rahimov Suhbatlari</b>\n\nQaysi suhbatni tinglamoqchisiz?",
            parse_mode="HTML",
            reply_markup=_podcast_list_keyboard()
        )
        return

    try:
        idx = int(callback.data.split("_")[1])
    except (IndexError, ValueError):
        return

    data = PODCASTS.get(idx)
    if not data:
        await callback.message.answer("⚠️ Suhbat topilmadi.")
        return

    user_id = callback.from_user.id
    from storage import state_store
    import time

    current_state = state_store.get_state(user_id)
    came_from_funnel = (current_state == state_store.WANT_MORE_ASKED)
    should_track_funnel = (user_id not in ADMIN_IDS and current_state != state_store.REGISTERED)

    if should_track_funnel:
        state_store.set_state(user_id, state_store.PODCAST_SELECTED)
    state_store.set_metadata(user_id, "podcast_selected_ts", time.time())


    title       = data.get("title", f"Suhbat {idx}")
    description = data.get("description", "")
    file_id     = data.get("audio", "").strip()
    file_type   = data.get("type", "audio") # audio yoki video
    markup      = _podcast_action_keyboard(idx)

    emoji = "📹" if file_type == "video" else "🎧"
    caption = f"<b>{emoji} {title}</b>"
    if description:
        caption += f"\n\n{description}"
    caption += "\n\n🏫 Rahimov School suhbatlari"

    if file_id:
        try:
            if file_type == "video":
                await callback.message.answer_video(
                    video=file_id,
                    caption=caption,
                    parse_mode="HTML",
                    reply_markup=markup
                )
            else:
                await callback.message.answer_audio(
                    audio=file_id,
                    caption=caption,
                    parse_mode="HTML",
                    reply_markup=markup,
                    title=title,
                    performer="Rahimov School"
                )
            # Video yuborildi — 30 daqiqa kutish boshlaydi
            if should_track_funnel:
                state_store.set_state(user_id, state_store.VIDEO_SENT)
                state_store.set_metadata(user_id, "video_sent_ts", time.time())
            state_store.set_metadata(user_id, "last_video_idx", idx)
            if came_from_funnel:
                import asyncio
                from handlers.funnel import send_like_question
                asyncio.create_task(send_like_question(callback.message.bot, user_id))
            return
        except Exception as e:
            logger.error("Suhbat yuborishda xatolik (idx=%d, type=%s): %s", idx, file_type, e)
            # Agar audio deb xato bersa, video qilib ko'ramiz (fallback)
            try:
                await callback.message.answer_video(video=file_id, caption=caption, parse_mode="HTML", reply_markup=markup)
                if should_track_funnel:
                    state_store.set_state(user_id, state_store.VIDEO_SENT)
                    state_store.set_metadata(user_id, "video_sent_ts", time.time())
                state_store.set_metadata(user_id, "last_video_idx", idx)
                if came_from_funnel:
                    import asyncio
                    from handlers.funnel import send_like_question
                    asyncio.create_task(send_like_question(callback.message.bot, user_id))
                return
            except:
                pass

    # Faqat matn
    await callback.message.answer(caption, parse_mode="HTML", reply_markup=markup)
    if should_track_funnel:
        state_store.set_state(user_id, state_store.VIDEO_SENT)
        state_store.set_metadata(user_id, "video_sent_ts", time.time())
    state_store.set_metadata(user_id, "last_video_idx", idx)
    if came_from_funnel:
        import asyncio
        from handlers.funnel import send_like_question
        asyncio.create_task(send_like_question(callback.message.bot, user_id))


# ── Admin: Suhbat qo'shish ───────────────────────────────────────────────────

async def admin_add_podcast(message: types.Message, state: FSMContext):
    """Admin /addpodcast yoki tugma orqali suhbat qo'shadi."""
    if message.from_user.id not in ADMIN_IDS:
        return
    await AddPodcastStates.GET_FILE.set()
    await message.answer(
        "📹 <b>Yangi suhbat qo'shish</b>\n\n"
        "1️⃣ Suhbat <b>video</b> yoki <b>audio</b> faylini yuboring:",
        parse_mode="HTML"
    )


async def ap_get_file(message: types.Message, state: FSMContext):
    """Fayl qabul qilindi."""
    if message.video:
        await state.update_data(audio=message.video.file_id, type="video")
    elif message.audio:
        await state.update_data(audio=message.audio.file_id, type="audio")
    elif message.document and message.document.mime_type.startswith("video/"):
        await state.update_data(audio=message.document.file_id, type="video")
    elif message.text and (message.text.startswith("http://") or message.text.startswith("https://")):
        await state.update_data(audio=message.text.strip(), type="audio")
    else:
        await message.answer("❌ Iltimos, video yoki audio fayl yuboring.")
        return

    await AddPodcastStates.GET_TITLE.set()
    await message.answer("2️⃣ Suhbat <b>nomini</b> kiriting:", parse_mode="HTML")


async def ap_get_title(message: types.Message, state: FSMContext):
    """Sarlavha qabul qilindi."""
    await state.update_data(title=message.text.strip())
    await AddPodcastStates.GET_URL.set()
    await message.answer(
        "3️⃣ Suhbat uchun <b>havola (link)</b> kiriting (ixtiyoriy):\n"
        "<i>O'tkazib yuborish uchun — /skip yozing</i>",
        parse_mode="HTML"
    )


async def ap_get_url(message: types.Message, state: FSMContext):
    """URL qabul qilindi."""
    if message.text and message.text.strip() == "/skip":
        await state.update_data(url="")
    else:
        await state.update_data(url=message.text.strip())
    
    await AddPodcastStates.GET_DESC.set()
    await message.answer(
        "4️⃣ Suhbat <b>tavsifini</b> kiriting (ixtiyoriy):\n"
        "<i>O'tkazib yuborish uchun — /skip yozing</i>",
        parse_mode="HTML"
    )


async def ap_get_desc(message: types.Message, state: FSMContext):
    """Tavsif qabul qilindi — tasdiqlash."""
    if message.text and message.text.strip() == "/skip":
        await state.update_data(description="")
    else:
        await state.update_data(description=message.text.strip())

    data = await state.get_data()
    idx  = max(PODCASTS.keys(), default=0) + 1

    preview = (
        f"✅ <b>Yangi Suhbat #{idx}</b>\n\n"
        f"📹 Nomi: <b>{data.get('title', '—')}</b>\n"
        f"🔗 Havola: {data.get('url', '—') or '—'}\n"
        f"📝 Tavsif: {data.get('description', '—') or '—'}\n"
        f"📁 Fayl turi: <b>{data.get('type', 'audio')}</b>\n\n"
        "Qo'shilsinmi?"
    )
    await state.update_data(new_index=idx)
    await AddPodcastStates.CONFIRM.set()
    await message.answer(preview, parse_mode="HTML", reply_markup=_confirm_add_keyboard())


async def ap_confirm(callback: types.CallbackQuery, state: FSMContext):
    """Suhbat qo'shish tasdiqlandi."""
    if callback.data == "podcast_add_cancel":
        await state.finish()
        await callback.message.edit_text("❌ Bekor qilindi.")
        return

    data = await state.get_data()
    idx  = data.get("new_index", max(PODCASTS.keys(), default=0) + 1)

    from config import clean_title
    podcast_data = {
        "title":       clean_title(data.get("title", "")),
        "description": data.get("description", ""),
        "audio":       data.get("audio", ""),
        "url":         data.get("url", ""),
        "type":        data.get("type", "audio"),
    }
    
    # Doimiy xotiraga saqlash
    save_podcast(idx, podcast_data)
    
    # RAM dagi dict ni yangilash
    PODCASTS[idx] = podcast_data

    await state.finish()

    # Env variable ko'rinishida chiqaramiz
    env_hint = (
        f"\n\n📋 <b>Railway ENV uchun:</b>\n"
        f"<code>PODCAST_{idx}_TITLE={podcast_data['title']}</code>\n"
        f"<code>PODCAST_{idx}_AUDIO={podcast_data['audio']}</code>"
    )
    if podcast_data.get("description"):
        env_hint += f"\n<code>PODCAST_{idx}_DESCRIPTION={podcast_data['description']}</code>"
    if podcast_data.get("url"):
        env_hint += f"\n<code>PODCAST_{idx}_URL={podcast_data['url']}</code>"

    await callback.message.edit_text(
        f"✅ <b>Suhbat #{idx} muvaffaqiyatli qo'shildi!</b>\n"
        f"📹 <b>{podcast_data['title']}</b>\n"
        f"{env_hint}\n\n"
        "💡 Suhbat doimiy saqlab qolindi. Railway ENV'ga qo'shib qo'yish tavsiya etiladi.",
        parse_mode="HTML"
    )

# ── Registration ───────────────────────────────────────────────────────────────

def register_podcast_handlers(dp: Dispatcher) -> None:
    # Foydalanuvchi
    dp.register_message_handler(show_podcast_list, text="📹 Rahimov Suhbatlari")
    dp.register_callback_query_handler(
        handle_podcast_callback,
        lambda c: c.data and (c.data.startswith("podcast_") or c.data == "podcasts_back_list"),
    )

    # Admin: suhbat qo'shish FSM
    dp.register_message_handler(admin_add_podcast, commands=["addsuhbat"], state="*")
    dp.register_message_handler(admin_add_podcast, text="📹 Suhbat qo'shish", state="*")
    dp.register_message_handler(ap_get_file, content_types=types.ContentType.ANY, state=AddPodcastStates.GET_FILE)
    dp.register_message_handler(ap_get_title, state=AddPodcastStates.GET_TITLE)
    dp.register_message_handler(ap_get_url,   state=AddPodcastStates.GET_URL)
    dp.register_message_handler(ap_get_desc,  state=AddPodcastStates.GET_DESC)
    dp.register_callback_query_handler(
        ap_confirm,
        lambda c: c.data in ("podcast_add_confirm", "podcast_add_cancel"),
        state=AddPodcastStates.CONFIRM
    )
