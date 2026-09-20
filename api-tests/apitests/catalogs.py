"""Beskrivelse av Core sine seks admin-styrte katalogressurser, brukt av tilgangsmatrisen og CRUD-testene."""
from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from typing import Callable

from .models.base import ApiModel
from .models.core import Allergen, IngredientCategory, RecipeCategory, SearchKeyword, Unit, UnitType


@dataclass(frozen=True)
class CatalogSpec:
    resource: str
    model: type[ApiModel]
    build: Callable[[str, str | None], dict]  # (navn, parent_id) -> payload uten id (serveren tildeler id)
    modify: Callable[[dict], dict]  # payload -> endret payload (brukes i PUT)
    parent: str | None = None  # ressursen denne peker på (fremmednøkkel), som må finnes først

    @property
    def user_path(self) -> str:
        return f"/api/user/{self.resource}"

    @property
    def admin_path(self) -> str:
        return f"/api/admin/{self.resource}"


def new_id() -> str:
    return str(uuid.uuid4())


def _named(name: str, parent_id: str | None = None) -> dict:
    return {"name": name}


def _rename(payload: dict) -> dict:
    return {**payload, "name": payload["name"] + "-endret"}


def _unit(name: str, parent_id: str | None) -> dict:
    # Forkortelsen er også unik, og radene slettes først ved slutten av kjøringen: den utledes derfor fra navnet
    abbreviation = "a" + hashlib.sha1(name.encode()).hexdigest()[:6]
    return {"name": name, "abbreviation": abbreviation, "unitTypeId": parent_id, "baseUnitRatio": 1.5}


def _modify_unit(payload: dict) -> dict:
    return {**payload, "name": payload["name"] + "-endret", "abbreviation": payload["abbreviation"] + "x", "baseUnitRatio": 2.0}


# Rekkefølgen er viktig for opprydding: rader som peker på andre (units) må slettes før det de peker på (unit-types).
CATALOGS: list[CatalogSpec] = [
    CatalogSpec("units", Unit, _unit, _modify_unit, parent="unit-types"),
    CatalogSpec("unit-types", UnitType, _named, _rename),
    CatalogSpec("allergens", Allergen, _named, _rename),
    CatalogSpec("ingredient-categories", IngredientCategory, _named, _rename),
    CatalogSpec("search-keywords", SearchKeyword, _named, _rename),
    CatalogSpec("recipe-categories", RecipeCategory, _named, _rename),
]

BY_RESOURCE = {spec.resource: spec for spec in CATALOGS}
