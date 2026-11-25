import copy
from datetime import date, datetime

import pytest
from helpers import BESIKTAS

from club_calendar import ics
from club_calendar.http import SourceError
from club_calendar.models import FOOTBALL, TURKEY_TZ, Match
from club_calendar.providers import bein

DAY = date(2026, 11, 30)
KICKOFF = datetime(2026, 11, 30, 21, tzinfo=TURKEY_TZ)
MATCH = Match(
    "tff", "1234", FOOTBALL, "Trendyol Süper Lig", "13. Hafta",
    DAY, "Beşiktaş", "Galatasaray",
)
ROWS = [
    {
        "homeTeam": {"name": "Beşiktaş"},
        "awayTeam": {"name": "Galatasaray"},
        "round": 13,
        "matchDate": "2026-11-30T18:00:00",
        "liteMatchStatus": "preMatch",
        "venue": "Tüpraş Stadyumu",
    },
    {
        "homeTeam": {"name": "Kocaelispor"},
        "awayTeam": {"name": "Samsunspor"},
        "round": 13,
        "matchDate": "2026-11-29T16:00:00",
    },
]


def test_fallback_updates_confirmed_kickoff_without_changing_published_uid(tmp_path):
    path = tmp_path / "fixture.ics"
    path.write_bytes(ics.render_calendar([MATCH], "Futbol", "Test", BESIKTAS).encode("utf-8"))
    old = bein._previous_matches(path, DAY, BESIKTAS)[13]
    updated = bein._updated_match(old, ROWS, 13, BESIKTAS)

    assert updated.start == KICKOFF
    assert updated.uid == MATCH.uid
    assert updated.source == "bein"
    assert updated.venue == "Tüpraş Stadyumu"


def test_fallback_keeps_provisional_fixture_all_day():
    rows = copy.deepcopy(ROWS)
    rows[1]["matchDate"] = rows[0]["matchDate"]
    assert bein._updated_match(MATCH, rows, 13, BESIKTAS) == MATCH


def test_fallback_rejects_a_different_opponent():
    rows = copy.deepcopy(ROWS)
    rows[0]["awayTeam"]["name"] = "Trabzonspor"
    with pytest.raises(SourceError, match="eşleşmesi"):
        bein._updated_match(MATCH, rows, 13, BESIKTAS)


def test_fallback_updates_a_final_score():
    rows = copy.deepcopy(ROWS)
    rows[0].update(liteMatchStatus="matchEnded", score={"homeScore": 0, "awayScore": 2})

    updated = bein._updated_match(MATCH, rows, 13, BESIKTAS)
    assert updated.start == KICKOFF
    assert updated.result == "0-2"
