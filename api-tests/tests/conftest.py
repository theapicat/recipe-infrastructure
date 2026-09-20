"""Fixtures for Core-testene (ingredienser, ubekreftede ingredienser og oppskrifter).

Alt som opprettes registreres for sletting via `cleanup` (barn før foreldre, med nye forsøk), og får prefikset `apitest-`.
"""
from __future__ import annotations

import itertools

import pytest

from apitests.actors import Actor
from apitests.config import Settings
from apitests.core_data import Reference, delete_or_raise, ingredient_payload, load_reference, recipe_payload
from apitests.http import expect
from apitests.models.core import Ingredient, Recipe, UnconfirmedIngredient


@pytest.fixture(scope="session")
def ref(core_ready: None, admin: Actor) -> Reference:
    """Seedede kataloger (enheter, kategorier, næringsstoffer) og én ekte ingrediens, brukt som fremmednøkler."""
    return load_reference(admin)


@pytest.fixture(scope="session")
def unique(settings: Settings):
    """Gir unike, prefikserte navn (`apitest-<kjøre-ID>-<tag>-<n>`), i små bokstaver slik serveren lagrer dem."""
    counter = itertools.count(1)
    return lambda tag: settings.test_name(f"{tag}-{next(counter)}")


@pytest.fixture(scope="session")
def make_ingredient(admin: Actor, ref: Reference, cleanup, unique, core_admin_ready):
    """Oppretter en offisiell ingrediens som admin (201) og registrerer den for sletting."""

    def make(tag: str = "ingrediens", **overrides) -> Ingredient:
        payload = ingredient_payload(ref, unique(tag), **overrides)
        created = expect(admin.core.post("/api/admin/ingredients", json=payload), 201, Ingredient)
        cleanup.register(f"slett ingrediens {created.name}", lambda: delete_or_raise(admin.core, f"/api/admin/ingredients/{created.id}"))
        return created

    return make


@pytest.fixture
def make_unconfirmed(cleanup, unique, core_ready):
    """Oppretter en ubekreftet ingrediens som en bruker (201), evt. rett til vurdering.

    Raden slettes igjen når testen er ferdig (grensene er per bruker: 10 ventende, 100 totalt), og den er i tillegg
    registrert i den felles oppryddingen som sikkerhetsnett."""
    made: list[tuple[Actor, str]] = []

    def make(owner: Actor, tag: str = "ubekreftet", *, request_review: bool = False) -> UnconfirmedIngredient:
        body = {"name": unique(tag), "requestReview": request_review}
        created = expect(owner.core.post("/api/user/unconfirmed-ingredients", json=body), 201, UnconfirmedIngredient)
        path = f"/api/user/unconfirmed-ingredients/{created.id}"
        cleanup.register(f"slett ubekreftet ingrediens {created.name}", lambda: delete_or_raise(owner.core, path))
        made.append((owner, path))
        return created

    yield make
    for owner, path in reversed(made):
        owner.core.delete(path)  # best effort: kan allerede være slettet av testen, eller brukes av en oppskrift (da tar den felles oppryddingen det)


@pytest.fixture
def make_recipe(ref: Reference, cleanup, unique, core_ready):
    """Oppretter en oppskrift som en bruker (201). `overrides` erstatter felt i forespørselen.

    Oppskriften slettes når testen er ferdig, så delte brukere alltid starter en test uten oppskrifter."""
    made: list[tuple[Actor, str]] = []

    def make(owner: Actor, tag: str = "oppskrift", ingredient_id: str | None = None, **overrides) -> Recipe:
        payload = {**recipe_payload(ref, unique(tag), ingredient_id), **overrides}
        created = expect(owner.core.post("/api/user/recipes", json=payload), 201, Recipe)
        path = f"/api/user/recipes/{created.id}"
        cleanup.register(f"slett oppskrift {created.title}", lambda: delete_or_raise(owner.core, path))
        made.append((owner, path))
        return created

    yield make
    for owner, path in reversed(made):
        owner.core.delete(path)


@pytest.fixture
def approve(admin: Actor, ref: Reference, cleanup, unique):
    """Godkjenner en ventende ubekreftet ingrediens som admin (ny offisiell ingrediens) og registrerer den for sletting."""

    def do(unconfirmed: UnconfirmedIngredient, **overrides) -> Ingredient:
        payload = ingredient_payload(ref, overrides.pop("name", unique("godkjent")), **overrides)
        created = expect(admin.core.post(f"/api/admin/unconfirmed-ingredients/{unconfirmed.id}/approve", json=payload), 200, Ingredient)
        cleanup.register(f"slett ingrediens {created.name}", lambda: delete_or_raise(admin.core, f"/api/admin/ingredients/{created.id}"))
        return created

    return do


@pytest.fixture(scope="session")
def alice(user_factory) -> Actor:
    """Bruker A i tester som trenger to ulike brukere (oppskrifter og ubekreftede ingredienser er strengt private)."""
    return user_factory("alice")


@pytest.fixture(scope="session")
def bob(user_factory) -> Actor:
    """Bruker B: skal aldri se noe som tilhører A."""
    return user_factory("bob")


@pytest.fixture(scope="session")
def fresh_user(user_factory):
    """Oppretter en ny bruker uten data (hver test som trenger tomme lister lager sin egen)."""
    counter = itertools.count(1)
    return lambda tag: user_factory(f"{tag}-{next(counter)}")
