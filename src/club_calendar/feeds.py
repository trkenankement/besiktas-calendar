"""Yayınlanan takvim akışları."""

from __future__ import annotations

from dataclasses import dataclass

from .club import Club
from .models import BASKETBALL, FOOTBALL, Match


@dataclass(frozen=True)
class Feed:
    filename: str
    calendar_name: str  # takvim uygulamasında görünen ad
    label: str  # web sayfasındaki başlık
    description: str
    sports: frozenset[str]

    def select(self, matches: list[Match]) -> list[Match]:
        return [m for m in matches if m.sport in self.sports]


def feeds_for(club: Club) -> tuple[Feed, ...]:
    """Kulübün üç akışı: tümü, futbol, basketbol (dosya adları `<kulüp>-all.ics` gibi)."""
    return (
        Feed(
            f"{club.key}-all.ics",
            f"{club.name} Tüm Maçlar",
            "Tüm maçlar",
            f"{club.name} erkek futbol ve basketbol takımlarının maçları",
            frozenset({FOOTBALL, BASKETBALL}),
        ),
        Feed(
            f"{club.key}-football.ics",
            f"{club.name} Futbol Maçları",
            "Futbol",
            f"{club.name} erkek futbol takımının maçları",
            frozenset({FOOTBALL}),
        ),
        Feed(
            f"{club.key}-basketball.ics",
            f"{club.name} Basketbol Maçları",
            "Basketbol",
            f"{club.name} erkek basketbol takımının maçları",
            frozenset({BASKETBALL}),
        ),
    )
