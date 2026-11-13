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
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
MAX_RETRY_AFTER_SECONDS = 30
MAX_SESSION_RETRY_AFTER_SECONDS = 60


class SourceError(RuntimeError):
    """Bir veri kaynağı yanıt vermedi ya da beklenmedik bir biçimde yanıt verdi."""


class _BoundedRetry(Retry):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._retry_after_budget = [MAX_SESSION_RETRY_AFTER_SECONDS]

    def new(self, **kwargs):
        retry = super().new(**kwargs)
        retry._retry_after_budget = self._retry_after_budget
        return retry

    def get_retry_after(self, response):
        delay = super().get_retry_after(response)
        return min(delay, MAX_RETRY_AFTER_SECONDS) if delay is not None else None

    def sleep_for_retry(self, response):
        delay = self.get_retry_after(response)
        if not delay:
            return False
        if delay > self._retry_after_budget[0]:
            raise SourceError("HTTP: yeniden deneme bekleme sınırı aşıldı")
        self._retry_after_budget[0] -= delay
        time.sleep(delay)
        return True


def user_agent() -> str:
    repository = os.environ.get("GITHUB_REPOSITORY")
    contact = f"; +https://github.com/{repository}" if repository else ""
    return f"club-calendar/1.0 (fan-made match calendar, one run per day{contact})"


def new_session() -> requests.Session:
    retry = _BoundedRetry(
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
        response = session.get(url, params=params, timeout=TIMEOUT, headers={"Accept": accept}, stream=True)
        try:
            response.raise_for_status()
            chunks = []
            size = 0
            for chunk in response.iter_content(chunk_size=65536):
                size += len(chunk)
                if size > MAX_RESPONSE_BYTES:
                    raise SourceError(f"{url} yanıtı {MAX_RESPONSE_BYTES} bayt sınırını aştı")
                chunks.append(chunk)
            response._content = b"".join(chunks)
        finally:
            response.close()
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
