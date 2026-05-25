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


def skip_cancel_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура «Пропустить / Отменить» (для шагов фото и ссылок)."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=SKIP_BUTTON_TEXT)],
            [KeyboardButton(text=CANCEL_BUTTON_TEXT)],
        ],
        resize_keyboard=True,
    )


def photos_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура шага сбора фотографий: «Готово / Пропустить / Отменить»."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=DONE_BUTTON_TEXT)],
            [KeyboardButton(text=SKIP_BUTTON_TEXT)],
            [KeyboardButton(text=CANCEL_BUTTON_TEXT)],
        ],
        resize_keyboard=True,
    )


def cancel_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура с единственной кнопкой «Отменить»."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=CANCEL_BUTTON_TEXT)]],
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
