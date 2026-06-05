from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Optional

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, select, func
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from .config import settings


class SubmissionStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class Base(DeclarativeBase):
    pass


class Submission(Base):
    __tablename__ = "submissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(Integer, index=True)
    student_username: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    student_full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    title: Mapped[str] = mapped_column(String(512))
    text: Mapped[str] = mapped_column(Text)
    photo_file_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    links: Mapped[list[str]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(
        String(16), default=SubmissionStatus.PENDING, index=True
    )
    reject_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    reviewed_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    reviewed_by_username: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True
    )
    channel_message_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)


# ---------------------------------------------------------------------------
# Черновики (задача 1)
# ---------------------------------------------------------------------------

class Draft(Base):
    """Черновик заявки — сохраняется пользователем в любой момент FSM."""
    __tablename__ = "drafts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(Integer, index=True)
    title: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    photo_file_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    links: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


# ---------------------------------------------------------------------------
# Чёрный список (задача 3)
# ---------------------------------------------------------------------------

class BlacklistEntry(Base):
    """Запись о забаненном пользователе."""
    __tablename__ = "blacklist"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    banned_by: Mapped[int] = mapped_column(Integer)
    banned_by_username: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    banned_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ---------------------------------------------------------------------------
# Engine / session
# ---------------------------------------------------------------------------

engine = create_async_engine(settings.database_url, echo=False, future=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def init_db() -> None:
    """Создаёт таблицы при первом запуске."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# ---------------------------------------------------------------------------
# CRUD — Submission (без изменений)
# ---------------------------------------------------------------------------

async def create_submission(
    *,
    student_id: int,
    student_username: Optional[str],
    student_full_name: Optional[str],
    title: str,
    text: str,
    photo_file_ids: list[str],
    links: list[str],
) -> Submission:
    async with SessionLocal() as session:
        submission = Submission(
            student_id=student_id,
            student_username=student_username,
            student_full_name=student_full_name,
            title=title,
            text=text,
            photo_file_ids=photo_file_ids,
            links=links,
            status=SubmissionStatus.PENDING,
        )
        session.add(submission)
        await session.commit()
        await session.refresh(submission)
        return submission


async def get_submission(submission_id: int) -> Optional[Submission]:
    async with SessionLocal() as session:
        return await session.get(Submission, submission_id)


async def list_pending_submissions(limit: int = 50) -> list[Submission]:
    async with SessionLocal() as session:
        stmt = (
            select(Submission)
            .where(Submission.status == SubmissionStatus.PENDING)
            .order_by(Submission.created_at.asc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())


async def list_recent_processed_submissions(limit: int = 20) -> list[Submission]:
    async with SessionLocal() as session:
        stmt = (
            select(Submission)
            .where(Submission.status != SubmissionStatus.PENDING)
            .order_by(Submission.reviewed_at.desc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())


async def list_submissions_by_student(
    student_id: int, limit: int = 5
) -> list[Submission]:
    async with SessionLocal() as session:
        stmt = (
            select(Submission)
            .where(Submission.student_id == student_id)
            .order_by(Submission.created_at.desc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())


async def approve_submission(
    submission_id: int,
    reviewer_id: int,
    reviewer_username: Optional[str],
) -> Optional[Submission]:
    async with SessionLocal() as session:
        submission = await session.get(Submission, submission_id)
        if submission is None or submission.status != SubmissionStatus.PENDING:
            return submission
        submission.status = SubmissionStatus.APPROVED
        submission.reviewed_by = reviewer_id
        submission.reviewed_by_username = reviewer_username
        submission.reviewed_at = datetime.utcnow()
        await session.commit()
        await session.refresh(submission)
        return submission


async def reject_submission(
    submission_id: int,
    reviewer_id: int,
    reviewer_username: Optional[str],
    reason: str,
) -> Optional[Submission]:
    async with SessionLocal() as session:
        submission = await session.get(Submission, submission_id)
        if submission is None or submission.status != SubmissionStatus.PENDING:
            return submission
        submission.status = SubmissionStatus.REJECTED
        submission.reviewed_by = reviewer_id
        submission.reviewed_by_username = reviewer_username
        submission.reviewed_at = datetime.utcnow()
        submission.reject_reason = reason
        await session.commit()
        await session.refresh(submission)
        return submission


async def set_channel_message_id(submission_id: int, message_id: int) -> None:
    async with SessionLocal() as session:
        submission = await session.get(Submission, submission_id)
        if submission is None:
            return
        submission.channel_message_id = message_id
        await session.commit()


async def count_submissions_by_status(student_id: int) -> dict[str, int]:
    async with SessionLocal() as session:
        stmt = (
            select(Submission.status, func.count(Submission.id))
            .where(Submission.student_id == student_id)
            .group_by(Submission.status)
        )
        result = await session.execute(stmt)
        return {row[0]: row[1] for row in result.all()}


# ---------------------------------------------------------------------------
# CRUD — Draft (задача 1)
# ---------------------------------------------------------------------------

async def save_draft(
    *,
    student_id: int,
    title: Optional[str],
    text: Optional[str],
    photo_file_ids: list[str],
    links: list[str],
) -> Draft:
    """Создаёт новый черновик."""
    async with SessionLocal() as session:
        draft = Draft(
            student_id=student_id,
            title=title,
            text=text,
            photo_file_ids=photo_file_ids,
            links=links,
        )
        session.add(draft)
        await session.commit()
        await session.refresh(draft)
        return draft


async def get_draft(draft_id: int) -> Optional[Draft]:
    async with SessionLocal() as session:
        return await session.get(Draft, draft_id)


async def list_drafts_by_student(student_id: int, limit: int = 10) -> list[Draft]:
    async with SessionLocal() as session:
        stmt = (
            select(Draft)
            .where(Draft.student_id == student_id)
            .order_by(Draft.updated_at.desc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())


async def delete_draft(draft_id: int, student_id: int) -> bool:
    """Удаляет черновик. Возвращает True если удалён, False если не найден
    или не принадлежит студенту."""
    async with SessionLocal() as session:
        draft = await session.get(Draft, draft_id)
        if draft is None or draft.student_id != student_id:
            return False
        await session.delete(draft)
        await session.commit()
        return True


# ---------------------------------------------------------------------------
# CRUD — Blacklist (задача 3)
# ---------------------------------------------------------------------------

async def ban_user(
    *,
    user_id: int,
    username: Optional[str],
    full_name: Optional[str],
    reason: Optional[str],
    banned_by: int,
    banned_by_username: Optional[str],
) -> tuple[BlacklistEntry, bool]:
    """Добавляет пользователя в чёрный список.
    Возвращает (запись, created): created=False если уже был забанен."""
    async with SessionLocal() as session:
        existing = await session.scalar(
            select(BlacklistEntry).where(BlacklistEntry.user_id == user_id)
        )
        if existing is not None:
            return existing, False
        entry = BlacklistEntry(
            user_id=user_id,
            username=username,
            full_name=full_name,
            reason=reason,
            banned_by=banned_by,
            banned_by_username=banned_by_username,
        )
        session.add(entry)
        await session.commit()
        await session.refresh(entry)
        return entry, True


async def unban_user(user_id: int) -> bool:
    """Удаляет из чёрного списка. Возвращает True если запись была."""
    async with SessionLocal() as session:
        entry = await session.scalar(
            select(BlacklistEntry).where(BlacklistEntry.user_id == user_id)
        )
        if entry is None:
            return False
        await session.delete(entry)
        await session.commit()
        return True


async def is_banned(user_id: int) -> bool:
    async with SessionLocal() as session:
        entry = await session.scalar(
            select(BlacklistEntry).where(BlacklistEntry.user_id == user_id)
        )
        return entry is not None


async def list_blacklist(limit: int = 50) -> list[BlacklistEntry]:
    async with SessionLocal() as session:
        stmt = (
            select(BlacklistEntry)
            .order_by(BlacklistEntry.banned_at.desc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())


async def get_blacklist_entry_by_user_id(user_id: int) -> Optional[BlacklistEntry]:
    async with SessionLocal() as session:
        return await session.scalar(
            select(BlacklistEntry).where(BlacklistEntry.user_id == user_id)
        )

async def update_submission_text(
    submission_id: int,
    new_text: str,
) -> Optional[Submission]:
    async with SessionLocal() as session:
        submission = await session.get(Submission, submission_id)

        if submission is None:
            return None

        if submission.status != SubmissionStatus.PENDING:
            return submission

        submission.text = new_text

        await session.commit()
        await session.refresh(submission)

        return submission