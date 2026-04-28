from aiogram import Dispatcher, types

SCHOOL_INFO_TEXT = """🏫 Rahimov School — maktabimizning toshkent shahrida 2 ta: Mirzo Ulug'bek tumani va Ibn Sino mavzesida, Farg'ona shahrida esa 1 ta filiali mavjud.

Missiyamiz — bolalarni o'qitish, jamiyatga kerakli, o'ziga oilasiga va atrofiga foyda bera oladigan qilib ulg'aytirish, tarbiyalash.

O'quvchilarni 0-sinfdan 11-sinfgacha imtihon va suhbat asosida qabul qilamiz.

Maktabimiz 0- va 1-sinflar uchun o'zbek, ingliz va rus guruhlarni; 2-4-sinflar uchun o'zbek va rus guruhlarni; 5-sinfdan 11-sinfgacha o'zbek guruhlarini taklif qiladi.

📅 Darslar haftasiga 5 kun: dushanbadan jumaga qadar.
⏰ Dars soatlari: 8:30 dan 16:50 gacha.

Matematika, Ingliz tili, Kimyo, futbol, voleybol, shaxmat kabi bepul to'garaklarimiz bor.
Bundan tashqari o'quvchilarimiz uchun mini futbol, basketbol va voleybol o'yingohlarimiz mavjud.

🍜 0-sinfdan 8-sinfgacha bo'lgan o'quvchilarimiz uchun 3 mahal va 9-10-11-sinflarimiz uchun ixtiyoriy 1 yoki 3 mahal pokiza bepul ovqat mavjud.

Maktabimizda barcha fanlarni chuqurlashtirilib o'rgatamiz. Ingliz tili va matematikadan esa dars soatlarimiz ko'proq.

🌐 2 yildan buyon bitiruvchilarimiz 100% universitetga kirib kelishmoqda. Ular kirgan universitetlar dunyo reytingida TOP-11, TOP-50, TOP-300 talikda turadigan universitetlardir:
- Hong Kong University
- Columbia University
- HKUST
- Michigan State University
- Manhattan University
- Duke Kunshan University
- NYU Shanghai
- University of Bristol
- Maryville College
- Sycrause University
- University of Alberta

🔥 Yuqori sinflarimiz o'quvchilar uchun intensiv guruhlar ochganmiz. Bunda IELTS, SAT, CEFR kabi maxsus sertifikatga tayyorlanadigan o'quvchilarni kuchaytirilgan tartibda o'qitamiz. O'quvchilarimizdan:
- Jasmina Sobirjonova — 8.0
- Ro'ziboyev Odilbek – 7.5
- Abdujabborova Mubina — 7.5
- Shukurova Odina — 7.5
- Farzona Abdumuxtorova — 7.5
kabi 50+ o'quvchilar IELTS natijalarni qo'lga kiritishdi

💵 Maktab oylik narxlari:
1-11-sinflar uchun — 6 500 000 so'm.
Ular orasidan 0- va 1-Ingliz sinflarimiz uchun esa 6 800 000 so'mni tashkil qiladi.

Maktabimizning boshqa maktablardan ustunliklari, stipendiya va maxsus chegirmalar haqida batafsil ma'lumot olish uchun dushanbadan shanbagacha har kuni 09:00-18:00 da 78-113-0005 raqamimizga murojaat qilishingiz mumkin.

⭐️ Ijtimoiy tarmoqlarimiz:
t.me/rahimovschool
instagram.com/rahimovschool
youtube.com/@rahimovschool"""


async def handle_school_info(callback: types.CallbackQuery) -> None:
    await callback.answer()  # Remove loading spinner
    await callback.message.answer(SCHOOL_INFO_TEXT)


def register_school_handler(dp: Dispatcher) -> None:
    dp.register_callback_query_handler(
        handle_school_info,
        lambda c: c.data == "school_info",
    )
