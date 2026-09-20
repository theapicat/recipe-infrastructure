"""Delt, innlastet konfigurasjon for hele testkjøringen (konfigurasjonen leses én gang, med én kjøre-ID)."""
from __future__ import annotations

from .config import load_settings

SETTINGS = load_settings()
