"""Testler için ortak yardımcılar: gerçek yanıtlardan küçültülmüş örnekler ve sahte HTTP oturumu."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import requests

from club_calendar.club import get_club

BESIKTAS = get_club("besiktas")  # gerçek yanıt örnekleri Beşiktaş'a aittir
FIXTURES = Path(__file__).parent / "fixtures"
EMPTY_PAGE = "<!doctype html><html><head><title>boş</title></head><body></body></html>"


def fixture_text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def fixture_json(name: str) -> Any:
    return json.loads(fixture_text(name))


class FakeResponse:
    def __init__(self, payload: Any) -> None:
        self._payload = payload
        self.encoding: str | None = None

    def raise_for_status(self) -> None:
        return None

    def json(self) -> Any:
        if isinstance(self._payload, str):
            raise ValueError("JSON değil")
        return self._payload

    @property
    def text(self) -> str:
        return self._payload if isinstance(self._payload, str) else json.dumps(self._payload)


class FakeSession:
    """`requests.Session` yerine geçer; her isteği `route(url, params)` fonksiyonuna yönlendirir.

    `route` None döndürürse sunucu 404 vermiş gibi davranılır.
    """

    def __init__(self, route: Callable[[str, dict[str, Any]], Any]) -> None:
        self.route = route
        self.requests: list[tuple[str, dict[str, Any]]] = []

    def get(self, url: str, params: dict[str, Any] | None = None, timeout: Any = None, headers: Any = None) -> FakeResponse:
        params = dict(params or {})
        self.requests.append((url, params))
        payload = self.route(url, params)
        if payload is None:
            response = requests.Response()
            response.status_code = 404
            response.url = url
            raise requests.HTTPError(f"404 Not Found for url: {url}", response=response)
        return FakeResponse(payload)
