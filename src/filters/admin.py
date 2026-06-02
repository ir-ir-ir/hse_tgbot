from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, Message

from ..config import settings


class AdminFilter(BaseFilter):
    """Пропускает события только от пользователей из ADMIN_IDS."""

    async def __call__(self, event: Message | CallbackQuery) -> bool:
        user = event.from_user
        if user is None:
            return False
        return user.id in settings.admin_ids
