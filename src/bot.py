from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage
from redis.asyncio import Redis

from .config import settings
from .database import init_db
from .handlers import admin as admin_handlers
from .handlers import student as student_handlers
from .middlewares.ban_check import BanCheckMiddleware


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger = logging.getLogger(__name__)

    await init_db()
    logger.info("Database initialised")

    redis_client = Redis.from_url(
        settings.redis_url,
        decode_responses=False,
    )

    try:
        await redis_client.ping()
        logger.info(f"Connected to Redis at {settings.redis_host}:{settings.redis_port}")
    except Exception as e:
        logger.error(f"Failed to connect to Redis: {e}")
        raise

    storage = RedisStorage(
        redis=redis_client,
        state_ttl=settings.fsm_ttl,
        data_ttl=settings.fsm_ttl,
    )

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    dp = Dispatcher(storage=storage)

    # Подключаем middleware бан-фильтра для студентов.
    # Регистрируем на уровне диспетчера — до роутеров.
    ban_middleware = BanCheckMiddleware()
    dp.message.middleware(ban_middleware)
    dp.callback_query.middleware(ban_middleware)

    # Порядок важен: admin-роутер раньше — у него есть свой filter.
    dp.include_router(admin_handlers.router)
    dp.include_router(student_handlers.router)

    logger.info("Starting polling (admins=%s)", settings.admin_ids)
    try:
        await dp.start_polling(bot)
    finally:
        await redis_client.aclose()
        await bot.session.close()
        logger.info("Connections closed")


if __name__ == "__main__":
    asyncio.run(main())
