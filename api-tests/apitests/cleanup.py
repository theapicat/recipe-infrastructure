"""Opprydding: registrerte slette-handlinger (LIFO) pluss en sweep som fjerner alt med testprefikset.

Alt testene oppretter har prefikset `apitest-`, så oppryddingen kan aldri treffe ekte data.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from .actors import Actor, admin_delete_user, admin_list_blacklist, admin_list_users
from .catalogs import CATALOGS
from .config import TEST_PREFIX


@dataclass
class Cleanup:
    """Slette-handlinger registrert underveis, kjørt i omvendt rekkefølge (barn før foreldre)."""

    _actions: list[tuple[str, Callable[[], None]]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def register(self, label: str, action: Callable[[], None]) -> None:
        self._actions.append((label, action))

    def run(self) -> None:
        while self._actions:
            label, action = self._actions.pop()
            try:
                action()
            except Exception as exc:  # opprydding skal aldri stoppe på én feil
                self.errors.append(f"{label}: {exc}")


@dataclass
class Leftovers:
    users: list[dict] = field(default_factory=list)
    blacklist: list[dict] = field(default_factory=list)
    catalog_rows: list[tuple[str, dict]] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.users) + len(self.blacklist) + len(self.catalog_rows)

    def describe(self) -> str:
        parts = [f"bruker {u['email']}" for u in self.users]
        parts += [f"svartelisteoppføring {b['pattern']}" for b in self.blacklist]
        parts += [f"{res}/{row['name']}" for res, row in self.catalog_rows]
        return ", ".join(parts)


def find_leftovers(admin: Actor) -> Leftovers:
    left = Leftovers()
    left.users = [u for u in admin_list_users(admin) if u["email"].lower().startswith(TEST_PREFIX)]
    left.blacklist = [b for b in admin_list_blacklist(admin) if b["pattern"].lower().startswith(TEST_PREFIX)]
    for spec in CATALOGS:
        resp = admin.core.get(spec.admin_path)
        if resp.status_code != 200:
            continue  # ingen tilgang til Core (kjent feil) — da har testene heller ikke kunnet opprette noe der
        left.catalog_rows += [(spec.resource, r) for r in resp.json() if r["name"].startswith(TEST_PREFIX)]
    return left


def sweep(admin: Actor, left: Leftovers | None = None) -> Leftovers:
    """Sletter alt med testprefikset. Returnerer det som ble funnet (før sletting)."""
    left = left or find_leftovers(admin)
    for resource, row in left.catalog_rows:  # CATALOGS-rekkefølgen sørger for at units går før unit-types
        admin.core.delete(f"/api/admin/{resource}/{row['id']}")
    for entry in left.blacklist:
        admin.auth.delete(f"/api/auth/admin/blacklist/{entry['id']}")
    for user in left.users:
        admin_delete_user(admin, user["userId"])
    return left
