"""Core API: ubekreftede ingredienser. En bruker som ikke finner en ingrediens lager en privat rad og kan be admin om å ta
den inn i katalogen (`NotRequested → Pending → Approved | Merged | Rejected`).

Alt filtreres på brukeren i tokenet: en annen brukers rad finnes ikke (404). Testene bruker to brukere, `alice` og `bob`.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from apitests.actors import Actor
from apitests.core_data import Reference, delete_or_raise, ingredient_payload
from apitests.http import describe, expect
from apitests.models.common import ProblemDetails
from apitests.models.core import Ingredient, UnconfirmedIngredient

pytestmark = pytest.mark.mutating  # oppretter brukere og rader

UP, AP = "/api/user/unconfirmed-ingredients", "/api/admin/unconfirmed-ingredients"


def _mine(actor: Actor) -> list[UnconfirmedIngredient]:
    return expect(actor.core.get(UP), 200, list[UnconfirmedIngredient])


def _queue(admin: Actor, **params) -> list[UnconfirmedIngredient]:
    return expect(admin.core.get(AP, params=params), 200, list[UnconfirmedIngredient])


# --------------------------------------------------------------------------------------------- tilgang

_ID = uuid.uuid4()
USER_CALLS = [
    pytest.param("GET", UP, None, id="user-liste"),
    pytest.param("GET", f"{UP}/{_ID}", None, id="user-hent"),
    pytest.param("POST", UP, {"name": "apitest-avvist"}, id="user-opprett"),
    pytest.param("PUT", f"{UP}/{_ID}", {"name": "apitest-avvist"}, id="user-endre"),
    pytest.param("POST", f"{UP}/{_ID}/request-review", None, id="user-be-om-vurdering"),
    pytest.param("DELETE", f"{UP}/{_ID}", None, id="user-slett"),
]
ADMIN_CALLS = [
    pytest.param("GET", AP, None, id="admin-koe"),
    pytest.param("GET", f"{AP}/{_ID}", None, id="admin-hent"),
    pytest.param("POST", f"{AP}/{_ID}/approve", {}, id="admin-godkjenn"),
    pytest.param("POST", f"{AP}/{_ID}/merge", {"ingredientId": str(uuid.uuid4())}, id="admin-slaa-sammen"),
    pytest.param("POST", f"{AP}/{_ID}/reject", {"reason": "nei"}, id="admin-avslaa"),
]


@pytest.mark.parametrize("method,path,body", USER_CALLS + ADMIN_CALLS)
def test_anonymous_is_rejected(anon: Actor, method: str, path: str, body):
    assert anon.core.request(method, path, json=body).status_code == 401


@pytest.mark.parametrize("method,path,body", ADMIN_CALLS)
def test_the_review_queue_is_admin_only(alice: Actor, method: str, path: str, body):
    assert alice.core.request(method, path, json=body).status_code == 403


# ------------------------------------------------------------------------------------- livssyklus (bruker)

def test_create_read_rename_and_delete(alice: Actor, make_unconfirmed):
    created = make_unconfirmed(alice, "Livssyklus")
    assert created.name == created.name.lower(), "navnet skal lagres med små bokstaver"
    assert created.review_status == "NotRequested"
    assert created.created_by_user_id == alice.user_id
    assert created.rejection_reason is None and created.reviewed_at is None and created.resolved_ingredient_id is None
    assert abs(datetime.now(timezone.utc) - created.created_at) < timedelta(minutes=5), "createdAt er ikke satt til nå"

    assert expect(alice.core.get(f"{UP}/{created.id}"), 200, UnconfirmedIngredient) == created
    assert created.id in {row.id for row in _mine(alice)}

    new_name = created.name + "-endret"
    renamed = expect(alice.core.put(f"{UP}/{created.id}", json={"name": new_name.upper()}), 200, UnconfirmedIngredient)
    assert renamed.name == new_name and renamed.id == created.id, "PUT skal gi elementet med normalisert nytt navn"
    assert expect(alice.core.get(f"{UP}/{created.id}"), 200, UnconfirmedIngredient).name == new_name

    assert alice.core.delete(f"{UP}/{created.id}").status_code == 204
    assert alice.core.get(f"{UP}/{created.id}").status_code == 404
    assert created.id not in {row.id for row in _mine(alice)}
    assert alice.core.delete(f"{UP}/{created.id}").status_code == 404


def test_create_gives_201_with_a_location_and_a_normalized_name(alice: Actor, unique, cleanup):
    resp = alice.core.post(UP, json={"name": f"  {unique('Lilla   GULROT')}  "})
    created = expect(resp, 201, UnconfirmedIngredient)
    cleanup.register("slett ubekreftet (normalisering)", lambda: delete_or_raise(alice.core, f"{UP}/{created.id}"))
    assert resp.headers.get("Location", "").endswith(created.id), f"Location peker ikke på raden: {describe(resp)}"
    assert created.name == created.name.lower() and "  " not in created.name and created.name == created.name.strip()


def test_the_list_is_newest_first(alice: Actor, make_unconfirmed):
    first, second = make_unconfirmed(alice, "eldst"), make_unconfirmed(alice, "nyest")
    ids = [row.id for row in _mine(alice)]
    assert ids.index(second.id) < ids.index(first.id), "nyeste skal komme først"


def test_request_review_moves_a_row_to_pending_and_locks_it(alice: Actor, make_unconfirmed):
    row = make_unconfirmed(alice, "til-vurdering")
    pending = expect(alice.core.post(f"{UP}/{row.id}/request-review"), 200, UnconfirmedIngredient)
    assert (pending.id, pending.review_status) == (row.id, "Pending")
    assert alice.core.post(f"{UP}/{row.id}/request-review").status_code == 409, "kan ikke be om vurdering to ganger"
    assert alice.core.put(f"{UP}/{row.id}", json={"name": row.name + "-x"}).status_code == 409, "bare NotRequested kan endres"
    assert alice.core.delete(f"{UP}/{row.id}").status_code == 204, "eieren kan slette uansett status"


def test_request_review_can_be_given_at_creation(alice: Actor, make_unconfirmed):
    assert make_unconfirmed(alice, "direkte", request_review=True).review_status == "Pending"


@pytest.mark.parametrize("method,suffix,body", [
    ("GET", "", None), ("PUT", "", {"name": "apitest-x"}), ("POST", "/request-review", None), ("DELETE", "", None)])
@pytest.mark.parametrize("id_", [str(uuid.uuid4()), "ikke-en-guid"], ids=["ukjent-id", "ugyldig-id"])
def test_unknown_id_is_404(alice: Actor, method: str, suffix: str, body, id_: str):
    """Både en id som ikke finnes og en som ikke er en Guid gir 404 (håndskrevne kontrollere)."""
    assert alice.core.request(method, f"{UP}/{id_}{suffix}", json=body).status_code == 404


# ------------------------------------------------------------------------------------------- validering

@pytest.mark.parametrize("name", ["", "   ", "x" * 201], ids=["tomt", "bare-mellomrom", "for-langt"])
def test_a_name_must_be_1_to_200_characters(alice: Actor, name: str):
    resp = alice.core.post(UP, json={"name": name})
    assert resp.status_code == 400, f"forventet 400: {describe(resp)}"


def test_a_name_of_exactly_200_characters_is_accepted(alice: Actor, cleanup):
    name = "apitest-" + "x" * 192
    created = expect(alice.core.post(UP, json={"name": name}), 201, UnconfirmedIngredient)
    cleanup.register("slett ubekreftet (lengde)", lambda: delete_or_raise(alice.core, f"{UP}/{created.id}"))
    assert len(created.name) == 200


def test_the_name_field_is_required(alice: Actor):
    assert expect(alice.core.post(UP, json={}), 400, ProblemDetails).errors is not None


def test_rename_validates_the_name(alice: Actor, make_unconfirmed):
    row = make_unconfirmed(alice, "endre-ugyldig")
    assert alice.core.put(f"{UP}/{row.id}", json={"name": "  "}).status_code == 400
    assert alice.core.put(f"{UP}/{row.id}", json={"name": "x" * 201}).status_code == 400


def test_a_name_that_exists_as_an_official_ingredient_is_a_conflict(alice: Actor, ref: Reference, make_unconfirmed):
    for name in (ref.official.name, ref.official.name.upper()):
        resp = alice.core.post(UP, json={"name": name})
        assert resp.status_code == 409, f"«{name}» finnes som offisiell ingrediens, forventet 409: {describe(resp)}"
    row = make_unconfirmed(alice, "endre-til-offisiell")
    assert alice.core.put(f"{UP}/{row.id}", json={"name": ref.official.name}).status_code == 409


def test_a_user_cannot_have_the_same_name_twice_but_others_can(alice: Actor, bob: Actor, make_unconfirmed):
    mine = make_unconfirmed(alice, "delt-navn")
    assert alice.core.post(UP, json={"name": mine.name}).status_code == 409, "samme navn to ganger hos samme bruker"
    theirs = expect(bob.core.post(UP, json={"name": mine.name}), 201, UnconfirmedIngredient)
    try:
        assert theirs.name == mine.name and theirs.created_by_user_id == bob.user_id, "radene er private per bruker"
    finally:
        assert bob.core.delete(f"{UP}/{theirs.id}").status_code == 204


def test_at_most_10_requests_can_be_pending_at_once(fresh_user, make_unconfirmed):
    """Grensen er per bruker, så testen bruker en egen fersk bruker. Nr. 11 avvises, hverken ved opprettelse eller vurdering."""
    carol = fresh_user("carol")
    for n in range(10):
        make_unconfirmed(carol, f"ventende{n}", request_review=True)
    resp = carol.core.post(UP, json={"name": "apitest-for-mange", "requestReview": True})
    assert resp.status_code == 409, f"nr. 11 ventende skal gi 409: {describe(resp)}"
    unrequested = make_unconfirmed(carol, "ikke-bedt")
    assert carol.core.post(f"{UP}/{unrequested.id}/request-review").status_code == 409, "grensen gjelder også request-review"


# ------------------------------------------------------------------------------------------ isolasjon

def test_a_user_only_sees_their_own_rows(alice: Actor, bob: Actor, admin: Actor, make_unconfirmed):
    row = make_unconfirmed(alice, "privat")
    assert row.id not in {r.id for r in _mine(bob)}, "B ser As rad i lista"
    assert row.id not in {r.id for r in _mine(admin)}, "admin ser As rad på brukerruten"
    assert bob.core.get(f"{UP}/{row.id}").status_code == 404
    assert bob.core.put(f"{UP}/{row.id}", json={"name": "apitest-kapret"}).status_code == 404
    assert bob.core.post(f"{UP}/{row.id}/request-review").status_code == 404
    assert bob.core.delete(f"{UP}/{row.id}").status_code == 404
    assert expect(alice.core.get(f"{UP}/{row.id}"), 200, UnconfirmedIngredient) == row, "As rad ble endret av B"


def test_a_new_user_starts_with_an_empty_list(fresh_user):
    assert _mine(fresh_user("tom")) == []


# ---------------------------------------------------------------------------------------- admin: køen

def test_the_queue_shows_pending_rows_oldest_first(admin: Actor, alice: Actor, bob: Actor, make_unconfirmed):
    first = make_unconfirmed(alice, "koe-eldst", request_review=True)
    second = make_unconfirmed(bob, "koe-nyest", request_review=True)
    idle = make_unconfirmed(alice, "koe-ikke-bedt")
    queue = _queue(admin)
    ids = [row.id for row in queue]
    assert {first.id, second.id} <= set(ids) and idle.id not in ids, "køen viser bare ventende rader (fra alle brukere)"
    assert all(row.review_status == "Pending" for row in queue)
    assert ids.index(first.id) < ids.index(second.id), "eldste først"
    assert [r.created_at for r in queue] == sorted(r.created_at for r in queue)


def test_the_queue_can_show_all_rows_or_one_status(admin: Actor, alice: Actor, make_unconfirmed):
    idle = make_unconfirmed(alice, "koe-alle")
    pending = make_unconfirmed(alice, "koe-alle-ventende", request_review=True)
    everything = {row.id for row in _queue(admin, all="true")}
    assert {idle.id, pending.id} <= everything, "?all=true skal gi alle statuser"
    rejected = expect(admin.core.post(f"{AP}/{pending.id}/reject", json={"reason": "duplikat"}), 200, UnconfirmedIngredient)
    only_rejected = _queue(admin, status="Rejected")
    assert rejected.id in {row.id for row in only_rejected} and all(row.review_status == "Rejected" for row in only_rejected)


def test_admin_can_read_any_users_row_by_id(admin: Actor, alice: Actor, make_unconfirmed):
    row = make_unconfirmed(alice, "admin-les", request_review=True)
    assert expect(admin.core.get(f"{AP}/{row.id}"), 200, UnconfirmedIngredient) == row
    assert admin.core.get(f"{AP}/{uuid.uuid4()}").status_code == 404


# ------------------------------------------------------------------------------- admin: godkjenn / slå sammen / avslå

def test_approve_creates_the_official_ingredient(admin: Actor, alice: Actor, user: Actor, make_unconfirmed, approve):
    row = make_unconfirmed(alice, "til-godkjenning", request_review=True)
    ingredient = approve(row)

    resolved = expect(alice.core.get(f"{UP}/{row.id}"), 200, UnconfirmedIngredient)
    assert resolved.review_status == "Approved" and resolved.resolved_ingredient_id == ingredient.id
    assert resolved.reviewed_at is not None and resolved.rejection_reason is None
    assert expect(user.core.get(f"/api/user/ingredients/{ingredient.id}"), 200, Ingredient) == ingredient
    assert ingredient.id in {i["id"] for i in user.core.get("/api/user/ingredients").json()}, "den nye ingrediensen er søkbar for alle"
    assert row.id not in {r.id for r in _queue(admin)}, "avgjort rad skal ut av køen"


def test_approve_can_make_the_ingredient_a_variant(alice: Actor, make_unconfirmed, make_ingredient, approve):
    base = make_ingredient("basis-godkjenning")
    variant = approve(make_unconfirmed(alice, "variant-godkjenning", request_review=True), variantOfIngredientId=base.id)
    assert variant.variant_of_ingredient_id == base.id


def test_merge_links_to_an_existing_ingredient(admin: Actor, alice: Actor, make_unconfirmed, make_ingredient):
    target = make_ingredient("sammenslaatt-med")
    row = make_unconfirmed(alice, "til-sammenslaaing", request_review=True)
    merged = expect(admin.core.post(f"{AP}/{row.id}/merge", json={"ingredientId": target.id}), 200, UnconfirmedIngredient)
    assert (merged.review_status, merged.resolved_ingredient_id) == ("Merged", target.id) and merged.reviewed_at is not None
    assert expect(alice.core.get(f"{UP}/{row.id}"), 200, UnconfirmedIngredient) == merged


def test_reject_is_final_and_stays_private(admin: Actor, alice: Actor, make_unconfirmed, make_ingredient, ref: Reference, unique):
    row = make_unconfirmed(alice, "til-avslag", request_review=True)
    rejected = expect(admin.core.post(f"{AP}/{row.id}/reject", json={"reason": "duplikat av noe annet"}), 200, UnconfirmedIngredient)
    assert rejected.review_status == "Rejected" and rejected.rejection_reason == "duplikat av noe annet"
    assert rejected.resolved_ingredient_id is None and rejected.reviewed_at is not None
    assert expect(alice.core.get(f"{UP}/{row.id}"), 200, UnconfirmedIngredient) == rejected, "brukeren ser utfallet"

    # Terminal: ingen videre avgjørelser, og brukeren kan ikke be om ny vurdering eller endre navnet
    other = make_ingredient("avslag-maal")
    assert admin.core.post(f"{AP}/{row.id}/reject", json={}).status_code == 409
    assert admin.core.post(f"{AP}/{row.id}/merge", json={"ingredientId": other.id}).status_code == 409
    assert admin.core.post(f"{AP}/{row.id}/approve", json=ingredient_payload(ref, unique("avslag"))).status_code == 409
    assert alice.core.post(f"{UP}/{row.id}/request-review").status_code == 409
    assert alice.core.put(f"{UP}/{row.id}", json={"name": row.name + "-x"}).status_code == 409
    assert alice.core.delete(f"{UP}/{row.id}").status_code == 204, "en avslått rad kan slettes av eieren"


def test_reject_reason_is_optional(admin: Actor, alice: Actor, make_unconfirmed):
    row = make_unconfirmed(alice, "avslag-uten-grunn", request_review=True)
    rejected = expect(admin.core.post(f"{AP}/{row.id}/reject", json={}), 200, UnconfirmedIngredient)
    assert rejected.review_status == "Rejected" and rejected.rejection_reason is None


def test_only_pending_rows_can_be_decided(admin: Actor, alice: Actor, make_unconfirmed, make_ingredient, ref: Reference, unique):
    """Ikke bedt om vurdering (`NotRequested`) og allerede avgjort (`Approved`/`Merged`) gir 409 på alle tre avgjørelsene."""
    target = make_ingredient("avgjoer-maal")
    idle = make_unconfirmed(alice, "ikke-bedt-avgjoer")
    assert admin.core.post(f"{AP}/{idle.id}/approve", json=ingredient_payload(ref, unique("x"))).status_code == 409
    assert admin.core.post(f"{AP}/{idle.id}/merge", json={"ingredientId": target.id}).status_code == 409
    assert admin.core.post(f"{AP}/{idle.id}/reject", json={}).status_code == 409

    done = make_unconfirmed(alice, "allerede-slaatt-sammen", request_review=True)
    assert admin.core.post(f"{AP}/{done.id}/merge", json={"ingredientId": target.id}).status_code == 200
    assert admin.core.post(f"{AP}/{done.id}/merge", json={"ingredientId": target.id}).status_code == 409
    assert admin.core.post(f"{AP}/{done.id}/reject", json={}).status_code == 409
    assert alice.core.put(f"{UP}/{done.id}", json={"name": done.name + "-x"}).status_code == 409
    assert alice.core.post(f"{UP}/{done.id}/request-review").status_code == 409


def test_invalid_decisions_are_rejected_and_leave_the_row_pending(
        admin: Actor, alice: Actor, make_unconfirmed, ref: Reference, unique):
    row = make_unconfirmed(alice, "ugyldig-avgjoerelse", request_review=True)
    assert admin.core.post(f"{AP}/{row.id}/approve", json=ingredient_payload(ref, "  ")).status_code == 400
    bad_category = ingredient_payload(ref, unique("ugyldig"), categoryId=str(uuid.uuid4()))
    assert admin.core.post(f"{AP}/{row.id}/approve", json=bad_category).status_code == 409
    assert admin.core.post(f"{AP}/{row.id}/merge", json={"ingredientId": str(uuid.uuid4())}).status_code == 400, \
        "sammenslåing med en ingrediens som ikke finnes gir 400"
    assert expect(admin.core.get(f"{AP}/{row.id}"), 200, UnconfirmedIngredient).review_status == "Pending"


@pytest.mark.parametrize("action,body", [("approve", {}), ("merge", {"ingredientId": str(uuid.uuid4())}), ("reject", {})])
def test_deciding_an_unknown_row_is_404(admin: Actor, ref: Reference, unique, action: str, body: dict):
    if action == "approve":
        body = ingredient_payload(ref, unique("ukjent"))
    assert admin.core.post(f"{AP}/{uuid.uuid4()}/{action}", json=body).status_code == 404
