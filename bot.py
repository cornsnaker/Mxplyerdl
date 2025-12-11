import asyncio
import logging
from aiogram import Bot, Dispatcher
from config import BOT_TOKEN
from core.database import init_db
from core.worker import worker
from plugins.handlers import router as handlers_router
from plugins.callbacks import router as callbacks_router

logging.basicConfig(level=logging.INFO)

async def main():
    await init_db()
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(handlers_router)
    dp.include_router(callbacks_router)

    # Start worker in background
    asyncio.create_task(worker(bot))

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
