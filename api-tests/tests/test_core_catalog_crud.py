"""Core API: livssyklus for alle seks kataloger (opprett, les, endre, slett), serverregler, feilhåndtering og DTO-kontroll.

Serveren tildeler id-er og gjør navn om til små bokstaver. Testene oppretter egne rader med prefikset `apitest-`, og
sletter dem igjen (også ved feil).
"""
from __future__ import annotations

import uuid

import pytest

from apitests.actors import Actor
from apitests.catalogs import BY_RESOURCE, CATALOGS, CatalogSpec, new_id
from apitests.config import Settings
from apitests.http import describe, expect
from apitests.models.common import ProblemDetails
from apitests.models.core import UnitType

by_resource = pytest.mark.parametrize("spec", CATALOGS, ids=lambda s: s.resource)


@pytest.fixture
def create_row(admin: Actor, cleanup, settings: Settings, core_admin_ready):
    """Oppretter en katalograd via admin-API-et (201 med server-tildelt id) og registrerer den for sletting."""

    def create(spec: CatalogSpec, tag: str, parent_id: str | None = None, **overrides) -> dict:
        payload = {**spec.build(settings.test_name(tag), parent_id), **overrides}
        resp = admin.core.post(spec.admin_path, json=payload)
        row = expect(resp, 201, spec.model).to_json()
        assert resp.headers.get("Location", "").endswith(f"/{row['id']}"), f"Location peker ikke på raden: {describe(resp)}"
        cleanup.register(f"slett {spec.resource}/{row['id']}", lambda: admin.core.delete(f"{spec.admin_path}/{row['id']}"))
        return row

    return create


def _create_with_parent(create_row, spec: CatalogSpec, tag: str, **overrides) -> tuple[dict, dict | None]:
    parent = create_row(BY_RESOURCE[spec.parent], f"{tag}-forelder") if spec.parent else None
    return create_row(spec, tag, parent["id"] if parent else None, **overrides), parent


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

    # Endre: hele raden med id i body (ingen id i stien), svar 200 uten kropp
    changed = spec.modify(row)
    resp = admin.core.put(spec.admin_path, json=changed)
    assert resp.status_code == 200 and not resp.content, f"PUT skal gi 200 uten kropp: {describe(resp)}"
    assert expect(admin.core.get(f"{spec.admin_path}/{row_id}"), 200, spec.model).to_json() == changed
    listed = {r["id"]: r for r in user.core.get(spec.user_path).json()}
    assert listed[row_id]["name"] == changed["name"], "listen for brukere viser gammelt navn (cache ikke ugyldiggjort?)"

    # Slette
    assert admin.core.delete(f"{spec.admin_path}/{row_id}").status_code == 204
    assert admin.core.get(f"{spec.admin_path}/{row_id}").status_code == 404
    assert user.core.get(f"{spec.user_path}/{row_id}").status_code == 404
    assert row_id not in _ids(admin.core.get(spec.admin_path))
    assert row_id not in _ids(user.core.get(spec.user_path))
    assert admin.core.delete(f"{spec.admin_path}/{row_id}").status_code == 404, "ny sletting av en rad som er borte skal gi 404"


# ---------------------------------------------------------------------------------- DTO-kontroll

@by_resource
@pytest.mark.parametrize("route", ["user_path", "admin_path"])
def test_every_existing_row_matches_the_dto(spec: CatalogSpec, admin: Actor, core_admin_ready, route: str):
    """Leser hele katalogen og validerer hver rad strengt mot DTO-en (admin-token gir tilgang til begge rutene)."""
    assert expect(admin.core.get(getattr(spec, route)), 200, list[spec.model]) is not None


# ------------------------------------------------------------------------------- serverregler

@pytest.mark.mutating
@by_resource
def test_server_assigns_the_id_and_normalizes_the_name(spec: CatalogSpec, settings: Settings, create_row):
    """En `id` fra klienten ignoreres, og navnet trimmes, slås sammen og gjøres om til små bokstaver."""
    sent_id = new_id()
    messy = f"  {settings.test_name('Stor   Bokstav').upper()}  "
    parent = create_row(BY_RESOURCE[spec.parent], "normalisering-forelder") if spec.parent else None
    row = create_row(spec, "normalisering", parent["id"] if parent else None, id=sent_id, name=messy)
    assert row["id"] != sent_id, "serveren skal tildele egen id, ikke bruke klientens"
    assert row["name"] == settings.test_name("stor bokstav"), f"navnet er ikke normalisert: {row['name']!r}"


@pytest.mark.mutating
@by_resource
def test_is_system_and_usage_count_cannot_be_set_by_the_client(spec: CatalogSpec, admin: Actor, create_row):
    """Begge er serverstyrte: ignoreres på POST (og nullstilles i 201-svaret) og på PUT."""
    parent = create_row(BY_RESOURCE[spec.parent], "serverstyrt-forelder") if spec.parent else None
    row = create_row(spec, "serverstyrt", parent["id"] if parent else None, isSystem=True, usageCount=99)
    assert (row["isSystem"], row["usageCount"]) == (False, 0)
    assert admin.core.put(spec.admin_path, json={**row, "isSystem": True, "usageCount": 99}).status_code == 200
    stored = expect(admin.core.get(f"{spec.admin_path}/{row['id']}"), 200, spec.model).to_json()
    assert (stored["isSystem"], stored["usageCount"]) == (False, 0)


@pytest.mark.mutating
def test_unit_abbreviation_keeps_its_case(create_row):
    """Enhetsforkortelser er symboler (`µg`, `mg-ATE`) og beholder store/små bokstaver."""
    unit_type = create_row(BY_RESOURCE["unit-types"], "symbol-forelder")
    unit = create_row(BY_RESOURCE["units"], "symbol", unit_type["id"], abbreviation="AtU-X")
    assert unit["abbreviation"] == "AtU-X"


@pytest.mark.mutating
@by_resource
def test_an_existing_name_is_a_conflict(spec: CatalogSpec, admin: Actor, settings: Settings, create_row):
    parent = create_row(BY_RESOURCE[spec.parent], "duplikat-forelder") if spec.parent else None
    parent_id = parent["id"] if parent else None
    row = create_row(spec, "duplikat", parent_id)
    # units har også unik forkortelse, så den byttes for at det er navnet som skal gi konflikten
    second = {**spec.build(row["name"].upper(), parent_id), **({"abbreviation": row["abbreviation"] + "-2"} if "abbreviation" in row else {})}
    resp = admin.core.post(spec.admin_path, json=second)
    assert resp.status_code == 409, f"samme navn to ganger skal gi 409: {describe(resp)}"
    assert expect(resp, 409, ProblemDetails).status == 409


@pytest.mark.mutating
def test_a_catalog_row_in_use_cannot_be_deleted(admin: Actor, create_row):
    """Enhetstypen brukes av en enhet: `usageCount` teller den, sletting gir 409, og går først når enheten er borte."""
    unit_type = create_row(BY_RESOURCE["unit-types"], "i-bruk-forelder")
    unit = create_row(BY_RESOURCE["units"], "i-bruk", unit_type["id"])
    assert expect(admin.core.get(f"/api/admin/unit-types/{unit_type['id']}"), 200, UnitType).usage_count == 1
    resp = admin.core.delete(f"/api/admin/unit-types/{unit_type['id']}")
    assert expect(resp, 409, ProblemDetails).detail == "Brukes av 1 enheter og ingredienser og kan ikke slettes."
    assert admin.core.delete(f"/api/admin/units/{unit['id']}").status_code == 204
    assert expect(admin.core.get(f"/api/admin/unit-types/{unit_type['id']}"), 200, UnitType).usage_count == 0
    assert admin.core.delete(f"/api/admin/unit-types/{unit_type['id']}").status_code == 204


def _system_rows_in_use(admin: Actor, spec: CatalogSpec) -> list[dict]:
    rows = expect(admin.core.get(spec.admin_path), 200, list[spec.model])
    return [r.to_json() for r in rows if r.is_system and r.usage_count > 0]


@by_resource
def test_seed_rows_are_system_rows_and_cannot_be_deleted(spec: CatalogSpec, admin: Actor, core_admin_ready):
    """Seed-rader har `isSystem: true` og gir 409 ved sletting.

    Testen bruker bare systemrader som også er i bruk, så selv om systemsjekken skulle svikte, stopper bruks-sjekken
    slettingen (da feiler testen på meldingen, men seed-dataene blir stående)."""
    candidates = _system_rows_in_use(admin, spec)
    if not candidates:
        pytest.skip(f"{spec.resource} har ingen seedede rader i bruk")
    row = candidates[0]
    resp = admin.core.delete(f"{spec.admin_path}/{row['id']}")
    assert expect(resp, 409, ProblemDetails).detail == "Systemrader (fra seed-data) kan ikke slettes."
    assert admin.core.get(f"{spec.admin_path}/{row['id']}").status_code == 200


def test_every_seeded_unit_type_has_a_dimension(admin: Actor, core_admin_ready):
    """De tre seedede enhetstypene dekker hver sin dimensjon; beregningene bruker dimensjonen, ikke navnet."""
    seeded = [t for t in expect(admin.core.get("/api/admin/unit-types"), 200, list[UnitType]) if t.is_system]
    assert sorted(t.dimension for t in seeded) == ["Count", "Volume", "Weight"]


# --------------------------------------------------------------------------------- enheter og enhetstyper

UNIT_RULES = {
    "tom-forkortelse": ({"abbreviation": "  "}, "Forkortelse må oppgis."),
    "forholdstall-null": ({"baseUnitRatio": 0}, "Forholdstallet må være større enn 0."),
    "negativt-forholdstall": ({"baseUnitRatio": -1}, "Forholdstallet må være større enn 0."),
    "ukjent-enhetstype": ({"unitTypeId": new_id()}, "Enhetstypen finnes ikke."),
}


@pytest.mark.mutating
@pytest.mark.parametrize("case", UNIT_RULES)
def test_invalid_units_are_rejected_on_create_and_update(admin: Actor, create_row, case: str):
    change, detail = UNIT_RULES[case]
    unit_type = create_row(BY_RESOURCE["unit-types"], f"enhetsregel-{case}-forelder")
    spec = BY_RESOURCE["units"]
    bad = {**spec.build(f"apitest-enhetsregel-{case}-avvist", unit_type["id"]), **change}
    assert expect(admin.core.post(spec.admin_path, json=bad), 400, ProblemDetails).detail == detail

    unit = create_row(spec, f"enhetsregel-{case}", unit_type["id"])
    assert expect(admin.core.put(spec.admin_path, json={**unit, **change}), 400, ProblemDetails).detail == detail
    assert expect(admin.core.get(f"{spec.admin_path}/{unit['id']}"), 200, spec.model).to_json() == unit


@pytest.mark.mutating
def test_count_units_must_have_ratio_one(admin: Actor, create_row):
    """Antall-enheter (stk, skive ...) regnes ikke om, så forholdstallet må være nøyaktig 1."""
    count_type = create_row(BY_RESOURCE["unit-types"], "antall-forelder", dimension="Count")
    spec = BY_RESOURCE["units"]
    bad = spec.build("apitest-antall", count_type["id"])  # forholdstall 1.5
    detail = "Enheter av typen antall regnes ikke om - forholdstallet må være 1."
    assert expect(admin.core.post(spec.admin_path, json=bad), 400, ProblemDetails).detail == detail
    assert create_row(spec, "antall", count_type["id"], baseUnitRatio=1)["baseUnitRatio"] == 1


@pytest.mark.mutating
@pytest.mark.parametrize("dimension", ["Weight", "Volume", "Count"])
def test_unit_types_keep_their_dimension(admin: Actor, create_row, dimension: str):
    row = create_row(BY_RESOURCE["unit-types"], f"dimensjon-{dimension.lower()}", dimension=dimension)
    assert row["dimension"] == dimension
    assert expect(admin.core.get(f"/api/admin/unit-types/{row['id']}"), 200, UnitType).dimension == dimension


@pytest.mark.mutating
@pytest.mark.parametrize("dimension", [None, "Length", "vekt", 7])
def test_a_unit_type_needs_a_valid_dimension(admin: Actor, settings: Settings, core_admin_ready, dimension):
    body = {"name": settings.test_name("uten-dimensjon")}
    if dimension is not None:
        body["dimension"] = dimension
    resp = admin.core.post("/api/admin/unit-types", json=body)
    if resp.status_code == 201:  # sikkerhetsnett: ikke la en feilaktig opprettet rad bli liggende
        admin.core.delete(f"/api/admin/unit-types/{resp.json()['id']}")
    assert resp.status_code == 400, f"ugyldig/manglende dimensjon skal gi 400: {describe(resp)}"


# ------------------------------------------------------------------------------- feilhåndtering

@pytest.mark.mutating
@by_resource
def test_create_without_required_fields_is_rejected(spec: CatalogSpec, admin: Actor, core_admin_ready):
    resp = admin.core.post(spec.admin_path, json={})
    assert expect(resp, 400, ProblemDetails).errors is not None


@pytest.mark.mutating
@by_resource
def test_create_with_a_blank_name_is_rejected(spec: CatalogSpec, admin: Actor, create_row):
    parent = create_row(BY_RESOURCE[spec.parent], "tomt-navn-forelder") if spec.parent else None
    resp = admin.core.post(spec.admin_path, json=spec.build("   ", parent["id"] if parent else None))
    assert expect(resp, 400, ProblemDetails).detail == "Navn må oppgis."


@pytest.mark.mutating
@by_resource
def test_update_requires_an_id(spec: CatalogSpec, admin: Actor, create_row):
    parent = create_row(BY_RESOURCE[spec.parent], "uten-id-forelder") if spec.parent else None
    body = spec.build("apitest-uten-id", parent["id"] if parent else None)
    resp = admin.core.put(spec.admin_path, json=body)
    assert resp.status_code == 400, f"PUT uten id skal gi 400: {describe(resp)}"


@by_resource
@pytest.mark.parametrize("route", ["user_path", "admin_path"])
def test_malformed_id_is_a_bad_request(spec: CatalogSpec, admin: Actor, core_admin_ready, route: str):
    """De generiske katalogkontrollerne svarer 400 på en id som ikke er en Guid (de håndskrevne svarer 404)."""
    assert admin.core.get(f"{getattr(spec, route)}/ikke-en-guid").status_code == 400


@pytest.mark.mutating
@by_resource
def test_unknown_id_is_404(spec: CatalogSpec, admin: Actor, core_admin_ready):
    missing = uuid.uuid4()
    assert admin.core.get(f"{spec.admin_path}/{missing}").status_code == 404
    assert admin.core.delete(f"{spec.admin_path}/{missing}").status_code == 404
