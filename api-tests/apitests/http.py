"""Tynn HTTP-klient og hjelpere for å sjekke svar mot DTO-er."""
from __future__ import annotations

from typing import Any

import requests
from pydantic import TypeAdapter, ValidationError


class ApiClient:
    """Én rolle (anonym/bruker/admin) mot én base-URL. Følger aldri redirects automatisk."""

    def __init__(self, base_url: str, *, timeout: float, token: str | None = None, label: str = "anon") -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.token = token
        self.label = label
        self._session = requests.Session()

    def with_token(self, token: str | None, label: str) -> "ApiClient":
        return ApiClient(self.base_url, timeout=self.timeout, token=token, label=label)

    def request(self, method: str, path: str, *, headers: dict[str, str] | None = None, **kwargs: Any) -> requests.Response:
        merged = dict(headers or {})
        if self.token and "Authorization" not in merged:
            merged["Authorization"] = f"Bearer {self.token}"
        kwargs.setdefault("allow_redirects", False)
        return self._session.request(method, self.base_url + path, headers=merged, timeout=self.timeout, **kwargs)

    def get(self, path: str, **kw: Any) -> requests.Response:
        return self.request("GET", path, **kw)

    def post(self, path: str, **kw: Any) -> requests.Response:
        return self.request("POST", path, **kw)

    def put(self, path: str, **kw: Any) -> requests.Response:
        return self.request("PUT", path, **kw)

    def delete(self, path: str, **kw: Any) -> requests.Response:
        return self.request("DELETE", path, **kw)


def describe(resp: requests.Response) -> str:
    return f"{resp.request.method} {resp.request.url} -> {resp.status_code} {resp.text[:400]!r}"


def parse(resp: requests.Response, model: Any) -> Any:
    """Validerer hele svaret mot en (streng) DTO, eller `list[Dto]`. Ukjente/manglende felt = feil."""
    try:
        return TypeAdapter(model).validate_json(resp.content)
    except ValidationError as exc:
        raise AssertionError(f"Svaret matcher ikke DTO {model}:\n{exc}\n{describe(resp)}") from exc


def expect(resp: requests.Response, status: int | tuple[int, ...] | set[int], model: Any = None) -> Any:
    """Sjekker statuskode (evt. flere gyldige) og validerer valgfritt kroppen mot en DTO."""
    allowed = {status} if isinstance(status, int) else set(status)
    assert resp.status_code in allowed, f"forventet {sorted(allowed)}, fikk {describe(resp)}"
    return parse(resp, model) if model is not None else None
