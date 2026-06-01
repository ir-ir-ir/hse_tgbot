from __future__ import annotations

import logging
from html import escape

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart, StateFilter, or_f
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InputMediaPhoto,
    Message,
)

from .. import database
from ..keyboards.student import (
    CANCEL_BUTTON_TEXT,
    DONE_BUTTON_TEXT,
    SKIP_BUTTON_TEXT,
    cancel_keyboard,
    confirm_keyboard,
    photos_keyboard,
    remove_keyboard,
    skip_cancel_keyboard,
    main_menu_keyboard,
)
from ..states.submission import SubmissionStates
from .admin import notify_admins_about_new_submission

logger = logging.getLogger(__name__)

router = Router(name="student")

MAX_TITLE_LEN = 200
MAX_TEXT_LEN = 3000
MAX_PHOTOS = 10


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "Привет! Я бот для подачи студенческих новостей.\n\n"
        "Используй /submit, чтобы предложить новость.\n"
        "Используй /status, чтобы посмотреть статусы своих заявок.",
        reply_markup=main_menu_keyboard(),
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "Команды:\n"
        "/submit — подать новость\n"
        "/status — статусы моих заявок\n"
        "/cancel — отменить текущую подачу",
        reply_markup=remove_keyboard(),
    )

@router.message(F.text == "Предложить новость")
async def menu_submit(message: Message, state: FSMContext):
    await cmd_submit(message, state)

@router.message(F.text == "Статус")
async def menu_status(message: Message):
    await cmd_status(message)

@router.message(Command("cancel"), StateFilter("*"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    current = await state.get_state()
    if current is None:
        await message.answer("Нечего отменять.", reply_markup=main_menu_keyboard())
        return
    await state.clear()
    await message.answer("Подача отменена.", reply_markup=main_menu_keyboard())


@router.message(F.text == CANCEL_BUTTON_TEXT, StateFilter(SubmissionStates))
async def text_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Подача отменена.", reply_markup=main_menu_keyboard())


@router.message(Command("submit"))
async def cmd_submit(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(SubmissionStates.waiting_title)
    await message.answer(
        "Введите <b>заголовок</b> новости (до 200 символов).",
        reply_markup=cancel_keyboard(),
    )


@router.message(SubmissionStates.waiting_title, F.text)
async def on_title(message: Message, state: FSMContext) -> None:
    title = (message.text or "").strip()
    if title == CANCEL_BUTTON_TEXT:
        return  # обработано выше
    if not title:
        await message.answer("Заголовок не может быть пустым. Попробуйте ещё раз.")
        return
    if len(title) > MAX_TITLE_LEN:
        await message.answer(
            f"Заголовок слишком длинный ({len(title)} симв.). "
            f"Максимум — {MAX_TITLE_LEN} символов."
        )
        return
    await state.update_data(title=title)
    await state.set_state(SubmissionStates.waiting_text)
    await message.answer(
        f"Отлично! Теперь пришлите <b>текст</b> новости (до {MAX_TEXT_LEN} символов).",
        reply_markup=cancel_keyboard(),
    )


@router.message(SubmissionStates.waiting_title)
async def on_title_invalid(message: Message) -> None:
    await message.answer("Пожалуйста, отправьте заголовок текстом.")


@router.message(SubmissionStates.waiting_text, F.text)
async def on_text(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if text == CANCEL_BUTTON_TEXT:
        return
    if not text:
        await message.answer("Текст не может быть пустым.")
        return
    if len(text) > MAX_TEXT_LEN:
        await message.answer(
            f"Текст слишком длинный ({len(text)} симв.). "
            f"Максимум — {MAX_TEXT_LEN} символов."
        )
        return
    await state.update_data(text=text, photo_file_ids=[])
    await state.set_state(SubmissionStates.waiting_photos)
    await message.answer(
        "Прикрепите <b>фотографии</b> (можно несколько, по одной за раз).\n"
        f"Когда закончите — нажмите «{DONE_BUTTON_TEXT}» или отправьте /done.\n"
        f"Если фото нет — нажмите «{SKIP_BUTTON_TEXT}».",
        reply_markup=photos_keyboard(),
    )


@router.message(SubmissionStates.waiting_text)
async def on_text_invalid(message: Message) -> None:
    await message.answer("Пожалуйста, отправьте текст новости сообщением.")


@router.message(SubmissionStates.waiting_photos, F.photo)
async def on_photo(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    photos: list[str] = list(data.get("photo_file_ids", []))
    if len(photos) >= MAX_PHOTOS:
        await message.answer(
            f"Достигнут лимит фото ({MAX_PHOTOS}). "
            f"Нажмите «{DONE_BUTTON_TEXT}» для продолжения."
        )
        return
    # message.photo — список PhotoSize'ов разных размеров; берём наибольший (последний)
    biggest = message.photo[-1]
    photos.append(biggest.file_id)
    await state.update_data(photo_file_ids=photos)
    await message.answer(
        f"Фото добавлено ({len(photos)}). "
        f"Можно прислать ещё или нажать «{DONE_BUTTON_TEXT}»."
    )


@router.message(
    SubmissionStates.waiting_photos,
    or_f(F.text == DONE_BUTTON_TEXT, F.text == "/done", Command("done")),
)
async def on_photos_done(message: Message, state: FSMContext) -> None:
    await _go_to_links(message, state)


@router.message(SubmissionStates.waiting_photos, F.text == SKIP_BUTTON_TEXT)
async def on_photos_skip(message: Message, state: FSMContext) -> None:
    await state.update_data(photo_file_ids=[])
    await _go_to_links(message, state)


@router.message(SubmissionStates.waiting_photos)
async def on_photos_invalid(message: Message) -> None:
    await message.answer(
        "Пришлите фотографию, нажмите "
        f"«{DONE_BUTTON_TEXT}», «{SKIP_BUTTON_TEXT}» или «{CANCEL_BUTTON_TEXT}»."
    )


async def _go_to_links(message: Message, state: FSMContext) -> None:
    await state.set_state(SubmissionStates.waiting_links)
    await message.answer(
        "Пришлите <b>ссылки</b> на внешние материалы — текстом, по одной "
        "или через запятую.\nЕсли ссылок нет — нажмите «Пропустить».",
        reply_markup=skip_cancel_keyboard(),
    )


@router.message(SubmissionStates.waiting_links, F.text == SKIP_BUTTON_TEXT)
async def on_links_skip(message: Message, state: FSMContext) -> None:
    await state.update_data(links=[])
    await _show_preview(message, state)


@router.message(SubmissionStates.waiting_links, F.text)
async def on_links(message: Message, state: FSMContext) -> None:
    raw = (message.text or "").strip()
    if raw == CANCEL_BUTTON_TEXT:
        return
    parts = [p.strip() for p in raw.replace("\n", ",").split(",")]
    links = [p for p in parts if p]
    await state.update_data(links=links)
    await _show_preview(message, state)


@router.message(SubmissionStates.waiting_links)
async def on_links_invalid(message: Message) -> None:
    await message.answer("Пришлите ссылки текстом или нажмите «Пропустить».")


async def _show_preview(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    title = data.get("title", "")
    text = data.get("text", "")
    photos: list[str] = data.get("photo_file_ids", [])
    links: list[str] = data.get("links", [])

    caption = _build_preview_caption(title=title, text=text, links=links)
    await state.set_state(SubmissionStates.waiting_confirm)
    await message.answer("Вот превью вашей заявки:", reply_markup=remove_keyboard())
    if photos:
        media = [InputMediaPhoto(media=photos[0], caption=caption, parse_mode="HTML")]
        for file_id in photos[1:]:
            media.append(InputMediaPhoto(media=file_id))
        await message.answer_media_group(media=media)
        await message.answer(
            "Подтвердите отправку:", reply_markup=confirm_keyboard()
        )
    else:
        await message.answer(caption, reply_markup=confirm_keyboard())


def _build_preview_caption(*, title: str, text: str, links: list[str]) -> str:
    parts = [f"<b>{escape(title)}</b>", "", escape(text)]
    if links:
        parts.append("")
        parts.append("<b>Ссылки:</b>")
        for link in links:
            parts.append(f"• {escape(link)}")
    return "\n".join(parts)


@router.callback_query(
    SubmissionStates.waiting_confirm, F.data == "submission:cancel"
)
async def confirm_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if callback.message:
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer("Подача отменена.", reply_markup=main_menu_keyboard())
    await callback.answer("Отменено")


@router.callback_query(
    SubmissionStates.waiting_confirm, F.data == "submission:send"
)
async def confirm_send(
    callback: CallbackQuery, state: FSMContext, bot: Bot
) -> None:
    data = await state.get_data()
    user = callback.from_user
    submission = await database.create_submission(
        student_id=user.id,
        student_username=user.username,
        student_full_name=user.full_name,
        title=data.get("title", ""),
        text=data.get("text", ""),
        photo_file_ids=list(data.get("photo_file_ids", [])),
        links=list(data.get("links", [])),
    )
    await state.clear()

    if callback.message:
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer(
            f"Ваша заявка #{submission.id} отправлена на модерацию ✅",
            reply_markup=main_menu_keyboard()
        )
    await callback.answer("Заявка отправлена")

    try:
        await notify_admins_about_new_submission(bot, submission)
    except Exception:
        logger.exception(
            "Failed to notify admins about submission #%s", submission.id
        )


@router.message(Command("status"))
async def cmd_status(message: Message) -> None:
    user = message.from_user
    if user is None:
        return
    submissions = await database.list_submissions_by_student(user.id, limit=5)
    if not submissions:
        await message.answer(
            "У вас пока нет заявок. Используйте /submit, чтобы подать новость.",
            reply_markup=main_menu_keyboard(),
        )
        return
    lines = ["<b>Ваши последние заявки:</b>", ""]
    for s in submissions:
        emoji = {"pending": "🕒", "approved": "✅", "rejected": "❌"}.get(
            s.status, "•"
        )
        line = f"{emoji} #{s.id} — {escape(s.title)} — <i>{s.status}</i>"
        if s.status == "rejected" and s.reject_reason:
            line += f"\n   причина: {escape(s.reject_reason)}"
        lines.append(line)
    await message.answer("\n".join(lines), reply_markup=main_menu_keyboard())

@router.message()
async def handle_unknown(message: Message) -> None:
    """Ответ на любое неизвестное сообщение."""
    await message.answer(
        "Пожалуйста, выберите команду.",
        reply_markup=main_menu_keyboard()
    )