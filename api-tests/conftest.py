"""Felles fixtures og hooks for API-testene.

Rollene er `anon`, `user` (delt vanlig bruker) og `admin` (seedet administrator). Alt testene oppretter
registreres for opprydding, og etter kjøringen kontrolleres det at ingenting med prefikset `apitest-` er igjen.
"""
from __future__ import annotations

import pytest

from apitests.actors import (
    Actor, admin_confirm_email, admin_delete_user, login, make_actor, register,
)
from apitests.cleanup import Cleanup, find_leftovers, sweep
from apitests.config import TEST_PASSWORD, ConfigError, Settings
from apitests.emails import EmailChecklist
from apitests.http import ApiClient, describe, expect
from apitests.models.auth import UserProfile
from apitests.runtime import SETTINGS

try:
    SETTINGS.assert_safe_target()
except ConfigError as exc:
    raise pytest.UsageError(str(exc)) from exc


class _State:
    """Ting som samles under kjøringen og vises til slutt."""

    checklist_path = None
    startup_notes: list[str] = []
    cleanup_problems: list[str] = []


STATE = _State()


# --------------------------------------------------------------------------------------------- hooks

def pytest_report_header(config: pytest.Config) -> list[str]:
    s = SETTINGS
    return [
        f"api-tests: env={s.env}  kjøring={s.run_id}  (data/e-post: {'tillatt' if s.mutating_allowed else 'AV, kun lesetester'})",
        f"  gateway={s.gateway_url}  auth={s.auth_url}  core={s.core_url}",
    ]


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if SETTINGS.mutating_allowed:
        return
    skip = pytest.mark.skip(
        reason=f"API_TEST_ENV='{SETTINGS.env}': tester som endrer data eller sender e-post kjøres kun i local/test"
    )
    for item in items:
        if item.get_closest_marker("mutating") or item.get_closest_marker("emails"):
            item.add_marker(skip)


def pytest_terminal_summary(terminalreporter, exitstatus, config) -> None:
    tr = terminalreporter
    for note in STATE.startup_notes:
        tr.write_line(f"ℹ️  {note}")
    if STATE.checklist_path:
        tr.write_line(f"📬 E-postsjekkliste (kryss av manuelt i Mailpit): {STATE.checklist_path}")
    for problem in STATE.cleanup_problems:
        tr.write_line(f"⚠️  OPPRYDDING: {problem}", red=True)


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    if STATE.cleanup_problems and session.exitstatus == 0:
        session.exitstatus = pytest.ExitCode.TESTS_FAILED


# ------------------------------------------------------------------------------------------- fixtures

@pytest.fixture(scope="session")
def settings() -> Settings:
    return SETTINGS


@pytest.fixture(scope="session", autouse=True)
def stack(settings: Settings) -> None:
    """Forhåndssjekk: avbryter med en klar melding hvis stacken ikke kjører (i stedet for hundre uforståelige feil)."""
    probes = [
        ("gateway", settings.gateway_url, "/api/gateway/health"),
        ("auth-api", settings.auth_url, "/api/auth/health"),
        ("core-api", settings.core_url, "/api/public/health"),
    ]
    down: list[str] = []
    for name, base, path in probes:
        try:
            ok = ApiClient(base, timeout=5).get(path).status_code == 200
        except Exception:
            ok = False
        if not ok:
            down.append(f"{name} ({base}{path})")
    if down:
        pytest.exit(
            "Stacken kjører ikke: " + ", ".join(down) + ".\n"
            "Start alt med ./dev-scripts/start-project.sh (og sjekk at docker compose up -d er kjørt).",
            returncode=3,
        )


@pytest.fixture(scope="session")
def anon(settings: Settings) -> Actor:
    return make_actor(settings, "anon")


@pytest.fixture(scope="session")
def admin(settings: Settings, anon: Actor, stack: None) -> Actor:
    resp = anon.auth.post(
        "/api/auth/connect/token",
        data={"grant_type": "password", "username": settings.admin_email,
              "password": settings.admin_password, "client_id": settings.client_id},
    )
    if resp.status_code != 200:
        pytest.exit(
            f"Kunne ikke logge inn som admin ({settings.admin_email}): {describe(resp)}\n"
            "Sjekk API_TEST_ADMIN_EMAIL/API_TEST_ADMIN_PASSWORD (se .env.example).",
            returncode=3,
        )
    tokens = login(settings, anon.auth, settings.admin_email, settings.admin_password)
    return make_actor(settings, "admin", tokens, email=settings.admin_email, password=settings.admin_password)


@pytest.fixture(scope="session")
def checklist(settings: Settings):
    items = EmailChecklist(settings)
    yield items
    STATE.checklist_path = items.write()


@pytest.fixture(scope="session", autouse=True)
def cleanup(request: pytest.FixtureRequest, settings: Settings, checklist: EmailChecklist, stack: None):
    """Rydder etter kjøringen, og kontrollerer at ingenting med testprefikset er igjen (resten fjernes uansett)."""
    registry = Cleanup()
    if not settings.mutating_allowed:
        yield registry
        return

    admin_actor: Actor = request.getfixturevalue("admin")
    stale = find_leftovers(admin_actor)  # rester etter en tidligere, avbrutt kjøring
    if stale.count:
        sweep(admin_actor, stale)
        STATE.startup_notes.append(f"Fjernet {stale.count} rest(er) etter en tidligere kjøring: {stale.describe()}")

    yield registry

    registry.run()
    STATE.cleanup_problems += registry.errors
    left = find_leftovers(admin_actor)
    if left.count:
        sweep(admin_actor, left)
        STATE.cleanup_problems.append(
            f"{left.count} objekt(er) var IKKE ryddet av testene selv og ble feid bort til slutt: {left.describe()}"
        )
    still = find_leftovers(admin_actor)
    if still.count:
        STATE.cleanup_problems.append(f"Kunne ikke fjerne: {still.describe()}")


@pytest.fixture(scope="session")
def track_user(settings: Settings, admin: Actor, cleanup: Cleanup, checklist: EmailChecklist):
    """Registrerer en opprettet testbruker for sletting (og e-postsjekklisten) uansett hvordan testen ender."""

    def track(email: str, user_id: str) -> None:
        def delete() -> None:
            if admin_delete_user(admin, user_id).status_code == 200:
                checklist.expect_cleanup(email, "Konto slettet av administrator", "opprydding")

        cleanup.register(f"slett bruker {email}", delete)

    return track


@pytest.fixture(scope="session")
def user_factory(settings: Settings, anon: Actor, admin: Actor, checklist: EmailChecklist, track_user):
    """Oppretter en ekte bruker via registrering, bekrefter e-posten som admin (med mindre annet er bedt om) og logger inn."""

    def factory(tag: str, *, confirm: bool = True, first: str = "Api", last: str = "Test") -> Actor:
        email = settings.test_email(tag)
        profile = expect(register(anon.auth, email, first=first, last=last), 200, UserProfile)
        track_user(email, profile.user_id)
        checklist.expect(email, "Registrering: velkomst- og bekreftelses-e-post", f"registrering av «{tag}»")
        if confirm:
            expect(admin_confirm_email(admin, profile.user_id), 200)
            checklist.expect(email, "E-post manuelt bekreftet av admin", f"bekreftelse av «{tag}»")
        tokens = login(settings, anon.auth, email, TEST_PASSWORD)
        return make_actor(settings, tag, tokens, email=email, password=TEST_PASSWORD, user_id=profile.user_id)

    return factory


@pytest.fixture(scope="session")
def user(user_factory) -> Actor:
    """Delt vanlig bruker for rene lese-/tilgangstester. Tester som endrer brukeren skal lage sin egen."""
    return user_factory("shared")


@pytest.fixture(scope="session")
def core_ready(admin: Actor) -> None:
    """Hopper over tester som trenger et token Core godtar, når gateway/Core avviser tokenet.

    Selve feilen rapporteres av `test_issued_token_is_accepted_by_gateway_and_core`; her unngås bare hundrevis av
    følgefeil med samme årsak."""
    resp = admin.core.get("/api/user/unit-types")
    if resp.status_code == 401:
        pytest.skip(
            "Blokkert: Core/gateway avviser tokenet Auth API utsteder "
            f"({resp.headers.get('www-authenticate', '')[:140]}). Sjekk at Jwt:Issuer/Key/Audience er identiske i "
            "auth, gateway og core, og at Auth API setter en fast issuer."
        )
    if resp.status_code != 200:
        pytest.skip(f"Core er ikke tilgjengelig for innloggede brukere: {describe(resp)}")


@pytest.fixture(scope="session")
def core_admin_ready(core_ready: None, admin: Actor) -> None:
    """Hopper over tester som må skrive til /api/admin/** når admin blokkeres av gatewayen (403)."""
    resp = admin.core.get("/api/admin/unit-types")
    if resp.status_code == 403:
        pytest.skip(
            "Blokkert: admin får 403 på /api/admin/** via gatewayen (sjekk at AdminUser-policyen bruker rollen `admin` "
            "med små bokstaver). Sett API_TEST_CORE_URL=http://localhost:5002 for å teste Core direkte."
        )
    if resp.status_code != 200:
        pytest.skip(f"/api/admin/** er ikke tilgjengelig for admin: {describe(resp)}")
