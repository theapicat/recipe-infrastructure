"""Gateway: helsesjekker, rutepolicyer (anonym avvises), spoofede identitets-headere og CORS."""
from __future__ import annotations

import uuid

import pytest

from apitests.actors import Actor
from apitests.config import Settings
from apitests.http import describe, expect
from apitests.models.common import HealthResponse
from apitests.tokens import claims_of


def test_gateway_health(anon: Actor):
    health = expect(anon.gateway.get("/api/gateway/health"), 200, HealthResponse)
    assert health.status == "Healthy"
    assert health.service == "recipe-gateway-api"


def test_core_health_is_public(anon: Actor):
    health = expect(anon.core.get("/api/public/health"), 200, HealthResponse)
    assert health.status == "Healthy"
    assert health.service == "recipe-core-api"


def test_auth_health_is_public(anon: Actor):
    assert expect(anon.auth.get("/api/auth/health"), 200, HealthResponse).status == "Healthy"


def test_unknown_route_is_404(anon: Actor):
    resp = anon.gateway.get(f"/api/finnes-ikke-{uuid.uuid4().hex[:6]}")
    assert resp.status_code == 404, describe(resp)


@pytest.mark.parametrize("path", ["/api/user/units", "/api/admin/units", "/hubs/anything"])
def test_protected_gateway_routes_reject_anonymous(anon: Actor, path: str):
    resp = anon.gateway.get(path)
    assert resp.status_code == 401, f"{path}: {describe(resp)}"


@pytest.mark.parametrize("path", ["/api/user/units", "/api/admin/units"])
def test_spoofed_identity_headers_do_not_authenticate(anon: Actor, path: str):
    """Klienten kan aldri selv erklære seg som bruker/admin: gatewayen fjerner X-User-*-headerne."""
    resp = anon.gateway.get(path, headers={"X-User-Id": str(uuid.uuid4()), "X-User-Roles": "admin,Admin"})
    assert resp.status_code == 401, describe(resp)


@pytest.mark.mutating
def test_user_cannot_escalate_with_spoofed_role_header(user: Actor, core_ready):
    resp = user.gateway.get("/api/admin/units", headers={"X-User-Id": user.user_id, "X-User-Roles": "admin,Admin"})
    assert resp.status_code in (401, 403), describe(resp)


def test_cors_allows_the_frontend_origin(anon: Actor, settings: Settings):
    resp = anon.gateway.request(
        "OPTIONS", "/api/auth/health",
        headers={"Origin": settings.frontend_origin, "Access-Control-Request-Method": "GET"},
    )
    assert resp.headers.get("Access-Control-Allow-Origin") == settings.frontend_origin, describe(resp)
    assert resp.headers.get("Access-Control-Allow-Credentials") == "true"


def test_cors_does_not_allow_other_origins(anon: Actor):
    resp = anon.gateway.request(
        "OPTIONS", "/api/auth/health",
        headers={"Origin": "http://evil.example", "Access-Control-Request-Method": "GET"},
    )
    assert "Access-Control-Allow-Origin" not in resp.headers, describe(resp)


def test_issued_token_is_accepted_by_gateway_and_core(admin: Actor):
    """Selve kontrakten mellom Auth API og resten: et token fra /connect/token må godtas av gateway og Core."""
    resp = admin.core.get("/api/user/unit-types")
    issuer = claims_of(admin.tokens.access_token).get("iss")
    assert resp.status_code == 200, (
        f"tokenets issuer er {issuer!r}, men Core/gateway avviste det: {describe(resp)} "
        f"www-authenticate={resp.headers.get('www-authenticate')!r}"
    )
