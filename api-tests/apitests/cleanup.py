"""Opprydding: registrerte slette-handlinger (LIFO) pluss en sweep som fjerner alt med testprefikset.

Alt testene oppretter har prefikset `apitest-`, så oppryddingen kan aldri treffe ekte data.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from .actors import Actor, admin_delete_user, admin_list_blacklist, admin_list_users, make_actor, password_login
from .catalogs import CATALOGS
from .config import TEST_PASSWORD, TEST_PREFIX
from .models.auth import TokenResponse
from .runtime import SETTINGS


@dataclass
class Cleanup:
    """Slette-handlinger registrert underveis, kjørt i omvendt rekkefølge (barn før foreldre).

    En handling som feiler (kaster) prøves på nytt i opptil tre runder: rekkefølgen er ikke alltid nok, for eksempel
    må en oppskrift slettes før ingrediensen den bruker, og godkjenning av en ubekreftet ingrediens flytter linjer."""

    _actions: list[tuple[str, Callable[[], None]]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def register(self, label: str, action: Callable[[], None]) -> None:
        self._actions.append((label, action))

    def run(self) -> None:
        pending = self._actions[::-1]
        self._actions = []
        failures: list[tuple[str, Callable[[], None], Exception]] = []
        for _ in range(3):
            failures = []
            for label, action in pending:
                try:
                    action()
                except Exception as exc:  # opprydding skal aldri stoppe på én feil
                    failures.append((label, action, exc))
            pending = [(label, action) for label, action, _ in failures]
            if not pending:
                break
        self.errors += [f"{label}: {exc}" for label, _, exc in failures]


@dataclass
class Leftovers:
    users: list[dict] = field(default_factory=list)
    blacklist: list[dict] = field(default_factory=list)
    catalog_rows: list[tuple[str, dict]] = field(default_factory=list)
    ingredients: list[dict] = field(default_factory=list)
    # Oppskrifter og ubekreftede ingredienser som tilhører testbrukere (Core rydder ikke når en konto slettes)
    user_items: list[tuple[str, str, dict]] = field(default_factory=list)  # (e-post, "recipes"|"unconfirmed-ingredients", rad)

    @property
    def count(self) -> int:
        return (len(self.users) + len(self.blacklist) + len(self.catalog_rows) + len(self.ingredients)
                + len(self.user_items))

    def describe(self) -> str:
        parts = [f"bruker {u['email']}" for u in self.users]
        parts += [f"svartelisteoppføring {b['pattern']}" for b in self.blacklist]
        parts += [f"{res}/{row['name']}" for res, row in self.catalog_rows]
        parts += [f"ingrediens {row['name']}" for row in self.ingredients]
        parts += [f"{kind} «{row.get('title') or row.get('name')}» ({email})" for email, kind, row in self.user_items]
        return ", ".join(parts)


def _user_actor(admin: Actor, email: str) -> Actor | None:
    """Logger inn som en (gjenværende) testbruker med det kjente testpassordet, for å rydde brukerens egne data."""
    resp = password_login(SETTINGS, admin.auth, email, TEST_PASSWORD)
    if resp.status_code != 200:
        return None
    return make_actor(SETTINGS, email, TokenResponse.model_validate(resp.json()), email=email)


def find_leftovers(admin: Actor) -> Leftovers:
    left = Leftovers()
    left.users = [u for u in admin_list_users(admin) if u["email"].lower().startswith(TEST_PREFIX)]
    left.blacklist = [b for b in admin_list_blacklist(admin) if b["pattern"].lower().startswith(TEST_PREFIX)]
    for spec in CATALOGS:
        resp = admin.core.get(spec.admin_path)
        if resp.status_code != 200:
            continue  # ingen tilgang til Core (kjent feil) — da har testene heller ikke kunnet opprette noe der
        left.catalog_rows += [(spec.resource, r) for r in resp.json() if r["name"].startswith(TEST_PREFIX)]
    resp = admin.core.get("/api/admin/ingredients", params={"name": TEST_PREFIX})
    if resp.status_code == 200:
        left.ingredients = [r for r in resp.json() if r["name"].startswith(TEST_PREFIX)]
    for user in left.users:  # bare mulig så lenge brukeren finnes (etter sletting er dataene utilgjengelige)
        actor = _user_actor(admin, user["email"])
        if actor is None:
            continue
        for kind in ("recipes", "unconfirmed-ingredients"):
            resp = actor.core.get(f"/api/user/{kind}")
            if resp.status_code == 200:
                left.user_items += [(user["email"], kind, row) for row in resp.json()]
    return left


def sweep(admin: Actor, left: Leftovers | None = None) -> Leftovers:
    """Sletter alt med testprefikset. Returnerer det som ble funnet (før sletting)."""
    left = left or find_leftovers(admin)
    actors: dict[str, Actor | None] = {}
    for kind in ("recipes", "unconfirmed-ingredients"):  # oppskrifter først: de bruker de ubekreftede ingrediensene
        for email, item_kind, row in left.user_items:
            if item_kind == kind:
                actor = actors.setdefault(email, _user_actor(admin, email))
                if actor is not None:
                    actor.core.delete(f"/api/user/{kind}/{row['id']}")
    for row in left.ingredients:
        admin.core.delete(f"/api/admin/ingredients/{row['id']}")
    for resource, row in left.catalog_rows:  # CATALOGS-rekkefølgen sørger for at units går før unit-types
        admin.core.delete(f"/api/admin/{resource}/{row['id']}")
    for entry in left.blacklist:
        admin.auth.delete(f"/api/auth/admin/blacklist/{entry['id']}")
    for user in left.users:
        admin_delete_user(admin, user["userId"])
    return left
