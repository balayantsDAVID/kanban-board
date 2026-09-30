import asyncio

from aiogram import Bot, Dispatcher
from redis.asyncio import Redis

from app.bot.handlers import router
from app.bot.middleware import DbSessionMiddleware
from app.core.config import get_settings
from app.core.logging import get_logger, setup_from_settings

logger = get_logger(__name__)


async def main() -> None:
    settings = get_settings()
    setup_from_settings()

    bot = Bot(token=settings.telegram_bot_token)
    redis = Redis.from_url(settings.redis_url)
    dp = Dispatcher()
    dp.include_router(router)
    dp.message.middleware(DbSessionMiddleware())
    dp["redis"] = redis

    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("bot_starting")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        await redis.aclose()


if __name__ == "__main__":
    asyncio.run(main())
