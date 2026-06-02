from aiogram.filters.callback_data import CallbackData
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

SKIP_BUTTON_TEXT = "Пропустить"
DONE_BUTTON_TEXT = "Готово"
CANCEL_BUTTON_TEXT = "Отменить"
SAVE_DRAFT_BUTTON_TEXT = "Сохранить черновик"


# ---------------------------------------------------------------------------
# CallbackData для черновиков
# ---------------------------------------------------------------------------

class DraftCallback(CallbackData, prefix="draft"):
    action: str   # "load" | "delete"
    draft_id: int


# ---------------------------------------------------------------------------
# Reply-клавиатуры
# ---------------------------------------------------------------------------

def skip_cancel_keyboard() -> ReplyKeyboardMarkup:
    """«Пропустить / Сохранить черновик / Отменить»."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=SKIP_BUTTON_TEXT)],
            [KeyboardButton(text=SAVE_DRAFT_BUTTON_TEXT)],
            [KeyboardButton(text=CANCEL_BUTTON_TEXT)],
        ],
        resize_keyboard=True,
    )


def photos_keyboard() -> ReplyKeyboardMarkup:
    """«Готово / Пропустить / Сохранить черновик / Отменить»."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=DONE_BUTTON_TEXT)],
            [KeyboardButton(text=SKIP_BUTTON_TEXT)],
            [KeyboardButton(text=SAVE_DRAFT_BUTTON_TEXT)],
            [KeyboardButton(text=CANCEL_BUTTON_TEXT)],
        ],
        resize_keyboard=True,
    )


def cancel_keyboard() -> ReplyKeyboardMarkup:
    """«Сохранить черновик / Отменить» — для шагов заголовка и текста."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=SAVE_DRAFT_BUTTON_TEXT)],
            [KeyboardButton(text=CANCEL_BUTTON_TEXT)],
        ],
        resize_keyboard=True,
    )


def remove_keyboard() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()


def confirm_keyboard() -> InlineKeyboardMarkup:
    """Инлайн-клавиатура подтверждения отправки заявки."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Отправить", callback_data="submission:send"),
                InlineKeyboardButton(text="Отменить", callback_data="submission:cancel"),
            ]
        ]
    )


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Главное меню."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Предложить новость")],
            [KeyboardButton(text="Статус"), KeyboardButton(text="Черновики")],
        ],
        resize_keyboard=True,
        persistent=True,
    )


# ---------------------------------------------------------------------------
# Инлайн-клавиатура списка черновиков
# ---------------------------------------------------------------------------

def drafts_list_keyboard(drafts: list) -> InlineKeyboardMarkup:
    """Кнопка на каждый черновик: «📂 #N заголовок» + «🗑 Удалить»."""
    rows = []
    for draft in drafts:
        title_preview = (draft.title or "Без заголовка")[:30]
        rows.append([
            InlineKeyboardButton(
                text=f"📂 #{draft.id} {title_preview}",
                callback_data=DraftCallback(action="load", draft_id=draft.id).pack(),
            ),
            InlineKeyboardButton(
                text="🗑",
                callback_data=DraftCallback(action="delete", draft_id=draft.id).pack(),
            ),
        ])
    return InlineKeyboardMarkup(inline_keyboard=rows)
