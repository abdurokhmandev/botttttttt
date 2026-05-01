import asyncio
from aiogram import Bot, Dispatcher, types, executor

BOT_TOKEN = "8370113732:AAEepYpyvVp5zEoir0T3I5tT2E655NsGUZA"
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

@dp.message_handler(content_types=[types.ContentType.VIDEO, types.ContentType.DOCUMENT])
async def get_id(message: types.Message):
    if message.video:
        file_id = message.video.file_id
        file_name = message.video.file_name or "video"
        print(f"\n✅ VIDEO QABUL QILINDI!")
        print(f"Nomi: {file_name}")
        print(f"FILE_ID: {file_id}\n")
        await message.reply(f"Ushbu videoning FILE_ID si:\n\n<code>{file_id}</code>", parse_mode="HTML")
    elif message.document and message.document.mime_type.startswith("video/"):
        file_id = message.document.file_id
        file_name = message.document.file_name or "video"
        print(f"\n✅ VIDEO (Hujjat ko'rinishida) QABUL QILINDI!")
        print(f"Nomi: {file_name}")
        print(f"FILE_ID: {file_id}\n")
        await message.reply(f"Ushbu videoning FILE_ID si:\n\n<code>{file_id}</code>", parse_mode="HTML")
    else:
        await message.reply("Iltimos, video fayl yuboring.")

if __name__ == "__main__":
    print("🚀 File ID aniqlash boti ishga tushdi...")
    print("Botingizga 100MB gacha bo'lgan videolarni yuboring, u sizga FILE_ID qaytaradi.")
    executor.start_polling(dp, skip_updates=True)
