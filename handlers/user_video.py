"""
handlers/user_video.py

"Ilmli ota-onalar" oqimi:
1. Podkast yuborilgandan 3 soniya o'tib img11 + "qo'shilish" tugmasi (WebApp)
2. WebApp orqali ro'yxatdan o'tilgandan keyin (funnel.on_registered orqali) →
   img22 "Rahmat" + "Darslar ro'yxatini olish" tugmasi
3. Tugma → img33 + 9 ta dars tugmalari
4. 3 ta dars bosilganda → img44 maktab taklifi
5. Ha → agar profil (telefon) mavjud bo'lsa to'g'ridan-to'g'ri lead,
       aks holda contact + sinf so'rab keyin lead
6. Yo'q → rahmat
"""

import asyncio
import html as _html
import logging
import os

from aiogram import Dispatcher, types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    InputFile, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
)

from config import BASE_DIR, LEAD_GROUP_ID, ADMIN_IDS, WEBAPP_URL
from storage import state_store

logger = logging.getLogger(__name__)

# ── Darslar ro'yxati ──────────────────────────────────────────────────────────
LESSONS = [
    ("1", "1-18 yosh farzandingiz uchun yo'l xaritasi | Rahimov Suhbatlari"),
    ("2", "Ota va o'g'il munosabati haqida gaplashamiz"),
    ("3", "Tarbiya uchun vaqt yo'q"),
    ("4", "Farzandim bloger bo'lmoqchi"),
    ("5", "Bola bilan do'stlashing"),
    ("6", "1-18 yosh farzandingiz uchun yo'l xaritasi | Rahimov Suhbatlari"),
    ("7", "O'qishga bo'lgan qiziqish nega yo'qoladi? | Rahimov Suhbatlari"),
    ("8", "Maktab emas — ustoz muhim! | Rahimov Suhbatlari"),
    ("9", "Tarbiyada qilinayotgan katta xato | Rahimov Suhbatlari"),
]

SINF_LIST = [
    "1-sinf", "2-sinf", "3-sinf", "4-sinf", "5-sinf",
    "6-sinf", "7-sinf", "8-sinf", "9-sinf", "10-sinf", "11-sinf",
]


# ── FSM (faqat profil topilmaganda zaxira yo'l uchun) ────────────────────────
class UserVideoFlow(StatesGroup):
    waiting_contact = State()
    waiting_sinf    = State()


# ── Yordamchi: rasm yo'li (static/{folder}/ ICHIDAGI birinchi rasm) ──────────
def _img(folder: str) -> str | None:
    d = os.path.join(BASE_DIR, "static", folder)
    if os.path.isdir(d):
        imgs = [f for f in os.listdir(d)
                if f.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))]
        if imgs:
            return os.path.join(d, imgs[0])
    return None


async def _send(bot, chat_id: int, folder: str, text: str, markup=None):
    """Rasm bo'lsa rasm+caption, bo'lmasa faqat matn yuboradi."""
    path = _img(folder)
    if path:
        return await bot.send_photo(
            chat_id, InputFile(path),
            caption=text, parse_mode="HTML", reply_markup=markup,
        )
    return await bot.send_message(
        chat_id, text, parse_mode="HTML", reply_markup=markup,
    )


# ── Tugmalar ──────────────────────────────────────────────────────────────────
def _kb_join():
    """Ilmli ota-onalar safiga qo'shilish — haqiqiy WebApp ro'yxatdan o'tish."""
    if WEBAPP_URL:
        return InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                "📝 Ilmli ota-onalar safiga qo'shilish",
                web_app=types.WebAppInfo(url=WEBAPP_URL),
            )
        ]])
    # WEBAPP_URL sozlanmagan bo'lsa — zaxira (haqiqiy ro'yxatdan o'tish bo'lmaydi)
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            "📝 Ilmli ota-onalar safiga qo'shilish",
            callback_data="uv_join",
        )
    ]])


def _kb_get_list():
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            "📝 Farzand tarbiyasidagi darslar ro'yxatini olish",
            callback_data="uv_get_list",
        )
    ]])


def _kb_lessons():
    rows = []
    for num, title in LESSONS:
        rows.append([InlineKeyboardButton(f"📹 {num}. {title}", callback_data=f"uv_lesson_{num}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _kb_school():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("Ha, qidiryapman, ma'lumot bering 💯", callback_data="uv_school_yes")],
        [InlineKeyboardButton("Yo'q, bizga maktab kerak emas, rahmat 😊",  callback_data="uv_school_no")],
    ])


def _kb_sinf():
    rows, row = [], []
    for sinf in SINF_LIST:
        row.append(InlineKeyboardButton(sinf, callback_data=f"uv_sinf_{sinf}"))
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ── Lead yuborish (ham profil orqali, ham contact/sinf orqali ishlatiladi) ───
async def _send_school_lead(bot, chat_id: int, name: str, phone: str, grade: str, username: str) -> None:
    await bot.send_message(
        chat_id,
        "Birozdan so'ng, operatorlarimiz sizga maktabimiz haqida to'liq ma'lumot "
        "berish uchun qo'ng'iroq qiladi 📞",
        reply_markup=ReplyKeyboardRemove(),
    )
    lead = (
        "🔔 <b>YANGI LEAD — Rahimov School — E'TIBOR BERING!</b>\n\n"
        f"👤 {_html.escape(str(name))}\n"
        f"📱 {_html.escape(str(username))}\n"
        f"☎️ {_html.escape(str(phone))}\n"
        f"🏫 Sinf: {_html.escape(str(grade))}\n\n"
        "Iltimos, mijoz bilan bog'laning."
    )
    if LEAD_GROUP_ID:
        try:
            await bot.send_message(LEAD_GROUP_ID, lead, parse_mode="HTML")
        except Exception as e:
            logger.error("Lead guruhiga yuborishda xato: %s", e)
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, lead, parse_mode="HTML")
        except Exception as e:
            logger.error("Adminga yuborishda xato %s: %s", admin_id, e)


# ── Podkast yuborilgandan keyin 3 sekund o'tib chaqiriladi (ro'yxatdan o'tmagan foydalanuvchilar uchun) ─
async def send_ilmli_message(bot, user_id: int) -> None:
    await asyncio.sleep(3)
    text = (
        "Video farzandingizni tarbiyasida katta foyda beradi degan umiddamiz ✨\n\n"
        "Aytgancha, bizda yana farzand tarbiyasiga doir 10+ foydali darsimiz bor. Unda:\n\n"
        "• Bolalarni o'qishga qiziqtirish yo'llari\n"
        "• Tarbiya uchun vaqt yetmayotgan ota-onalarga maslahatlar\n"
        "• Aytganni qilmaydigan bola bilan qanday ishlash kerak?\n"
        "• Farzandga to'g'ri o'qituvchi tanlash\n\n"
        "kabi muammolarga yechim berganmiz.\n\n"
        "🎧 Bu hali hammasi emas, biz bu botda har hafta yangi dars yuboramiz.\n\n"
        "Va bularning barchasi mutlaqo bepul 😇\n\n"
        "Istasangiz, sizga ham bu podkastlar ro'yxatini yuborib, har hafta yangi dars "
        "chiqqanda xabar berib turishimiz mumkin.\n\n"
        'Buning uchun 1 daqiqa ajratib, botimizdagi "Ilmli ota-onalar" safiga '
        "qo'shilsangiz kifoya:"
    )
    try:
        await _send(bot, user_id, "img11", text, _kb_join())
    except Exception as e:
        logger.error("send_ilmli_message xato user=%s: %s", user_id, e)


# ── (Ixtiyoriy) foydalanuvchi o'zi video yuborganda ───────────────────────────
async def handle_user_video(message: types.Message):
    logger.info("📹 Video qabul qilindi user_id=%s", message.from_user.id)
    await asyncio.sleep(3)
    text = (
        "Video farzandingizni tarbiyasida katta foyda beradi degan umiddamiz ✨\n\n"
        "Aytgancha, bizda yana farzand tarbiyasiga doir 10+ foydali darsimiz bor. Unda:\n\n"
        "• Bolalarni o'qishga qiziqtirish yo'llari\n"
        "• Tarbiya uchun vaqt yetmayotgan ota-onalarga maslahatlar\n"
        "• Aytganni qilmaydigan bola bilan qanday ishlash kerak?\n"
        "• Farzandga to'g'ri o'qituvchi tanlash\n\n"
        "kabi muammolarga yechim berganmiz.\n\n"
        "🎧 Bu hali hammasi emas, biz bu botda har hafta yangi dars yuboramiz.\n\n"
        "Va bularning barchasi mutlaqo bepul 😇\n\n"
        "Istasangiz, sizga ham bu podkastlar ro'yxatini yuborib, har hafta yangi dars "
        "chiqqanda xabar berib turishimiz mumkin.\n\n"
        'Buning uchun 1 daqiqa ajratib, botimizdagi "Ilmli ota-onalar" safiga '
        "qo'shilsangiz kifoya:"
    )
    await _send(message.bot, message.chat.id, "img11", text, _kb_join())


# ── Zaxira: WEBAPP_URL sozlanmaganda ishlaydigan eski callback ───────────────
async def cb_uv_join(callback: types.CallbackQuery):
    await callback.answer()
    text = (
        "🎉 Rahmat, mehmon. Endi siz bizning farzand tarbiyasi haqida qayg'uradigan "
        '"Ilmli ota-onalar" jamoamizga qo\'shildingiz. Yangi darslarimizni kuting.'
    )
    try:
        if callback.message.photo or callback.message.caption:
            await callback.message.edit_caption(caption=text, reply_markup=_kb_get_list())
        else:
            await callback.message.edit_text(text=text, reply_markup=_kb_get_list())
    except Exception:
        await callback.message.answer(text, reply_markup=_kb_get_list())


# ── "Ro'yxatini olish" tugmasi ─────────────────────────────────────────────
async def cb_uv_get_list(callback: types.CallbackQuery):
    await callback.answer()
    try:
        await callback.message.delete()
    except Exception:
        pass
    
    from handlers.podcasts import _podcast_list_text, _podcast_list_keyboard
    from handlers.webapp import _build_main_reply_keyboard
    
    await callback.message.answer(
        text=f"🎧 <b>Qaysi darsni tinglamoqchisiz?</b>\n\n{_podcast_list_text()}",
        parse_mode="HTML",
        reply_markup=_podcast_list_keyboard()
    )
    
    await callback.message.answer(
        text="Pastdagi menyu orqali darslar va boshqa bo'limlarni tanlashingiz mumkin:",
        reply_markup=_build_main_reply_keyboard()
    )

# ── Dars tugmasi bosildi — doimiy xotirada sanaladi ──────────────────────────
async def cb_uv_lesson(callback: types.CallbackQuery):
    uid = callback.from_user.id
    num = callback.data.replace("uv_lesson_", "")

    watched = state_store.get_metadata(uid, "uv_watched_lessons") or []
    if num not in watched:
        watched = watched + [num]
        state_store.set_metadata(uid, "uv_watched_lessons", watched)

    await callback.answer(f"✅ {num}-dars tanlandi")

    if len(watched) == 3:
        text = (
            "Aytgancha, sizga ushbu darslarni o'tib berayotgan Aziz Rahimovning "
            "maktablari — Rahimov School haqida eshitganmisiz?\n\n"
            "Agar farzandingizga maktab qidiryotgan bo'lsangiz, Rahimov School "
            "haqida ma'lumot berishimiz mumkin."
        )
        await _send(callback.message.bot, uid, "img44", text, _kb_school())


# ── "Ha, maktab kerak" — avval mavjud profilni tekshiramiz ───────────────────
async def cb_uv_school_yes(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    user_id = callback.from_user.id
    profile = state_store.get_profile(user_id)

    if profile and profile.get("phone"):
        tg_user = callback.from_user
        username = f"@{tg_user.username}" if tg_user.username else f"ID: {user_id}"
        await _send_school_lead(
            callback.message.bot, user_id,
            name=profile.get("name") or tg_user.full_name,
            phone=profile.get("phone", "—"),
            grade=profile.get("grade", "—"),
            username=username,
        )
        return

    # Zaxira: profil topilmadi — telefon va sinfni so'raymiz
    contact_kb = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    contact_kb.add(KeyboardButton("📞 Telefon raqamimni yuborish", request_contact=True))
    await callback.message.answer(
        "Yaxshi! Sizga qo'ng'iroq qilishimiz uchun telefon raqamingizni yuboring 👇",
        reply_markup=contact_kb,
    )
    await UserVideoFlow.waiting_contact.set()


async def got_contact(message: types.Message, state: FSMContext):
    phone = message.contact.phone_number
    async with state.proxy() as d:
        d["phone"]     = phone
        d["full_name"] = message.from_user.full_name
        d["username"]  = message.from_user.username or "username yo'q"
    await message.answer("Farzandingiz qaysi sinfda o'qiydi?", reply_markup=_kb_sinf())
    await UserVideoFlow.waiting_sinf.set()


async def cb_uv_sinf(callback: types.CallbackQuery, state: FSMContext):
    uid  = callback.from_user.id
    sinf = callback.data.replace("uv_sinf_", "")
    async with state.proxy() as d:
        phone     = d.get("phone", "noma'lum")
        full_name = d.get("full_name", "noma'lum")
        username  = d.get("username", "username yo'q")
    await state.finish()
    await _send_school_lead(
        callback.message.bot, uid,
        name=full_name, phone=phone, grade=sinf,
        username=(f"@{username}" if username != "username yo'q" else "username yo'q"),
    )
    await callback.answer()


async def cb_uv_school_no(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.answer("Rahmat, bizni kuzatishda davom eting 😊 @RahimovSchool")


# ── Register ──────────────────────────────────────────────────────────────────
def register_user_video_handlers(dp: Dispatcher) -> None:
    dp.register_message_handler(
        handle_user_video,
        content_types=["video", "video_note"],
        state="*",
    )

    dp.register_callback_query_handler(cb_uv_join,     lambda c: c.data == "uv_join",       state="*")
    dp.register_callback_query_handler(cb_uv_get_list, lambda c: c.data == "uv_get_list",   state="*")
    dp.register_callback_query_handler(
        cb_uv_lesson, lambda c: c.data and c.data.startswith("uv_lesson_"), state="*")
    dp.register_callback_query_handler(cb_uv_school_yes, lambda c: c.data == "uv_school_yes", state="*")
    dp.register_callback_query_handler(cb_uv_school_no,  lambda c: c.data == "uv_school_no",  state="*")

    dp.register_callback_query_handler(
        cb_uv_sinf,
        lambda c: c.data and c.data.startswith("uv_sinf_"),
        state=UserVideoFlow.waiting_sinf,
    )
    dp.register_message_handler(
        got_contact,
        content_types=["contact"],
        state=UserVideoFlow.waiting_contact,
    )
