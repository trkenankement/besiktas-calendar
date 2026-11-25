import copy
import json
from dataclasses import replace
from datetime import date, datetime

import pytest
from helpers import BESIKTAS

from club_calendar import ics
from club_calendar.http import SourceError
from club_calendar.models import FOOTBALL, TURKEY_TZ, Match
from club_calendar.providers import bein
from club_calendar.providers._league_history import read_league_history

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
    old = read_league_history(path, DAY, BESIKTAS)[13]
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


@pytest.mark.parametrize("recent, expected", [(True, [13]), (False, list(range(1, 35)))])
def test_backup_refresh_uses_the_same_scope_and_keeps_all_events(tmp_path, monkeypatch, recent, expected):
    history = {
        week: replace(MATCH, source_id=str(week), round_label=f"{week}. Hafta", start=date(2027, 3, 1))
        for week in range(1, 35)
    }
    history[13] = replace(history[13], start=DAY)
    previous = tmp_path / "fixture.ics"
    previous.write_bytes(ics.render_calendar(history.values(), "Futbol", "Test", BESIKTAS).encode("utf-8"))
    metadata = {"activeOrganization": {"id": 18}, "activeSeason": {"name": "2026/2027", "id": 3974},
                "rounds": [{"round": week} for week in history]}
    payload = json.dumps({"props": {"pageProps": {"orgData": metadata}}})
    monkeypatch.setattr(bein, "get_html", lambda *a, **kw: f'<script id="__NEXT_DATA__" type="application/json">{payload}</script>')
    requested = []

    def fixture(*args, r, **kwargs):
        requested.append(r)
        rows = copy.deepcopy(ROWS)
        rows[0]["round"] = r
        if r != 13:
            rows[0]["matchDate"] = rows[1]["matchDate"]
        return {"Data": rows + [rows[1]] * 7}

    monkeypatch.setattr(bein, "get_json", fixture)
    matches = bein.fetch_super_lig(object(), DAY, BESIKTAS, previous, recent=recent)

    assert requested == expected
    assert {match.uid for match in matches} == {match.uid for match in history.values()}
    assert next(match for match in matches if match.round_label == "13. Hafta").start == KICKOFF
