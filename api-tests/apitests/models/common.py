"""Felles svarformer på tvers av tjenestene."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from .base import ApiModel


class HealthResponse(ApiModel):
    status: str
    service: str
    environment: str
    timestamp: datetime


class MessageResponse(ApiModel):
    """`{ "message": "..." }` (Auth API sine suksess-/feilsvar)."""

    message: str


class IdentityError(ApiModel):
    code: str
    description: str


class MessageWithErrors(ApiModel):
    message: str
    errors: list[IdentityError]


class ProblemDetails(BaseModel):
    """RFC 9110 problem details fra ASP.NET (modellvalidering, 404 uten kropp osv.). Rammeverksdefinert, så åpen."""

    model_config = ConfigDict(extra="allow")

    type: str | None = None
    title: str | None = None
    status: int | None = None
    errors: dict[str, list[str]] | None = None
    traceId: str | None = None
