"""SQLAlchemy models for CeremonyGuard foundation entities."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Ceremony(Base):
    """A multi-party cryptographic ceremony."""

    __tablename__ = "ceremonies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )

    participants: Mapped[list["Participant"]] = relationship(
        back_populates="ceremony", cascade="all, delete-orphan"
    )
    attempts: Mapped[list["CeremonyAttempt"]] = relationship(
        back_populates="ceremony", cascade="all, delete-orphan"
    )
    contributions: Mapped[list["Contribution"]] = relationship(
        back_populates="ceremony", cascade="all, delete-orphan"
    )
    audit_events: Mapped[list["AuditEvent"]] = relationship(
        back_populates="ceremony", cascade="all, delete-orphan"
    )


class Participant(Base):
    """A participant contributing to a ceremony."""

    __tablename__ = "participants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ceremony_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("ceremonies.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )

    ceremony: Mapped["Ceremony"] = relationship(back_populates="participants")
    contributions: Mapped[list["Contribution"]] = relationship(
        back_populates="participant"
    )
    audit_events: Mapped[list["AuditEvent"]] = relationship(
        back_populates="participant"
    )


class CeremonyAttempt(Base):
    """A single attempt/run of a ceremony.

    Multiple attempts may exist for a ceremony due to retries or restarts.
    Contributions are scoped to a specific attempt to prevent mixing.
    """

    __tablename__ = "ceremony_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ceremony_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("ceremonies.id", ondelete="CASCADE"), nullable=False
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )

    ceremony: Mapped["Ceremony"] = relationship(back_populates="attempts")
    contributions: Mapped[list["Contribution"]] = relationship(
        back_populates="attempt", cascade="all, delete-orphan"
    )


class Contribution(Base):
    """A participant's contribution within a specific ceremony attempt.

    The ``status`` column distinguishes the canonical contribution
    (``accepted``) from rejected retries (``duplicate`` or ``conflict``).
    A partial unique index ensures at most one ``accepted`` contribution per
    (ceremony, participant) pair, enforcing the one-canonical-contribution
    rule at the database level.
    """

    __tablename__ = "contributions"
    __table_args__ = (
        Index(
            "ix_contributions_canonical",
            "ceremony_id",
            "participant_id",
            unique=True,
            sqlite_where=text("status = 'accepted'"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ceremony_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("ceremonies.id", ondelete="CASCADE"), nullable=False
    )
    attempt_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("ceremony_attempts.id", ondelete="CASCADE"), nullable=False
    )
    participant_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("participants.id", ondelete="CASCADE"), nullable=False
    )
    contribution_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    contribution_data: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="accepted")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )

    ceremony: Mapped["Ceremony"] = relationship(back_populates="contributions")
    attempt: Mapped["CeremonyAttempt"] = relationship(back_populates="contributions")
    participant: Mapped["Participant"] = relationship(back_populates="contributions")


class AuditEvent(Base):
    """An immutable audit trail entry for ceremony-related events."""

    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ceremony_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("ceremonies.id", ondelete="CASCADE"), nullable=False
    )
    participant_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("participants.id", ondelete="SET NULL"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )

    ceremony: Mapped["Ceremony"] = relationship(back_populates="audit_events")
    participant: Mapped["Participant | None"] = relationship(
        back_populates="audit_events"
    )


class CeremonyResult(Base):
    """The generated final result for a completed ceremony (Phase 4).

    Stores the cryptographic digest of the canonical contribution set at
    finalization time so that subsequent verification can detect tampering,
    removal, or replacement of canonical contributions.
    """

    __tablename__ = "ceremony_results"
    __table_args__ = (Index("ix_ceremony_results_ceremony", "ceremony_id", unique=True),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ceremony_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("ceremonies.id", ondelete="CASCADE"), nullable=False
    )
    final_digest: Mapped[str] = mapped_column(String(128), nullable=False)
    contribution_digest: Mapped[str] = mapped_column(String(128), nullable=False)
    participant_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )

    ceremony: Mapped["Ceremony"] = relationship()


class SubmissionRecord(Base):
    """Tracks a logical (idempotent) contribution submission.

    When a participant submits a contribution with a ``submission_key``, a
    record is stored mapping that key to the resulting contribution.  If the
    same key is submitted again (e.g. after a lost response), the existing
    result is returned instead of creating a new contribution.

    This enables safe retries: the client can re-send the same logical
    submission without risk of creating a duplicate canonical contribution.
    """

    __tablename__ = "submission_records"
    __table_args__ = (
        Index(
            "ix_submission_records_ceremony_key",
            "ceremony_id",
            "submission_key",
            unique=True,
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ceremony_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("ceremonies.id", ondelete="CASCADE"), nullable=False
    )
    participant_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("participants.id", ondelete="CASCADE"), nullable=False
    )
    attempt_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("ceremony_attempts.id", ondelete="CASCADE"), nullable=False
    )
    submission_key: Mapped[str] = mapped_column(String(128), nullable=False)
    contribution_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("contributions.id", ondelete="CASCADE"), nullable=False
    )
    submission_status: Mapped[str] = mapped_column(String(64), nullable=False)
    submitted_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )
