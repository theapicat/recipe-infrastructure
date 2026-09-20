"""Auth API: kontoflyten som innlogget bruker. Oppretter ekte brukere (slettes til slutt) og utløser e-post."""
from __future__ import annotations

import uuid

import pytest

from apitests.actors import Actor, admin_confirm_email, password_login, register
from apitests.config import TEST_NEW_PASSWORD, TEST_PASSWORD, Settings
from apitests.http import describe, expect
from apitests.models.auth import OAuthError, UserProfile
from apitests.models.common import IdentityError, MessageResponse, MessageWithErrors, ProblemDetails
from pydantic import TypeAdapter

pytestmark = [pytest.mark.mutating, pytest.mark.emails]


def test_register_creates_an_unconfirmed_user(settings: Settings, anon: Actor, track_user, checklist):
    email = settings.test_email("registrer")
    profile = expect(register(anon.auth, email, first="Kari", last="Nordmann"), 200, UserProfile)
    track_user(email, profile.user_id)
    checklist.expect(email, "Registrering: velkomst- og bekreftelses-e-post", "POST /register")

    assert profile.email == profile.user_name == email
    assert (profile.first_name, profile.last_name) == ("Kari", "Nordmann")
    assert profile.role == "user"
    assert profile.has_password and not profile.is_google_account
    assert not profile.is_email_confirmed and not profile.welcome_completed and not profile.is_locked


def test_register_rejects_a_duplicate_email(anon: Actor, user_factory):
    existing = user_factory("duplikat")
    resp = register(anon.auth, existing.email)
    assert expect(resp, 400, MessageResponse).message == "E-postadressen er allerede i bruk."


def test_unconfirmed_user_can_log_in_but_is_flagged(user_factory):
    """Bevisst: 14 dagers frist for å bekrefte e-posten (se AccountLifecycleJob), så innlogging er tillatt."""
    user = user_factory("ubekreftet", confirm=False)
    me = expect(user.auth.get("/api/auth/account/me"), 200, UserProfile)
    assert me.email == user.email
    assert me.is_email_confirmed is False


def test_resend_confirmation_only_for_unconfirmed_users(admin: Actor, user_factory, checklist):
    user = user_factory("bekreft-igjen", confirm=False)
    expect(user.auth.post("/api/auth/account/resend-confirmation"), 200, MessageResponse)
    checklist.expect(user.email, "Ny bekreftelseslenke", "POST /resend-confirmation")

    expect(admin_confirm_email(admin, user.user_id), 200)
    checklist.expect(user.email, "E-post manuelt bekreftet av admin", "admin confirm-email")
    again = expect(user.auth.post("/api/auth/account/resend-confirmation"), 400, MessageResponse)
    assert "allerede bekreftet" in again.message


def test_me_returns_the_logged_in_users_profile(user: Actor):
    me = expect(user.auth.get("/api/auth/account/me"), 200, UserProfile)
    assert me.user_id == user.user_id
    assert me.email == user.email
    assert me.role == "user"
    assert me.is_email_confirmed


def test_update_profile(user_factory):
    user = user_factory("profil")
    updated = expect(
        user.auth.put("/api/auth/account/profile", json={"firstName": "Ny", "lastName": "Navnesen"}), 200, UserProfile
    )
    assert (updated.first_name, updated.last_name) == ("Ny", "Navnesen")
    me = expect(user.auth.get("/api/auth/account/me"), 200, UserProfile)
    assert (me.first_name, me.last_name) == ("Ny", "Navnesen")


def test_update_profile_requires_both_names(user: Actor):
    problem = expect(user.auth.put("/api/auth/account/profile", json={"firstName": "", "lastName": ""}), 400, ProblemDetails)
    assert problem.errors is not None and {"FirstName", "LastName"} <= set(problem.errors)


def test_complete_welcome_marks_the_wizard_as_done(user_factory):
    user = user_factory("velkomst")
    assert expect(user.auth.get("/api/auth/account/me"), 200, UserProfile).welcome_completed is False
    assert expect(user.auth.get("/api/auth/account/complete-welcome"), 200, UserProfile).welcome_completed is True


def test_change_password_flow(settings: Settings, anon: Actor, user_factory, checklist):
    user = user_factory("passord")
    change = "/api/auth/account/change-password"

    wrong = user.auth.post(change, json={"currentPassword": "Feil#Passord123", "newPassword": TEST_NEW_PASSWORD})
    assert wrong.status_code == 400, describe(wrong)
    assert TypeAdapter(list[IdentityError]).validate_json(wrong.content)[0].code == "PasswordMismatch"

    weak = user.auth.post(change, json={"currentPassword": TEST_PASSWORD, "newPassword": "kort"})
    assert expect(weak, 400, ProblemDetails).errors is not None

    ok = user.auth.post(change, json={"currentPassword": TEST_PASSWORD, "newPassword": TEST_NEW_PASSWORD})
    assert "Passord ble endret" in expect(ok, 200, MessageResponse).message
    checklist.expect(user.email, "Passord endret (sikkerhetsvarsel)", "POST /change-password")

    assert password_login(settings, anon.auth, user.email, TEST_NEW_PASSWORD).status_code == 200
    assert expect(password_login(settings, anon.auth, user.email, TEST_PASSWORD), 400, OAuthError).error == "invalid_grant"


def test_set_password_is_rejected_when_a_password_exists(user_factory):
    user = user_factory("sett-passord")
    resp = user.auth.post("/api/auth/account/set-password", json={"newPassword": TEST_NEW_PASSWORD})
    assert "allerede et passord" in expect(resp, 400, MessageResponse).message


def test_recover_password_for_an_existing_user_gives_the_same_answer(anon: Actor, user_factory, checklist):
    user = user_factory("glemt-passord")
    unknown = anon.auth.post("/api/auth/account/recover", json={"email": f"apitest-ukjent-{uuid.uuid4().hex[:6]}@example.com"})
    known = anon.auth.post("/api/auth/account/recover", json={"email": user.email})
    assert expect(known, 200, MessageResponse).message == expect(unknown, 200, MessageResponse).message
    checklist.expect(user.email, "Tilbakestilling av passord (lenke)", "POST /recover")


def test_reset_password_with_an_invalid_token_is_rejected(anon: Actor, user: Actor):
    resp = anon.auth.post(
        "/api/auth/account/reset-password", json={"email": user.email, "token": "ugyldig", "newPassword": TEST_NEW_PASSWORD}
    )
    assert expect(resp, 400, MessageWithErrors).errors[0].code == "InvalidToken"


def test_confirm_email_with_an_invalid_token_is_rejected(anon: Actor, user: Actor):
    resp = anon.auth.post("/api/auth/account/confirm-email", json={"userId": user.user_id, "token": "ugyldig"})
    assert expect(resp, 400, MessageWithErrors).errors[0].code == "InvalidToken"


def test_user_can_delete_own_account(settings: Settings, anon: Actor, admin: Actor, user_factory, checklist):
    user = user_factory("slett-meg")
    resp = user.auth.delete("/api/auth/account/me")
    assert "slettet" in expect(resp, 200, MessageResponse).message
    checklist.expect(user.email, "Konto slettet av bruker", "DELETE /me")

    assert password_login(settings, anon.auth, user.email, TEST_PASSWORD).status_code == 400
    gone = admin.auth.get(f"/api/auth/admin/users/{user.user_id}")
    assert gone.status_code == 404, describe(gone)
