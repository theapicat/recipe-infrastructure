"""Core API: livssyklus for alle seks kataloger (opprett, les, endre, slett), feilhåndtering og DTO-kontroll.

Testene oppretter egne rader med prefikset `apitest-`, og sletter dem igjen (også ved feil).
"""
from __future__ import annotations

import uuid

import pytest

from apitests.actors import Actor
from apitests.catalogs import BY_RESOURCE, CATALOGS, CatalogSpec, new_id
from apitests.config import Settings
from apitests.http import describe, expect
from apitests.models.common import ProblemDetails

by_resource = pytest.mark.parametrize("spec", CATALOGS, ids=lambda s: s.resource)


@pytest.fixture
def create_row(admin: Actor, cleanup, settings: Settings, core_admin_ready):
    """Oppretter en katalograd via admin-API-et og registrerer den for sletting."""

    def create(spec: CatalogSpec, tag: str, parent_id: str | None = None) -> dict:
        payload = spec.build(settings.test_name(tag), parent_id)
        resp = admin.core.post(spec.admin_path, json=payload)
        assert resp.status_code == 200, f"kunne ikke opprette {spec.resource}: {describe(resp)}"
        cleanup.register(
            f"slett {spec.resource}/{payload['id']}", lambda: admin.core.delete(f"{spec.admin_path}/{payload['id']}")
        )
        return payload

    return create


def _create_with_parent(create_row, spec: CatalogSpec, tag: str) -> tuple[dict, dict | None]:
    parent = create_row(BY_RESOURCE[spec.parent], f"{tag}-forelder") if spec.parent else None
    return create_row(spec, tag, parent["id"] if parent else None), parent


def _ids(resp) -> set[str]:
    return {row["id"] for row in resp.json()}


# ------------------------------------------------------------------------------------- livssyklus

@pytest.mark.mutating
@by_resource
def test_full_lifecycle(spec: CatalogSpec, admin: Actor, user: Actor, create_row):
    row, _ = _create_with_parent(create_row, spec, "livssyklus")
    row_id = row["id"]

    # Opprettet: les tilbake på begge rutene, og se den i (cachede) lister
    assert expect(admin.core.get(f"{spec.admin_path}/{row_id}"), 200, spec.model).to_json() == row
    assert expect(user.core.get(f"{spec.user_path}/{row_id}"), 200, spec.model).to_json() == row
    assert row_id in _ids(admin.core.get(spec.admin_path))
    assert row_id in _ids(user.core.get(spec.user_path)), "listen for brukere viser ikke den nye raden (cache ikke ugyldiggjort?)"

    # Endre
    changed = spec.modify(row)
    assert admin.core.put(spec.admin_path, json=changed).status_code == 200
    assert expect(admin.core.get(f"{spec.admin_path}/{row_id}"), 200, spec.model).to_json() == changed
    listed = {r["id"]: r for r in user.core.get(spec.user_path).json()}
    assert listed[row_id]["name"] == changed["name"], "listen for brukere viser gammelt navn (cache ikke ugyldiggjort?)"

    # Slette
    assert admin.core.delete(f"{spec.admin_path}/{row_id}").status_code == 204
    assert admin.core.get(f"{spec.admin_path}/{row_id}").status_code == 404
    assert user.core.get(f"{spec.user_path}/{row_id}").status_code == 404
    assert row_id not in _ids(admin.core.get(spec.admin_path))
    assert row_id not in _ids(user.core.get(spec.user_path))
    assert admin.core.delete(f"{spec.admin_path}/{row_id}").status_code == 204, "sletting skal være idempotent (204 også når raden er borte)"


# ---------------------------------------------------------------------------------- DTO-kontroll

@by_resource
@pytest.mark.parametrize("route", ["user_path", "admin_path"])
def test_every_existing_row_matches_the_dto(spec: CatalogSpec, admin: Actor, core_admin_ready, route: str):
    """Leser hele katalogen og validerer hver rad strengt mot DTO-en (admin-token gir tilgang til begge rutene)."""
    assert expect(admin.core.get(getattr(spec, route)), 200, list[spec.model]) is not None


# ------------------------------------------------------------------------------- feilhåndtering

@pytest.mark.mutating
@by_resource
def test_create_without_required_fields_is_rejected(spec: CatalogSpec, admin: Actor, core_admin_ready):
    resp = admin.core.post(spec.admin_path, json={"id": new_id()})
    assert expect(resp, 400, ProblemDetails).errors is not None


@by_resource
def test_malformed_id_is_not_found(spec: CatalogSpec, admin: Actor, core_admin_ready):
    assert admin.core.get(f"{spec.admin_path}/ikke-en-guid").status_code == 404


@pytest.mark.mutating
@by_resource
def test_unknown_id_is_404_and_delete_is_idempotent(spec: CatalogSpec, admin: Actor, core_admin_ready):
    missing = uuid.uuid4()
    assert admin.core.get(f"{spec.admin_path}/{missing}").status_code == 404
    assert admin.core.delete(f"{spec.admin_path}/{missing}").status_code == 204
