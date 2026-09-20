"""Core API: `GET /api/user/recipes/{id}/nutrition`, næring regnet ut på forespørsel fra dagens ingrediensdata.

Testene lager egne ingredienser med kjente verdier (per 100 g spiselig del) og sjekker regnestykket i dokumentasjonen:
mengde til gram (egen porsjon, vekt minus uspiselig del, volum via porsjonens vekt), totalt og per porsjon, at bare stoffer
med verdi over 0 kommer med, og at linjer som ikke kan regnes rapporteres med årsak.
"""
from __future__ import annotations

import pytest

from apitests.actors import Actor
from apitests.core_data import Reference, ingredient_payload, line
from apitests.http import expect
from apitests.models.core import RecipeNutrition

pytestmark = pytest.mark.mutating  # oppretter brukere, ingredienser og oppskrifter

approx = lambda value: pytest.approx(value, rel=1e-3, abs=1e-3)  # noqa: E731  (verdiene er veiledende og avrundet av serveren)


def nutrition(actor: Actor, recipe_id: str) -> RecipeNutrition:
    return expect(actor.core.get(f"/api/user/recipes/{recipe_id}/nutrition"), 200, RecipeNutrition)


def _totals(result: RecipeNutrition) -> dict[str, float]:
    return {n.nutrient_id: n.total for n in result.nutrients}


@pytest.fixture
def food(make_ingredient, ref: Reference):
    """100 kcal, 420 kJ, næringsstoff A = 10 og B = 2,5 per 100 g (C = 0 skal ikke komme med), 1 stk = 50 g."""
    a, b, c = (n.id for n in ref.nutrients[:3])
    return make_ingredient("naering", nutrientValues=[
        {"nutrientDefinitionId": a, "quantity": 10}, {"nutrientDefinitionId": b, "quantity": 2.5}, {"nutrientDefinitionId": c, "quantity": 0}])


def test_nutrition_is_total_and_per_serving(alice: Actor, ref: Reference, food, make_recipe):
    """200 g av 100 kcal/100 g er 200 kcal, og med fire porsjoner 50 kcal per porsjon."""
    recipe = make_recipe(alice, "naering", food.id, ingredients=[line(ref, ingredient_id=food.id, amount=200, unit="g")], servings=4)
    result = nutrition(alice, recipe.id)

    assert (result.recipe_id, result.servings) == (recipe.id, 4)
    assert (result.energy_kcal.total, result.energy_kcal.per_serving) == (approx(200), approx(50))
    assert (result.energy_kj.total, result.energy_kj.per_serving) == (approx(840), approx(210))
    a, b, c = (n.id for n in ref.nutrients[:3])
    assert {n.nutrient_id: (n.total, n.per_serving) for n in result.nutrients} == {a: (approx(20), approx(5)), b: (approx(5), approx(1.25))}, \
        "bare stoffer med verdi over 0 kommer med (C har 0 og skal utelates)"
    assert (result.counted_ingredients, result.total_ingredients, result.skipped_lines) == (1, 1, [])


def test_nutrients_come_in_the_order_of_the_catalog(alice: Actor, ref: Reference, make_ingredient, make_recipe):
    a, b, c = ref.nutrients[:3]
    rich = make_ingredient("rekkefolge", nutrientValues=[  # sendt i omvendt rekkefølge
        {"nutrientDefinitionId": c.id, "quantity": 1}, {"nutrientDefinitionId": b.id, "quantity": 1}, {"nutrientDefinitionId": a.id, "quantity": 1}])
    recipe = make_recipe(alice, "rekkefolge", rich.id, ingredients=[line(ref, ingredient_id=rich.id, amount=100)])
    assert [n.nutrient_id for n in nutrition(alice, recipe.id).nutrients] == [a.id, b.id, c.id]


def test_per_serving_follows_the_servings_but_the_total_does_not(alice: Actor, ref: Reference, food, make_recipe):
    recipe = make_recipe(alice, "porsjoner", food.id, ingredients=[line(ref, ingredient_id=food.id, amount=200)], servings=4)
    before = nutrition(alice, recipe.id)
    body = {"title": recipe.title, "description": recipe.description, "categoryId": recipe.category_id, "servings": 8,
            "steps": [{"description": s.description} for s in recipe.steps],
            "ingredients": [line(ref, ingredient_id=food.id, amount=200)]}
    assert alice.core.put(f"/api/user/recipes/{recipe.id}", json=body).status_code == 200
    after = nutrition(alice, recipe.id)
    assert after.servings == 8 and after.energy_kcal.total == approx(before.energy_kcal.total)
    assert after.energy_kcal.per_serving == approx(before.energy_kcal.per_serving / 2)


def test_several_lines_are_summed(alice: Actor, ref: Reference, food, make_ingredient, make_recipe):
    other = make_ingredient("summert", energyKcal=300)
    recipe = make_recipe(alice, "sum", food.id, ingredients=[
        line(ref, ingredient_id=food.id, amount=100), line(ref, ingredient_id=other.id, amount=50)], servings=1)
    result = nutrition(alice, recipe.id)
    assert result.energy_kcal.total == approx(100 + 150) and (result.counted_ingredients, result.total_ingredients) == (2, 2)


# ------------------------------------------------------------------------------------- fra linje til gram

def test_an_own_portion_is_used_without_deducting_the_inedible_part(alice: Actor, ref: Reference, make_ingredient, make_recipe):
    """1 stk = 50 g er allerede vekt av spiselig del, selv om 50 % av ingrediensen er uspiselig."""
    half_edible = make_ingredient("porsjon", energyKcal=200, ediblePartPercent=50)
    recipe = make_recipe(alice, "porsjon", half_edible.id, ingredients=[line(ref, ingredient_id=half_edible.id, amount=2, unit="stk")])
    assert nutrition(alice, recipe.id).energy_kcal.total == approx(200), "2 stk = 100 g spiselig = 200 kcal"


def test_weight_units_lose_the_inedible_part(alice: Actor, ref: Reference, make_ingredient, make_recipe):
    """500 g innkjøpt vekt med 50 % spiselig del er 250 g å regne med."""
    half_edible = make_ingredient("uspiselig", energyKcal=200, ediblePartPercent=50)
    recipe = make_recipe(alice, "uspiselig", half_edible.id, ingredients=[line(ref, ingredient_id=half_edible.id, amount=500, unit="g")])
    assert nutrition(alice, recipe.id).energy_kcal.total == approx(500)  # 250 g * 2 kcal/g


def test_weight_units_are_converted_with_the_unit_ratio(alice: Actor, ref: Reference, food, make_recipe):
    kg = ref.units["kg"]
    recipe = make_recipe(alice, "kilo", food.id, ingredients=[line(ref, ingredient_id=food.id, amount=0.5, unit="kg")])
    assert nutrition(alice, recipe.id).energy_kcal.total == approx(100 * 0.5 * kg.base_unit_ratio / 100)


def test_volume_uses_the_weight_of_the_ingredients_volume_portion(alice: Actor, ref: Reference, make_ingredient, make_recipe):
    """Ingrediensen har 1 dl = 90 g. En egen porsjon for enheten brukes direkte, og andre volumenheter skaleres via den."""
    dl, ss = ref.units["dl"], ref.units["ss"]
    flour = make_ingredient("volum", portions=[{"unitId": dl.id, "gramsPerPortion": 90}])
    recipe = make_recipe(alice, "volum", flour.id, ingredients=[
        line(ref, ingredient_id=flour.id, amount=2, unit="dl"), line(ref, ingredient_id=flour.id, amount=2, unit="ss")])
    result = nutrition(alice, recipe.id)
    grams_dl = 2 * 90
    grams_ss = 2 * ss.base_unit_ratio * (90 / dl.base_unit_ratio)  # gram per ml fra dl-porsjonen
    assert result.energy_kcal.total == approx(grams_dl + grams_ss)  # 100 kcal per 100 g
    assert result.skipped_lines == [] and result.counted_ingredients == 2


# ---------------------------------------------------------------------------------- linjer som hoppes over

def test_lines_that_cannot_be_counted_are_reported_with_a_reason(
        alice: Actor, ref: Reference, food, make_unconfirmed, make_recipe):
    own = make_unconfirmed(alice, "uten-naering")
    recipe = make_recipe(alice, "hoppet-over", food.id, ingredients=[
        line(ref, ingredient_id=food.id, amount=100, unit="g"),          # telles
        line(ref, ingredient_id=food.id, amount=None, unit="g"),         # etter smak
        line(ref, unconfirmed_id=own.id, amount=100, unit="g"),          # ubekreftet: ingen næringsdata
        line(ref, ingredient_id=food.id, amount=1, unit="dl")])          # volum uten volumporsjon: kan ikke omregnes
    result = nutrition(alice, recipe.id)

    assert (result.counted_ingredients, result.total_ingredients) == (1, 4)
    skipped = {(s.name, s.reason) for s in result.skipped_lines}
    assert skipped == {(food.name, "ToTaste"), (own.name, "Unconfirmed"), (food.name, "NoConversion")}
    by_id = {i.id for i in recipe.ingredients}
    assert {s.recipe_ingredient_id for s in result.skipped_lines} <= by_id, "hver hoppet linje peker på en linje i oppskriften"
    assert result.energy_kcal.total == approx(100), "bare den tellende linjen bidrar"


def test_a_recipe_with_nothing_to_count_has_no_totals(alice: Actor, ref: Reference, food, make_recipe):
    """Bare «etter smak»: ingen energi og ingen stoffer (null, ikke 0), og linjen er rapportert som hoppet over."""
    recipe = make_recipe(alice, "ingenting", food.id, ingredients=[line(ref, ingredient_id=food.id, amount=None)])
    result = nutrition(alice, recipe.id)
    assert result.energy_kcal is None and result.energy_kj is None and result.nutrients == []
    assert (result.counted_ingredients, result.total_ingredients) == (0, 1)
    assert [s.reason for s in result.skipped_lines] == ["ToTaste"]


# ------------------------------------------------------------------------------------- aldri utdatert

def test_nutrition_follows_changes_to_the_ingredient(admin: Actor, alice: Actor, ref: Reference, food, make_recipe):
    """Næringen lagres ikke i oppskriften: når admin endrer ingrediensen, gir neste kall nye tall."""
    recipe = make_recipe(alice, "aldri-utdatert", food.id, ingredients=[line(ref, ingredient_id=food.id, amount=100)])
    assert nutrition(alice, recipe.id).energy_kcal.total == approx(100)
    change = ingredient_payload(ref, food.name, energyKcal=300)
    assert admin.core.put(f"/api/admin/ingredients/{food.id}", json=change).status_code == 200
    assert nutrition(alice, recipe.id).energy_kcal.total == approx(300)


def test_an_approved_ingredient_starts_counting_when_it_gets_nutrition_data(
        alice: Actor, ref: Reference, make_unconfirmed, make_recipe, approve):
    own = make_unconfirmed(alice, "faar-data", request_review=True)
    recipe = make_recipe(alice, "faar-data", ingredients=[line(ref, unconfirmed_id=own.id, amount=100, unit="g")])
    assert [s.reason for s in nutrition(alice, recipe.id).skipped_lines] == ["Unconfirmed"]
    approve(own, energyKcal=120)
    result = nutrition(alice, recipe.id)
    assert result.skipped_lines == [] and result.counted_ingredients == 1
    assert result.energy_kcal.total == approx(120), "linjen er flyttet til den offisielle ingrediensen og regnes nå med"
