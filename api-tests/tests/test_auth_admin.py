"""Auth API: admin-endepunktene (`/api/auth/admin/*`): tilgangskontroll, brukeradministrasjon og svarteliste."""
from __future__ import annotations

import uuid

import pytest

from apitests.actors import Actor, admin_list_blacklist, admin_list_users, password_login, register
from apitests.config import TEST_PASSWORD, Settings
from apitests.http import describe, expect
from apitests.models.auth import AdminUserDetails, AdminUserListItem, BlacklistEntry, BlacklistType, OAuthError, UserProfile
from apitests.models.common import MessageResponse, ProblemDetails

pytestmark = [pytest.mark.mutating, pytest.mark.emails]

A = "/api/auth/admin"
_RANDOM = "00000000-0000-0000-0000-000000000001"

# (metode, sti, body) for alle admin-endepunkter. Body er bare nødvendig for at forespørselen skal være gyldig.
ADMIN_ENDPOINTS = [
    ("GET", f"{A}/users", None),
    ("GET", f"{A}/users/{_RANDOM}", None),
    ("PUT", f"{A}/users", {"userId": _RANDOM, "firstName": "A", "lastName": "B", "email": "a@example.com"}),
    ("POST", f"{A}/users/lock", {"userId": _RANDOM}),
    ("POST", f"{A}/users/unlock", {"userId": _RANDOM}),
    ("POST", f"{A}/users/confirm-email", {"userId": _RANDOM}),
    ("POST", f"{A}/users/resend-confirmation", {"userId": _RANDOM}),
    ("POST", f"{A}/users/reset-password-request", {"userId": _RANDOM}),
    ("POST", f"{A}/users/delete", {"userId": _RANDOM}),
    ("POST", f"{A}/users/delete-and-blacklist", {"userId": _RANDOM}),
    ("GET", f"{A}/blacklist", None),
    ("POST", f"{A}/blacklist", {"pattern": "apitest-x@example.com", "type": 1}),
    ("DELETE", f"{A}/blacklist/{_RANDOM}", None),
    ("POST", f"{A}/send-email", {"userId": _RANDOM, "subject": "s", "message": "m"}),
]


@pytest.mark.parametrize("method,path,body", ADMIN_ENDPOINTS, ids=lambda v: v if isinstance(v, str) else "")
def test_admin_endpoints_reject_anonymous(anon: Actor, method: str, path: str, body):
    resp = anon.auth.request(method, path, json=body)
    assert resp.status_code == 401, f"{method} {path}: {describe(resp)}"


@pytest.mark.parametrize("method,path,body", ADMIN_ENDPOINTS, ids=lambda v: v if isinstance(v, str) else "")
def test_admin_endpoints_reject_a_normal_user(user: Actor, method: str, path: str, body):
    resp = user.auth.request(method, path, json=body)
    assert resp.status_code == 403, f"{method} {path}: {describe(resp)}"


def test_list_users_matches_the_dto_for_every_user(admin: Actor, user: Actor):
    resp = admin.auth.get(f"{A}/users")
    users = expect(resp, 200, list[AdminUserListItem])  # strengt: alle eksisterende brukere må matche DTO-en
    mine = next(u for u in users if u.user_id == user.user_id)
    assert mine.email == user.email and mine.role == "user" and mine.is_email_confirmed and not mine.is_locked
    seeded = next(u for u in users if u.email == admin.email)
    assert seeded.role == "admin"


def test_user_details(admin: Actor, user: Actor):
    details = expect(admin.auth.get(f"{A}/users/{user.user_id}"), 200, AdminUserDetails)
    assert details.user_id == user.user_id and details.email == user.email
    assert details.role == "user" and details.is_email_confirmed and not details.is_locked
    assert details.lockout_reason == "None"


def test_unknown_user_is_404(admin: Actor):
    resp = admin.auth.get(f"{A}/users/{uuid.uuid4()}")
    assert "ikke funnet" in expect(resp, 404, MessageResponse).message


def test_admin_can_update_a_user(admin: Actor, user_factory, checklist):
    user = user_factory("admin-endrer")
    resp = admin.auth.put(
        f"{A}/users", json={"userId": user.user_id, "firstName": "Endret", "lastName": "Avadmin", "email": user.email}
    )
    expect(resp, 200, MessageResponse)
    checklist.expect(user.email, "Profil oppdatert av administrator", "PUT /admin/users")
    details = expect(admin.auth.get(f"{A}/users/{user.user_id}"), 200, AdminUserDetails)
    assert (details.first_name, details.last_name) == ("Endret", "Avadmin")


def test_lock_blocks_login_and_unlock_restores_it(settings: Settings, anon: Actor, admin: Actor, user_factory, checklist):
    user = user_factory("sperr")
    expect(admin.auth.post(f"{A}/users/lock", json={"userId": user.user_id, "reasonDetails": "apitest"}), 200, MessageResponse)
    checklist.expect(user.email, "Konto sperret", "POST /admin/users/lock")

    assert expect(admin.auth.get(f"{A}/users/{user.user_id}"), 200, AdminUserDetails).is_locked
    blocked = expect(password_login(settings, anon.auth, user.email, TEST_PASSWORD), 400, OAuthError)
    assert "sperret" in (blocked.error_description or "")

    expect(admin.auth.post(f"{A}/users/unlock", json={"userId": user.user_id}), 200, MessageResponse)
    checklist.expect(user.email, "Konto gjenåpnet", "POST /admin/users/unlock")
    assert password_login(settings, anon.auth, user.email, TEST_PASSWORD).status_code == 200


def test_admin_can_confirm_email_and_trigger_mails(admin: Actor, user_factory, checklist):
    user = user_factory("admin-bekrefter", confirm=False)

    expect(admin.auth.post(f"{A}/users/resend-confirmation", json={"userId": user.user_id}), 200, MessageResponse)
    checklist.expect(user.email, "Ny bekreftelseslenke", "POST /admin/users/resend-confirmation")

    expect(admin.auth.post(f"{A}/users/confirm-email", json={"userId": user.user_id}), 200, MessageResponse)
    checklist.expect(user.email, "E-post manuelt bekreftet av admin", "POST /admin/users/confirm-email")
    assert expect(admin.auth.get(f"{A}/users/{user.user_id}"), 200, AdminUserDetails).is_email_confirmed

    again = admin.auth.post(f"{A}/users/resend-confirmation", json={"userId": user.user_id})
    assert "allerede bekreftet" in expect(again, 400, MessageResponse).message

    expect(admin.auth.post(f"{A}/users/reset-password-request", json={"userId": user.user_id}), 200, MessageResponse)
    checklist.expect(user.email, "Tilbakestilling av passord (lenke)", "POST /admin/users/reset-password-request")


def test_admin_can_send_a_custom_email(settings: Settings, admin: Actor, user_factory, checklist):
    user = user_factory("admin-epost")
    subject = settings.test_name("admin-melding")
    resp = admin.auth.post(f"{A}/send-email", json={"userId": user.user_id, "subject": subject, "message": "Hei fra API-testen"})
    expect(resp, 200, MessageResponse)
    checklist.expect(user.email, f"Skreddersydd melding fra admin, emne «{subject}»", "POST /admin/send-email")


def test_admin_can_delete_a_user(settings: Settings, anon: Actor, admin: Actor, user_factory, checklist):
    user = user_factory("admin-sletter")
    expect(admin.auth.post(f"{A}/users/delete", json={"userId": user.user_id}), 200, MessageResponse)
    checklist.expect(user.email, "Konto slettet av administrator", "POST /admin/users/delete")

    assert admin.auth.get(f"{A}/users/{user.user_id}").status_code == 404
    assert user.user_id not in {u["userId"] for u in admin_list_users(admin)}
    assert password_login(settings, anon.auth, user.email, TEST_PASSWORD).status_code == 400


def _drop_blacklist_entries(admin: Actor, cleanup, pattern: str) -> None:
    def action() -> None:
        for entry in admin_list_blacklist(admin):
            if entry["pattern"] == pattern:
                admin.auth.delete(f"{A}/blacklist/{entry['id']}")

    cleanup.register(f"fjern svartelisteoppføring {pattern}", action)


def test_delete_and_blacklist_blocks_re_registration(anon: Actor, admin: Actor, user_factory, cleanup, checklist):
    user = user_factory("slett-og-svartelist")
    _drop_blacklist_entries(admin, cleanup, user.email)

    resp = admin.auth.post(f"{A}/users/delete-and-blacklist", json={"userId": user.user_id, "reason": "apitest"})
    expect(resp, 200, MessageResponse)
    checklist.expect(user.email, "Konto slettet og svartelistet", "POST /admin/users/delete-and-blacklist")

    entries = {e.pattern: e for e in expect(admin.auth.get(f"{A}/blacklist"), 200, list[BlacklistEntry])}
    assert user.email in entries and entries[user.email].type == BlacklistType.EXACT_EMAIL
    blocked = register(anon.auth, user.email)
    assert "ikke tillatt" in expect(blocked, 400, MessageResponse).message


def test_blacklist_exact_email_and_domain(settings: Settings, anon: Actor, admin: Actor, cleanup, track_user, checklist):
    exact = settings.test_email("svartelistet")
    domain = f"{settings.test_name('blokkert')}.example.net"
    for pattern in (exact, domain):
        _drop_blacklist_entries(admin, cleanup, pattern)

    expect(admin.auth.post(f"{A}/blacklist", json={"pattern": exact, "type": int(BlacklistType.EXACT_EMAIL), "reason": "apitest"}), 200, MessageResponse)
    expect(admin.auth.post(f"{A}/blacklist", json={"pattern": domain, "type": int(BlacklistType.DOMAIN)}), 200, MessageResponse)

    entries = {e.pattern: e for e in expect(admin.auth.get(f"{A}/blacklist"), 200, list[BlacklistEntry])}
    assert entries[exact].type == BlacklistType.EXACT_EMAIL and entries[exact].reason == "apitest"
    assert entries[domain].type == BlacklistType.DOMAIN

    for email in (exact, f"noen@{domain}"):
        assert "ikke tillatt" in expect(register(anon.auth, email), 400, MessageResponse).message

    for pattern in (exact, domain):
        expect(admin.auth.delete(f"{A}/blacklist/{entries[pattern].id}"), 200, MessageResponse)
    assert exact not in {b["pattern"] for b in admin_list_blacklist(admin)}

    profile = expect(register(anon.auth, exact), 200, UserProfile)  # etter fjerning kan adressen brukes igjen
    track_user(exact, profile.user_id)
    checklist.expect(exact, "Registrering: velkomst- og bekreftelses-e-post", "POST /register etter at svartelisten ble fjernet")


def test_blacklist_requires_a_pattern(admin: Actor):
    resp = admin.auth.post(f"{A}/blacklist", json={"pattern": "", "type": 1})
    problem = expect(resp, 400, ProblemDetails)
    assert problem.errors is not None and "Pattern" in problem.errors
