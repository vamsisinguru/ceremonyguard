"""SQLAlchemy models for CeremonyGuard foundation entities."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Ceremony(Base):
    """A multi-party cryptographic ceremony."""

    __tablename__ = "ceremonies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="created")
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
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="registered")
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
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )

    ceremony: Mapped["Ceremony"] = relationship(back_populates="attempts")
    contributions: Mapped[list["Contribution"]] = relationship(
        back_populates="attempt", cascade="all, delete-orphan"
    )


class Contribution(Base):
    """A participant's contribution within a specific ceremony attempt."""

    __tablename__ = "contributions"

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
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="submitted")
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
