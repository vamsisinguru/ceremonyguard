"""Pydantic request/response schemas for foundation entities."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# --------------------------------------------------------------------------- #
# Base / shared
# --------------------------------------------------------------------------- #
class ORMBase(BaseModel):
    """Base schema for ORM-backed responses."""

    model_config = ConfigDict(from_attributes=True)


# --------------------------------------------------------------------------- #
# Ceremony
# --------------------------------------------------------------------------- #
class CeremonyBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    status: str = Field("created", max_length=64)


class CeremonyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class CeremonyStatusUpdate(BaseModel):
    status: str = Field(..., min_length=1, max_length=64)


class CeremonyResponse(ORMBase):
    id: int
    name: str
    status: str
    created_at: datetime


# --------------------------------------------------------------------------- #
# Participant
# --------------------------------------------------------------------------- #
class ParticipantBase(BaseModel):
    ceremony_id: int
    name: str = Field(..., min_length=1, max_length=255)
    status: str = Field("active", max_length=64)


class ParticipantCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class ParticipantResponse(ORMBase):
    id: int
    ceremony_id: int
    name: str
    status: str
    created_at: datetime


# --------------------------------------------------------------------------- #
# CeremonyAttempt
# --------------------------------------------------------------------------- #
class CeremonyAttemptBase(BaseModel):
    ceremony_id: int
    attempt_number: int = Field(..., ge=1)
    status: str = Field("active", max_length=64)


class CeremonyAttemptCreate(BaseModel):
    pass


class CeremonyAttemptResponse(ORMBase):
    id: int
    ceremony_id: int
    attempt_number: int
    status: str
    created_at: datetime


# --------------------------------------------------------------------------- #
# Contribution
# --------------------------------------------------------------------------- #
class ContributionBase(BaseModel):
    ceremony_id: int
    attempt_id: int
    participant_id: int
    contribution_hash: str = Field(..., min_length=1, max_length=128)
    contribution_data: str = Field(..., min_length=1)
    status: str = Field("accepted", max_length=64)


class ContributionCreate(BaseModel):
    participant_id: int
    contribution_data: str = Field(..., min_length=1)


class ContributionResponse(ORMBase):
    id: int
    ceremony_id: int
    attempt_id: int
    participant_id: int
    contribution_hash: str
    contribution_data: str
    status: str
    created_at: datetime


class ContributionSubmissionResponse(BaseModel):
    """Response for contribution submission covering all Phase 3 outcomes.

    ``status`` is one of ``accepted``, ``duplicate``, or ``conflict``.
    ``contribution`` is always the canonical (accepted) contribution.
    ``submitted_hash`` is the SHA-256 hash of the current submission.
    """

    status: str
    message: str
    ceremony_id: int
    participant_id: int
    contribution: ContributionResponse
    submitted_hash: str


# --------------------------------------------------------------------------- #
# AuditEvent
# --------------------------------------------------------------------------- #
class AuditEventBase(BaseModel):
    ceremony_id: int
    participant_id: int | None = None
    event_type: str = Field(..., min_length=1, max_length=64)
    message: str = ""


class AuditEventCreate(BaseModel):
    ceremony_id: int
    participant_id: int | None = None
    event_type: str = Field(..., min_length=1, max_length=64)
    message: str = ""


class AuditEventResponse(ORMBase):
    id: int
    ceremony_id: int
    participant_id: int | None
    event_type: str
    message: str
    created_at: datetime


# --------------------------------------------------------------------------- #
# Health
# --------------------------------------------------------------------------- #
class HealthResponse(BaseModel):
    status: str
    app: str
    environment: str
