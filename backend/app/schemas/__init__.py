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


class CeremonyCreate(CeremonyBase):
    pass


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
    status: str = Field("registered", max_length=64)


class ParticipantCreate(BaseModel):
    ceremony_id: int
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
    status: str = Field("pending", max_length=64)


class CeremonyAttemptCreate(BaseModel):
    ceremony_id: int
    attempt_number: int = Field(..., ge=1)


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
    status: str = Field("submitted", max_length=64)


class ContributionCreate(BaseModel):
    ceremony_id: int
    attempt_id: int
    participant_id: int
    contribution_hash: str = Field(..., min_length=1, max_length=128)


class ContributionResponse(ORMBase):
    id: int
    ceremony_id: int
    attempt_id: int
    participant_id: int
    contribution_hash: str
    status: str
    created_at: datetime


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
