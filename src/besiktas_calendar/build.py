"""Tüm kaynaklardan maçları toplar, doğrular ve çıktı klasörüne (docs/) yazar."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterable

import requests

from . import ics, site
from .feeds import FEEDS
from .http import SourceError, new_session
from .models import BASKETBALL, FOOTBALL, SPORT_LABELS, TURKEY_TZ, Match
from .providers import PROVIDERS, Provider

MIN_MATCHES_PER_SPORT = 5  # bunun altı, kaynakların ciddi biçimde bozulduğu anlamına gelir


@dataclass
class Outcome:
    provider: Provider
    matches: list[Match]
    error: str | None = None


def _in_actions() -> bool:
    return os.environ.get("GITHUB_ACTIONS") == "true"


def log(message: str) -> None:
    print(message, flush=True)


def warn(message: str) -> None:
    print(f"::warning::{message}" if _in_actions() else f"UYARI: {message}", flush=True)


def error(message: str) -> None:
    print(f"::error::{message}" if _in_actions() else f"HATA: {message}", flush=True)


def collect(providers: Iterable[Provider], session: requests.Session, today: date) -> list[Outcome]:
    outcomes: list[Outcome] = []
    for provider in providers:
        try:
            matches = provider.fetch(session, today)
            if len(matches) < provider.min_matches:
                raise SourceError(
                    f"beklenenden az maç bulundu ({len(matches)} < {provider.min_matches}); "
                    "kaynak sayfanın yapısı değişmiş olabilir"
                )
        except Exception as exc:  # noqa: BLE001 - bir kaynağın hatası diğerlerinin raporlanmasını engellemesin
            outcomes.append(Outcome(provider, [], f"{type(exc).__name__}: {exc}"))
        else:
            outcomes.append(Outcome(provider, matches))
    return outcomes


def unique(matches: Iterable[Match]) -> list[Match]:
    by_uid: dict[str, Match] = {}
    for match in matches:
        by_uid.setdefault(match.uid, match)
    return sorted(by_uid.values(), key=lambda m: m.sort_key)


def coverage_problems(matches: list[Match]) -> list[str]:
    problems = []
    for sport in (FOOTBALL, BASKETBALL):
        count = sum(1 for m in matches if m.sport == sport)
        if count < MIN_MATCHES_PER_SPORT:
            problems.append(f"{SPORT_LABELS[sport]} için yalnızca {count} maç bulundu (en az {MIN_MATCHES_PER_SPORT} bekleniyor)")
    return problems


def write_outputs(out_dir: Path, matches: list[Match], now: datetime) -> dict[str, bool]:
    """Dosyaları yazar; yalnızca gerçekten değişenler için True döndürür."""
    out_dir.mkdir(parents=True, exist_ok=True)
    changed: dict[str, bool] = {}
    for feed in FEEDS:
        content = ics.render_calendar(
            feed.select(matches), feed.calendar_name, feed.description, stamp=now.astimezone(timezone.utc)
        )
        changed[feed.filename] = ics.write_if_changed(out_dir / feed.filename, content)
    changed["index.html"] = ics.write_if_changed(out_dir / "index.html", site.render_index(matches, now), ignore_prefixes=())
    # Son kontrol zamanı her çalışmada değişir; bu yüzden git'te izlenmez (.gitignore) ama siteye girer.
    (out_dir / "last_check.txt").write_text(now.strftime("%d.%m.%Y %H:%M (TSİ)") + "\n", encoding="utf-8")
    return changed


def write_step_summary(outcomes: list[Outcome], matches: list[Match]) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    lines = ["### Beşiktaş takvimi", "", "| Kaynak | Durum | Maç |", "| --- | --- | ---: |"]
    for outcome in outcomes:
        status = "✅" if outcome.error is None else ("❌" if outcome.provider.required else "⚠️")
        lines.append(f"| {outcome.provider.name} | {status} | {len(outcome.matches)} |")
    football = sum(1 for m in matches if m.sport == FOOTBALL)
    lines += ["", f"Toplam: **{football}** futbol, **{len(matches) - football}** basketbol maçı."]
    with open(path, "a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def run(out_dir: Path, *, providers: Iterable[Provider] = PROVIDERS, session: requests.Session | None = None, now: datetime | None = None) -> int:
    now = now or datetime.now(TURKEY_TZ)
    outcomes = collect(providers, session or new_session(), now.date())

    errors: list[str] = []
    for outcome in outcomes:
        name = outcome.provider.name
        if outcome.error is None:
            log(f"✓ {name}: {len(outcome.matches)} maç")
        elif outcome.provider.required:
            errors.append(f"{name}: {outcome.error}")
            log(f"✗ {name}: {outcome.error}")
        else:
            warn(f"{name} okunamadı, bu kaynak bu çalışmada atlandı: {outcome.error}")

    matches = unique(m for outcome in outcomes for m in outcome.matches)
    errors += coverage_problems(matches)
    write_step_summary(outcomes, matches)

    if errors:
        for message in errors:
            error(message)
        error("Takvimler güncellenmedi; yayındaki son sağlam sürüm korunuyor.")
        return 1

    changed = write_outputs(out_dir, matches, now)
    football = sum(1 for m in matches if m.sport == FOOTBALL)
    log(f"Toplam {football} futbol + {len(matches) - football} basketbol maçı.")
    for filename, did_change in changed.items():
        log(f"  {'güncellendi' if did_change else 'değişmedi  '}  {out_dir / filename}")
    return 0
