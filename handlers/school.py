from aiogram import Dispatcher, types
from config import SCHOOL_INFO


async def handle_school_info(callback: types.CallbackQuery) -> None:
    await callback.answer()  # Remove loading spinner
    await callback.message.answer(SCHOOL_INFO)


def register_school_handler(dp: Dispatcher) -> None:
    dp.register_callback_query_handler(
        handle_school_info,
        lambda c: c.data == "school_info",
    )
