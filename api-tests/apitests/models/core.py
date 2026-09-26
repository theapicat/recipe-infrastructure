"""DTO-er for recipe-core-api (speiler entitetene i `Domain/`, som brukes direkte som API-modeller)."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from .base import ApiModel


UnitDimension = Literal["Weight", "Volume", "Count"]


class UnitType(ApiModel):
    """`name` er bare en etikett; `dimension` er det beregningene bruker."""

    id: str
    name: str
    dimension: UnitDimension
    is_system: bool
    usage_count: int


class Unit(ApiModel):
    id: str
    name: str
    abbreviation: str
    unit_type_id: str
    base_unit_ratio: float
    is_system: bool
    usage_count: int


class Allergen(ApiModel):
    id: str
    name: str
    is_system: bool
    usage_count: int


class IngredientCategory(ApiModel):
    id: str
    name: str
    is_system: bool
    usage_count: int


class SearchKeyword(ApiModel):
    id: str
    name: str
    is_system: bool
    usage_count: int


class RecipeCategory(ApiModel):
    id: str
    name: str
    is_system: bool
    usage_count: int


# ------------------------------------------------------------------------------------ næringsstoffer

class NutrientGroup(ApiModel):
    id: str
    name: str
    sort_order: int
    parent_group: "NutrientGroup | None"


class NutrientDefinition(ApiModel):
    """Skrivebeskyttet katalog med Matvaretabellens tekstkode som id (`Vit C`, `Fett`)."""

    id: str
    name: str
    unit_id: str
    unit: str
    unit_type_id: str
    decimal_precision: int
    group: NutrientGroup
    source_url: str | None
    sort_order: int


# ---------------------------------------------------------------------------------------- ingredienser

class IngredientListItem(ApiModel):
    """Lettvektsraden i søket (`GET /ingredients`)."""

    id: str
    name: str
    category_id: str
    primary_unit_type_id: str
    default_unit_id: str
    energy_kcal: float
    is_verified: bool
    is_official: bool
    created_at: datetime
    updated_at: datetime
    verified_at: datetime | None
    nutrient_value_count: int
    portion_count: int
    allergens_reviewed: bool
    usage_count: int
    variant_of_ingredient_id: str | None
    allergen_ids: list[str]
    search_keyword_ids: list[str]


class IngredientNutrientValue(ApiModel):
    id: str
    ingredient_id: str
    nutrient_definition_id: str
    quantity: float
    source_id: str | None


class IngredientPortion(ApiModel):
    id: str
    ingredient_id: str
    unit_id: str
    grams_per_portion: float


class Ingredient(ApiModel):
    id: str
    name: str
    category_id: str
    allergen_ids: list[str]
    primary_unit_type_id: str
    default_unit_id: str
    energy_kcal: float
    energy_kj: float | None
    edible_part_percent: float | None
    search_keyword_ids: list[str]
    source_id: str | None
    source_url: str | None
    variant_of_ingredient_id: str | None
    nutrient_values: list[IngredientNutrientValue]
    portions: list[IngredientPortion]
    is_verified: bool
    is_official: bool
    updated_at: datetime
    created_at: datetime
    allergens_reviewed: bool
    usage_count: int
    updated_by_user_id: str | None
    verified_at: datetime | None
    verified_by_user_id: str | None


ReviewStatus = Literal["NotRequested", "Pending", "Approved", "Merged", "Rejected"]


class UnconfirmedIngredient(ApiModel):
    id: str
    name: str
    created_by_user_id: str
    review_status: ReviewStatus
    rejection_reason: str | None
    reviewed_at: datetime | None
    resolved_ingredient_id: str | None
    created_at: datetime


# ---------------------------------------------------------------------------------------- oppskrifter

class RecipeIngredient(ApiModel):
    id: str
    recipe_id: str
    ingredient_id: str | None
    unconfirmed_ingredient_id: str | None
    amount: float
    unit_id: str
    note: str | None
    sort_order: int
    name: str | None


class RecipeStep(ApiModel):
    id: str
    recipe_id: str
    step_number: int
    description: str
    timer_minutes: int | None


class RecipeSource(ApiModel):
    type: Literal["Manual", "Scraped"]
    reference: str | None
    url: str | None
    is_edited_from_source: bool | None


class Recipe(ApiModel):
    id: str
    owner_user_id: str
    title: str
    description: str
    category_id: str
    cook_time_minutes: int
    servings: int
    image_url: str | None
    image_attribution: str | None
    is_favorite: bool
    ingredients: list[RecipeIngredient]
    steps: list[RecipeStep]
    source: RecipeSource
    created_at: datetime
    updated_at: datetime


class RecipeListItem(ApiModel):
    id: str
    title: str
    image_url: str | None
    category_id: str
    cook_time_minutes: int
    servings: int
    is_favorite: bool


class NutritionAmount(ApiModel):
    total: float
    per_serving: float


class RecipeNutrientTotal(ApiModel):
    nutrient_id: str
    total: float
    per_serving: float


class SkippedLine(ApiModel):
    recipe_ingredient_id: str
    name: str
    reason: Literal["ToTaste", "Unconfirmed", "NoConversion"]


class RecipeNutrition(ApiModel):
    recipe_id: str
    servings: int
    energy_kcal: NutritionAmount | None
    energy_kj: NutritionAmount | None
    nutrients: list[RecipeNutrientTotal]
    counted_ingredients: int
    total_ingredients: int
    skipped_lines: list[SkippedLine]
