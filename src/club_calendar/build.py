"""Tüm kaynaklardan maçları toplar, doğrular ve çıktı klasörüne (docs/) yazar."""

from __future__ import annotations

import os
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

import requests

from . import ics, site
from .club import Club
from .console import error, log, warn
from .feeds import feeds_for
from .http import SourceError, new_session
from .models import BASKETBALL, FOOTBALL, SPORT_LABELS, TURKEY_TZ, Match
from .providers import Provider, providers_for
from .stats import load_stats

MIN_MATCHES_PER_SPORT = 5  # bunun altı, kaynakların ciddi biçimde bozulduğu anlamına gelir
MAX_DISTANCE_DAYS = 500  # bir sezonluk takvimde bugünden bundan uzak tarih, ayrıştırma hatası demektir


@dataclass
class Outcome:
    provider: Provider
    matches: list[Match]
    error: str | None = None


def collect(providers: Iterable[Provider], session: requests.Session, today: date, club: Club) -> list[Outcome]:
    outcomes: list[Outcome] = []
    for provider in providers:
        try:
            matches = provider.fetch(session, today, club)
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


def date_problems(matches: list[Match], today: date) -> list[str]:
    """Mantıksız tarihli maçlar (ör. yanlış okunmuş yıl) yayınlanmadan yakalanır."""
    off = [m for m in matches if abs((m.day - today).days) > MAX_DISTANCE_DAYS]
    return [f"{m.home} - {m.away} ({m.competition}) maçının tarihi mantıksız: {m.day:%d.%m.%Y}" for m in off[:5]]


def write_outputs(out_dir: Path, matches: list[Match], now: datetime, club: Club) -> dict[str, bool]:
    """Dosyaları yazar; yalnızca gerçekten değişenler için True döndürür."""
    out_dir.mkdir(parents=True, exist_ok=True)
    changed: dict[str, bool] = {}
    for feed in feeds_for(club):
        content = ics.render_calendar(
            feed.select(matches), feed.calendar_name, feed.description, club, stamp=now.astimezone(UTC)
        )
        changed[feed.filename] = ics.write_if_changed(out_dir / feed.filename, content)
    page = site.render_index(matches, now, club, load_stats(out_dir / "stats.json"))
    changed["index.html"] = ics.write_if_changed(out_dir / "index.html", page, ignore_prefixes=())
    # Son kontrol zamanı her çalışmada değişir; bu yüzden git'te izlenmez (.gitignore) ama siteye girer.
    (out_dir / "last_check.txt").write_text(now.strftime("%d.%m.%Y %H:%M (TSİ)") + "\n", encoding="utf-8")
    return changed


def write_step_summary(outcomes: list[Outcome], matches: list[Match], club: Club) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    lines = [f"### {club.name} takvimi", "", "| Kaynak | Durum | Maç |", "| --- | --- | ---: |"]
    for outcome in outcomes:
        status = "✅" if outcome.error is None else ("❌" if outcome.provider.required else "⚠️")
        lines.append(f"| {outcome.provider.name} | {status} | {len(outcome.matches)} |")
    football = sum(1 for m in matches if m.sport == FOOTBALL)
    lines += ["", f"Toplam: **{football}** futbol, **{len(matches) - football}** basketbol maçı."]
    with open(path, "a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def run(
    out_dir: Path,
    club: Club,
    *,
    providers: Iterable[Provider] | None = None,
    session: requests.Session | None = None,
    now: datetime | None = None,
) -> int:
    now = now or datetime.now(TURKEY_TZ)
    providers = providers_for(club) if providers is None else providers
    outcomes = collect(providers, session or new_session(), now.date(), club)

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
    errors += coverage_problems(matches) + date_problems(matches, now.date())
    write_step_summary(outcomes, matches, club)

    if errors:
        for message in errors:
            error(message)
        error("Takvimler güncellenmedi; yayındaki son sağlam sürüm korunuyor.")
        return 1

    changed = write_outputs(out_dir, matches, now, club)
    football = sum(1 for m in matches if m.sport == FOOTBALL)
    log(f"Toplam {football} futbol + {len(matches) - football} basketbol maçı.")
    for filename, did_change in changed.items():
        log(f"  {'güncellendi' if did_change else 'değişmedi  '}  {out_dir / filename}")
    return 0
