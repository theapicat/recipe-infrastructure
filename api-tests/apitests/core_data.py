"""Testdata for Core API: oppslag av seedede referanser og byggere for ingrediens-, oppskrifts- og ubekreftet-forespørsler.

Byggerne lager gyldige forespørsler (slik dokumentasjonen beskriver dem). Testene overstyrer enkeltfelt for å prøve regler.
"""
from __future__ import annotations

from dataclasses import dataclass

from .actors import Actor
from .http import ApiClient, describe, expect
from .models.core import IngredientListItem, NutrientDefinition, Unit, UnitType


@dataclass(frozen=True)
class Reference:
    """Seedede kataloger testene bruker som fremmednøkler (testene oppretter aldri egne kategorier/enheter til dette)."""

    units: dict[str, Unit]  # på forkortelse: g, stk, dl, ss, ml ...
    unit_type_ids: dict[str, str]  # på dimensjon: Weight, Volume, Count (navnet er bare en etikett og kan endres)
    ingredient_category_id: str
    recipe_category_id: str
    nutrients: list[NutrientDefinition]
    official: IngredientListItem  # en ekte, seedet ingrediens (kun til lesing/bruk i oppskrifter)

    def unit(self, abbreviation: str) -> str:
        return self.units[abbreviation].id


def load_reference(actor: Actor) -> Reference:
    units = expect(actor.core.get("/api/user/units"), 200, list[Unit])
    unit_types = expect(actor.core.get("/api/user/unit-types"), 200, list[UnitType])
    ingredient_categories = actor.core.get("/api/user/ingredient-categories").json()
    recipe_categories = actor.core.get("/api/user/recipe-categories").json()
    nutrients = expect(actor.core.get("/api/user/nutrient-definitions"), 200, list[NutrientDefinition])
    ingredients = expect(actor.core.get("/api/user/ingredients"), 200, list[IngredientListItem])
    assert ingredient_categories and recipe_categories and ingredients, "seed-dataene mangler (kategorier/ingredienser)"
    return Reference(
        units={u.abbreviation: u for u in units},
        unit_type_ids={t.dimension: t.id for t in unit_types if t.is_system},
        ingredient_category_id=ingredient_categories[0]["id"],
        recipe_category_id=recipe_categories[0]["id"],
        nutrients=nutrients,
        official=ingredients[0],
    )


def ingredient_payload(ref: Reference, name: str, **overrides) -> dict:
    """Gyldig `IngredientRequest`: 100 kcal og to næringsstoffer per 100 g, og en porsjon (1 stk = 50 g)."""
    payload = {
        "name": name,
        "categoryId": ref.ingredient_category_id,
        "primaryUnitTypeId": ref.unit_type_ids["Weight"],
        "defaultUnitId": ref.unit("g"),
        "energyKcal": 100,
        "energyKj": 420,
        "isVerified": False,
        "allergenIds": [],
        "searchKeywordIds": [],
        "nutrientValues": [
            {"nutrientDefinitionId": ref.nutrients[0].id, "quantity": 10, "sourceId": None},
            {"nutrientDefinitionId": ref.nutrients[1].id, "quantity": 2.5, "sourceId": None},
        ],
        "portions": [{"unitId": ref.unit("stk"), "gramsPerPortion": 50}],
    }
    return {**payload, **overrides}


def recipe_payload(ref: Reference, title: str, ingredient_id: str | None = None, **overrides) -> dict:
    """Gyldig `RecipeRequest`: to steg (ett med timer på 20 min) og én ingrediensrad (2 stk)."""
    payload = {
        "title": title,
        "description": "Enkel hverdagsmiddag.",
        "categoryId": ref.recipe_category_id,
        "servings": 4,
        "steps": [{"description": "Kutt ingrediensene."}, {"description": "Kok i 20 minutter.", "timerMinutes": 20}],
        "ingredients": [{"ingredientId": ingredient_id or ref.official.id, "amount": 2, "unitId": ref.unit("stk")}],
    }
    return {**payload, **overrides}


def line(ref: Reference, *, ingredient_id: str | None = None, unconfirmed_id: str | None = None,
         amount: float | None = 1, unit: str = "g", note: str | None = None) -> dict:
    """Én ingrediensrad i en oppskrift."""
    row: dict = {"unitId": ref.unit(unit)}
    if ingredient_id:
        row["ingredientId"] = ingredient_id
    if unconfirmed_id:
        row["unconfirmedIngredientId"] = unconfirmed_id
    if amount is not None:
        row["amount"] = amount
    if note:
        row["note"] = note
    return row


def delete_or_raise(client: ApiClient, path: str, allowed: tuple[int, ...] = (204, 404)) -> None:
    """Sletting for opprydding: kaster ved uventet svar, slik at `Cleanup` prøver på nytt og til slutt melder feilen."""
    resp = client.delete(path)
    if resp.status_code not in allowed:
        raise AssertionError(describe(resp))
