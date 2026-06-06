from aiogram.fsm.state import State, StatesGroup


class SubmissionStates(StatesGroup):
    """FSM-состояния пошаговой подачи заявки студентом."""

    waiting_title = State()
    waiting_text = State()
    waiting_photos = State()
    waiting_links = State()
    waiting_confirm = State()


class ModerationStates(StatesGroup):
    """FSM-состояния модератора при отклонении заявки."""

    waiting_reject_reason = State()
    waiting_edit_text = State()
