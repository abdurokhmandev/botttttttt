import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

logging.basicConfig(level=logging.INFO)

# Environment-configured values (Railway variables)
BOT_TOKEN = os.getenv("BOT_TOKEN")
# OPERATOR_CHAT_ID can be a channel username like @channel or an integer chat id
OPERATOR_CHAT_ID_RAW = os.getenv("OPERATOR_CHAT_ID")
GROUP_INVITE_LINK = os.getenv("GROUP_INVITE_LINK", "")
PHOTO_URL = os.getenv("ILMLI_PHOTO_URL", "https://telegra.ph/file/placeholder.jpg")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is required")

# try convert operator chat id to int if possible
OPERATOR_CHAT_ID = None
if OPERATOR_CHAT_ID_RAW:
    try:
        OPERATOR_CHAT_ID = int(OPERATOR_CHAT_ID_RAW)
    except ValueError:
        OPERATOR_CHAT_ID = OPERATOR_CHAT_ID_RAW  # keep as string (e.g., @channel)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

# Simple in-memory storage for which lessons user clicked. Persist elsewhere in production.
user_watched = {}  # {user_id: set(video_index)}

LESSONS = [
    "1. 📹 1-18 yosh farzandingiz uchun yo'l xaritasi | Rahimov Suhbatlari",
    "2. 📹 Ota va o'g'il munosabati haqida gaplashamiz",
    "3. 📹 Tarbiya uchun vaqt yo'q",
    "4. 📹 Farzandim bloger bo'lmoqchi",
    "5. 📹 Bola bilan do'stlashing",
    "6. 📹 1-18 yosh farzandingiz uchun yo'l xaritasi | Rahimov Suhbatlari",
    "7. 📹 O'qishga bo'lgan qiziqish nega yo'qoladi? | Rahimov Suhbatlari",
    "8. 📹 Maktab emas — ustoz muhim! | Rahimov Suhbatlari",
    "9. 📹 Tarbiyada qilinayotgan katta xato | Rahimov Suhbatlari",
]


@dp.message_handler(content_types=["video", "video_note"])
async def handle_video(message: types.Message):
    """When a user sends a video, wait 3 seconds then send a photo + caption with a join button."""
    await asyncio.sleep(3)

    caption = (
        "Video farzandingizni tarbiyasida katta foyda beradi degan umiddamiz ✨\n\n"
        "Aytgancha, bizda yana farzand tarbiyasiga doir 10+ foydali darsimiz bor. Unda:\n\n"
        "• Bolalarni o'qishga qiziqtirish yo'llari\n"
        "• Tarbiya uchun vaqt yetmayotgan ota-onalarga maslahatlar\n"
        "• Aytganni qilmaydigan bola bilan qanday ishlash kerak?\n"
        "• Farzandga to'g'ri o'qituvchi tanlash\n\n"
        "🎧️️️️️️ Bu hali hammasi emas, biz bu botda har hafta yangi dars yuboramiz.\n\n"
        "Bularning barchasi mutlaqo bepul 😇\n\n"
        "Istasangiz, sizga ham bu podkastlar ro'yxatini yuborib, har hafta yangi dars chiqqanda xabar berib turishimiz mumkin.\n\n"
        "Buning uchun 1 daqiqa ajratib, botimizdagi \"Ilmli ota-onalar\" safiga qo'shilsangiz kifoya:"
    )

    keyboard = InlineKeyboardMarkup().add(
        InlineKeyboardButton("📝 Ilmli ota-onalar safiga qo'shilish", callback_data="join_group")
    )

    await bot.send_photo(chat_id=message.chat.id, photo=PHOTO_URL, caption=caption, reply_markup=keyboard)


@dp.callback_query_handler(lambda c: c.data == "join_group")
async def process_join(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id

    text = (
        "🎉 Rahmat, mehmon. Endi siz bizning farzand tarbiyasi haqida qayg'uradigan "
        "\"Ilmli ota-onalar\" jamoamizga qo'shildingiz. Yangi darslarimizni kuting."
    )
    keyboard = InlineKeyboardMarkup().add(
        InlineKeyboardButton("📝 Farzand tarbiyasidagi darslar ro'yxatini olish", callback_data="get_list")
    )

    # In production: persist that the user joined (DB/Redis)
    await bot.send_message(chat_id=user_id, text=text, reply_markup=keyboard)
    await bot.answer_callback_query(callback_query.id)


@dp.callback_query_handler(lambda c: c.data == "get_list")
async def send_lessons(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id

    keyboard = InlineKeyboardMarkup(row_width=1)
    for idx, lesson in enumerate(LESSONS, start=1):
        keyboard.insert(InlineKeyboardButton(f"▶️ {lesson}", callback_data=f"watch_{idx}"))

    await bot.send_message(chat_id=user_id, text="Darslar ro'yxati:", reply_markup=keyboard)
    await bot.answer_callback_query(callback_query.id)


@dp.callback_query_handler(lambda c: c.data and c.data.startswith("watch_"))
async def watch_lesson(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    data = callback_query.data
    try:
        idx = int(data.split("_")[1])
    except Exception:
        await bot.answer_callback_query(callback_query.id, text="Noto'g'ri tugma")
        return

    user_watched.setdefault(user_id, set()).add(idx)
    watched_count = len(user_watched[user_id])

    await bot.answer_callback_query(callback_query.id, text=f"✅ {LESSONS[idx-1]} ga kirdingiz.")

    if watched_count >= 3:
        text = (
            "Aytgancha, sizga ushbu darslarni o'tib berayotgan Aziz Rahimovning maktablari — Rahimov School haqida eshitganmisiz? "
            "Agar farzandingizga maktab qidiryotgan bo'lsangiz, Rahimov School haqida ma'lumot berishimiz mumkin."
        )
        keyboard = InlineKeyboardMarkup().add(
            InlineKeyboardButton("Ha, qidiryapman, ma'lumot bering 💯", callback_data="school_yes"),
            InlineKeyboardButton("Yo'q, bizga maktab kerak emas, rahmat 😊", callback_data="school_no"),
        )
        await bot.send_message(chat_id=user_id, text=text, reply_markup=keyboard)


@dp.callback_query_handler(lambda c: c.data in ("school_yes", "school_no"))
async def school_response(callback_query: types.CallbackQuery):
    user = callback_query.from_user
    if callback_query.data == "school_yes":
        school_info = (
            "Rahimov School haqida ma'lumot:\n\n"
            "📚 Nomi: Rahimov School\n"
            "�� Aloqa: 914438285\n"
            "🏫 Qo'shimcha: ...\n\n"
            "Birozdan so'ng, operatorlarimiz sizga maktabimiz haqida to'liq ma'lumot berish uchun qo'ng'iroq qiladi 📞"
        )
        await bot.send_message(chat_id=user.id, text=school_info)

        # send lead to operator chat
        if OPERATOR_CHAT_ID is not None:
            lead_text = (
                "🔔 YANGI LEAD — Rahimov School — E'TIBOR BERING!\n\n"
                f"👤 {user.full_name}\n"
                f"📱 @{user.username if user.username else 'username yo‘q'}\n"
                f"☎️ {user.id} (user id)\n"
                "🏫 Sinf: 1-sinf\n\n"
                "Iltimos, mijoz bilan bog'laning."
            )
            try:
                await bot.send_message(chat_id=OPERATOR_CHAT_ID, text=lead_text)
            except Exception as e:
                logging.exception("Failed to send lead to operator chat: %s", e)
        else:
            logging.warning("OPERATOR_CHAT_ID not set, skipping lead notification")

    else:
        # 'no' branch
        reply = "Rahmat, bizni kuzatishda davom eting 😊️️️️️️ @RahimovSchool"
        # if you want, include group link or channel username
        if GROUP_INVITE_LINK:
            reply += f"\n\nGuruhga qo'shilish: {GROUP_INVITE_LINK}"
        await bot.send_message(chat_id=user.id, text=reply)

    await bot.answer_callback_query(callback_query.id)


if __name__ == "__main__":
    # Run polling. On Railway, use a Procfile to run `python flows/ilmli_ota_onalar.py` or integrate into your main bot.
    executor.start_polling(dp, skip_updates=True)
