"""Konfigurasjon for API-testene.

Alt kan overstyres med miljøvariabler eller en `api-tests/.env`-fil (se `.env.example`).
"""
from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = ROOT / "reports"

# Miljøer der det er trygt å opprette/endre/slette data og utløse e-post.
SAFE_ENVIRONMENTS = {"local", "test"}
LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}

# Alt testene oppretter får dette prefikset, slik at opprydding aldri kan treffe ekte data.
TEST_PREFIX = "apitest-"
# Reservert domene (RFC 2606): ingen ekte postkasse, og Mailpit fanger uansett alt i dev.
TEST_EMAIL_DOMAIN = "example.com"
# Oppfyller passordreglene (stor/liten bokstav, tall, spesialtegn, minst 8 tegn).
TEST_PASSWORD = "ApiTest#12345aB"
TEST_NEW_PASSWORD = "ApiTest#67890xY"


class ConfigError(RuntimeError):
    """Feil i testoppsettet (ikke i systemet som testes)."""


def _load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _admin_from_auth_repo() -> tuple[str | None, str | None]:
    """Leser dev-adminkontoen fra recipe-auth-api (samme kilde som IdentitySeeder bruker)."""
    api_dir = ROOT.parent.parent / "recipe-auth-api" / "API"
    for name in ("appsettings.Development.json", "appsettings.json"):
        path = api_dir / name
        if not path.is_file():
            continue
        admin = json.loads(path.read_text(encoding="utf-8-sig")).get("AdminUser") or {}
        if admin.get("Email") and admin.get("Password"):
            return admin["Email"], admin["Password"]
    return None, None


@dataclass(frozen=True)
class Settings:
    env: str
    gateway_url: str
    auth_url: str
    core_url: str
    admin_email: str
    admin_password: str
    client_id: str
    frontend_origin: str
    mailpit_url: str
    timeout: float
    run_id: str

    @property
    def mutating_allowed(self) -> bool:
        return self.env in SAFE_ENVIRONMENTS

    @property
    def auth_via_gateway(self) -> bool:
        return self.auth_url == self.gateway_url

    @property
    def core_via_gateway(self) -> bool:
        return self.core_url == self.gateway_url

    def test_email(self, tag: str) -> str:
        return f"{TEST_PREFIX}{self.run_id}-{tag}@{TEST_EMAIL_DOMAIN}"

    def test_name(self, tag: str) -> str:
        return f"{TEST_PREFIX}{self.run_id}-{tag}"

    def assert_safe_target(self) -> None:
        """Nektet å kjøre i env=local mot noe annet enn localhost."""
        if self.env != "local":
            return
        for label, url in (("gateway", self.gateway_url), ("auth", self.auth_url), ("core", self.core_url)):
            host = urlparse(url).hostname
            if host not in LOOPBACK_HOSTS:
                raise ConfigError(
                    f"API_TEST_ENV=local, men {label}-URL-en ({url}) peker ikke på localhost. "
                    "Bruk API_TEST_ENV=test hvis dette er et dedikert testmiljø."
                )


def load_settings() -> Settings:
    _load_dotenv(ROOT / ".env")
    env = os.environ.get("API_TEST_ENV", "local").strip().lower()
    gateway = os.environ.get("API_TEST_GATEWAY_URL", "http://localhost:5000").rstrip("/")

    email = os.environ.get("API_TEST_ADMIN_EMAIL")
    password = os.environ.get("API_TEST_ADMIN_PASSWORD")
    if not (email and password):
        found_email, found_password = _admin_from_auth_repo()
        email, password = email or found_email, password or found_password
    if not (email and password):
        raise ConfigError(
            "Fant ingen admin-konto. Sett API_TEST_ADMIN_EMAIL og API_TEST_ADMIN_PASSWORD "
            "(se .env.example), eller kjør fra en mappe der recipe-auth-api ligger ved siden av."
        )

    return Settings(
        env=env,
        gateway_url=gateway,
        auth_url=os.environ.get("API_TEST_AUTH_URL", gateway).rstrip("/"),
        core_url=os.environ.get("API_TEST_CORE_URL", gateway).rstrip("/"),
        admin_email=email,
        admin_password=password,
        client_id=os.environ.get("API_TEST_CLIENT_ID", "recipe-web-app"),
        frontend_origin=os.environ.get("API_TEST_FRONTEND_ORIGIN", "http://localhost:3000"),
        mailpit_url=os.environ.get("API_TEST_MAILPIT_URL", "http://localhost:8025"),
        timeout=float(os.environ.get("API_TEST_TIMEOUT", "15")),
        run_id=uuid.uuid4().hex[:8],
    )
