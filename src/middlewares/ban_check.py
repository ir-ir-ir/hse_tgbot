from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from .. import database


class BanCheckMiddleware(BaseMiddleware):
    """Блокирует отправку новостей забаненными пользователями.

    Разрешает: /start, /help, /status, /drafts — чтобы пользователь
    понял, что происходит, и не был заперт в пустоте.
    Блокирует: /submit и все FSM-шаги подачи заявки.
    """

    # Команды, которые разрешены даже забаненным
    _ALLOWED_COMMANDS = {"/start", "/help", "/status", "/drafts", "/cancel"}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        # Определяем пользователя
        if isinstance(event, Message):
            user = event.from_user
        elif isinstance(event, CallbackQuery):
            user = event.from_user
        else:
            return await handler(event, data)

        if user is None:
            return await handler(event, data)

        # Проверяем только тех, кто не является администратором
        from ..config import settings
        if user.id in settings.admin_ids:
            return await handler(event, data)

        # Для Message: разрешаем «безопасные» команды
        if isinstance(event, Message):
            text = (event.text or "").strip()
            # Разрешаем команды из белого списка
            if any(text.startswith(cmd) for cmd in self._ALLOWED_COMMANDS):
                return await handler(event, data)

            # Проверяем бан только для /submit и кнопки «Предложить новость»
            # и любых сообщений в FSM-состоянии (т.е. когда идёт подача)
            from aiogram.fsm.context import FSMContext
            fsm: FSMContext | None = data.get("state")
            current_state = await fsm.get_state() if fsm else None

            is_submit_attempt = (
                text.startswith("/submit")
                or text == "Предложить новость"
                or current_state is not None  # активный FSM = подача заявки
            )

            if is_submit_attempt and await database.is_banned(user.id):
                await event.answer(
                    "🚫 Вы заблокированы и не можете подавать новости.\n"
                    "Если считаете это ошибкой — обратитесь к администратору."
                )
                return  # не передаём дальше

        # Для CallbackQuery во время подачи — тоже блокируем
        elif isinstance(event, CallbackQuery):
            from aiogram.fsm.context import FSMContext
            fsm: FSMContext | None = data.get("state")
            current_state = await fsm.get_state() if fsm else None
            if current_state is not None and await database.is_banned(user.id):
                await event.answer(
                    "🚫 Вы заблокированы и не можете подавать новости.",
                    show_alert=True,
                )
                return

        return await handler(event, data)
