"""
handlers/user_video.py

Foydalanuvchi o'zi video yuborganda ishlaydigan oqim:

1. Video qabul qilinadi
2. 3 soniya kutiladi  
3. Rasm + caption + "Ilmli ota-onalar safiga qo'shilish" tugmasi
4. Tugma → tasdiq + "Ro'yxatini olish" tugmasi
5. Ro'yxat → 9 ta dars tugmalari
6. 3 ta dars bosilganda → maktab taklifi
7. Ha → contact → sinf → operatorga lead
8. Yo'q → rahmat
"""

import asyncio
import logging
import os

from aiogram import Dispatcher, types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    InputFile, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
)

from config import BASE_DIR, LEAD_GROUP_ID, ADMIN_IDS

logger = logging.getLogger(__name__)

# ── In-memory: foydalanuvchi bosgan darslar ──────────────────────────────────
_user_watched: dict[int, set] = {}

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


# ── FSM ───────────────────────────────────────────────────────────────────────
class UserVideoFlow(StatesGroup):
    waiting_contact = State()
    waiting_sinf    = State()


# ── Yordamchi: rasm yo'li ─────────────────────────────────────────────────────
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
    rows = []
    row  = []
    for sinf in SINF_LIST:
        row.append(InlineKeyboardButton(sinf, callback_data=f"uv_sinf_{sinf}"))
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ── 1. Foydalanuvchi video yubordi ───────────────────────────────────────────
async def handle_user_video(message: types.Message):
    """Foydalanuvchi video yuborganda 3 sekund kutib javob beradi."""
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

    await _send(message.bot, message.chat.id, "start", text, _kb_join())


# ── 2. "Ilmli ota-onalar" tugmasi ─────────────────────────────────────────────
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


# ── 3. "Ro'yxatini olish" tugmasi ─────────────────────────────────────────────
async def cb_uv_get_list(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.answer("Darslar ro'yxati:", reply_markup=_kb_lessons())


# ── 4. Dars tugmasi bosildi ───────────────────────────────────────────────────
async def cb_uv_lesson(callback: types.CallbackQuery):
    uid = callback.from_user.id
    num = callback.data.replace("uv_lesson_", "")   # "uv_lesson_3" → "3"

    _user_watched.setdefault(uid, set()).add(num)
    count = len(_user_watched[uid])

    await callback.answer(f"✅ {num}-dars tanlandi")

    # 3 ta bosilganda maktab taklifi (har safar emas, faqat birinchi marta 3 ga yetganda)
    if count == 3:
        text = (
            "Aytgancha, sizga ushbu darslarni o'tib berayotgan Aziz Rahimovning "
            "maktablari — Rahimov School haqida eshitganmisiz?\n\n"
            "Agar farzandingizga maktab qidiryotgan bo'lsangiz, Rahimov School "
            "haqida ma'lumot berishimiz mumkin."
        )
        await _send(callback.message.bot, uid, "school_ask", text, _kb_school())


# ── 5a. "Ha, maktab kerak" ────────────────────────────────────────────────────
async def cb_uv_school_yes(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()

    contact_kb = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    contact_kb.add(KeyboardButton("📞 Telefon raqamimni yuborish", request_contact=True))

    await callback.message.answer(
        "Yaxshi! Sizga qo'ng'iroq qilishimiz uchun telefon raqamingizni yuboring 👇",
        reply_markup=contact_kb,
    )
    await UserVideoFlow.waiting_contact.set()


# ── 5b. Contact keldi → sinf so'ra ───────────────────────────────────────────
async def got_contact(message: types.Message, state: FSMContext):
    phone = message.contact.phone_number
    async with state.proxy() as d:
        d["phone"]     = phone
        d["full_name"] = message.from_user.full_name
        d["username"]  = message.from_user.username or "username yo'q"

    await message.answer(
        "Farzandingiz qaysi sinfda o'qiydi?",
        reply_markup=_kb_sinf(),
    )
    await UserVideoFlow.waiting_sinf.set()


# ── 5c. Sinf tanlandi → lead yuborish ────────────────────────────────────────
async def cb_uv_sinf(callback: types.CallbackQuery, state: FSMContext):
    uid  = callback.from_user.id
    sinf = callback.data.replace("uv_sinf_", "")

    async with state.proxy() as d:
        phone     = d.get("phone", "noma'lum")
        full_name = d.get("full_name", "noma'lum")
        username  = d.get("username", "username yo'q")

    await state.finish()

    # Foydalanuvchiga xabar
    await callback.message.answer(
        "Birozdan so'ng, operatorlarimiz sizga maktabimiz haqida to'liq ma'lumot "
        "berish uchun qo'ng'iroq qiladi 📞",
        reply_markup=ReplyKeyboardRemove(),
    )

    # Operatorga lead
    import html as _html
    lead = (
        "🔔 <b>YANGI LEAD — Rahimov School — E'TIBOR BERING!</b>\n\n"
        f"👤 {_html.escape(full_name)}\n"
        f"📱 @{_html.escape(username)}\n"
        f"☎️ {_html.escape(phone)}\n"
        f"🏫 Sinf: {_html.escape(sinf)}\n\n"
        "Iltimos, mijoz bilan bog'laning."
    )

    if LEAD_GROUP_ID:
        try:
            await callback.message.bot.send_message(LEAD_GROUP_ID, lead, parse_mode="HTML")
        except Exception as e:
            logger.error("Lead guruhiga yuborishda xato: %s", e)

    for admin_id in ADMIN_IDS:
        try:
            await callback.message.bot.send_message(admin_id, lead, parse_mode="HTML")
        except Exception as e:
            logger.error("Adminga yuborishda xato %s: %s", admin_id, e)

    await callback.answer()


# ── 6. "Yo'q, maktab kerak emas" ─────────────────────────────────────────────
async def cb_uv_school_no(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.answer("Rahmat, bizni kuzatishda davom eting 😊 @RahimovSchool")


# ── Register ──────────────────────────────────────────────────────────────────
def register_user_video_handlers(dp: Dispatcher) -> None:
    # Foydalanuvchi video yuborganda (state='*' — har qanday holatda)
    dp.register_message_handler(
        handle_user_video,
        content_types=["video", "video_note"],
        state="*",
    )

    # Inline callback'lar
    dp.register_callback_query_handler(
        cb_uv_join,     lambda c: c.data == "uv_join",       state="*")
    dp.register_callback_query_handler(
        cb_uv_get_list, lambda c: c.data == "uv_get_list",   state="*")
    dp.register_callback_query_handler(
        cb_uv_lesson,
        lambda c: c.data and c.data.startswith("uv_lesson_"), state="*")
    dp.register_callback_query_handler(
        cb_uv_school_yes, lambda c: c.data == "uv_school_yes", state="*")
    dp.register_callback_query_handler(
        cb_uv_school_no,  lambda c: c.data == "uv_school_no",  state="*")

    # Sinf — faqat waiting_sinf holatida
    dp.register_callback_query_handler(
        cb_uv_sinf,
        lambda c: c.data and c.data.startswith("uv_sinf_"),
        state=UserVideoFlow.waiting_sinf,
    )

    # Contact — faqat waiting_contact holatida
    dp.register_message_handler(
        got_contact,
        content_types=["contact"],
        state=UserVideoFlow.waiting_contact,
    )
