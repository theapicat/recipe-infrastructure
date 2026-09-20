"""Roller (anonym/bruker/admin) og felles handlinger mot Auth API."""
from __future__ import annotations

from dataclasses import dataclass, field

from .config import TEST_PASSWORD, Settings
from .http import ApiClient, expect, parse
from .models.auth import TokenResponse, UserProfile
from .models.common import MessageResponse


@dataclass
class Actor:
    """En rolle mot systemet, med én klient per tjeneste (alle peker på gatewayen som standard)."""

    name: str
    gateway: ApiClient
    auth: ApiClient
    core: ApiClient
    email: str | None = None
    password: str | None = None
    user_id: str | None = None
    tokens: TokenResponse | None = field(default=None, repr=False)


def make_actor(settings: Settings, name: str, tokens: TokenResponse | None = None, **extra) -> Actor:
    token = tokens.access_token if tokens else None
    return Actor(
        name=name,
        gateway=ApiClient(settings.gateway_url, timeout=settings.timeout, token=token, label=name),
        auth=ApiClient(settings.auth_url, timeout=settings.timeout, token=token, label=name),
        core=ApiClient(settings.core_url, timeout=settings.timeout, token=token, label=name),
        tokens=tokens,
        **extra,
    )


def password_login(settings: Settings, client: ApiClient, email: str, password: str):
    """Rå innlogging (OAuth2 password grant). Returnerer responsen slik at feilscenarier kan testes."""
    return client.post(
        "/api/auth/connect/token",
        data={"grant_type": "password", "username": email, "password": password, "client_id": settings.client_id},
    )


def login(settings: Settings, client: ApiClient, email: str, password: str) -> TokenResponse:
    return expect(password_login(settings, client, email, password), 200, TokenResponse)


def register(client: ApiClient, email: str, password: str = TEST_PASSWORD, first: str = "Api", last: str = "Test"):
    """Registrering. Endepunktet binder med [FromForm], så kroppen sendes som skjema (slik webappen gjør)."""
    return client.post(
        "/api/auth/account/register",
        data={"email": email, "password": password, "firstName": first, "lastName": last},
    )


def admin_confirm_email(admin: Actor, user_id: str):
    return admin.auth.post("/api/auth/admin/users/confirm-email", json={"userId": user_id})


def admin_delete_user(admin: Actor, user_id: str):
    return admin.auth.post("/api/auth/admin/users/delete", json={"userId": user_id})


def admin_list_users(admin: Actor) -> list[dict]:
    resp = admin.auth.get("/api/auth/admin/users")
    assert resp.status_code == 200, f"kunne ikke liste brukere: {resp.status_code} {resp.text[:200]}"
    return resp.json()


def admin_list_blacklist(admin: Actor) -> list[dict]:
    resp = admin.auth.get("/api/auth/admin/blacklist")
    assert resp.status_code == 200, f"kunne ikke liste svartelisten: {resp.status_code} {resp.text[:200]}"
    return resp.json()


__all__ = [
    "Actor", "make_actor", "password_login", "login", "register", "admin_confirm_email", "admin_delete_user",
    "admin_list_users", "admin_list_blacklist", "parse", "UserProfile", "MessageResponse",
]
