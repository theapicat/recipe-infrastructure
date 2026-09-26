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
    assert len(as_user) > 500, f"forventet hele den seedede katalogen (ca. 700), fikk {len(as_user)} rader"
    assert _ids(as_user) == _ids(as_admin), "brukere og admin skal se samme ingredienser"


def test_seeded_ingredients_are_official_and_verified(user: Actor, ref: Reference):
    """Seed-radene (Matvaretabellen + derivater) er offisielle og verifiserte, og revisjonsfeltene er tomme for dem."""
    official = _search(user, isOfficial="true")
    assert len(official) > 500, f"forventet de seedede offisielle ingrediensene, fikk {len(official)}"
    assert all(row.is_official and row.is_verified for row in official)
    derivatives = [row for row in official if row.variant_of_ingredient_id]
    assert derivatives, "seed-dataene skal ha derivater (spaghetti, whisky ...) som peker på en basisingrediens"
    base_ids = _ids(official)
    assert all(row.variant_of_ingredient_id in base_ids for row in derivatives), "et derivat skal peke på en offisiell basis"


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


def test_search_filters_by_origin_and_variant(user: Actor, make_ingredient):
    """`isOfficial` skiller seed-rader fra admin-opprettede, `isVariant` skiller varianter fra grunningredienser."""
    base = make_ingredient("opprinnelse")
    variant = make_ingredient("opprinnelse-variant", variantOfIngredientId=base.id)

    not_official = _search(user, isOfficial="false")
    assert {base.id, variant.id} <= _ids(not_official) and all(not row.is_official for row in not_official)
    assert not {base.id, variant.id} & _ids(_search(user, isOfficial="true"))

    variants = _search(user, isVariant="true")
    assert variant.id in _ids(variants) and base.id not in _ids(variants)
    assert all(row.variant_of_ingredient_id for row in variants)
    bases = _search(user, isVariant="false")
    assert base.id in _ids(bases) and variant.id not in _ids(bases)
    assert all(row.variant_of_ingredient_id is None for row in bases)
    assert _ids(_search(user, isOfficial="false", isVariant="true")) >= {variant.id}


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
    row = listed[created.id]
    assert row.energy_kcal == 100
    assert (row.nutrient_value_count, row.portion_count, row.usage_count) == (2, 1, 0)
    assert (row.created_at, row.updated_at, row.verified_at) == (created.created_at, created.updated_at, None)


def test_server_controlled_fields_cannot_be_set_by_the_client(admin: Actor, ref: Reference, unique, cleanup):
    """`isOfficial`, `usageCount`, tidsstempler og revisjonsfelt settes av serveren; en klient som sender dem ignoreres."""
    payload = ingredient_payload(
        ref, unique("serverstyrt"), isOfficial=True, usageCount=99, createdAt="2000-01-01T00:00:00+00:00",
        updatedByUserId=str(uuid.uuid4()), verifiedAt="2000-01-01T00:00:00+00:00", verifiedByUserId=str(uuid.uuid4()))
    created = expect(admin.core.post(ADMIN, json=payload), 201, Ingredient)
    cleanup.register("slett ingrediens (serverstyrt)", lambda: delete_or_raise(admin.core, f"{ADMIN}/{created.id}"))
    assert created.is_official is False, "en ingrediens laget via API-et er aldri offisiell"
    assert (created.usage_count, created.allergens_reviewed) == (0, False)
    assert created.created_at.year > 2000
    assert created.updated_by_user_id not in (None, payload["updatedByUserId"]), "hvem som endret kommer fra tokenet"
    assert (created.verified_at, created.verified_by_user_id) == (None, None), "ikke verifisert, så ingen verifiseringsdata"


def test_verification_is_audited(admin: Actor, ref: Reference, make_ingredient):
    """Verifisering settes når `isVerified` går til true, beholdes mens den er true, og nullstilles når den går til false."""
    created = make_ingredient("revisjon", isVerified=True)
    assert created.verified_at is not None and created.verified_by_user_id == created.updated_by_user_id is not None

    path = f"{ADMIN}/{created.id}"
    kept = expect(admin.core.put(path, json=ingredient_payload(ref, created.name, isVerified=True, energyKcal=101)), 200, Ingredient)
    assert (kept.verified_at, kept.verified_by_user_id) == (created.verified_at, created.verified_by_user_id)
    assert kept.created_at == created.created_at and kept.updated_at > created.updated_at

    cleared = expect(admin.core.put(path, json=ingredient_payload(ref, created.name, isVerified=False)), 200, Ingredient)
    assert (cleared.verified_at, cleared.verified_by_user_id) == (None, None)
    assert expect(admin.core.get(path), 200, Ingredient).verified_at is None


def test_allergens_reviewed_is_a_normal_editable_field(admin: Actor, ref: Reference, make_ingredient):
    created = make_ingredient("allergener-gjennomgaatt", allergensReviewed=True)
    assert created.allergens_reviewed is True
    updated = expect(admin.core.put(f"{ADMIN}/{created.id}", json=ingredient_payload(ref, created.name)), 200, Ingredient)
    assert updated.allergens_reviewed is False, "utelatt i PUT betyr false"


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


# Hver sak: (endring i forespørselen, forventet `detail` - tekst, eller en funksjon av `ref` når meldingen navngir noe).
# Alle skal gi 400 med nøyaktig denne meldingen.
BAD_REQUESTS = {
    "tomt-navn": (lambda ref: {"name": "  "}, "Navn må oppgis."),
    "negative-kcal": (lambda ref: {"energyKcal": -1}, "Energi (kcal) kan ikke være negativ."),
    "negative-kj": (lambda ref: {"energyKj": -1}, "Energi (kJ) kan ikke være negativ."),
    "spiselig-del-null": (lambda ref: {"ediblePartPercent": 0}, "Spiselig del må være mellom 0 og 100 %."),
    "spiselig-del-over-100": (lambda ref: {"ediblePartPercent": 100.5}, "Spiselig del må være mellom 0 og 100 %."),
    "for-stor-energi": (lambda ref: {"energyKcal": 100_000_000}, "Verdien for energi er for stor."),
    "kilde-url-ftp": (lambda ref: {"sourceUrl": "ftp://example.test/x"}, "Kilde-URL må starte med http:// eller https://."),
    "negativ-naeringsverdi": (lambda ref: {"nutrientValues": [{"nutrientDefinitionId": ref.nutrients[0].id, "quantity": -0.1}]},
                              "Næringsverdier må ha et næringsstoff og en verdi som ikke er negativ."),
    "duplisert-naeringsstoff": (lambda ref: {"nutrientValues": [
        {"nutrientDefinitionId": ref.nutrients[0].id, "quantity": 1}, {"nutrientDefinitionId": ref.nutrients[0].id, "quantity": 2}]},
        lambda ref: f"Næringsstoffet {ref.nutrients[0].id} er oppgitt flere ganger."),
    "verifisert-uten-naering": (lambda ref: {"isVerified": True, "nutrientValues": []},
                                "Ingrediensen må ha næringsverdier for å kunne verifiseres."),
    "porsjon-med-null-gram": (lambda ref: {"portions": [{"unitId": ref.unit("stk"), "gramsPerPortion": 0}]},
                              "Porsjoner må ha en gramverdi større enn null."),
    # Referanser som ikke finnes eller ikke henger sammen (tidligere en generisk 409 fra databasen)
    "ukjent-kategori": (lambda ref: {"categoryId": str(uuid.uuid4())}, "Kategorien finnes ikke."),
    "ukjent-enhetstype": (lambda ref: {"primaryUnitTypeId": str(uuid.uuid4())}, "Enhetstypen finnes ikke."),
    "ukjent-standardenhet": (lambda ref: {"defaultUnitId": str(uuid.uuid4())}, "Standardenheten finnes ikke."),
    "standardenhet-av-annen-type": (lambda ref: {"defaultUnitId": ref.unit("dl")}, "Standardenheten må høre til den valgte enhetstypen."),
    "ukjent-allergen": (lambda ref: {"allergenIds": [str(uuid.uuid4())]}, "Ett eller flere allergener finnes ikke."),
    "ukjent-soekeord": (lambda ref: {"searchKeywordIds": [str(uuid.uuid4())]}, "Ett eller flere søkeord finnes ikke."),
    "ukjent-naeringsstoff": (lambda ref: {"nutrientValues": [{"nutrientDefinitionId": "finnes-ikke", "quantity": 1}]},
                             "Næringsstoffet finnes-ikke finnes ikke."),
    "ukjent-porsjonsenhet": (lambda ref: {"portions": [{"unitId": str(uuid.uuid4()), "gramsPerPortion": 10}]},
                             "Enheten i en porsjon finnes ikke."),
    "duplisert-porsjonsenhet": (lambda ref: {"portions": [{"unitId": ref.unit("stk"), "gramsPerPortion": 10},
                                                         {"unitId": ref.unit("stk"), "gramsPerPortion": 20}]},
                                lambda ref: f"Enheten {ref.units['stk'].name} er brukt i flere porsjoner."),
    "ukjent-basisingrediens": (lambda ref: {"variantOfIngredientId": str(uuid.uuid4())}, "Basisingrediensen finnes ikke."),
}


@pytest.mark.parametrize("case", BAD_REQUESTS)
def test_invalid_content_is_rejected_with_a_specific_400(admin: Actor, ref: Reference, unique, core_admin_ready, case: str):
    change, detail = BAD_REQUESTS[case]
    payload = {**ingredient_payload(ref, unique("ugyldig")), **change(ref)}
    problem = expect(admin.core.post(ADMIN, json=payload), 400, ProblemDetails)
    assert problem.detail == (detail(ref) if callable(detail) else detail)


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
    path = f"{ADMIN}/{created.id}"
    assert admin.core.put(path, json=ingredient_payload(ref, "  ")).status_code == 400
    bad_category = ingredient_payload(ref, created.name, categoryId=str(uuid.uuid4()))
    assert expect(admin.core.put(path, json=bad_category), 400, ProblemDetails).detail == "Kategorien finnes ikke."
    itself = ingredient_payload(ref, created.name, variantOfIngredientId=created.id)
    assert expect(admin.core.put(path, json=itself), 400, ProblemDetails).detail == "En ingrediens kan ikke være en variant av seg selv."
    assert expect(admin.core.get(path), 200, Ingredient) == created, "en avvist endring skal ikke endre noe"


def test_a_variant_chain_cannot_form_a_loop(admin: Actor, ref: Reference, make_ingredient):
    base = make_ingredient("loekke-basis")
    variant = make_ingredient("loekke-variant", variantOfIngredientId=base.id)
    loop = ingredient_payload(ref, base.name, variantOfIngredientId=variant.id)
    assert expect(admin.core.put(f"{ADMIN}/{base.id}", json=loop), 400, ProblemDetails).detail == "Variantkjeden danner en løkke."


# ---------------------------------------------------------------------------------------- admin: samtidighet

CONCURRENCY_CONFLICT = "Ingrediensen er endret av noen andre siden du åpnet den. Last den på nytt."


def test_optimistic_concurrency_rejects_a_stale_update(admin: Actor, ref: Reference, make_ingredient):
    """`updatedAt` fra siste GET sendes med i PUT; er den eldre enn det lagrede, har noen andre endret ingrediensen."""
    created = make_ingredient("samtidighet")
    path = f"{ADMIN}/{created.id}"
    opened = expect(admin.core.get(path), 200, Ingredient)
    stamp = opened.to_json()["updatedAt"]

    first = expect(admin.core.put(path, json=ingredient_payload(ref, created.name, energyKcal=110, updatedAt=stamp)), 200, Ingredient)
    stale = admin.core.put(path, json=ingredient_payload(ref, created.name, energyKcal=120, updatedAt=stamp))
    assert expect(stale, 409, ProblemDetails).detail == CONCURRENCY_CONFLICT
    assert expect(admin.core.get(path), 200, Ingredient).energy_kcal == 110, "den utdaterte endringen skal ikke lagres"

    fresh = expect(admin.core.get(path), 200, Ingredient).to_json()["updatedAt"]
    assert admin.core.put(path, json=ingredient_payload(ref, created.name, energyKcal=130, updatedAt=fresh)).status_code == 200
    assert first.updated_at > opened.updated_at
    # Uten updatedAt gjøres ingen sjekk (bakoverkompatibelt)
    assert admin.core.put(path, json=ingredient_payload(ref, created.name, energyKcal=140)).status_code == 200


# ------------------------------------------------------------------------------ admin: offisielle ingredienser

OFFICIAL_LOCKED = "Offisielle ingredienser kan ikke endre kildedata. Opprett en variant."


def _official_as_request(full: Ingredient, **overrides) -> dict:
    """En offisiell ingrediens gjort om til en `IngredientRequest` uten endringer i kildedataene."""
    data = full.to_json()
    request = {key: data[key] for key in (
        "name", "categoryId", "primaryUnitTypeId", "defaultUnitId", "energyKcal", "energyKj", "ediblePartPercent", "sourceId",
        "sourceUrl", "variantOfIngredientId", "isVerified", "allergenIds", "searchKeywordIds", "allergensReviewed", "updatedAt")}
    request["nutrientValues"] = [
        {"nutrientDefinitionId": v["nutrientDefinitionId"], "quantity": v["quantity"], "sourceId": v["sourceId"]}
        for v in reversed(data["nutrientValues"])]  # annen rekkefølge enn lagret: skal ikke telle som en endring
    request["portions"] = [{"unitId": p["unitId"], "gramsPerPortion": p["gramsPerPortion"]} for p in data["portions"]]
    return {**request, **overrides}


@pytest.fixture
def official(admin: Actor, ref: Reference) -> Ingredient:
    """En seedet, offisiell ingrediens med næringsverdier. Testene under endrer den ALDRI (se `_never_written`)."""
    row = next(r for r in expect(admin.core.get(ADMIN, params={"isOfficial": "true", "isVariant": "false"}), 200,
                                 list[IngredientListItem]) if r.nutrient_value_count > 1)
    return expect(admin.core.get(f"{ADMIN}/{row.id}"), 200, Ingredient)


def _never_written(overrides: dict) -> dict:
    """Alle forespørsler mot seed-rader får i tillegg en ukjent kategori.

    Låsen sjekkes før fremmednøklene, så en virkende lås svarer med låsemeldingen. Er låsen ødelagt, stopper
    fremmednøkkelsjekken skrivingen i stedet (og testen feiler) - seed-dataene endres aldri av testsuiten."""
    return {**overrides, "categoryId": str(uuid.uuid4())}


@pytest.mark.parametrize("change", [
    pytest.param(lambda o: {"name": o.name + " endret"}, id="navn"),
    pytest.param(lambda o: {"energyKcal": o.energy_kcal + 1}, id="energi-kcal"),
    pytest.param(lambda o: {"energyKj": (o.energy_kj or 0) + 1}, id="energi-kj"),
    pytest.param(lambda o: {"ediblePartPercent": 50 if o.edible_part_percent != 50 else 60}, id="spiselig-del"),
    pytest.param(lambda o: {"sourceId": "apitest"}, id="kilde-id"),
    pytest.param(lambda o: {"sourceUrl": "https://example.test/apitest"}, id="kilde-url"),
    pytest.param(lambda o: {"nutrientValues": [{"nutrientDefinitionId": v.nutrient_definition_id, "quantity": v.quantity,
                                                "sourceId": v.source_id} for v in o.nutrient_values[1:]]}, id="naeringsverdi-fjernet"),
    pytest.param(lambda o: {"nutrientValues": [{"nutrientDefinitionId": v.nutrient_definition_id, "quantity": v.quantity + 1,
                                                "sourceId": v.source_id} for v in o.nutrient_values]}, id="naeringsverdi-endret"),
])
def test_source_data_of_an_official_ingredient_is_locked(admin: Actor, official: Ingredient, change):
    body = _official_as_request(official, **_never_written(change(official)))
    problem = expect(admin.core.put(f"{ADMIN}/{official.id}", json=body), 400, ProblemDetails)
    assert problem.detail == OFFICIAL_LOCKED


def test_other_fields_of_an_official_ingredient_pass_the_lock(admin: Actor, official: Ingredient, ref: Reference):
    """Kategori, enheter, allergener, porsjoner, verifisering og `allergensReviewed` er fritt redigerbare, og
    næringsverdiene i en annen rekkefølge er ingen endring. Forespørselen stoppes først av den ukjente kategorien,
    altså etter at låsen har godtatt den."""
    body = _official_as_request(official, **_never_written({
        "allergensReviewed": not official.allergens_reviewed, "isVerified": True,
        "portions": [{"unitId": ref.unit("stk"), "gramsPerPortion": 123}]}))
    assert expect(admin.core.put(f"{ADMIN}/{official.id}", json=body), 400, ProblemDetails).detail == "Kategorien finnes ikke."
    assert expect(admin.core.get(f"{ADMIN}/{official.id}"), 200, Ingredient) == official, "seed-raden skal være uendret"


def test_update_of_an_unknown_ingredient_is_404(admin: Actor, ref: Reference, unique, core_admin_ready):
    resp = admin.core.put(f"{ADMIN}/{uuid.uuid4()}", json=ingredient_payload(ref, unique("ukjent")))
    assert resp.status_code == 404, describe(resp)


# ---------------------------------------------------------------------------------------- admin: slett

IN_USE = "Brukes av {n} oppskriftslinjer, varianter og ubekreftede ingredienser og kan ikke slettes."

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
    listed = {row.id: row for row in _search(user)}
    assert listed[used.id].usage_count == 1
    assert expect(admin.core.get(f"{ADMIN}/{used.id}"), 200, Ingredient).usage_count == 1
    resp = admin.core.delete(f"{ADMIN}/{used.id}")
    assert expect(resp, 409, ProblemDetails).detail == IN_USE.format(n=1)
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
