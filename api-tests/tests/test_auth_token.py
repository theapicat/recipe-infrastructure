"""Innlogging og tokens: OAuth2 password grant, refresh og revokering (`/api/auth/connect/*`)."""
from __future__ import annotations

import pytest

from apitests.actors import Actor, login, password_login
from apitests.config import TEST_PASSWORD, Settings
from apitests.http import describe, expect
from apitests.models.auth import OAuthError, TokenResponse
from apitests.tokens import claims_of


def test_admin_login_issues_a_token_pair(admin: Actor, settings: Settings):
    tokens = admin.tokens
    assert tokens.token_type == "Bearer"
    assert tokens.expires_in > 0
    claims = claims_of(tokens.access_token)
    assert claims["email"] == settings.admin_email
    assert claims["role"] == "admin", "rollen skal være med små bokstaver (Auth API sin konvensjon)"
    assert claims["aud"] == "recipe-frontend"
    assert claims["client_id"] == settings.client_id


def test_wrong_password_is_rejected(settings: Settings, anon: Actor):
    err = expect(password_login(settings, anon.auth, settings.admin_email, "Feil#Passord123"), 400, OAuthError)
    assert err.error == "invalid_grant"


def test_unknown_user_gets_the_same_error_as_wrong_password(settings: Settings, anon: Actor):
    """Ingen brukeropplisting: samme svar om e-posten finnes eller ikke."""
    unknown = expect(password_login(settings, anon.auth, settings.test_email("finnes-ikke"), TEST_PASSWORD), 400, OAuthError)
    wrong = expect(password_login(settings, anon.auth, settings.admin_email, "Feil#Passord123"), 400, OAuthError)
    assert unknown.error == wrong.error == "invalid_grant"
    assert unknown.error_description == wrong.error_description


def test_unsupported_grant_type_is_rejected(settings: Settings, anon: Actor):
    resp = anon.auth.post(
        "/api/auth/connect/token", data={"grant_type": "client_credentials", "client_id": settings.client_id}
    )
    assert expect(resp, 400, OAuthError).error == "unsupported_grant_type"


def test_token_endpoint_requires_form_encoding(settings: Settings, anon: Actor):
    resp = anon.auth.post(
        "/api/auth/connect/token",
        json={"grant_type": "password", "username": settings.admin_email, "password": settings.admin_password},
    )
    assert resp.status_code in (400, 415), describe(resp)


@pytest.mark.mutating
def test_refresh_token_grant_and_revocation(settings: Settings, anon: Actor, user_factory):
    user = user_factory("refresh")
    refreshed = expect(
        anon.auth.post(
            "/api/auth/connect/token",
            data={"grant_type": "refresh_token", "refresh_token": user.tokens.refresh_token, "client_id": settings.client_id},
        ),
        200, TokenResponse,
    )
    assert claims_of(refreshed.access_token)["email"] == user.email

    revoke = anon.auth.post(
        "/api/auth/connect/revoke",
        data={"token": refreshed.refresh_token, "token_type_hint": "refresh_token", "client_id": settings.client_id},
    )
    assert revoke.status_code == 200, describe(revoke)

    after = anon.auth.post(
        "/api/auth/connect/token",
        data={"grant_type": "refresh_token", "refresh_token": refreshed.refresh_token, "client_id": settings.client_id},
    )
    assert expect(after, 400, OAuthError).error == "invalid_grant"


@pytest.mark.mutating
def test_login_accepts_the_right_password_and_rejects_a_wrong_one(settings: Settings, anon: Actor, user_factory):
    """Sanity for innloggingsflyten som alle andre tester bygger på."""
    user = user_factory("login")
    assert login(settings, anon.auth, user.email, TEST_PASSWORD).token_type == "Bearer"
    assert password_login(settings, anon.auth, user.email, TEST_PASSWORD + "x").status_code == 400
