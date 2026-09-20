"""Auth API: anonym tilgang og avvisning av anonyme kall. Endrer ingen data og sender ingen e-post."""
from __future__ import annotations

import uuid

import pytest

from apitests.actors import Actor
from apitests.config import Settings
from apitests.http import describe, expect
from apitests.models.common import MessageResponse, ProblemDetails

# Endepunkter som krever innlogging: (metode, sti)
AUTHENTICATED_ACCOUNT_ENDPOINTS = [
    ("GET", "/api/auth/account/me"),
    ("PUT", "/api/auth/account/profile"),
    ("POST", "/api/auth/account/change-password"),
    ("POST", "/api/auth/account/set-password"),
    ("GET", "/api/auth/account/complete-welcome"),
    ("POST", "/api/auth/account/resend-confirmation"),
    ("DELETE", "/api/auth/account/me"),
]


@pytest.mark.parametrize("method,path", AUTHENTICATED_ACCOUNT_ENDPOINTS, ids=lambda v: v)
def test_account_endpoints_reject_anonymous(anon: Actor, method: str, path: str):
    resp = anon.auth.request(method, path, json={})
    assert resp.status_code == 401, f"{method} {path}: {describe(resp)}"


@pytest.mark.parametrize("method,path", AUTHENTICATED_ACCOUNT_ENDPOINTS, ids=lambda v: v)
def test_account_endpoints_reject_a_garbage_token(anon: Actor, method: str, path: str):
    """Webappen sender `Bearer undefined` når sesjonen mangler; det skal gi 401, ikke 500 eller 200."""
    resp = anon.auth.request(method, path, json={}, headers={"Authorization": "Bearer undefined"})
    assert resp.status_code == 401, f"{method} {path}: {describe(resp)}"


def test_register_validation_errors_are_reported_per_field(anon: Actor):
    resp = anon.auth.post(
        "/api/auth/account/register", data={"email": "ikke-en-epost", "password": "x", "firstName": "", "lastName": ""}
    )
    problem = expect(resp, 400, ProblemDetails)
    assert problem.errors is not None
    assert set(problem.errors) == {"Email", "Password", "FirstName", "LastName"}


def test_register_rejects_a_password_that_breaks_the_rules(settings: Settings, anon: Actor):
    resp = anon.auth.post(
        "/api/auth/account/register",
        data={"email": settings.test_email("svakt-passord"), "password": "alltidsmatt", "firstName": "A", "lastName": "B"},
    )
    problem = expect(resp, 400, ProblemDetails)
    assert problem.errors is not None and "Password" in problem.errors


def test_recover_password_never_reveals_whether_the_email_exists(settings: Settings, anon: Actor):
    """Ukjent adresse: generisk 200 og INGEN e-post (så testen er trygg uten e-postsjekk)."""
    resp = anon.auth.post("/api/auth/account/recover", json={"email": settings.test_email(f"ukjent-{uuid.uuid4().hex[:6]}")})
    assert "Dersom e-posten er registrert" in expect(resp, 200, MessageResponse).message


def test_confirm_email_for_an_unknown_user_id_is_404(anon: Actor):
    """Id-en er en GUID (ikke gjettbar), så 404 avslører ingenting. Med kjent bruker + ugyldig token: se kontoflyten."""
    resp = anon.auth.post("/api/auth/account/confirm-email", json={"userId": str(uuid.uuid4()), "token": "ugyldig"})
    assert resp.status_code == 404, describe(resp)


def test_google_login_redirects_to_google(anon: Actor):
    """Selve Google-innloggingen kan ikke automatiseres; vi sjekker at utfordringen starter og går til Google."""
    resp = anon.auth.get("/api/auth/account/external-login", params={"provider": "Google"})
    assert resp.status_code == 302, describe(resp)
    assert resp.headers["Location"].startswith("https://accounts.google.com/"), resp.headers["Location"]
