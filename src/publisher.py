from __future__ import annotations

import logging
from html import escape
from typing import Optional

from aiogram import Bot
from aiogram.types import InputMediaPhoto

from .config import settings
from .database import Submission

logger = logging.getLogger(__name__)


def _build_post_text(submission: Submission) -> str:
    """Формирует HTML-текст поста для канала."""
    parts = [f"<b>{escape(submission.title)}</b>", "", escape(submission.text)]
    if submission.links:
        parts.append("")
        parts.append("<b>Ссылки:</b>")
        for link in submission.links:
            parts.append(f'• <a href="{escape(link)}">{escape(link)}</a>')
    student_tag = (
        f"@{submission.student_username}"
        if submission.student_username
        else (submission.student_full_name or "автор не указан")
    )
    parts.append("")
    parts.append(f"📝 Материал подготовлен студентом {escape(student_tag)}")
    return "\n".join(parts)


async def publish_submission(bot: Bot, submission: Submission) -> Optional[int]:
    """Публикует одобренную заявку в канал. Возвращает message_id (или первого
    сообщения media-group)."""
    text = _build_post_text(submission)
    chat_id: str | int = settings.channel_id
    photos = submission.photo_file_ids or []

    if not photos:
        msg = await bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode="HTML",
        )
        return msg.message_id

    media: list[InputMediaPhoto] = [
        InputMediaPhoto(media=photos[0], caption=text, parse_mode="HTML")
    ]
    for file_id in photos[1:]:
        media.append(InputMediaPhoto(media=file_id))
    sent = await bot.send_media_group(chat_id=chat_id, media=media)
    return sent[0].message_id if sent else None
