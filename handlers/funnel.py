"""
handlers/funnel.py

Video ko'rish funnel — foydalanuvchi video ko'rgandan 30 daqiqa o'tib
ishga tushadigan savol-javob oqimi.
"""
import asyncio
import logging
import os
import time

from aiogram import Dispatcher, types, Bot
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    InputFile, InputMediaPhoto,
)

from config import ADMIN_IDS, LEAD_GROUP_ID
from storage import state_store

logger = logging.getLogger(__name__)

# ── Rasmlarni papkadan olish ──────────────────────────────────────────────────

def _get_image(folder_name: str) -> str | None:
    """static/{folder_name}/ papkasidan birinchi rasim yo'lini qaytaradi."""
    from config import BASE_DIR
    d = os.path.join(BASE_DIR, "static", folder_name)
    if os.path.isdir(d):
        try:
            imgs = [f for f in os.listdir(d)
                    if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))]
            if imgs:
                return os.path.join(d, imgs[0])
        except Exception as e:
            logger.error("❌ _get_image(%s): %s", folder_name, e)
    return None


# ── Xabar yuborish yordamchisi ────────────────────────────────────────────────

async def _send_photo_or_text(
    bot: Bot,
    chat_id: int,
    folder: str,
    text: str,
    markup: InlineKeyboardMarkup = None,
    parse_mode: str = "HTML",
) -> types.Message:
    """Rasm bo'lsa rasm + caption, bo'lmasa faqat matn yuboradi."""
    path = _get_image(folder)
    if path and os.path.isfile(path):
        return await bot.send_photo(
            chat_id=chat_id,
            photo=InputFile(path),
            caption=text,
            parse_mode=parse_mode,
            reply_markup=markup,
        )
    return await bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode=parse_mode,
        reply_markup=markup,
    )


# ── Keyboard builders ─────────────────────────────────────────────────────────

def _kb_watched():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton("Ha, albatta, yana bormi? 💯", callback_data="funnel_yes_watched"),
        ],
        [
            InlineKeyboardButton("Yo'q, birozdan keyin ko'raman 😊", callback_data="funnel_no_watched"),
        ],
    ])


def _kb_like():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton("Ha 💯", callback_data="funnel_like_yes"),
            InlineKeyboardButton("Yo'q 😊", callback_data="funnel_like_no"),
        ],
    ])


def _kb_register():
    from config import WEBAPP_URL
    if WEBAPP_URL:
        return InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton("📝 Ro'yxatdan o'tish", web_app=types.WebAppInfo(url=WEBAPP_URL)),
        ]])
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton("📝 Ro'yxatdan o'tish", callback_data="start_registration"),
    ]])


def _kb_school():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("Ha, qidiryapman, ma'lumot bering 💯", callback_data="funnel_school_yes")],
        [InlineKeyboardButton("Yo'q, bizga maktab kerak emas, rahmat 😊", callback_data="funnel_school_no")],
    ])


def _kb_snooze():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("Hozir boshlayman ✅", callback_data="funnel_snooze_now")],
        [InlineKeyboardButton("10-15 daqiqada 🕗", callback_data="funnel_snooze_15")],
        [InlineKeyboardButton("1 soatlar o'tib ⏳", callback_data="funnel_snooze_60")],
        [InlineKeyboardButton("Ertaga ko'raman ➡️", callback_data="funnel_snooze_tomorrow")],
    ])


def _kb_snooze_remind(delay_cb: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("Eslatib qo'ying ⏰", callback_data=delay_cb)],
        [InlineKeyboardButton("Hozir ko'raman 👀", callback_data="funnel_snooze_now_watch")],
    ])


# ── Asosiy funnel trigger (reminder tomonidan chaqiriladi) ───────────────────

async def send_watched_question(bot: Bot, user_id: int) -> None:
    """30 daqiqa o'tgandan keyin "Ko'rib bo'ldingizmi?" yuboriladi."""
    try:
        await _send_photo_or_text(
            bot, user_id,
            folder="watched",
            text=(
                "Videoimizni ko'rib bo'ldingizmi, mehmon? Sizga yoqdimi?"
            ),
            markup=_kb_watched(),
        )
        state_store.set_state(user_id, state_store.VIDEO_WATCHED_ASKED)
    except Exception as e:
        logger.error("❌ send_watched_question user=%s: %s", user_id, e)


# ── Callback handlers ─────────────────────────────────────────────────────────

async def cb_yes_watched(callback: types.CallbackQuery) -> None:
    """Ha, ko'rdim — podkast ro'yxatini ko'rsatamiz."""
    await callback.answer()
    user_id = callback.from_user.id

    from handlers.podcasts import _podcast_list_text, _podcast_list_keyboard
    from config import PODCASTS

    if not PODCASTS:
        await callback.message.answer("📹 Hozircha suhbatlar mavjud emas.")
        return

    text = (
        "🎧 <b>Endi qaysi birini ko'ramiz?</b>\n\n"
        f"{_podcast_list_text()}"
    )
    try:
        if callback.message.photo or callback.message.caption:
            await callback.message.edit_caption(caption=text, parse_mode="HTML",
                                                 reply_markup=_podcast_list_keyboard())
        else:
            await callback.message.edit_text(text=text, parse_mode="HTML",
                                              reply_markup=_podcast_list_keyboard())
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=_podcast_list_keyboard())

    state_store.set_state(user_id, state_store.WANT_MORE_ASKED)


async def cb_no_watched(callback: types.CallbackQuery) -> None:
    """Yo'q, keyinroq — snooze variantlarini ko'rsatamiz."""
    await callback.answer()
    user_id = callback.from_user.id

    text = "Qachon ko'rmoqchisiz, nasib bo'lsa? 😊"
    try:
        if callback.message.photo or callback.message.caption:
            await callback.message.edit_caption(caption=text, reply_markup=_kb_snooze())
        else:
            await callback.message.edit_text(text=text, reply_markup=_kb_snooze())
    except Exception:
        await callback.message.answer(text, reply_markup=_kb_snooze())

    state_store.set_state(user_id, state_store.SNOOZE_15)


# ── "Yoqdimi?" — podkast tanlanib bo'lgandan keyin yuboriladi ────────────────

async def send_like_question(bot: Bot, user_id: int) -> None:
    """Podkast tugaganidan keyin 'Sizga yoqyaptimi?' savoli."""
    try:
        await _send_photo_or_text(
            bot, user_id,
            folder="like_asked",
            text=(
                "Sizga darslarimiz yoqyaptimi?\n\n"
                "Eng yangi darslarimiz chiqqanda, birinchilardan bo'lib "
                "uni ko'rishni istaysizmi?"
            ),
            markup=_kb_like(),
        )
        state_store.set_state(user_id, state_store.LIKE_ASKED)
    except Exception as e:
        logger.error("❌ send_like_question user=%s: %s", user_id, e)


async def cb_like_yes(callback: types.CallbackQuery) -> None:
    """Ha — ro'yxatga taklif."""
    await callback.answer()
    user_id = callback.from_user.id

    text = (
        "Kelishdik, biz yap-yangi darslarimiz chiqqan eng birinchi sizni "
        "xabardor qilamiz. Faqat buning uchun sizni ro'yxatga olib qo'yishimiz "
        "kerak. 1 daqiqada ro'yxatdan o'tkazib qo'yamiz. Quyidagi tugmani bosing:"
    )
    try:
        if callback.message.photo or callback.message.caption:
            await callback.message.edit_caption(
                caption=text, reply_markup=_kb_register())
        else:
            await callback.message.edit_text(text=text, reply_markup=_kb_register())
    except Exception:
        await _send_photo_or_text(
            callback.message.bot, user_id,
            folder="register_offer",
            text=text,
            markup=_kb_register(),
        )

    state_store.set_state(user_id, state_store.REGISTER_OFFERED)


async def cb_like_no(callback: types.CallbackQuery) -> None:
    """Yo'q — rahmat xabari."""
    await callback.answer()
    await callback.message.answer("Rahmat, bizni kuzatishda davom eting 😊")


# ── Ro'yxatdan o'tib bo'lgandan keyin (webapp/chat orqali) ───────────────────

async def on_registered(bot: Bot, user_id: int) -> None:
    """
    Foydalanuvchi ro'yxatdan o'tganda chaqiriladi.
    'Rahmat' xabari + 10 sek kutib maktab savoli yuboriladi.
    """
    try:
        await _send_photo_or_text(
            bot, user_id,
            folder="registered",
            text=(
                "Rahmat, mehmon. Endi siz bizning farzand tarbiyasi haqida "
                "qayg'uradigan ota-onalar jamoamizga qo'shildingiz. "
                "Yangi darslarimizni kuting."
            ),
        )
        state_store.set_state(user_id, state_store.SCHOOL_ASKED)

        await asyncio.sleep(10)

        # 10 sek keyin maktab savoli
        if state_store.get_state(user_id) == state_store.SCHOOL_ASKED:
            await _send_photo_or_text(
                bot, user_id,
                folder="school_ask",
                text=(
                    "Aytgancha, sizga ushbu darslarni o'tib berayotgan Aziz "
                    "Rahimovning maktablari — Rahimov School haqida "
                    "eshitganmisiz? Agar farzandingizga maktab qidiryotgan "
                    "bo'lsangiz, Rahimov School haqida ma'lumot berishimiz mumkin."
                ),
                markup=_kb_school(),
            )
    except Exception as e:
        logger.error("❌ on_registered user=%s: %s", user_id, e)


async def cb_school_yes(callback: types.CallbackQuery) -> None:
    """Ha, maktab haqida ma'lumot kerak — school info + lead guruhiga."""
    await callback.answer()
    user_id = callback.from_user.id

    # Maktab haqida ma'lumot
    from storage.settings_store import get_settings
    settings = get_settings()
    school_info = settings.get("maktab_haqida", "🏫 Rahimov School haqida ma'lumot uchun biz bilan bog'laning.")

    await callback.message.answer(school_info, parse_mode="HTML")
    await callback.message.answer(
        "Birozdan so'ng, operatorlarimiz sizga maktabimiz haqida to'liq "
        "ma'lumot berish uchun qo'ng'iroq qiladi 📞"
    )

    # Foydalanuvchi profili
    profile = state_store.get_profile(user_id)
    name    = profile.get("name", "—")    if profile else "—"
    phone   = profile.get("phone", "—")   if profile else "—"
    grade   = profile.get("grade", "—")   if profile else "—"
    tg_user = callback.from_user
    username = f"@{tg_user.username}" if tg_user.username else f"ID: {user_id}"

    # Admin guruhiga lead yuborish
    if LEAD_GROUP_ID:
        lead_text = (
            "🔔 <b>YANGI LEAD — Rahimov School — E'TIBOR BERING!</b>\n\n"
            f"👤 {name}\n"
            f"📱 {username}\n"
            f"☎️ {phone}\n"
            f"🏫 Sinf: {grade}\n\n"
            "Iltimos, mijoz bilan bog'laning."
        )
        try:
            await callback.message.bot.send_message(
                chat_id=LEAD_GROUP_ID,
                text=lead_text,
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error("❌ Lead guruhiga yuborishda xato: %s", e)

    # Adminlarga ham yuborish (zaxira)
    for admin_id in ADMIN_IDS:
        try:
            lead_text_admin = (
                "🔔 <b>YANGI LEAD — Rahimov School</b>\n\n"
                f"👤 {name}\n"
                f"📱 {username}\n"
                f"☎️ {phone}\n"
                f"🏫 Sinf: {grade}"
            )
            await callback.message.bot.send_message(
                chat_id=admin_id,
                text=lead_text_admin,
                parse_mode="HTML",
            )
        except Exception:
            pass

    state_store.set_state(user_id, state_store.REGISTERED)


async def cb_school_no(callback: types.CallbackQuery) -> None:
    """Yo'q — rahmat."""
    await callback.answer()
    await callback.message.answer("Rahmat, bizni kuzatishda davom eting 😊")
    state_store.set_state(callback.from_user.id, state_store.REGISTERED)


# ── Snooze handlers ───────────────────────────────────────────────────────────

async def _send_snooze_info(callback: types.CallbackQuery, delay_label: str, delay_cb: str) -> None:
    """Snooze tanlanganda ma'lumot xabari va 2 tugma chiqaradi."""
    await callback.answer()
    user_id = callback.from_user.id

    # Podkast haqida qisqacha ma'lumot
    last_idx = state_store.get_metadata(user_id, "last_video_idx")
    from config import PODCASTS
    lesson_info = ""
    if last_idx and last_idx in PODCASTS:
        desc = PODCASTS[last_idx].get("description", "")
        if desc:
            lesson_info = f"\n\nBu darsni ko'rib siz quyidagi savollarga yechim topasiz:\n{desc}"

    text = (
        f"Qaroringizdan xursandmiz.{lesson_info}\n\n"
        f"Sizga {delay_label} eslatib qo'yamizmi?"
    )
    try:
        if callback.message.photo or callback.message.caption:
            await callback.message.edit_caption(
                caption=text, reply_markup=_kb_snooze_remind(delay_cb))
        else:
            await callback.message.edit_text(text=text, reply_markup=_kb_snooze_remind(delay_cb))
    except Exception:
        await callback.message.answer(text, reply_markup=_kb_snooze_remind(delay_cb))


async def cb_snooze_now(callback: types.CallbackQuery) -> None:
    """Hozir boshlayman — video qayta yuboramiz."""
    await callback.answer()
    user_id = callback.from_user.id
    await _resend_last_video(callback.message.bot, user_id)
    try:
        await callback.message.delete()
    except Exception:
        pass


async def cb_snooze_15(callback: types.CallbackQuery) -> None:
    await _send_snooze_info(callback, "10-15 daqiqada", "funnel_remind_15")
    state_store.set_state(callback.from_user.id, state_store.SNOOZE_15)
    state_store.set_metadata(callback.from_user.id, "snooze_ts", time.time())


async def cb_snooze_60(callback: types.CallbackQuery) -> None:
    await _send_snooze_info(callback, "1 soatdan keyin", "funnel_remind_60")
    state_store.set_state(callback.from_user.id, state_store.SNOOZE_60)
    state_store.set_metadata(callback.from_user.id, "snooze_ts", time.time())


async def cb_snooze_tomorrow(callback: types.CallbackQuery) -> None:
    await _send_snooze_info(callback, "ertaga", "funnel_remind_tomorrow")
    state_store.set_state(callback.from_user.id, state_store.SNOOZE_TOMORROW)
    state_store.set_metadata(callback.from_user.id, "snooze_ts", time.time())


async def cb_snooze_now_watch(callback: types.CallbackQuery) -> None:
    """Hozir ko'raman — video chiqarib, 30 daqiqa kutishni boshlaydi."""
    await callback.answer()
    user_id = callback.from_user.id
    await _resend_last_video(callback.message.bot, user_id)
    try:
        await callback.message.delete()
    except Exception:
        pass


async def cb_remind_set(callback: types.CallbackQuery) -> None:
    """Eslatib qo'ying tugmasi — faqat tasdiqlash xabari."""
    await callback.answer("Yaxshi, eslatamiz! ⏰", show_alert=False)
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    # Holat allaqachon snooze ga o'rnatilgan, reminder xizmat o'zi kuzatadi


# ── Video qayta yuborish ──────────────────────────────────────────────────────

async def _resend_last_video(bot: Bot, user_id: int) -> None:
    """Oxirgi yuborilgan video/podkastni qayta yuboradi."""
    from config import PODCASTS
    from handlers.podcasts import _podcast_action_keyboard

    last_idx = state_store.get_metadata(user_id, "last_video_idx")
    if not last_idx or last_idx not in PODCASTS:
        await bot.send_message(user_id, "📹 Video topilmadi. Quyidagi menyudan tanlang.")
        return

    data      = PODCASTS[last_idx]
    file_id   = data.get("audio", "").strip()
    file_type = data.get("type", "audio")
    title     = data.get("title", f"Suhbat {last_idx}")
    desc      = data.get("description", "")
    markup    = _podcast_action_keyboard(last_idx)

    emoji   = "📹" if file_type == "video" else "🎧"
    caption = f"<b>{emoji} {title}</b>"
    if desc:
        caption += f"\n\n{desc}"
    caption += "\n\n🏫 Rahimov School suhbatlari"

    if file_id:
        try:
            if file_type == "video":
                await bot.send_video(
                    chat_id=user_id, video=file_id,
                    caption=caption, parse_mode="HTML", reply_markup=markup
                )
            else:
                await bot.send_audio(
                    chat_id=user_id, audio=file_id,
                    caption=caption, parse_mode="HTML",
                    title=title, performer="Rahimov School", reply_markup=markup
                )
            # 30 daqiqa kutishni qayta boshlash
            state_store.set_state(user_id, state_store.VIDEO_SENT)
            state_store.set_metadata(user_id, "video_sent_ts", time.time())
            return
        except Exception as e:
            logger.error("❌ _resend_last_video user=%s: %s", user_id, e)

    await bot.send_message(user_id, caption, parse_mode="HTML", reply_markup=markup)
    state_store.set_state(user_id, state_store.VIDEO_SENT)
    state_store.set_metadata(user_id, "video_sent_ts", time.time())


# ── Register ──────────────────────────────────────────────────────────────────

def register_funnel_handlers(dp: Dispatcher) -> None:
    dp.register_callback_query_handler(cb_yes_watched,    lambda c: c.data == "funnel_yes_watched",        state="*")
    dp.register_callback_query_handler(cb_no_watched,     lambda c: c.data == "funnel_no_watched",         state="*")
    dp.register_callback_query_handler(cb_like_yes,       lambda c: c.data == "funnel_like_yes",           state="*")
    dp.register_callback_query_handler(cb_like_no,        lambda c: c.data == "funnel_like_no",            state="*")
    dp.register_callback_query_handler(cb_school_yes,     lambda c: c.data == "funnel_school_yes",         state="*")
    dp.register_callback_query_handler(cb_school_no,      lambda c: c.data == "funnel_school_no",          state="*")
    dp.register_callback_query_handler(cb_snooze_now,     lambda c: c.data == "funnel_snooze_now",         state="*")
    dp.register_callback_query_handler(cb_snooze_15,      lambda c: c.data == "funnel_snooze_15",          state="*")
    dp.register_callback_query_handler(cb_snooze_60,      lambda c: c.data == "funnel_snooze_60",          state="*")
    dp.register_callback_query_handler(cb_snooze_tomorrow,lambda c: c.data == "funnel_snooze_tomorrow",    state="*")
    dp.register_callback_query_handler(cb_snooze_now_watch,lambda c: c.data == "funnel_snooze_now_watch",  state="*")
    dp.register_callback_query_handler(cb_remind_set,
        lambda c: c.data in ("funnel_remind_15", "funnel_remind_60", "funnel_remind_tomorrow"),             state="*")
