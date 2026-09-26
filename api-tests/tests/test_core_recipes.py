"""Core API: oppskrifter. Strengt brukereide: en bruker får bare sine egne, en annen brukers oppskrift finnes ikke (404).

Bare selve oppskriften er en ressurs; steg, ingredienslinjer og kilde leses og skrives sammen med den. Testene bruker to
vanlige brukere (`alice`, `bob`) og ferske brukere der en helt tom oppskriftsliste trengs. Næring har egen fil.
"""
from __future__ import annotations

import time
import uuid

import pytest

from apitests.actors import Actor
from apitests.core_data import Reference, line, recipe_payload
from apitests.http import describe, expect
from apitests.models.common import ProblemDetails
from apitests.models.core import Recipe, RecipeListItem

pytestmark = pytest.mark.mutating  # oppretter brukere og oppskrifter

BASE = "/api/user/recipes"


def _list(actor: Actor) -> list[RecipeListItem]:
    return expect(actor.core.get(BASE), 200, list[RecipeListItem])


def _get(actor: Actor, recipe_id: str) -> Recipe:
    return expect(actor.core.get(f"{BASE}/{recipe_id}"), 200, Recipe)


def _post(actor: Actor, payload: dict):
    return actor.core.post(BASE, json=payload)


# --------------------------------------------------------------------------------------------- tilgang

ANON_CALLS = [
    pytest.param("GET", BASE, None, id="liste"),
    pytest.param("GET", f"{BASE}/{uuid.uuid4()}", None, id="hent"),
    pytest.param("POST", BASE, {"title": "apitest-avvist"}, id="opprett"),
    pytest.param("PUT", f"{BASE}/{uuid.uuid4()}", {"title": "apitest-avvist"}, id="endre"),
    pytest.param("DELETE", f"{BASE}/{uuid.uuid4()}", None, id="slett"),
    pytest.param("PUT", f"{BASE}/{uuid.uuid4()}/favorite", {"isFavorite": True}, id="favoritt"),
    pytest.param("GET", f"{BASE}/{uuid.uuid4()}/nutrition", None, id="naering"),
]


@pytest.mark.parametrize("method,path,body", ANON_CALLS)
def test_anonymous_is_rejected(anon: Actor, method: str, path: str, body):
    assert anon.core.request(method, path, json=body).status_code == 401


# -------------------------------------------------------------------------- hver bruker får bare sine egne

def test_a_user_with_no_recipes_gets_an_empty_list(fresh_user):
    assert _list(fresh_user("uten-oppskrifter")) == []


def test_a_user_with_ten_recipes_gets_exactly_those_ten_and_others_get_none(fresh_user, bob: Actor, make_recipe):
    carol, dave = fresh_user("carol"), fresh_user("dave")
    made = [make_recipe(carol, f"kake-{n:02d}") for n in range(10)]

    mine = _list(carol)
    assert {r.id for r in mine} == {r.id for r in made} and len(mine) == 10, "skal få akkurat de ti egne"
    assert [r.title for r in mine] == sorted(r.title for r in mine), "lista er sortert på tittel"
    assert _list(dave) == [], "en annen bruker uten oppskrifter skal få en tom liste, ikke Carols"
    assert not {r.id for r in _list(bob)} & {r.id for r in made}, "Bob ser oppskrifter som tilhører Carol"


def test_each_user_only_sees_their_own_recipes(alice: Actor, bob: Actor, admin: Actor, make_recipe):
    a, b = make_recipe(alice, "alices"), make_recipe(bob, "bobs")
    assert a.id in {r.id for r in _list(alice)} and b.id not in {r.id for r in _list(alice)}
    assert b.id in {r.id for r in _list(bob)} and a.id not in {r.id for r in _list(bob)}
    assert not {a.id, b.id} & {r.id for r in _list(admin)}, "admin har ingen tilgang til andres oppskrifter"


def _not_found_body(resp) -> dict:
    body = resp.json()
    body.pop("traceId", None)
    return body


OPERATIONS = {
    "hent": lambda actor, rid, payload: actor.core.get(f"{BASE}/{rid}"),
    "endre": lambda actor, rid, payload: actor.core.put(f"{BASE}/{rid}", json=payload),
    "slett": lambda actor, rid, payload: actor.core.delete(f"{BASE}/{rid}"),
    "favoritt": lambda actor, rid, payload: actor.core.put(f"{BASE}/{rid}/favorite", json={"isFavorite": True}),
    "naering": lambda actor, rid, payload: actor.core.get(f"{BASE}/{rid}/nutrition"),
}


@pytest.mark.parametrize("who", ["bob", "admin"])
@pytest.mark.parametrize("operation", OPERATIONS)
def test_someone_elses_recipe_does_not_exist(request: pytest.FixtureRequest, alice: Actor, make_recipe, ref: Reference,
                                             operation: str, who: str):
    """Å hente, endre, slette, markere som favoritt eller regne næring på en annen brukers oppskrift gir samme 404 som en
    id som ikke finnes (uten `detail`), og eierens oppskrift er urørt etterpå."""
    intruder: Actor = request.getfixturevalue(who)
    recipe = make_recipe(alice, "privat")
    attack = OPERATIONS[operation]
    payload = recipe_payload(ref, "apitest-kapret")

    theirs = attack(intruder, recipe.id, payload)
    nothing = attack(intruder, str(uuid.uuid4()), payload)
    assert theirs.status_code == 404, f"{who} {operation} på As oppskrift: forventet 404, fikk {describe(theirs)}"
    assert (theirs.status_code, _not_found_body(theirs)) == (nothing.status_code, _not_found_body(nothing)), \
        "svaret for en annens oppskrift skal være identisk med svaret for en som ikke finnes"
    assert _get(alice, recipe.id) == recipe, "eierens oppskrift ble endret (eller slettet) av en annen bruker"


def test_identity_comes_only_from_the_token(alice: Actor, bob: Actor, make_recipe):
    """En `ownerUserId` (eller `id`) i kroppen ignoreres: eieren er alltid brukeren i tokenet."""
    sent_id = str(uuid.uuid4())
    recipe = make_recipe(alice, "kapring", ownerUserId=bob.user_id, id=sent_id)
    assert recipe.owner_user_id == alice.user_id and recipe.id != sent_id
    assert recipe.id in {r.id for r in _list(alice)} and recipe.id not in {r.id for r in _list(bob)}
    assert bob.core.get(f"{BASE}/{recipe.id}").status_code == 404

    body = {**_recipe_request(alice, recipe), "ownerUserId": bob.user_id}
    assert alice.core.put(f"{BASE}/{recipe.id}", json=body).status_code == 200
    assert _get(alice, recipe.id).owner_user_id == alice.user_id, "eieren skal ikke kunne endres via PUT"


def _recipe_request(actor: Actor, recipe: Recipe) -> dict:
    """En forespørsel som gjenskaper en eksisterende oppskrift (uten id-er og avledede felt)."""
    return {
        "title": recipe.title, "description": recipe.description, "categoryId": recipe.category_id, "servings": recipe.servings,
        "steps": [{"description": s.description, "timerMinutes": s.timer_minutes} for s in recipe.steps],
        "ingredients": [{"ingredientId": i.ingredient_id, "unconfirmedIngredientId": i.unconfirmed_ingredient_id,
                         "amount": i.amount, "unitId": i.unit_id, "note": i.note} for i in recipe.ingredients],
    }


# ------------------------------------------------------------------------------------------ livssyklus

def test_create_returns_the_whole_recipe(alice: Actor, ref: Reference, unique, make_recipe):
    title = unique("Kremet   Kyllinggryte")
    resp = _post(alice, recipe_payload(
        ref, title, description="Enkel hverdagsmiddag.", imageUrl="https://example.test/gryte.jpg", imageAttribution="Fotograf",
        source={"reference": "min kokebok"},
        steps=[{"description": "Kutt kyllingen."}, {"description": "Kok i 20 minutter.", "timerMinutes": 20},
               {"description": "La den hvile.", "timerMinutes": 5}],
        ingredients=[line(ref, ingredient_id=ref.official.id, amount=2, unit="stk"),
                     line(ref, ingredient_id=ref.official.id, amount=100, unit="g", note="finhakket"),
                     line(ref, ingredient_id=ref.official.id, amount=None, unit="g")]))
    recipe = expect(resp, 201, Recipe)
    try:
        assert resp.headers.get("Location", "").endswith(recipe.id), f"Location peker ikke på oppskriften: {describe(resp)}"
        assert recipe.owner_user_id == alice.user_id
        assert recipe.title == title.lower().replace("   ", " "), f"tittelen skal lagres med små bokstaver: {recipe.title!r}"
        assert (recipe.servings, recipe.category_id, recipe.description) == (4, ref.recipe_category_id, "Enkel hverdagsmiddag.")
        assert (recipe.image_url, recipe.image_attribution) == ("https://example.test/gryte.jpg", "Fotograf")
        assert recipe.is_favorite is False
        assert recipe.cook_time_minutes == 25, "koketiden er summen av steg-timerne (20 + 5)"
        assert [(s.step_number, s.description, s.timer_minutes) for s in recipe.steps] == [
            (1, "Kutt kyllingen.", None), (2, "Kok i 20 minutter.", 20), (3, "La den hvile.", 5)], "stegene nummereres etter rekkefølge"
        assert [(i.sort_order, i.amount, i.note) for i in recipe.ingredients] == [(1, 2, None), (2, 100, "finhakket"), (3, 0, None)], \
            "linjene beholder rekkefølgen, og utelatt mengde blir 0 (etter smak)"
        assert all(i.name == ref.official.name and i.recipe_id == recipe.id for i in recipe.ingredients)
        assert recipe.source.type == "Manual" and recipe.source.reference == "min kokebok"
        assert recipe.source.url is None and recipe.source.is_edited_from_source is None
        child_ids = [s.id for s in recipe.steps] + [i.id for i in recipe.ingredients]
        assert len(set(child_ids)) == len(child_ids) and all(s.recipe_id == recipe.id for s in recipe.steps), "server-tildelte id-er"
        assert recipe.created_at == recipe.updated_at
        assert _get(alice, recipe.id) == recipe, "GET skal gi det samme som POST"
    finally:
        assert alice.core.delete(f"{BASE}/{recipe.id}").status_code == 204


def test_read_update_favorite_and_delete(alice: Actor, ref: Reference, make_recipe, unique):
    recipe = make_recipe(alice, "livssyklus")

    # Lista viser oppskriften i lettvektsform, og GET gir hele
    item = next(r for r in _list(alice) if r.id == recipe.id)
    assert (item.title, item.category_id, item.cook_time_minutes, item.servings, item.is_favorite, item.image_url) == (
        recipe.title, recipe.category_id, 20, 4, False, None)

    # Favoritt: egen liten operasjon, 204 uten kropp
    resp = alice.core.put(f"{BASE}/{recipe.id}/favorite", json={"isFavorite": True})
    assert resp.status_code == 204 and not resp.content, describe(resp)
    assert _get(alice, recipe.id).is_favorite is True
    assert next(r for r in _list(alice) if r.id == recipe.id).is_favorite is True

    # Endre: alt erstattes (steg og linjer får nye id-er), mens id, eier, favoritt og createdAt beholdes
    time.sleep(0.05)
    new_title = unique("endret")
    change = recipe_payload(ref, new_title, description="Ny beskrivelse.", servings=2,
                            steps=[{"description": "Bare ett steg.", "timerMinutes": 7}],
                            ingredients=[line(ref, ingredient_id=ref.official.id, amount=3, unit="dl", note="kald")])
    updated = expect(alice.core.put(f"{BASE}/{recipe.id}", json=change), 200, Recipe)
    assert (updated.id, updated.owner_user_id, updated.created_at, updated.is_favorite) == (
        recipe.id, recipe.owner_user_id, recipe.created_at, True)
    assert updated.updated_at > recipe.updated_at, "updatedAt settes av serveren"
    assert (updated.title, updated.description, updated.servings, updated.cook_time_minutes) == (new_title, "Ny beskrivelse.", 2, 7)
    assert [s.description for s in updated.steps] == ["Bare ett steg."] and [i.note for i in updated.ingredients] == ["kald"]
    assert not {s.id for s in recipe.steps} & {s.id for s in updated.steps}, "steg får nye id-er"
    assert not {i.id for i in recipe.ingredients} & {i.id for i in updated.ingredients}, "linjer får nye id-er"
    assert _get(alice, recipe.id) == updated
    assert next(r for r in _list(alice) if r.id == recipe.id).title == new_title

    # Favoritt kan slås av igjen
    assert alice.core.put(f"{BASE}/{recipe.id}/favorite", json={"isFavorite": False}).status_code == 204
    assert _get(alice, recipe.id).is_favorite is False

    # Slette
    assert alice.core.delete(f"{BASE}/{recipe.id}").status_code == 204
    assert alice.core.get(f"{BASE}/{recipe.id}").status_code == 404
    assert recipe.id not in {r.id for r in _list(alice)}
    assert alice.core.delete(f"{BASE}/{recipe.id}").status_code == 404, "sletting av en oppskrift som er borte gir 404"


def test_the_list_is_sorted_by_title(alice: Actor, make_recipe):
    for title in ("c-sist", "a-forst", "b-midt"):
        make_recipe(alice, title)
    titles = [r.title for r in _list(alice)]
    assert titles == sorted(titles)


@pytest.mark.parametrize("method,suffix,body", [
    ("GET", "", None), ("PUT", "", "recipe"), ("DELETE", "", None), ("PUT", "/favorite", {"isFavorite": True}), ("GET", "/nutrition", None)])
@pytest.mark.parametrize("id_", [str(uuid.uuid4()), "ikke-en-guid"], ids=["ukjent-id", "ugyldig-id"])
def test_unknown_or_malformed_id_is_404(alice: Actor, ref: Reference, method: str, suffix: str, body, id_: str):
    body = recipe_payload(ref, "apitest-ukjent") if body == "recipe" else body
    assert alice.core.request(method, f"{BASE}/{id_}{suffix}", json=body).status_code == 404


def test_the_source_is_manual_and_only_the_reference_can_be_set(alice: Actor, make_recipe):
    """Klienten kan bare oppgi fritekst. `type`, `url` og `isEditedFromSource` styres av serveren (Manual for API-et)."""
    recipe = make_recipe(alice, "kilde", source={"reference": "mormors kokebok", "type": "Scraped", "url": "https://example.test/x",
                                                 "isEditedFromSource": True})
    assert (recipe.source.type, recipe.source.reference, recipe.source.url, recipe.source.is_edited_from_source) == (
        "Manual", "mormors kokebok", None, None)
    assert make_recipe(alice, "uten-kilde").source.reference is None


def test_recipe_lines_can_be_to_taste(alice: Actor, ref: Reference, make_recipe):
    """Utelatt mengde og `0` betyr «etter smak» og lagres som 0. Rekkefølgen på linjene beholdes."""
    recipe = make_recipe(alice, "etter-smak", ingredients=[
        line(ref, ingredient_id=ref.official.id, amount=None), line(ref, ingredient_id=ref.official.id, amount=0),
        line(ref, ingredient_id=ref.official.id, amount=1.5, unit="dl")])
    assert [(i.sort_order, i.amount) for i in recipe.ingredients] == [(1, 0), (2, 0), (3, 1.5)]


# ------------------------------------------------------------------------------------------- unik tittel

DUPLICATE_TITLE = "Du har allerede en oppskrift med denne tittelen. Velg en annen tittel."


def test_a_title_is_unique_per_user(alice: Actor, bob: Actor, ref: Reference, make_recipe):
    """Samme tittel (uansett store/små bokstaver og mellomrom) gir 409 for samme bruker, men ikke for en annen bruker."""
    first = make_recipe(alice, "unik-tittel")
    messy = "  " + first.title.upper() + "  "
    assert expect(_post(alice, recipe_payload(ref, messy)), 409, ProblemDetails).detail == DUPLICATE_TITLE
    assert [r.id for r in _list(alice) if r.title == first.title] == [first.id], "ingen ny oppskrift skal være lagret"

    other = make_recipe(bob, "annen-bruker", title=first.title)
    assert other.title == first.title, "ulike brukere kan ha samme tittel"


def test_a_recipe_keeps_its_own_title_on_update_but_cannot_take_another(alice: Actor, make_recipe):
    first, second = make_recipe(alice, "tittel-a"), make_recipe(alice, "tittel-b")
    same = {**_recipe_request(alice, first), "servings": 6}
    assert expect(alice.core.put(f"{BASE}/{first.id}", json=same), 200, Recipe).servings == 6

    taken = {**_recipe_request(alice, second), "title": first.title.upper()}
    assert expect(alice.core.put(f"{BASE}/{second.id}", json=taken), 409, ProblemDetails).detail == DUPLICATE_TITLE
    assert _get(alice, second.id).title == second.title


# ------------------------------------------------------------------------------------------- validering

def _lines(ref: Reference, n: int) -> list[dict]:
    return [line(ref, ingredient_id=ref.official.id, amount=1) for _ in range(n)]


INVALID = {
    # forretningsregler (400 med norsk `detail`)
    "tom-tittel": lambda ref: {"title": "   "},
    "for-lang-tittel": lambda ref: {"title": "x" * 201},
    "for-lang-beskrivelse": lambda ref: {"description": "x" * 5001},
    "porsjoner-0": lambda ref: {"servings": 0},
    "porsjoner-negativ": lambda ref: {"servings": -2},
    "porsjoner-over-1000": lambda ref: {"servings": 1001},
    "ingen-steg": lambda ref: {"steps": []},
    "tomt-steg": lambda ref: {"steps": [{"description": "  "}]},
    "for-langt-steg": lambda ref: {"steps": [{"description": "x" * 2001}]},
    "negativ-timer": lambda ref: {"steps": [{"description": "a", "timerMinutes": -1}]},
    "timer-over-en-uke": lambda ref: {"steps": [{"description": "a", "timerMinutes": 10081}]},
    "over-100-steg": lambda ref: {"steps": [{"description": "a"} for _ in range(101)]},
    "ingen-ingredienser": lambda ref: {"ingredients": []},
    "over-100-ingredienser": lambda ref: {"ingredients": _lines(ref, 101)},
    "negativ-mengde": lambda ref: {"ingredients": [line(ref, ingredient_id=ref.official.id, amount=-1)]},
    "for-langt-notat": lambda ref: {"ingredients": [line(ref, ingredient_id=ref.official.id, note="x" * 201)]},
    "linje-uten-ingrediens": lambda ref: {"ingredients": [{"unitId": ref.unit("g"), "amount": 1}]},
    "linje-med-begge-typer": lambda ref: {"ingredients": [
        line(ref, ingredient_id=ref.official.id, unconfirmed_id=str(uuid.uuid4()))]},
    "ukjent-ubekreftet-ingrediens": lambda ref: {"ingredients": [line(ref, unconfirmed_id=str(uuid.uuid4()))]},
    "bildeadresse-uten-protokoll": lambda ref: {"imageUrl": "gryte.jpg"},
    "bildeadresse-ftp": lambda ref: {"imageUrl": "ftp://example.test/gryte.jpg"},
    "bildeadresse-javascript": lambda ref: {"imageUrl": "javascript:alert(1)"},
    # bindingsfeil (manglende påkrevd felt)
    "mangler-tittel": lambda ref: {"title": None},
    "mangler-beskrivelse": lambda ref: {"description": None},
    "mangler-kategori": lambda ref: {"categoryId": None},
    "mangler-porsjoner": lambda ref: {"servings": None},
}


@pytest.mark.parametrize("case", INVALID)
def test_invalid_content_is_rejected_with_400(alice: Actor, ref: Reference, unique, case: str):
    payload = {**recipe_payload(ref, unique("ugyldig")), **INVALID[case](ref)}
    payload = {k: v for k, v in payload.items() if v is not None}  # None = utelat feltet
    before = len(_list(alice))
    resp = _post(alice, payload)
    assert resp.status_code == 400, f"forventet 400: {describe(resp)}"
    assert expect(resp, 400, ProblemDetails).status == 400
    assert len(_list(alice)) == before, "en avvist oppskrift skal ikke lagres"


BOUNDARIES = {
    "en-porsjon": lambda ref: {"servings": 1},
    "tusen-porsjoner": lambda ref: {"servings": 1000},
    "timer-en-uke": lambda ref: {"steps": [{"description": "a", "timerMinutes": 10080}]},
    "timer-null": lambda ref: {"steps": [{"description": "a", "timerMinutes": 0}]},
    "100-steg": lambda ref: {"steps": [{"description": "a"} for _ in range(100)]},
    "100-ingredienser": lambda ref: {"ingredients": _lines(ref, 100)},
    "tittel-200-tegn": lambda ref: {"title": "apitest-" + "t" * 192},
    "https-bilde": lambda ref: {"imageUrl": "https://example.test/gryte.jpg"},
    "http-bilde": lambda ref: {"imageUrl": "http://example.test/gryte.jpg"},
}


@pytest.mark.parametrize("case", BOUNDARIES)
def test_the_limits_themselves_are_accepted(alice: Actor, ref: Reference, unique, make_recipe, case: str):
    overrides = BOUNDARIES[case](ref)
    make_recipe(alice, "grense", **overrides)  # 201 kreves av fabrikken


REFERENCES = {
    "ukjent-kategori": lambda ref: {"categoryId": str(uuid.uuid4())},
    "ukjent-ingrediens": lambda ref: {"ingredients": [line(ref, ingredient_id=str(uuid.uuid4()))]},
    "ukjent-enhet": lambda ref: {"ingredients": [{"ingredientId": ref.official.id, "amount": 1, "unitId": str(uuid.uuid4())}]},
}


@pytest.mark.parametrize("case", REFERENCES)
def test_references_to_things_that_do_not_exist_give_409(alice: Actor, ref: Reference, unique, case: str):
    resp = _post(alice, {**recipe_payload(ref, unique("ukjent-referanse")), **REFERENCES[case](ref)})
    assert resp.status_code == 409, f"forventet 409: {describe(resp)}"


def test_update_validates_like_create_and_changes_nothing_when_it_fails(alice: Actor, ref: Reference, make_recipe):
    recipe = make_recipe(alice, "endre-ugyldig")
    assert alice.core.put(f"{BASE}/{recipe.id}", json=recipe_payload(ref, "  ")).status_code == 400
    assert alice.core.put(f"{BASE}/{recipe.id}", json=recipe_payload(ref, recipe.title, steps=[])).status_code == 400
    assert alice.core.put(f"{BASE}/{recipe.id}", json=recipe_payload(ref, recipe.title, categoryId=str(uuid.uuid4()))).status_code == 409
    assert _get(alice, recipe.id) == recipe, "en mislykket endring skal ikke røre oppskriften"


def test_the_favorite_request_needs_a_boolean(alice: Actor, make_recipe):
    recipe = make_recipe(alice, "favoritt-ugyldig")
    assert alice.core.put(f"{BASE}/{recipe.id}/favorite", json={"isFavorite": "kanskje"}).status_code == 400
    assert _get(alice, recipe.id).is_favorite is False


# --------------------------------------------------------------------- egne (ubekreftede) ingredienser i oppskrifter

def test_a_recipe_can_use_the_users_own_unconfirmed_ingredient(alice: Actor, ref: Reference, make_unconfirmed, make_recipe):
    own = make_unconfirmed(alice, "egen-ingrediens")
    recipe = make_recipe(alice, "med-egen", ingredients=[
        line(ref, ingredient_id=ref.official.id, amount=1, unit="stk"), line(ref, unconfirmed_id=own.id, amount=100, unit="g")])
    official, custom = recipe.ingredients
    assert (official.ingredient_id, official.unconfirmed_ingredient_id) == (ref.official.id, None)
    assert (custom.ingredient_id, custom.unconfirmed_ingredient_id, custom.name) == (None, own.id, own.name)
    assert alice.core.delete(f"/api/user/unconfirmed-ingredients/{own.id}").status_code == 409, "brukt av en oppskrift"
    assert alice.core.delete(f"{BASE}/{recipe.id}").status_code == 204
    assert alice.core.delete(f"/api/user/unconfirmed-ingredients/{own.id}").status_code == 204


def test_someone_elses_unconfirmed_ingredient_cannot_be_used(alice: Actor, bob: Actor, ref: Reference, make_unconfirmed, unique):
    theirs = make_unconfirmed(bob, "bobs-egen")
    resp = _post(alice, recipe_payload(ref, unique("kaprer"), ingredients=[line(ref, unconfirmed_id=theirs.id)]))
    assert resp.status_code == 400, f"samme svar som for en som ikke finnes (400): {describe(resp)}"


def test_approving_moves_the_recipe_lines_to_the_official_ingredient(
        alice: Actor, ref: Reference, make_unconfirmed, make_recipe, approve, unique):
    own = make_unconfirmed(alice, "blir-godkjent", request_review=True)
    recipe = make_recipe(alice, "flyttes", ingredients=[line(ref, unconfirmed_id=own.id, amount=50, unit="g")])
    official = approve(own)

    moved = _get(alice, recipe.id).ingredients[0]
    assert (moved.ingredient_id, moved.unconfirmed_ingredient_id, moved.name) == (official.id, None, official.name), \
        "oppskriftslinjen skal peke på den offisielle ingrediensen etter godkjenning"
    assert (moved.amount, moved.unit_id) == (50, ref.unit("g")), "mengde og enhet er uendret"
    resp = _post(alice, recipe_payload(ref, unique("bruker-godkjent"), ingredients=[line(ref, unconfirmed_id=own.id)]))
    assert resp.status_code == 400, f"en løst ubekreftet ingrediens kan ikke brukes lenger (bruk den offisielle): {describe(resp)}"


def test_merging_moves_the_recipe_lines_to_the_existing_ingredient(
        admin: Actor, alice: Actor, ref: Reference, make_unconfirmed, make_recipe, make_ingredient):
    own = make_unconfirmed(alice, "blir-slaatt-sammen", request_review=True)
    target = make_ingredient("slaas-sammen-med")
    recipe = make_recipe(alice, "flyttes-ved-sammenslaaing", ingredients=[line(ref, unconfirmed_id=own.id, amount=2, unit="stk")])
    merged = admin.core.post(f"/api/admin/unconfirmed-ingredients/{own.id}/merge", json={"ingredientId": target.id})
    assert merged.status_code == 200, describe(merged)
    moved = _get(alice, recipe.id).ingredients[0]
    assert (moved.ingredient_id, moved.unconfirmed_ingredient_id, moved.name) == (target.id, None, target.name)
