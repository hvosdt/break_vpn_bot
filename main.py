from aiogram import executor
import logging
import asyncio
from handlers import *


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    asyncio.to_thread(executor.start_polling(dp, skip_updates=True))