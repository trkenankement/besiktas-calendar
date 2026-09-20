from copy import deepcopy
from datetime import date, datetime

import pytest
from helpers import BESIKTAS, FakeSession, fixture_json

from club_calendar.http import SourceError
from club_calendar.models import FOOTBALL, TURKEY_TZ
from club_calendar.providers import uefa

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
    finished = uefa.parse_match(fixture_json("uefa_matches.json")[0], COMPETITION, BESIKTAS)
    assert finished.sport == FOOTBALL
    assert (finished.home, finished.away) == ("Beşiktaş", "Midtjylland")
    assert finished.start == datetime(2026, 7, 23, 21, 0, tzinfo=TURKEY_TZ)  # 18:00 UTC
    assert finished.result == "1-0"
    assert finished.round_label == "2. Ön Eleme Turu"
    assert finished.venue == "Beşiktaş Stadium, Istanbul"
    assert finished.source == "uefa" and finished.source_id == "2048745"


def test_league_phase_match_is_labelled_with_its_matchday():
    away = uefa.parse_match(fixture_json("uefa_matches.json")[1], COMPETITION, BESIKTAS)
    assert (away.home, away.away) == ("Hoffenheim", "Beşiktaş")
    assert away.start == datetime(2026, 10, 15, 22, 0, tzinfo=TURKEY_TZ)
    assert away.round_label == "Lig Aşaması 2. Hafta"
    assert away.result == ""
    assert away.venue == "Rhein-Neckar-Arena, Sinsheim"


def test_penalty_shootout_is_added_to_the_result():
    item = deepcopy(fixture_json("uefa_matches.json")[0])
    item["score"]["penalty"] = {"home": 4, "away": 3}
    assert uefa.parse_match(item, COMPETITION, BESIKTAS).result == "1-0 (pen. 4-3)"


def test_unfinished_match_has_no_result_even_if_a_score_object_exists():
    item = deepcopy(fixture_json("uefa_matches.json")[0])
    item["status"] = "UPCOMING"
    assert uefa.parse_match(item, COMPETITION, BESIKTAS).result == ""


def test_unknown_round_names_fall_back_to_the_original_text():
    item = deepcopy(fixture_json("uefa_matches.json")[0])
    item["round"]["metaData"]["name"] = "Some new round"
    assert uefa.parse_match(item, COMPETITION, BESIKTAS).round_label == "Some new round"


def test_fetch_queries_every_competition_for_besiktas_only():
    items = fixture_json("uefa_matches.json")

    def route(url, params):
        return items if params["competitionId"] == "14" else []

    session = FakeSession(route)
    matches = uefa.fetch(session, date(2026, 9, 20), BESIKTAS)

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

    matches = uefa.fetch(FakeSession(route), date(2026, 9, 20), BESIKTAS)
    assert len(matches) == 105
    assert len({m.uid for m in matches}) == 105


def test_kickoff_with_only_a_date_becomes_an_all_day_match():
    item = deepcopy(fixture_json("uefa_matches.json")[1])
    item["kickOffTime"] = {"date": "2026-10-15"}
    match = uefa.parse_match(item, COMPETITION, BESIKTAS)
    assert not match.time_confirmed
    assert match.day == date(2026, 10, 15)


@pytest.mark.parametrize("kickoff", [{}, None, {"dateTime": "yarın"}, {"date": "15/10/2026"}])
def test_match_without_a_readable_kickoff_is_skipped_with_a_warning(kickoff, capsys, monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    item = deepcopy(fixture_json("uefa_matches.json")[1])
    item["kickOffTime"] = kickoff
    assert uefa.parse_match(item, COMPETITION, BESIKTAS) is None
    assert "tarihi okunamadı" in capsys.readouterr().out


def test_a_few_undated_matches_do_not_fail_the_provider(capsys, monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    items = fixture_json("uefa_matches.json") + [dict(fixture_json("uefa_matches.json")[0], id="9", kickOffTime={})]
    matches = uefa.fetch(FakeSession(lambda url, params: items if params["competitionId"] == "14" else []), date(2026, 9, 20), BESIKTAS)
    assert len(matches) == 3
    assert "UYARI" in capsys.readouterr().out


def test_nothing_readable_at_all_means_the_source_format_changed():
    template = fixture_json("uefa_matches.json")[0]
    items = [dict(template, id=str(i), kickOffTime={}) for i in range(3)]
    session = FakeSession(lambda url, params: items if params["competitionId"] == "14" else [])
    with pytest.raises(SourceError, match="biçimi değişmiş"):
        uefa.fetch(session, date(2026, 9, 20), BESIKTAS)


def test_unexpected_response_shape_is_an_error():
    with pytest.raises(SourceError, match="beklenmeyen"):
        uefa.fetch(FakeSession(lambda url, params: {"error": "nope"}), date(2026, 9, 20), BESIKTAS)
