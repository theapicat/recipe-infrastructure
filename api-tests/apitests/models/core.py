"""DTO-er for recipe-core-api (speiler entitetene i `Domain/`, som brukes direkte som API-modeller)."""
from __future__ import annotations

from .base import ApiModel


class UnitType(ApiModel):
    id: str
    name: str


class Unit(ApiModel):
    id: str
    name: str
    abbreviation: str
    unit_type_id: str
    base_unit_ratio: float


class Allergen(ApiModel):
    id: str
    name: str


class IngredientCategory(ApiModel):
    id: str
    name: str


class SearchKeyword(ApiModel):
    id: str
    name: str


class RecipeCategory(ApiModel):
    id: str
    name: str
