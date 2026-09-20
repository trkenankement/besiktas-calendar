"""Konsol çıktısı: GitHub Actions'ta ::warning:: / ::error:: ek açıklamaları, yerelde düz metin."""

from __future__ import annotations

import os


def _in_actions() -> bool:
    return os.environ.get("GITHUB_ACTIONS") == "true"


def log(message: str) -> None:
    print(message, flush=True)


def warn(message: str) -> None:
    print(f"::warning::{message}" if _in_actions() else f"UYARI: {message}", flush=True)


def error(message: str) -> None:
    print(f"::error::{message}" if _in_actions() else f"HATA: {message}", flush=True)
