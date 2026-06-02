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

async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger = logging.getLogger(__name__)

    await init_db()
    logger.info("Database initialised")

    # Подключаемся к Redis
    redis_client = Redis.from_url(
        settings.redis_url,
        decode_responses=False,  # aiogram требует bytes
    )

    # Проверяем соединение с Redis
    try:
        await redis_client.ping()
        logger.info(f"Connected to Redis at {settings.redis_host}:{settings.redis_port}")
    except Exception as e:
        logger.error(f"Failed to connect to Redis: {e}")
        raise

    # Создаем Redis storage для FSM
    storage = RedisStorage(
        redis=redis_client,
        state_ttl=settings.fsm_ttl,
        data_ttl=settings.fsm_ttl,
    )

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    # Инициализируем диспетчер с Redis storage
    dp = Dispatcher(storage=storage)

    """ Понадобится для третьего задания
    # Создаем менеджеры и middleware
    redis_manager = RedisManager(redis_client, settings.fsm_ttl)

    # Добавляем middleware
    dp.message.middleware(RateLimitMiddleware(redis_manager))
    dp.callback_query.middleware(RateLimitMiddleware(redis_manager))
    dp.message.middleware(BanCheckMiddleware(settings))
    dp.callback_query.middleware(BanCheckMiddleware(settings))

    # Передаем зависимости в роутеры
    admin_handlers.router.forward_to = None  # сбрасываем, если был
    student_handlers.router.forward_to = None
    """

    # Порядок важен: admin-роутер раньше — у него есть свой filter.
    dp.include_router(admin_handlers.router)
    dp.include_router(student_handlers.router)

    logger.info("Starting polling (admins=%s)", settings.admin_ids)
    try:
        await dp.start_polling(bot)
    finally:
        await redis_client.close()
        await bot.session.close()
        logger.info("Connections closed")


if __name__ == "__main__":
    asyncio.run(main())
