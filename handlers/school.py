from aiogram import Dispatcher, types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import logging

from config import ADMIN_IDS
from storage import state_store

logger = logging.getLogger(__name__)

SCHOOL_INFO_TEXT = """🏫  Rahimov School — maktabimizning toshkent shahrida 2 ta: Mirzo Ulug'bek tumani va Ibn Sino mavzesida, Farg'ona shahrida  esa 1 ta filiali mavjud.

Missiyamiz — bolalarni o'qitish, jamiyatga kerakli, o'ziga oilasiga va atrofiga foyda bera oladigan qilib ulg'aytirish, tarbiyalash.

O'quvchilarni 0-sinfdan 11-sinfgacha imtihon va suhbat asosida qabul qilamiz.

Maktabimiz 0- va 1-sinflar uchun o‘zbek, ingliz va rus guruhlarni; 2-4-sinflar uchun o‘zbek va rus guruhlarni; 5-sinfdan 11-sinfgacha o‘zbek guruhlarini taklif qiladi. 

📅 Darslar haftasiga 5 kun: dushanbadan jumaga qadar.

⏰ Dars soatlari: 8:30 dan 16:50 gacha.

Matematika, Ingliz tili, Kimyo, futbol, voleybol, shaxmat kabi bepul to‘garaklarimiz bor. 

Bundan tashqari o‘quvchilarimiz uchun mini futbol, basketbol va voleybol o‘yingohlarimiz mavjud. 

🍜 0-sinfdan 8-sinfgacha bo‘lgan o‘quvchilarimiz uchun 3 mahal va 9-10-11-sinflarimiz uchun ixtiyoriy 1 yoki 3 mahal pokiza bepul ovqat mavjud. 

Maktabimizda barcha fanlarni chuqurlashtirilib o'rgatamiz. Ingliz tili va matematikadan esa dars soatlarimiz ko'proq. 

🌐 2 yildan buyon bitiruvchilarimiz 100% universitetga kirib kelishmoqda. Ular kirgan universitetlar dunyo reytingida TOP-11, TOP-50, TOP-300 talikda turadigan universitetlardir:

• Hong Kong University
• Columbia University
• HKUST
• Michigan State University
• Manhattan University
• Duke Kunshan University
• NYU Shanghai
• University of Bristol
• Maryville College
• Sycrause University
• Universtiy of Alberta

🔥 Yuqori sinflarimiz o'quvchilar uchun intensiv guruhlar ochganmiz. Bunda IELTS, SAT, CEFR kabi maxsus sertifikatga tayyorlanadigan o'quvchilarni kuchaytirilgan tartibda o'qitamiz. O'quvchilarimizdan:

• Jasmina Sobirjonova — 8.0
• Ro‘ziboyev Odilbek – 7.5
• Abdujabborova Mubina — 7.5
• Shukurova Odina — 7.5
• Farzona Abdumuxtorova — 7.5 

kabi 50+ o'quvchilar IELTS natijalarni qo'lga kiritishdi

💵 Maktab oylik narxlari:

1-11-sinflar uchun — 6 500 000 so‘m.

Ular orasidan 0- va 1-Ingliz sinflarimiz uchun esa 6 800 000 so‘mni tashkil qiladi. 

Maktabimizning boshqa maktablardan ustunliklari, stipendiya va maxsus chegirmalar haqida batafsil ma’lumot olish uchun dushanbadadan shanbagacha har kuni 09:00-18:00 da 78-113-0005 raqamimizga murojaat qilishingiz mumkin."""

SOCIAL_MEDIA_TEXT = """⭐️ Bizni ijtimoiy tarmoqlarda kuzatib boring:

🔹 Telegram: t.me/rahimovschool
🔹 Instagram: instagram.com/rahimovschool
🔹 YouTube: youtube.com/@rahimovschool"""


# ── Feedback FSM ──────────────────────────────────────────────────────────────

class FeedbackState(StatesGroup):
    waiting_for_question = State()


async def handle_feedback_start(message: types.Message):
    """User 'Feedback' tugmasini bosdi."""
    await FeedbackState.waiting_for_question.set()
    await message.answer(
        "💬 <b>Savol yoki murojaat yuboring:</b>\n\n"
        "Savolingizni yozing va biz tez orada javob beramiz!\n\n"
        "<i>Bekor qilish uchun /cancel yozing</i>",
        parse_mode="HTML",
    )


async def handle_feedback_cancel(message: types.Message, state: FSMContext):
    await state.finish()
    await message.answer("❌ Bekor qilindi.")


async def handle_feedback_message(message: types.Message, state: FSMContext):
    """User savolini adminga yuboradi."""
    await state.finish()

    user = message.from_user
    user_info = (
        f"💬 <b>Yangi savol/murojaat!</b>\n\n"
        f"👤 Ism: {user.full_name}\n"
        f"🆔 ID: <code>{user.id}</code>\n"
        f"📱 Username: @{user.username or '—'}\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"📩 Xabar:"
    )

    # Har bir adminga xabar yuboramiz
    for admin_id in ADMIN_IDS:
        try:
            # Avval foydalanuvchi haqida ma'lumot
            await message.bot.send_message(
                chat_id=admin_id,
                text=user_info,
                parse_mode="HTML",
            )
            # Keyin original xabarni forward qilamiz
            await message.forward(admin_id)
            # Javob berish tugmasi
            reply_btn = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(
                    text="↩️ Javob berish",
                    callback_data=f"reply_{user.id}"
                )
            ]])
            await message.bot.send_message(
                chat_id=admin_id,
                text=f"Ushbu foydalanuvchiga javob berish uchun tugmani bosing:",
                reply_markup=reply_btn,
            )
        except Exception as e:
            logger.error("Failed to forward feedback to admin %s: %s", admin_id, e)

    await message.answer(
        "✅ <b>Savolingiz adminga yuborildi!</b>\n\n"
        "Tez orada javob beramiz 🙏",
        parse_mode="HTML",
    )


# ── Admin Reply to User ───────────────────────────────────────────────────────

class AdminReplyState(StatesGroup):
    waiting_for_reply = State()


async def handle_admin_reply_callback(callback: types.CallbackQuery, state: FSMContext):
    """Admin 'Javob berish' tugmasini bosdi."""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Ruxsat yo'q", show_alert=True)
        return

    target_id = int(callback.data.split("_")[1])
    await state.update_data(reply_target_id=target_id)
    await AdminReplyState.waiting_for_reply.set()

    await callback.message.edit_reply_markup()  # Tugmani o'chiramiz
    await callback.message.answer(
        f"✍️ Foydalanuvchi <code>{target_id}</code> ga javobingizni yozing:\n\n"
        "<i>Bekor qilish uchun /cancel yozing</i>",
        parse_mode="HTML",
    )


async def handle_admin_reply_message(message: types.Message, state: FSMContext):
    """Admin javobini foydalanuvchiga yuboradi."""
    if message.from_user.id not in ADMIN_IDS:
        return

    data = await state.get_data()
    target_id = data.get("reply_target_id")
    await state.finish()

    if not target_id:
        await message.answer("❌ Xatolik: foydalanuvchi ID topilmadi.")
        return

    try:
        await message.bot.send_message(
            chat_id=target_id,
            text="📩 <b>Admin javobi:</b>",
            parse_mode="HTML",
        )
        await message.copy_to(chat_id=target_id)
        await message.answer(
            f"✅ Javob <code>{target_id}</code> ga muvaffaqiyatli yuborildi!",
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error("Failed to send reply to user %s: %s", target_id, e)
        await message.answer(
            f"❌ Xabar yuborishda xatolik: <code>{e}</code>",
            parse_mode="HTML",
        )


async def handle_school_info_callback(callback: types.CallbackQuery) -> None:
    await callback.answer()
    await callback.message.answer(SCHOOL_INFO_TEXT)


async def handle_school_info_text(message: types.Message) -> None:
    await message.answer(SCHOOL_INFO_TEXT)


async def handle_social_media_text(message: types.Message) -> None:
    await message.answer(SOCIAL_MEDIA_TEXT)


async def handle_phone_number(message: types.Message) -> None:
    await message.answer(
        "📞 Rahimov School bilan bog'laning:\n\n"
        "☎️ Telefon: +998781130005\n\n"
        "🕐 Ish vaqti: Dushanba–Shanba, 09:00–18:00\n\n"
        "📍 Manzillar:\n"
        "• <a href=\"https://yandex.uz/maps/-/CPWoN6I3\">Toshkent — Mirzo Ulug'bek tumani</a>\n"
        "• <a href=\"https://yandex.uz/maps/-/CPWoN0yA\">Toshkent — Ibn Sino mavzesi</a>\n"
        "• <a href=\"https://yandex.uz/maps/-/CPWoN2i5\">Farg'ona shahri</a>",
        parse_mode="HTML",
        disable_web_page_preview=True
    )


async def handle_maktab_haqida(message: types.Message) -> None:
    # Bu yerga matnni keyinchalik o'zingiz qo'yasiz
    text = (
        "🏫 <b>Rahimov School haqida</b>\n\n"
        "Maktabimiz haqida batafsil ma'lumot olish uchun quyidagi tugmalardan foydalanishingiz mumkin yoki ushbu matnni o'zgartiring."
    )
    await message.answer(text, parse_mode="HTML")


def register_school_handler(dp: Dispatcher) -> None:
    # Callback
    dp.register_callback_query_handler(
        handle_school_info_callback,
        lambda c: c.data == "school_info",
        state="*",
    )

    # Reply keyboard buttons
    dp.register_message_handler(handle_maktab_haqida, text="Maktab haqida 🏫", state="*")
    dp.register_message_handler(handle_school_info_text, text="🏫 Rahimov School", state="*")
    dp.register_message_handler(handle_social_media_text, text="🔗 Ijtimoiy tarmoqlarimiz", state="*")
    dp.register_message_handler(handle_phone_number, text="📞 Telefon raqam", state="*")

    # Feedback
    dp.register_message_handler(handle_feedback_start, text="💬 Fikr va mulohazalar", state="*")
    dp.register_message_handler(
        handle_feedback_cancel, commands=["cancel"], state=FeedbackState.waiting_for_question
    )
    dp.register_message_handler(
        handle_feedback_message,
        content_types=types.ContentType.ANY,
        state=FeedbackState.waiting_for_question,
    )

    # Admin reply
    dp.register_callback_query_handler(
        handle_admin_reply_callback,
        lambda c: c.data and c.data.startswith("reply_"),
        state="*",
    )
    dp.register_message_handler(
        handle_feedback_cancel, commands=["cancel"], state=AdminReplyState.waiting_for_reply
    )
    dp.register_message_handler(
        handle_admin_reply_message,
        content_types=types.ContentType.ANY,
        state=AdminReplyState.waiting_for_reply,
    )
