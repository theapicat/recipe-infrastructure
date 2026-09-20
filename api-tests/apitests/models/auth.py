"""DTO-er for recipe-auth-api (speiler `Domain/DTOs` og OpenIddict-protokollen)."""
from __future__ import annotations

from datetime import datetime
from enum import IntEnum

from .base import ApiModel, SnakeModel


class TokenResponse(SnakeModel):
    access_token: str
    expires_in: int
    id_token: str
    refresh_token: str
    scope: str
    token_type: str


class OAuthError(SnakeModel):
    error: str
    error_description: str | None = None
    error_uri: str | None = None


class UserProfile(ApiModel):
    """`UserProfileResponse`: svar fra register, me, profile og complete-welcome."""

    user_id: str
    user_name: str
    email: str
    first_name: str
    last_name: str
    role: str
    has_password: bool
    is_google_account: bool
    is_email_confirmed: bool
    welcome_completed: bool
    is_locked: bool
    created_at: datetime
    last_modified_at: datetime | None = None
    last_login_at: datetime | None = None


class AdminUserListItem(ApiModel):
    user_id: str
    email: str
    full_name: str
    first_name: str
    last_name: str
    role: str
    is_email_confirmed: bool
    is_locked: bool
    is_google_account: bool
    created_at: datetime
    last_login_at: datetime | None = None


class AdminUserDetails(ApiModel):
    user_id: str
    user_name: str
    email: str
    first_name: str
    last_name: str
    role: str
    has_password: bool
    is_google_account: bool
    is_email_confirmed: bool
    welcome_completed: bool
    is_locked: bool
    lockout_end: datetime | None = None
    lockout_reason: str
    lockout_reason_details: str | None = None
    access_failed_count: int
    created_at: datetime
    last_modified_at: datetime
    last_login_at: datetime | None = None
    confirmation7_days_reminder_sent_at: datetime | None = None
    confirmation14_days_locked_sent_at: datetime | None = None
    inactivity_warning6_months_sent_at: datetime | None = None
    inactivity1_year_locked_sent_at: datetime | None = None


class BlacklistType(IntEnum):
    EXACT_EMAIL = 1
    DOMAIN = 2


class BlacklistEntry(ApiModel):
    id: str
    pattern: str
    type: BlacklistType
    reason: str | None = None
    created_at: datetime
    created_by_admin_id: str
