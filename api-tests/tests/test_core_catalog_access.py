"""Core API: tilgangsmatrise (anonym / bruker / admin) for alle katalogendepunkter.

Hver rad sier hvilken statuskode hver rolle skal få. `/api/user/**` krever innlogging, `/api/admin/**` krever
rollen `admin`, og brukerrutene har bare lesing.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field

import pytest

from apitests.actors import Actor
from apitests.catalogs import CATALOGS, new_id
from apitests.http import describe

pytestmark = pytest.mark.mutating  # rollen «user» krever en registrert bruker

ROLES = ("anon", "user", "admin")


@dataclass(frozen=True)
class Case:
    id: str
    method: str
    path: str
    expected: dict[str, frozenset[int]]
    body: dict | None = field(default=None, hash=False)


def _cases() -> list[Case]:
    cases: list[Case] = []
    for spec in CATALOGS:
        r, rand = spec.resource, uuid.uuid4()
        denied_body = {"id": new_id(), "name": "apitest-avvist"}
        cases += [
            Case(f"user-liste/{r}", "GET", f"/api/user/{r}", {"anon": {401}, "user": {200}, "admin": {200}}),
            Case(f"user-id/{r}", "GET", f"/api/user/{r}/{rand}", {"anon": {401}, "user": {404}, "admin": {404}}),
            Case(f"admin-liste/{r}", "GET", f"/api/admin/{r}", {"anon": {401}, "user": {403}, "admin": {200}}),
            Case(f"admin-id/{r}", "GET", f"/api/admin/{r}/{rand}", {"anon": {401}, "user": {403}, "admin": {404}}),
            # Skriving: kun admin (admin-tilfellet dekkes av CRUD-testene, her sjekkes bare at andre nektes)
            Case(f"admin-opprett/{r}", "POST", f"/api/admin/{r}", {"anon": {401}, "user": {403}}, denied_body),
            Case(f"admin-endre/{r}", "PUT", f"/api/admin/{r}", {"anon": {401}, "user": {403}}, denied_body),
            Case(f"admin-slett/{r}", "DELETE", f"/api/admin/{r}/{rand}", {"anon": {401}, "user": {403}}),
            # Brukerrutene har ingen skriving, heller ikke for admin. Anonym får 401 via gatewayen, men 405 rett mot Core
            # (der rutingen avviser ukjent metode før autentiseringen)
            Case(f"user-opprett/{r}", "POST", f"/api/user/{r}", {"anon": {401, 405}, "user": {405}, "admin": {405}}, denied_body),
            Case(f"user-endre/{r}", "PUT", f"/api/user/{r}", {"anon": {401, 405}, "user": {405}, "admin": {405}}, denied_body),
            Case(f"user-slett/{r}", "DELETE", f"/api/user/{r}/{rand}", {"anon": {401, 405}, "user": {405}, "admin": {405}}),
        ]
    return [Case(c.id, c.method, c.path, {k: frozenset(v) for k, v in c.expected.items()}, c.body) for c in cases]


def _params() -> list:
    return [
        pytest.param(case, role, id=f"{case.id}-{role}")
        for case in _cases()
        for role in case.expected
    ]


@pytest.mark.parametrize("case,role", _params())
def test_catalog_access_matrix(request: pytest.FixtureRequest, case: Case, role: str):
    actor: Actor = request.getfixturevalue(role)
    if role != "anon":
        request.getfixturevalue("core_ready")  # trenger et token Core godtar (ellers hoppes testen over)

    resp = actor.core.request(case.method, case.path, json=case.body)
    assert resp.status_code in case.expected[role], (
        f"{role} {case.method} {case.path}: forventet {sorted(case.expected[role])}, fikk {describe(resp)}"
    )
