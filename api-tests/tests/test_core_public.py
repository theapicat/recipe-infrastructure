"""Core API: de offentlige (anonyme) endepunktene. Kontaktskjemaet MÅ virke uten innlogging."""
from __future__ import annotations

import pytest

from apitests.actors import Actor
from apitests.config import Settings
from apitests.http import describe

pytestmark = [pytest.mark.emails]

# Anonym besøkende: ingen header, og «Bearer undefined» (det webappen sender når sesjonen mangler).
ANONYMOUS_HEADERS = {"ingen Authorization-header": {}, "Bearer undefined": {"Authorization": "Bearer undefined"}}


def _payload(settings: Settings, tag: str) -> dict:
    return {
        "name": "Api Test",
        "email": settings.test_email(tag),
        "subject": settings.test_name(f"kontakt-{tag}"),
        "message": "Hei! Dette er en automatisk melding fra API-testene.",
    }


@pytest.mark.parametrize("headers", ANONYMOUS_HEADERS.values(), ids=ANONYMOUS_HEADERS.keys())
def test_contact_form_works_for_users_who_are_not_signed_in(anon: Actor, settings: Settings, headers):
    payload = _payload(settings, "anonym-" + ("token" if headers else "uten"))
    resp = anon.gateway.post("/api/public/contact-form", json=payload, headers=headers)
    assert resp.status_code == 200, describe(resp)
    assert resp.text.strip(), "forventet en bekreftelsestekst"


@pytest.mark.mutating
def test_contact_form_also_works_for_signed_in_users(user: Actor, settings: Settings):
    payload = _payload(settings, "innlogget")
    resp = user.gateway.post("/api/public/contact-form", json=payload)
    assert resp.status_code == 200, describe(resp)
