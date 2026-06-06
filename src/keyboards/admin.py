from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


class ModerationCallback(CallbackData, prefix="mod"):
    """CallbackData для кнопок модерации."""

    action: str  # "approve" | "reject" | "edit_text"
    submission_id: int


def moderation_keyboard(submission_id: int) -> InlineKeyboardMarkup:
    """Клавиатура «Одобрить / Отклонить» для администраторов."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Одобрить",
                    callback_data=ModerationCallback(
                        action="approve", submission_id=submission_id
                    ).pack(),
                ),
                InlineKeyboardButton(
                    text="❌ Отклонить",
                    callback_data=ModerationCallback(
                        action="reject", submission_id=submission_id
                    ).pack(),
                ),
            ],
            [

                InlineKeyboardButton(

                    text="✏️ Редактировать текст",

                    callback_data=ModerationCallback(

                        action="edit_text", submission_id=submission_id

                    ).pack(),

                ),

            ],
        ]
    )
