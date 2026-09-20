"""Core API: næringsstoffene (`/api/user/nutrient-definitions`), en statisk og skrivebeskyttet katalog med tekstkode som id."""
from __future__ import annotations

from urllib.parse import quote

import pytest

from apitests.actors import Actor
from apitests.core_data import Reference
from apitests.http import expect
from apitests.models.core import NutrientDefinition

pytestmark = pytest.mark.mutating  # rollen «user» krever en registrert bruker

PATH = "/api/user/nutrient-definitions"


def test_nutrients_require_a_signed_in_user(anon: Actor):
    assert anon.core.get(PATH).status_code == 401
    assert anon.core.get(f"{PATH}/Fett").status_code == 401


@pytest.mark.parametrize("role", ["user", "admin"])
def test_every_signed_in_role_can_list_the_nutrients(request: pytest.FixtureRequest, role: str, core_ready):
    """Admin leser også via brukerruten (det finnes ingen admin-rute for næringsstoffer)."""
    actor: Actor = request.getfixturevalue(role)
    nutrients = expect(actor.core.get(PATH), 200, list[NutrientDefinition])
    assert nutrients, "katalogen er tom (er seed-dataene kjørt?)"


def test_the_list_is_sorted_by_sort_order(user: Actor, core_ready):
    nutrients = expect(user.core.get(PATH), 200, list[NutrientDefinition])
    orders = [n.sort_order for n in nutrients]
    assert orders == list(range(1, len(nutrients) + 1)), f"sortOrder skal gå fra 1 og opp uten hull: {orders}"
    assert len({n.id for n in nutrients}) == len(nutrients), "id-ene skal være unike"


def test_groups_are_nested_at_most_one_level(user: Actor, core_ready):
    """Hovedgrupper har `parentGroup = null`, undergrupper peker på en hovedgruppe (aldri dypere)."""
    for nutrient in expect(user.core.get(PATH), 200, list[NutrientDefinition]):
        parent = nutrient.group.parent_group
        assert parent is None or parent.parent_group is None, f"{nutrient.id}: gruppen er nøstet dypere enn ett nivå"


def test_unit_is_consistent_with_the_units_catalog(user: Actor, ref: Reference):
    """`unitId`, `unit` (forkortelsen) og `unitTypeId` på stoffet stemmer med enhetskatalogen."""
    units = {u.id: u for u in ref.units.values()}
    for nutrient in ref.nutrients:
        unit = units.get(nutrient.unit_id)
        assert unit is not None, f"{nutrient.id}: enheten {nutrient.unit_id} finnes ikke i /api/user/units"
        assert (unit.abbreviation, unit.unit_type_id) == (nutrient.unit, nutrient.unit_type_id), nutrient.id


def test_every_nutrient_can_be_read_by_its_url_encoded_id(user: Actor, ref: Reference):
    """Tekstkoden kan inneholde mellomrom, `+` og `:` og må URL-enkodes: hver rad hentes på id og er lik listeraden."""
    for nutrient in ref.nutrients:
        fetched = expect(user.core.get(f"{PATH}/{quote(nutrient.id, safe='')}"), 200, NutrientDefinition)
        assert fetched == nutrient, f"{nutrient.id}: GET på id gir noe annet enn listeraden"


def test_unknown_nutrient_is_404(user: Actor, core_ready):
    assert user.core.get(f"{PATH}/finnes-ikke").status_code == 404


@pytest.mark.parametrize("method", ["POST", "PUT", "DELETE"])
@pytest.mark.parametrize("role", ["user", "admin"])
def test_the_catalog_is_read_only(request: pytest.FixtureRequest, role: str, method: str, core_ready):
    """Ingen skriving, heller ikke for admin (metoden finnes ikke, derfor 405)."""
    actor: Actor = request.getfixturevalue(role)
    path = f"{PATH}/Fett" if method == "DELETE" else PATH
    assert actor.core.request(method, path, json={"id": "Fett", "name": "x"}).status_code == 405
