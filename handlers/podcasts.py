import logging

from aiogram import Dispatcher, types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import ADMIN_IDS, PODCASTS

logger = logging.getLogger(__name__)

# ── FSM ───────────────────────────────────────────────────────────────────────

class AddPodcastStates(StatesGroup):
    GET_AUDIO    = State()   # Audio fayl yoki URL
    GET_TITLE    = State()   # Sarlavha
    GET_DESC     = State()   # Tavsif (ixtiyoriy)
    GET_URL      = State()   # Tashqi havola (ixtiyoriy)
    CONFIRM      = State()   # Tasdiqlash

# ── Keyboards ─────────────────────────────────────────────────────────────────

def _podcast_list_keyboard() -> InlineKeyboardMarkup:
    """Barcha podcastlar ro'yxati."""
    if not PODCASTS:
        return InlineKeyboardMarkup(inline_keyboard=[])
    rows = []
    for idx in sorted(PODCASTS.keys()):
        title = PODCASTS[idx].get("title", f"Podcast {idx}")
        rows.append([InlineKeyboardButton(
            text=f"🎙 {idx}. {title[:40]}",
            callback_data=f"podcast_{idx}"
        )])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _podcast_action_keyboard(idx: int) -> InlineKeyboardMarkup:
    """Podcast yuborilgandan keyin chiqadigan tugmalar."""
    rows = []
    url = PODCASTS.get(idx, {}).get("url", "").strip()
    if url:
        rows.append([InlineKeyboardButton(text="🔗 To'liq ko'rish", url=url)])
    rows.append([InlineKeyboardButton(text="🏫 Rahimov School", callback_data="school_info")])
    rows.append([InlineKeyboardButton(text="◀️ Podcastlar ro'yxati", callback_data="podcasts_back_list")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _confirm_add_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Qo'shish", callback_data="podcast_add_confirm")],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="podcast_add_cancel")],
    ])

# ── User Handlers ─────────────────────────────────────────────────────────────

async def show_podcast_list(message: types.Message) -> None:
    """Foydalanuvchi 🎧 Podcastlar tugmasini bosganida."""
    if not PODCASTS:
        await message.answer("🎙 Hozircha podcastlar mavjud emas. Tez orada qo'shiladi!")
        return
    await message.answer(
        "🎙 <b>Podcastlar ro'yxati</b>\n\nQaysi podcastni tinglamoqchisiz?",
        parse_mode="HTML",
        reply_markup=_podcast_list_keyboard()
    )


async def handle_podcast_callback(callback: types.CallbackQuery) -> None:
    """Podcast tanlanganda audio yuborish + avtomatik tugmalar."""
    await callback.answer()

    if callback.data == "podcasts_back_list":
        if not PODCASTS:
            await callback.message.edit_text("🎙 Hozircha podcastlar mavjud emas.")
            return
        await callback.message.edit_text(
            "🎙 <b>Podcastlar ro'yxati</b>\n\nQaysi podcastni tinglamoqchisiz?",
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
        await callback.message.answer("⚠️ Podcast topilmadi.")
        return

    title       = data.get("title", f"Podcast {idx}")
    description = data.get("description", "")
    audio       = data.get("audio", "").strip()
    markup      = _podcast_action_keyboard(idx)

    caption = f"<b>🎙 {title}</b>"
    if description:
        caption += f"\n\n{description}"
    caption += "\n\n🏫 Rahimov School podcastlari"

    if audio:
        try:
            await callback.message.answer_audio(
                audio=audio,
                caption=caption,
                parse_mode="HTML",
                reply_markup=markup,
                title=title,
                performer="Rahimov School"
            )
            return
        except Exception as e:
            logger.error("Podcast audio yuborishda xatolik (idx=%d): %s", idx, e)

    # Audio yo'q bo'lsa — faqat matn
    await callback.message.answer(caption, parse_mode="HTML", reply_markup=markup)


# ── Admin: Podcast qo'shish ───────────────────────────────────────────────────

async def admin_add_podcast(message: types.Message, state: FSMContext):
    """Admin /addpodcast yoki tugma orqali podcast qo'shadi."""
    if message.from_user.id not in ADMIN_IDS:
        return
    await AddPodcastStates.GET_AUDIO.set()
    await message.answer(
        "🎙 <b>Yangi podcast qo'shish</b>\n\n"
        "1️⃣ Audio faylni yuboring (yoki URL kiriting):",
        parse_mode="HTML"
    )


async def ap_get_audio(message: types.Message, state: FSMContext):
    """Audio qabul qilindi."""
    if message.audio:
        # Telegram audio file_id saqlaymiz
        file_id = message.audio.file_id
        await state.update_data(audio=file_id)
    elif message.text and (message.text.startswith("http://") or message.text.startswith("https://")):
        await state.update_data(audio=message.text.strip())
    else:
        await message.answer("❌ Audio fayl yoki URL yuboring.")
        return

    await AddPodcastStates.GET_TITLE.set()
    await message.answer("2️⃣ Podcast sarlavhasini kiriting:")


async def ap_get_title(message: types.Message, state: FSMContext):
    """Sarlavha qabul qilindi."""
    await state.update_data(title=message.text.strip())
    await AddPodcastStates.GET_DESC.set()
    await message.answer(
        "3️⃣ Tavsif kiriting (ixtiyoriy):\n"
        "<i>O'tkazib yuborish uchun — kiritmang, /skip yozing</i>",
        parse_mode="HTML"
    )


async def ap_get_desc(message: types.Message, state: FSMContext):
    """Tavsif qabul qilindi."""
    if message.text and message.text.strip() == "/skip":
        await state.update_data(description="")
    else:
        await state.update_data(description=message.text.strip())
    await AddPodcastStates.GET_URL.set()
    await message.answer(
        "4️⃣ Tashqi havola (YouTube, Spotify va h.k.) kiriting (ixtiyoriy):\n"
        "<i>O'tkazib yuborish uchun — /skip yozing</i>",
        parse_mode="HTML"
    )


async def ap_get_url(message: types.Message, state: FSMContext):
    """URL qabul qilindi — tasdiqlash."""
    if message.text and message.text.strip() == "/skip":
        await state.update_data(url="")
    else:
        await state.update_data(url=message.text.strip())

    data = await state.get_data()
    idx  = max(PODCASTS.keys(), default=0) + 1  # Keyingi index

    preview = (
        f"✅ <b>Podcast #{idx}</b>\n\n"
        f"🎙 Sarlavha: <b>{data.get('title', '—')}</b>\n"
        f"📝 Tavsif: {data.get('description', '—') or '—'}\n"
        f"🔗 URL: {data.get('url', '—') or '—'}\n"
        f"📁 Audio: <code>{data.get('audio', '—')[:50]}...</code>\n\n"
        "Qo'shilsinmi?"
    )
    await state.update_data(new_index=idx)
    await AddPodcastStates.CONFIRM.set()
    await message.answer(preview, parse_mode="HTML", reply_markup=_confirm_add_keyboard())


async def ap_confirm(callback: types.CallbackQuery, state: FSMContext):
    """Podcast qo'shish tasdiqlandi."""
    if callback.data == "podcast_add_cancel":
        await state.finish()
        await callback.message.edit_text("❌ Bekor qilindi.")
        return

    data = await state.get_data()
    idx  = data.get("new_index", max(PODCASTS.keys(), default=0) + 1)

    # PODCASTS dict ga qo'shamiz (RAM ichida — bot restart bo'lsa qaytadi)
    PODCASTS[idx] = {
        "title":       data.get("title", ""),
        "description": data.get("description", ""),
        "audio":       data.get("audio", ""),
        "url":         data.get("url", ""),
    }

    await state.finish()

    # Env variable ko'rinishida chiqaramiz (Railway ga qo'yish uchun)
    env_hint = (
        f"\n\n📋 <b>Railway ENV uchun:</b>\n"
        f"<code>PODCAST_{idx}_TITLE={data.get('title', '')}</code>\n"
        f"<code>PODCAST_{idx}_AUDIO={data.get('audio', '')}</code>"
    )
    if data.get("description"):
        env_hint += f"\n<code>PODCAST_{idx}_DESCRIPTION={data.get('description', '')}</code>"
    if data.get("url"):
        env_hint += f"\n<code>PODCAST_{idx}_URL={data.get('url', '')}</code>"

    await callback.message.edit_text(
        f"✅ <b>Podcast #{idx} qo'shildi!</b>\n"
        f"🎙 <b>{data.get('title', '')}</b>\n"
        f"{env_hint}\n\n"
        "⚠️ Bot qayta ishga tushirilsa, yuqoridagi ENV o'zgaruvchilarini Railway ga qo'shing!",
        parse_mode="HTML"
    )

# ── Registration ───────────────────────────────────────────────────────────────

def register_podcast_handlers(dp: Dispatcher) -> None:
    # Foydalanuvchi
    dp.register_message_handler(show_podcast_list, text="🎙 Podcastlar")
    dp.register_callback_query_handler(
        handle_podcast_callback,
        lambda c: c.data and (c.data.startswith("podcast_") or c.data == "podcasts_back_list"),
    )

    # Admin: podcast qo'shish FSM
    dp.register_message_handler(admin_add_podcast, commands=["addpodcast"], state="*")
    dp.register_message_handler(ap_get_audio, content_types=types.ContentType.ANY, state=AddPodcastStates.GET_AUDIO)
    dp.register_message_handler(ap_get_title, state=AddPodcastStates.GET_TITLE)
    dp.register_message_handler(ap_get_desc,  state=AddPodcastStates.GET_DESC)
    dp.register_message_handler(ap_get_url,   state=AddPodcastStates.GET_URL)
    dp.register_callback_query_handler(
        ap_confirm,
        lambda c: c.data in ("podcast_add_confirm", "podcast_add_cancel"),
        state=AddPodcastStates.CONFIRM
    )
