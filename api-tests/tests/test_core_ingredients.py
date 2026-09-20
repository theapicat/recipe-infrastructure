"""Core API: ingredienser. Søk og lesing for alle innloggede, skriving kun for admin.

Ingrediensene er den tunge modellen (næringsverdier, porsjoner, allergener, søkeord). Søket filtrerer en cachet
lettvektsliste, mens `GET /{id}` alltid leser ferskt fra databasen. Testene lager egne ingredienser (`apitest-…`).
"""
from __future__ import annotations

import uuid

import pytest

from apitests.actors import Actor
from apitests.core_data import Reference, delete_or_raise, ingredient_payload
from apitests.http import describe, expect
from apitests.models.common import ProblemDetails
from apitests.models.core import Ingredient, IngredientListItem

pytestmark = pytest.mark.mutating  # rollen «user» krever en registrert bruker, og admin oppretter ingredienser

USER, ADMIN = "/api/user/ingredients", "/api/admin/ingredients"


def _search(actor: Actor, path: str = USER, **params) -> list[IngredientListItem]:
    return expect(actor.core.get(path, params=params), 200, list[IngredientListItem])


def _ids(rows: list[IngredientListItem]) -> set[str]:
    return {row.id for row in rows}


# --------------------------------------------------------------------------------------------- tilgang

def test_reading_requires_a_signed_in_user_and_admin_routes_require_admin(anon: Actor, user: Actor, ref: Reference):
    some = ref.official.id
    assert anon.core.get(USER).status_code == 401
    assert anon.core.get(f"{USER}/{some}").status_code == 401
    assert anon.core.get(ADMIN).status_code == 401
    assert user.core.get(ADMIN).status_code == 403
    assert user.core.get(f"{ADMIN}/{some}").status_code == 403


@pytest.mark.parametrize("method", ["POST", "PUT", "DELETE"])
def test_writing_is_admin_only(anon: Actor, user: Actor, ref: Reference, method: str):
    path = ADMIN if method == "POST" else f"{ADMIN}/{uuid.uuid4()}"
    body = ingredient_payload(ref, "apitest-avvist")
    assert anon.core.request(method, path, json=body).status_code == 401
    assert user.core.request(method, path, json=body).status_code == 403


def test_user_routes_have_no_write_methods(user: Actor, admin: Actor, ref: Reference):
    body = ingredient_payload(ref, "apitest-avvist")
    for actor in (user, admin):
        assert actor.core.post(USER, json=body).status_code == 405
        assert actor.core.delete(f"{USER}/{ref.official.id}").status_code == 405


# ---------------------------------------------------------------------------------------- lesing og søk

def test_the_whole_list_matches_the_dto_for_users_and_admin(user: Actor, admin: Actor, ref: Reference):
    as_user, as_admin = _search(user), _search(admin, ADMIN)
    assert len(as_user) > 1000, f"forventet hele den seedede katalogen, fikk {len(as_user)} rader"
    assert _ids(as_user) == _ids(as_admin), "brukere og admin skal se samme ingredienser"


def test_a_sample_of_full_ingredients_matches_the_dto(user: Actor, ref: Reference):
    """Full ingrediens (med næringsverdier og porsjoner) for 25 jevnt fordelte rader validert strengt mot DTO-en."""
    rows = _search(user)
    for row in rows[:: max(1, len(rows) // 25)]:
        full = expect(user.core.get(f"{USER}/{row.id}"), 200, Ingredient)
        assert (full.id, full.name, full.energy_kcal) == (row.id, row.name, row.energy_kcal), "listeraden og hele raden er ulike"
        assert all(v.ingredient_id == full.id for v in full.nutrient_values)


def test_unknown_or_malformed_ingredient_id_is_404(user: Actor, admin: Actor, core_ready):
    for path in (USER, ADMIN):
        actor = admin if path == ADMIN else user
        assert actor.core.get(f"{path}/{uuid.uuid4()}").status_code == 404
        assert actor.core.get(f"{path}/ikke-en-guid").status_code == 404


def test_search_by_name_is_partial_and_case_insensitive(user: Actor, make_ingredient, unique):
    created = make_ingredient("soek")
    needle = created.name.split("-", 2)[2]  # <tag>-<n>, unikt for denne raden
    assert _ids(_search(user, name=needle)) == {created.id}
    assert _ids(_search(user, name=needle.upper())) == {created.id}
    assert _ids(_search(user, name=created.name[:-1])) >= {created.id}, "delvis treff (uten siste tegn) skal finne raden"
    assert _search(user, name=unique("finnes-ikke")) == []


def test_search_by_name_also_matches_search_keywords(user: Actor, admin: Actor, make_ingredient, unique, cleanup):
    """Et søkeord som er navnet på en katalograd: ingrediensen med søkeordet kommer med i treff på ordet."""
    keyword_name = unique("soekeord")
    keyword = expect(admin.core.post("/api/admin/search-keywords", json={"name": keyword_name}), 201, dict)
    # Registreres før ingrediensen, så ingrediensen (som peker på søkeordet) slettes først
    cleanup.register("slett søkeord", lambda: delete_or_raise(admin.core, f"/api/admin/search-keywords/{keyword['id']}"))
    created = make_ingredient("med-soekeord", searchKeywordIds=[keyword["id"]])
    assert created.id in _ids(_search(user, name=keyword_name)), "søk på navn skal også treffe ingrediensens søkeord"
    assert created.id in _ids(_search(user, searchKeywordId=keyword["id"]))


def test_search_filters_by_category_and_keyword(user: Actor, make_ingredient, ref: Reference):
    keyword_id = user.core.get("/api/user/search-keywords").json()[0]["id"]
    created = make_ingredient("filter", searchKeywordIds=[keyword_id])
    in_category = _search(user, categoryId=ref.ingredient_category_id)
    assert created.id in _ids(in_category)
    assert all(row.category_id == ref.ingredient_category_id for row in in_category)
    with_keyword = _search(user, searchKeywordId=keyword_id)
    assert created.id in _ids(with_keyword)
    assert all(keyword_id in row.search_keyword_ids for row in with_keyword)
    other_category = next(c["id"] for c in user.core.get("/api/user/ingredient-categories").json() if c["id"] != ref.ingredient_category_id)
    assert created.id not in _ids(_search(user, categoryId=other_category))


def test_allergen_filters_include_and_exclude(user: Actor, make_ingredient):
    allergens = [a["id"] for a in user.core.get("/api/user/allergens").json()][:2]
    with_allergen = make_ingredient("allergen", allergenIds=[allergens[0]])
    without = make_ingredient("uten-allergen")

    contains = _search(user, allergenId=allergens[0])
    assert with_allergen.id in _ids(contains) and without.id not in _ids(contains)
    assert all(allergens[0] in row.allergen_ids for row in contains)

    safe = _search(user, excludeAllergenId=allergens[0])
    assert without.id in _ids(safe) and with_allergen.id not in _ids(safe)
    assert all(allergens[0] not in row.allergen_ids for row in safe)

    both = user.core.get(USER, params=[("excludeAllergenId", allergens[0]), ("excludeAllergenId", allergens[1])])
    assert without.id in _ids(expect(both, 200, list[IngredientListItem])), "excludeAllergenId kan gjentas"
    assert _search(user, allergenId=allergens[0], excludeAllergenId=allergens[0]) == [], "filtrene kombineres med OG"


def test_filters_are_combined_with_and(user: Actor, make_ingredient, ref: Reference):
    created = make_ingredient("kombinert")
    needle = created.name.split("-", 2)[2]
    assert _ids(_search(user, name=needle, categoryId=ref.ingredient_category_id)) == {created.id}
    other = next(c["id"] for c in user.core.get("/api/user/ingredient-categories").json() if c["id"] != ref.ingredient_category_id)
    assert _search(user, name=needle, categoryId=other) == []


# ---------------------------------------------------------------------------------------- admin: opprett

def test_create_returns_the_full_ingredient_with_server_assigned_ids(admin: Actor, user: Actor, ref: Reference, make_ingredient):
    created = make_ingredient("opprett")
    assert created.name.startswith("apitest-") and created.name == created.name.lower()
    assert created.is_verified is False and created.variant_of_ingredient_id is None
    assert created.energy_kcal == 100 and created.energy_kj == 420
    assert {v.nutrient_definition_id: v.quantity for v in created.nutrient_values} == {
        ref.nutrients[0].id: 10, ref.nutrients[1].id: 2.5}
    assert [(p.unit_id, p.grams_per_portion) for p in created.portions] == [(ref.unit("stk"), 50)]
    child_ids = [v.id for v in created.nutrient_values] + [p.id for p in created.portions]
    assert len(set(child_ids)) == len(child_ids) and created.id not in child_ids, "alle barn skal ha egne id-er"
    assert all(child.ingredient_id == created.id for child in [*created.nutrient_values, *created.portions])

    assert expect(admin.core.get(f"{ADMIN}/{created.id}"), 200, Ingredient) == created
    assert expect(user.core.get(f"{USER}/{created.id}"), 200, Ingredient) == created
    listed = {row.id: row for row in _search(user)}
    assert created.id in listed, "den nye ingrediensen mangler i søkelista (cache ikke ugyldiggjort?)"
    assert listed[created.id].energy_kcal == 100


def test_create_gives_201_with_a_location_header(admin: Actor, ref: Reference, unique, cleanup):
    resp = admin.core.post(ADMIN, json=ingredient_payload(ref, unique("location")))
    created = expect(resp, 201, Ingredient)
    cleanup.register("slett ingrediens (location)", lambda: admin.core.delete(f"{ADMIN}/{created.id}"))
    assert resp.headers.get("Location", "").endswith(created.id), f"Location peker ikke på ingrediensen: {describe(resp)}"


def test_names_are_normalized_and_unique(admin: Actor, ref: Reference, make_ingredient):
    created = make_ingredient("Stor   Bokstav")  # sendes med store bokstaver og flere mellomrom
    assert created.name == created.name.lower() and "  " not in created.name, f"navnet er ikke normalisert: {created.name!r}"
    resp = admin.core.post(ADMIN, json=ingredient_payload(ref, created.name.upper()))
    assert resp.status_code == 409, f"samme navn (andre bokstaver) skal gi 409: {describe(resp)}"


def test_create_can_make_a_variant_of_another_ingredient(user: Actor, make_ingredient):
    base = make_ingredient("basis")
    variant = make_ingredient("variant", variantOfIngredientId=base.id)
    assert variant.variant_of_ingredient_id == base.id
    listed = {row.id: row for row in _search(user)}
    assert listed[variant.id].variant_of_ingredient_id == base.id


BAD_REQUESTS = {
    "tomt-navn": lambda ref: {"name": "  "},
    "negative-kcal": lambda ref: {"energyKcal": -1},
    "negativ-naeringsverdi": lambda ref: {"nutrientValues": [{"nutrientDefinitionId": ref.nutrients[0].id, "quantity": -0.1}]},
    "porsjon-med-null-gram": lambda ref: {"portions": [{"unitId": ref.unit("stk"), "gramsPerPortion": 0}]},
}

CONFLICTING_REQUESTS = {
    "ukjent-kategori": lambda ref: {"categoryId": str(uuid.uuid4())},
    "ukjent-standardenhet": lambda ref: {"defaultUnitId": str(uuid.uuid4())},
    "ukjent-enhetstype": lambda ref: {"primaryUnitTypeId": str(uuid.uuid4())},
    "ukjent-naeringsstoff": lambda ref: {"nutrientValues": [{"nutrientDefinitionId": "finnes-ikke", "quantity": 1}]},
    "duplisert-naeringsstoff": lambda ref: {"nutrientValues": [
        {"nutrientDefinitionId": ref.nutrients[0].id, "quantity": 1}, {"nutrientDefinitionId": ref.nutrients[0].id, "quantity": 2}]},
    "ukjent-basisingrediens": lambda ref: {"variantOfIngredientId": str(uuid.uuid4())},
}


@pytest.mark.parametrize("case", BAD_REQUESTS)
def test_invalid_content_is_rejected_with_400(admin: Actor, ref: Reference, unique, core_admin_ready, case: str):
    payload = {**ingredient_payload(ref, unique("ugyldig")), **BAD_REQUESTS[case](ref)}
    resp = admin.core.post(ADMIN, json=payload)
    assert resp.status_code == 400, f"forventet 400: {describe(resp)}"


@pytest.mark.parametrize("case", CONFLICTING_REQUESTS)
def test_references_to_things_that_do_not_exist_give_409(admin: Actor, ref: Reference, unique, core_admin_ready, case: str):
    payload = {**ingredient_payload(ref, unique("konflikt")), **CONFLICTING_REQUESTS[case](ref)}
    resp = admin.core.post(ADMIN, json=payload)
    assert resp.status_code == 409, f"forventet 409: {describe(resp)}"


@pytest.mark.parametrize("missing", ["name", "categoryId", "primaryUnitTypeId", "defaultUnitId", "energyKcal"])
def test_required_fields_are_enforced(admin: Actor, ref: Reference, unique, core_admin_ready, missing: str):
    payload = ingredient_payload(ref, unique("mangler"))
    del payload[missing]
    assert expect(admin.core.post(ADMIN, json=payload), 400, ProblemDetails).errors is not None


# ---------------------------------------------------------------------------------------- admin: endre

def test_update_replaces_the_ingredient_and_all_children(admin: Actor, user: Actor, ref: Reference, make_ingredient, unique):
    created = make_ingredient("endre")
    new_name = unique("endret")
    request = ingredient_payload(
        ref, new_name, energyKcal=250, ediblePartPercent=80, allergenIds=[], isVerified=True,
        nutrientValues=[{"nutrientDefinitionId": ref.nutrients[2].id, "quantity": 7}],
        portions=[{"unitId": ref.unit("stk"), "gramsPerPortion": 60}, {"unitId": ref.unit("dl"), "gramsPerPortion": 90}],
    )
    updated = expect(admin.core.put(f"{ADMIN}/{created.id}", json=request), 200, Ingredient)

    assert updated.id == created.id and updated.name == new_name
    assert (updated.energy_kcal, updated.edible_part_percent, updated.is_verified) == (250, 80, True)
    assert [(v.nutrient_definition_id, v.quantity) for v in updated.nutrient_values] == [(ref.nutrients[2].id, 7)]
    assert sorted(p.grams_per_portion for p in updated.portions) == [60, 90]
    old_children = {v.id for v in created.nutrient_values} | {p.id for p in created.portions}
    assert not old_children & ({v.id for v in updated.nutrient_values} | {p.id for p in updated.portions}), "barna skal få nye id-er"

    assert expect(user.core.get(f"{USER}/{created.id}"), 200, Ingredient) == updated
    listed = {row.id: row for row in _search(user)}
    assert (listed[created.id].name, listed[created.id].energy_kcal) == (new_name, 250), "søkelista viser gamle verdier (cache?)"


def test_update_validates_like_create(admin: Actor, ref: Reference, make_ingredient):
    created = make_ingredient("endre-ugyldig")
    assert admin.core.put(f"{ADMIN}/{created.id}", json=ingredient_payload(ref, "  ")).status_code == 400
    bad_category = ingredient_payload(ref, created.name, categoryId=str(uuid.uuid4()))
    assert admin.core.put(f"{ADMIN}/{created.id}", json=bad_category).status_code == 409


def test_update_of_an_unknown_ingredient_is_404(admin: Actor, ref: Reference, unique, core_admin_ready):
    resp = admin.core.put(f"{ADMIN}/{uuid.uuid4()}", json=ingredient_payload(ref, unique("ukjent")))
    assert resp.status_code == 404, describe(resp)


# ---------------------------------------------------------------------------------------- admin: slett

def test_delete_removes_the_ingredient_everywhere(admin: Actor, user: Actor, make_ingredient):
    created = make_ingredient("slett")
    assert admin.core.delete(f"{ADMIN}/{created.id}").status_code == 204
    assert admin.core.get(f"{ADMIN}/{created.id}").status_code == 404
    assert user.core.get(f"{USER}/{created.id}").status_code == 404
    assert created.id not in _ids(_search(user)), "slettet ingrediens ligger fortsatt i søkelista (cache?)"
    assert admin.core.delete(f"{ADMIN}/{created.id}").status_code == 404, "ny sletting av en borte ingrediens skal gi 404"


def test_delete_of_an_unknown_ingredient_is_404(admin: Actor, core_admin_ready):
    assert admin.core.delete(f"{ADMIN}/{uuid.uuid4()}").status_code == 404


def test_an_ingredient_used_by_a_recipe_cannot_be_deleted(admin: Actor, user: Actor, make_ingredient, make_recipe):
    used = make_ingredient("brukt")
    recipe = make_recipe(user, "bruker-ingrediens", used.id)
    resp = admin.core.delete(f"{ADMIN}/{used.id}")
    assert resp.status_code == 409, f"ingrediensen er brukt av en oppskrift, forventet 409: {describe(resp)}"
    assert user.core.delete(f"/api/user/recipes/{recipe.id}").status_code == 204
    assert admin.core.delete(f"{ADMIN}/{used.id}").status_code == 204


def test_a_base_ingredient_with_a_variant_cannot_be_deleted(admin: Actor, make_ingredient):
    base = make_ingredient("basis-slett")
    variant = make_ingredient("variant-slett", variantOfIngredientId=base.id)
    assert admin.core.delete(f"{ADMIN}/{base.id}").status_code == 409
    assert admin.core.delete(f"{ADMIN}/{variant.id}").status_code == 204
    assert admin.core.delete(f"{ADMIN}/{base.id}").status_code == 204


def test_an_ingredient_used_by_an_unconfirmed_ingredient_cannot_be_deleted(
        admin: Actor, user: Actor, make_ingredient, make_unconfirmed):
    """En godkjent/sammenslått ubekreftet ingrediens peker på den offisielle og beholdes som historikk."""
    target = make_ingredient("maal")
    unconfirmed = make_unconfirmed(user, "peker-paa", request_review=True)
    merged = admin.core.post(f"/api/admin/unconfirmed-ingredients/{unconfirmed.id}/merge", json={"ingredientId": target.id})
    assert merged.status_code == 200, describe(merged)
    assert admin.core.delete(f"{ADMIN}/{target.id}").status_code == 409
    assert user.core.delete(f"/api/user/unconfirmed-ingredients/{unconfirmed.id}").status_code == 204
    assert admin.core.delete(f"{ADMIN}/{target.id}").status_code == 204
