"""Depo istatistikleri: GitHub'da izleyen (takipçi) ve yıldızlayan sayısı; web sayfasında gösterilir.

Takvim aboneleri anonimdir: Google, Apple ve Outlook takvimi kendi sunucularından çeker ve GitHub Pages erişim
kaydı vermez. Bu yüzden gerçek abone sayısı ölçülemez; sayfada yalnızca GitHub'daki takipçi ve yıldız sayısı
gösterilir. Değerleri iş akışı GitHub'dan alıp `docs/stats.json` dosyasına yazar.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RepoStats:
    stars: int
    watchers: int


def load_stats(path: Path) -> RepoStats | None:
    """`stats.json` dosyasını okur; yoksa ya da geçersizse None döndürür (sayfa sayıları göstermez)."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        stars, watchers = data["stars"], data["watchers"]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    # bool ve float de kabul edilmez: sayfaya yalnızca gerçek, negatif olmayan tam sayılar girer
    if any(type(value) is not int or value < 0 for value in (stars, watchers)):
        return None
    return RepoStats(stars=stars, watchers=watchers)
