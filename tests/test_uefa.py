from copy import deepcopy
from datetime import date, datetime

import pytest
from helpers import FakeSession, fixture_json

from besiktas_calendar.http import SourceError
from besiktas_calendar.models import FOOTBALL, TURKEY_TZ
from besiktas_calendar.providers import uefa

COMPETITION = "UEFA Avrupa Ligi"


@pytest.mark.parametrize(
    ("today", "season"),
    [
        (date(2026, 1, 15), 2026),
        (date(2026, 6, 30), 2026),
        (date(2026, 7, 1), 2027),
        (date(2026, 9, 20), 2027),
        (date(2027, 6, 30), 2027),
        (date(2027, 7, 1), 2028),
    ],
)
def test_season_year_follows_the_uefa_naming(today, season):
    assert uefa.season_year_for(today) == season


def test_finished_qualifier_has_time_result_venue_and_turkish_round_name():
    finished = uefa.parse_match(fixture_json("uefa_matches.json")[0], COMPETITION)
    assert finished.sport == FOOTBALL
    assert (finished.home, finished.away) == ("Beşiktaş", "Midtjylland")
    assert finished.start == datetime(2026, 7, 23, 21, 0, tzinfo=TURKEY_TZ)  # 18:00 UTC
    assert finished.result == "1-0"
    assert finished.round_label == "2. Ön Eleme Turu"
    assert finished.venue == "Beşiktaş Stadium, Istanbul"
    assert finished.source == "uefa" and finished.source_id == "2048745"


def test_league_phase_match_is_labelled_with_its_matchday():
    away = uefa.parse_match(fixture_json("uefa_matches.json")[1], COMPETITION)
    assert (away.home, away.away) == ("Hoffenheim", "Beşiktaş")
    assert away.start == datetime(2026, 10, 15, 22, 0, tzinfo=TURKEY_TZ)
    assert away.round_label == "Lig Aşaması 2. Hafta"
    assert away.result == ""
    assert away.venue == "Rhein-Neckar-Arena, Sinsheim"


def test_penalty_shootout_is_added_to_the_result():
    item = deepcopy(fixture_json("uefa_matches.json")[0])
    item["score"]["penalty"] = {"home": 4, "away": 3}
    assert uefa.parse_match(item, COMPETITION).result == "1-0 (pen. 4-3)"


def test_unfinished_match_has_no_result_even_if_a_score_object_exists():
    item = deepcopy(fixture_json("uefa_matches.json")[0])
    item["status"] = "UPCOMING"
    assert uefa.parse_match(item, COMPETITION).result == ""


def test_unknown_round_names_fall_back_to_the_original_text():
    item = deepcopy(fixture_json("uefa_matches.json")[0])
    item["round"]["metaData"]["name"] = "Some new round"
    assert uefa.parse_match(item, COMPETITION).round_label == "Some new round"


def test_fetch_queries_every_competition_for_besiktas_only():
    items = fixture_json("uefa_matches.json")

    def route(url, params):
        return items if params["competitionId"] == "14" else []

    session = FakeSession(route)
    matches = uefa.fetch(session, date(2026, 9, 20))

    assert len(matches) == 3
    assert {m.competition for m in matches} == {COMPETITION}
    assert [p["competitionId"] for _, p in session.requests] == ["1", "14", "2019"]
    assert all(p["teamId"] == "50157" and p["seasonYear"] == 2027 for _, p in session.requests)


def test_fetch_follows_pagination():
    template = fixture_json("uefa_matches.json")[0]

    def numbered(start, count):
        return [dict(template, id=str(start + i)) for i in range(count)]

    def route(url, params):
        if params["competitionId"] != "14":
            return []
        return numbered(0, 100) if params["offset"] == 0 else numbered(100, 5)

    matches = uefa.fetch(FakeSession(route), date(2026, 9, 20))
    assert len(matches) == 105
    assert len({m.uid for m in matches}) == 105


def test_unexpected_response_shape_is_an_error():
    with pytest.raises(SourceError, match="beklenmeyen"):
        uefa.fetch(FakeSession(lambda url, params: {"error": "nope"}), date(2026, 9, 20))
