from __future__ import annotations

import logging
from html import escape
from typing import Iterable

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InputMediaPhoto,
    Message,
)

from hse_tgbot.src import database, publisher
from hse_tgbot.src.config import settings
from hse_tgbot.src.database import Submission
from hse_tgbot.src.filters.admin import AdminFilter
from hse_tgbot.src.keyboards.admin import ModerationCallback, moderation_keyboard
from hse_tgbot.src.states.submission import ModerationStates

logger = logging.getLogger(__name__)

router = Router(name="admin")
router.message.filter(AdminFilter())
router.callback_query.filter(AdminFilter())

# submission_id -> [(chat_id, message_id)]
_NOTIFICATIONS: dict[int, list[tuple[int, int]]] = {}


def _register_notification(submission_id: int, chat_id: int, message_id: int) -> None:
    _NOTIFICATIONS.setdefault(submission_id, []).append((chat_id, message_id))


def _pop_notifications(submission_id: int) -> list[tuple[int, int]]:
    return _NOTIFICATIONS.pop(submission_id, [])


def _format_submission_card(submission: Submission) -> str:
    student_label = (
        f"@{submission.student_username}"
        if submission.student_username
        else (submission.student_full_name or f"id={submission.student_id}")
    )
    parts = [
        f"<b>Заявка #{submission.id}</b>",
        f"От: {escape(student_label)}",
        "",
        f"<b>{escape(submission.title)}</b>",
        "",
        submission.text,
    ]
    if submission.links:
        parts.append("")
        parts.append("<b>Ссылки:</b>")
        for link in submission.links:
            parts.append(f"• {escape(link)}")
    return "\n".join(parts)


async def notify_admins_about_new_submission(
    bot: Bot, submission: Submission
) -> None:
    if not settings.admin_ids:
        logger.warning("ADMIN_IDS пуст — карточка модерации не отправлена.")
        return

    caption = _format_submission_card(submission)
    photos = submission.photo_file_ids or []

    for admin_id in settings.admin_ids:
        try:
            if photos:
                media: list[InputMediaPhoto] = [
                    InputMediaPhoto(media=photos[0], caption=caption, parse_mode="HTML")
                ]
                for file_id in photos[1:]:
                    media.append(InputMediaPhoto(media=file_id))
                await bot.send_media_group(chat_id=admin_id, media=media)
                prompt = await bot.send_message(
                    chat_id=admin_id,
                    text=f"Решение по заявке #{submission.id}:",
                    reply_markup=moderation_keyboard(submission.id),
                )
            else:
                prompt = await bot.send_message(
                    chat_id=admin_id,
                    text=caption,
                    parse_mode="HTML",
                    reply_markup=moderation_keyboard(submission.id),
                )
            _register_notification(submission.id, prompt.chat.id, prompt.message_id)
        except TelegramAPIError:
            logger.exception("Failed to deliver moderation card to admin %s", admin_id)


async def notify_admins_about_publish_permissions_problem(
    *,
    bot: Bot,
    student_id: int,
    student_username: str | None,
    student_full_name: str | None,
    title: str | None = None,
) -> None:
    """Сообщает администраторам, что студент не смог отправить заявку."""
    if not settings.admin_ids:
        logger.warning("ADMIN_IDS пуст — уведомление о правах не отправлено.")
        return

    student_label = (
        f"@{student_username}"
        if student_username
        else (student_full_name or f"id={student_id}")
    )
    parts = [
        "⚠️ Студент хотел предложить новость, но у бота нет прав на "
        "публикацию в канале.",
        "",
        f"Студент: {escape(student_label)}",
    ]
    if title:
        parts.append(f"Заголовок: {escape(title)}")
    parts.extend(
        [
            f"Канал: {escape(settings.channel_id)}",
            "",
            "Проверьте, что бот добавлен администратором канала и имеет право "
            "публиковать сообщения.",
        ]
    )
    text = "\n".join(parts)

    for admin_id in settings.admin_ids:
        try:
            await bot.send_message(chat_id=admin_id, text=text, parse_mode="HTML")
        except TelegramAPIError:
            logger.exception(
                "Failed to notify admin %s about publish permissions problem",
                admin_id,
            )


async def _broadcast_decision(
    bot: Bot,
    submission_id: int,
    status_text: str,
    skip: tuple[int, int] | None = None,
) -> None:
    targets = _pop_notifications(submission_id)
    for chat_id, message_id in targets:
        if skip is not None and (chat_id, message_id) == skip:
            continue
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=status_text,
                parse_mode="HTML",
            )
        except TelegramAPIError:
            logger.warning(
                "Failed to edit moderation card chat=%s msg=%s", chat_id, message_id
            )


# ---------------------------------------------------------------------------
# Модерация
# ---------------------------------------------------------------------------

@router.callback_query(ModerationCallback.filter(F.action == "approve"))
async def on_approve(
    callback: CallbackQuery,
    callback_data: ModerationCallback,
    bot: Bot,
) -> None:
    submission_id = callback_data.submission_id
    reviewer = callback.from_user
    reviewer_label = f"@{reviewer.username}" if reviewer.username else reviewer.full_name

    submission = await database.approve_submission(
        submission_id=submission_id,
        reviewer_id=reviewer.id,
        reviewer_username=reviewer.username,
    )
    if submission is None:
        await callback.answer("Заявка не найдена", show_alert=True)
        return
    if submission.status != "approved":
        await callback.answer("Заявка уже обработана.", show_alert=True)
        await _broadcast_decision(
            bot, submission_id, f"Заявка #{submission_id} уже обработана."
        )
        return

    status_text = (
        f"✅ Заявка #{submission.id} одобрена администратором "
        f"{escape(reviewer_label)}"
    )
    if callback.message:
        try:
            await callback.message.edit_text(status_text, parse_mode="HTML")
        except TelegramAPIError:
            logger.warning("Failed to edit reviewer's card.")
    await callback.answer("Одобрено")

    skip = (
        (callback.message.chat.id, callback.message.message_id)
        if callback.message
        else None
    )
    await _broadcast_decision(bot, submission.id, status_text, skip=skip)

    # Публикуем в канал.
    published = False
    try:
        channel_message_id = await publisher.publish_submission(bot, submission)
        if channel_message_id is not None:
            await database.set_channel_message_id(submission.id, channel_message_id)
            published = True
    except Exception:
        logger.exception("Failed to publish submission #%s", submission.id)
        try:
            await bot.send_message(
                chat_id=reviewer.id,
                text=(
                    f"⚠️ Заявка #{submission.id} одобрена, но публикация в канал "
                    f"не удалась. Проверьте права бота в канале."
                ),
            )
        except TelegramAPIError:
            pass

    # Уведомляем студента.
    student_text = (
        f"✅ Ваша заявка #{submission.id} «{escape(submission.title)}» "
        f"одобрена и опубликована."
        if published
        else (
            f"✅ Ваша заявка #{submission.id} «{escape(submission.title)}» "
            "одобрена, но публикация временно не удалась по техническим "
            "причинам. Администраторы уже занимаются решением вопроса."
        )
    )
    try:
        await bot.send_message(
            chat_id=submission.student_id,
            text=student_text,
            parse_mode="HTML",
        )
    except TelegramAPIError:
        logger.warning("Failed to notify student %s about approval", submission.student_id)


@router.callback_query(ModerationCallback.filter(F.action == "reject"))
async def on_reject_click(
    callback: CallbackQuery,
    callback_data: ModerationCallback,
    state: FSMContext,
) -> None:
    submission_id = callback_data.submission_id
    submission = await database.get_submission(submission_id)
    if submission is None:
        await callback.answer("Заявка не найдена.", show_alert=True)
        return
    if submission.status != "pending":
        await callback.answer("Заявка уже обработана.", show_alert=True)
        return
    await state.set_state(ModerationStates.waiting_reject_reason)
    await state.update_data(reject_submission_id=submission_id)
    if callback.message:
        await callback.message.answer(
            f"Введите причину отклонения заявки #{submission_id} "
            f"одним сообщением. Для отмены — /cancel."
        )
    await callback.answer()


@router.message(Command("cancel"), ModerationStates.waiting_reject_reason)
async def cmd_cancel_reject(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Отклонение отменено. Заявка осталась в очереди.")


@router.message(ModerationStates.waiting_reject_reason, F.text)
async def on_reject_reason(
    message: Message, state: FSMContext, bot: Bot
) -> None:
    data = await state.get_data()
    submission_id = data.get("reject_submission_id")
    await state.clear()
    if submission_id is None:
        return
    reason = (message.text or "").strip()
    if not reason:
        await message.answer("Причина не может быть пустой.")
        return

    reviewer = message.from_user
    reviewer_label = (
        f"@{reviewer.username}" if reviewer.username else reviewer.full_name
    )
    submission = await database.reject_submission(
        submission_id=submission_id,
        reviewer_id=reviewer.id,
        reviewer_username=reviewer.username,
        reason=reason,
    )
    if submission is None:
        await message.answer("Заявка не найдена.")
        return
    if submission.status != "rejected":
        await message.answer("Заявка уже была обработана ранее.")
        await _broadcast_decision(
            bot, submission_id, f"Заявка #{submission_id} уже обработана."
        )
        return

    status_text = (
        f"❌ Заявка #{submission.id} отклонена администратором "
        f"{escape(reviewer_label)}\n"
        f"Причина: {escape(reason)}"
    )
    await message.answer(f"Готово. Заявка #{submission.id} отклонена.")
    await _broadcast_decision(bot, submission.id, status_text)

    try:
        await bot.send_message(
            chat_id=submission.student_id,
            text=(
                f"❌ Ваша заявка #{submission.id} «{escape(submission.title)}» "
                f"отклонена.\nПричина: {escape(reason)}"
            ),
            parse_mode="HTML",
        )
    except TelegramAPIError:
        logger.warning(
            "Failed to notify student %s about rejection", submission.student_id
        )


def _short_list(items: Iterable[Submission], header: str) -> str:
    submissions = list(items)
    if not submissions:
        return f"{header}\n\nПусто."
    lines = [header, ""]
    for s in submissions:
        author = (
            f"@{s.student_username}" if s.student_username else f"id={s.student_id}"
        )
        if s.status == "pending":
            line = f"🕒 #{s.id} — {escape(s.title)} — от {escape(author)}"
        else:
            emoji = "✅" if s.status == "approved" else "❌"
            line = (
                f"{emoji} #{s.id} — {escape(s.title)} — {s.status} — "
                f"от {escape(author)}"
            )
            if s.status == "rejected" and s.reject_reason:
                line += f"\n   причина: {escape(s.reject_reason)}"
        lines.append(line)
    return "\n".join(lines)


@router.message(Command("pending"))
async def cmd_pending(message: Message) -> None:
    submissions = await database.list_pending_submissions(limit=50)
    text = _short_list(submissions, "<b>Заявки на модерации:</b>")
    await message.answer(text, parse_mode="HTML")


@router.message(Command("history"))
async def cmd_history(message: Message) -> None:
    submissions = await database.list_recent_processed_submissions(limit=20)
    text = _short_list(submissions, "<b>Последние обработанные заявки:</b>")
    await message.answer(text, parse_mode="HTML")


# ---------------------------------------------------------------------------
# Чёрный список (задача 3)
# ---------------------------------------------------------------------------

@router.message(Command("ban"))
async def cmd_ban(message: Message) -> None:
    """
    Использование:
      /ban <user_id> [причина]
      /ban @username [причина]   — только если бот знает user_id по username
    Reply на сообщение пользователя — без аргументов.
    """
    admin = message.from_user

    # Определяем цель: reply или аргумент команды
    target_id: int | None = None
    target_username: str | None = None
    target_full_name: str | None = None
    reason: str | None = None

    if message.reply_to_message and message.reply_to_message.from_user:
        target = message.reply_to_message.from_user
        target_id = target.id
        target_username = target.username
        target_full_name = target.full_name
        # Всё после команды — причина
        parts = (message.text or "").split(maxsplit=1)
        reason = parts[1].strip() if len(parts) > 1 else None
    else:
        # /ban <user_id> [причина]
        parts = (message.text or "").split(maxsplit=2)
        if len(parts) < 2:
            await message.answer(
                "Использование:\n"
                "/ban &lt;user_id&gt; [причина]\n"
                "или ответьте на сообщение пользователя командой /ban [причина]"
            )
            return
        try:
            target_id = int(parts[1])
        except ValueError:
            await message.answer("user_id должен быть числом.")
            return
        reason = parts[2].strip() if len(parts) > 2 else None

    if target_id in settings.admin_ids:
        await message.answer("Нельзя забанить администратора.")
        return

    entry, created = await database.ban_user(
        user_id=target_id,
        username=target_username,
        full_name=target_full_name,
        reason=reason,
        banned_by=admin.id,
        banned_by_username=admin.username,
    )
    if not created:
        await message.answer(f"Пользователь {target_id} уже в чёрном списке.")
        return

    label = f"@{target_username}" if target_username else str(target_id)
    reason_str = f"\nПричина: {escape(reason)}" if reason else ""
    await message.answer(f"🚫 Пользователь {escape(label)} забанен.{reason_str}")


@router.message(Command("unban"))
async def cmd_unban(message: Message) -> None:
    """Использование: /unban <user_id>"""
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Использование: /unban &lt;user_id&gt;")
        return
    try:
        target_id = int(parts[1].strip())
    except ValueError:
        await message.answer("user_id должен быть числом.")
        return

    removed = await database.unban_user(target_id)
    if removed:
        await message.answer(f"✅ Пользователь {target_id} удалён из чёрного списка.")
    else:
        await message.answer(f"Пользователь {target_id} не найден в чёрном списке.")


@router.message(Command("blacklist"))
async def cmd_blacklist(message: Message) -> None:
    """Показывает список забаненных пользователей."""
    entries = await database.list_blacklist(limit=50)
    if not entries:
        await message.answer("Чёрный список пуст.")
        return

    lines = [f"<b>Чёрный список ({len(entries)}):</b>", ""]
    for e in entries:
        label = f"@{e.username}" if e.username else (e.full_name or str(e.user_id))
        line = f"🚫 {escape(label)} (id={e.user_id})"
        if e.reason:
            line += f" — {escape(e.reason)}"
        banned_by = f"@{e.banned_by_username}" if e.banned_by_username else str(e.banned_by)
        line += f"\n   забанен: {escape(banned_by)}, {e.banned_at.strftime('%d.%m.%Y %H:%M')}"
        lines.append(line)

    await message.answer("\n".join(lines), parse_mode="HTML")
