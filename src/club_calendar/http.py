"""Ortak HTTP oturumu: kendini tanıtan User-Agent, otomatik yeniden deneme, kibar bekleme."""

from __future__ import annotations

import os
import time
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

TIMEOUT = (10, 45)  # (bağlanma, okuma) saniye
REQUEST_PAUSE_SECONDS = 0.15  # kaynak sitelere art arda yüklenmemek için


class SourceError(RuntimeError):
    """Bir veri kaynağı yanıt vermedi ya da beklenmedik bir biçimde yanıt verdi."""


def user_agent() -> str:
    repository = os.environ.get("GITHUB_REPOSITORY")
    contact = f"; +https://github.com/{repository}" if repository else ""
    return f"club-calendar/1.0 (fan-made match calendar, one run per day{contact})"


def new_session() -> requests.Session:
    retry = Retry(
        total=4,
        backoff_factor=2.0,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        respect_retry_after_header=True,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session = requests.Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update(
        {"User-Agent": user_agent(), "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.5"}
    )
    return session


def _get(session: requests.Session, url: str, params: dict[str, Any], accept: str):
    time.sleep(REQUEST_PAUSE_SECONDS)
    try:
        response = session.get(url, params=params, timeout=TIMEOUT, headers={"Accept": accept})
        response.raise_for_status()
    except requests.RequestException as exc:
        raise SourceError(f"{url} alınamadı: {exc}") from exc
    return response


def get_json(session: requests.Session, url: str, **params: Any) -> Any:
    response = _get(session, url, params, "application/json")
    try:
        return response.json()
    except ValueError as exc:
        raise SourceError(f"{url} geçerli JSON döndürmedi") from exc


def get_html(session: requests.Session, url: str, *, encoding: str | None = None, **params: Any) -> str:
    response = _get(session, url, params, "text/html,application/xhtml+xml")
    if encoding:
        response.encoding = encoding
    return response.text
