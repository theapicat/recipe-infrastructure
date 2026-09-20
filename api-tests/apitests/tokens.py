"""Hjelpere for å lese (ikke validere) claims i et JWT, kun til assertions i testene."""
from __future__ import annotations

import base64
import json


def claims_of(jwt: str) -> dict:
    payload = jwt.split(".")[1]
    payload += "=" * (-len(payload) % 4)
    return json.loads(base64.urlsafe_b64decode(payload))
