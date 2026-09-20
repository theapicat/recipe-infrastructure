"""Basisklasser for DTO-ene.

Begge er STRENGE (`extra="forbid"`): et felt API-et returnerer som DTO-en ikke kjenner, eller et felt DTO-en
krever som mangler, gir testfeil. Det er meningen: DTO-ene skal speile de ekte dataene, så endringer i API-et
oppdages her og ikke først i webappen.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class ApiModel(BaseModel):
    """JSON i camelCase (ASP.NET-standard)."""

    model_config = ConfigDict(extra="forbid", alias_generator=to_camel, populate_by_name=True)

    def to_json(self) -> dict:
        return self.model_dump(by_alias=True, mode="json")


class SnakeModel(BaseModel):
    """JSON i snake_case (OAuth2/OpenID Connect, styrt av protokollen)."""

    model_config = ConfigDict(extra="forbid")
