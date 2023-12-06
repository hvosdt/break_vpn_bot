import logging
import asyncio
from handlers import *
from aiogram.methods import DeleteWebhook


async def main():
    await bot(DeleteWebhook(drop_pending_updates=True))
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())