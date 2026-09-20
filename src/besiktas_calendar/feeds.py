"""Yayınlanan takvim akışları."""

from __future__ import annotations

from dataclasses import dataclass

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


FEEDS = (
    Feed(
        "besiktas-all.ics",
        "Beşiktaş Tüm Maçlar",
        "Tüm maçlar",
        "Beşiktaş erkek futbol ve basketbol takımlarının maçları",
        frozenset({FOOTBALL, BASKETBALL}),
    ),
    Feed(
        "besiktas-football.ics",
        "Beşiktaş Futbol Maçları",
        "Futbol",
        "Beşiktaş erkek futbol takımının maçları",
        frozenset({FOOTBALL}),
    ),
    Feed(
        "besiktas-basketball.ics",
        "Beşiktaş Basketbol Maçları",
        "Basketbol",
        "Beşiktaş erkek basketbol takımının maçları",
        frozenset({BASKETBALL}),
    ),
)
