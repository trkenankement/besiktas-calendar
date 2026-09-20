from copy import deepcopy
from datetime import date, datetime

import pytest
from helpers import BESIKTAS, FakeSession, fixture_json

from club_calendar.http import SourceError
from club_calendar.models import BASKETBALL, TURKEY_TZ
from club_calendar.providers import euroleague

TODAY = date(2026, 9, 20)


def route_factory(seasons=None, games=None):
    seasons = seasons if seasons is not None else fixture_json("euroleague_seasons.json")
    games = games if games is not None else fixture_json("euroleague_games.json")

    def route(url, params):
        if url.endswith("/E/seasons"):
            return seasons
        if url.endswith("/U/seasons"):
            return {"data": []}
        if url.endswith("/games"):
            return games
        return None

    return route


def test_home_game_is_parsed_with_utc_converted_to_turkey_time():
    home_game = fixture_json("euroleague_games.json")["data"][1]
    match = euroleague.parse_game(home_game, "EuroLeague", BESIKTAS)
    assert match.sport == BASKETBALL
    assert (match.home, match.away) == ("Beşiktaş", "Valencia")
    assert match.start == datetime(2026, 9, 25, 20, 0, tzinfo=TURKEY_TZ)
    assert match.round_label == "1. Hafta"
    assert match.venue == "Turkcell Basketball Development Center"
    assert match.result == ""
    assert match.source == "euroleague" and match.source_id == "E2026_8"


def test_away_game_uses_the_opponents_short_name_and_venue():
    away_game = fixture_json("euroleague_games.json")["data"][0]
    match = euroleague.parse_game(away_game, "EuroLeague", BESIKTAS)
    assert (match.home, match.away) == ("Maccabi", "Beşiktaş")
    assert match.start == datetime(2026, 9, 30, 21, 5, tzinfo=TURKEY_TZ)
    assert match.venue == "Aleksandar Nikolic Hall"


def test_result_is_only_reported_for_played_games():
    game = deepcopy(fixture_json("euroleague_games.json")["data"][1])
    game["played"] = True
    game["local"]["score"], game["road"]["score"] = 84, 79
    assert euroleague.parse_game(game, "EuroLeague", BESIKTAS).result == "84-79"


@pytest.mark.parametrize("flag", ["confirmedHour", "confirmedDate"])
def test_unconfirmed_time_or_date_becomes_all_day(flag):
    game = deepcopy(fixture_json("euroleague_games.json")["data"][1])
    game[flag] = False
    match = euroleague.parse_game(game, "EuroLeague", BESIKTAS)
    assert not match.time_confirmed
    assert match.day == date(2026, 9, 25)


def test_playoff_games_use_the_round_name():
    game = deepcopy(fixture_json("euroleague_games.json")["data"][1])
    game["phaseType"] = {"code": "PO", "name": "Playoffs"}
    game["roundName"] = "Playoffs Game 2"
    assert euroleague.parse_game(game, "EuroLeague", BESIKTAS).round_label == "Playoffs Game 2"


def test_fetch_uses_the_current_season_and_filters_by_team_code():
    session = FakeSession(route_factory())
    matches = euroleague.fetch(session, TODAY, BESIKTAS)

    assert len(matches) == 2
    games_requests = [(url, params) for url, params in session.requests if url.endswith("/games")]
    assert len(games_requests) == 1
    url, params = games_requests[0]
    assert "/E/seasons/E2026/games" in url
    assert params == {"teamCode": "BES"}


def test_a_season_that_has_not_started_yet_is_ignored():
    session = FakeSession(route_factory())
    euroleague.fetch(session, date(2026, 6, 1), BESIKTAS)
    (url, _), = [(u, p) for u, p in session.requests if u.endswith("/games")]
    assert "/E/seasons/E2025/games" in url


def test_no_started_season_means_no_matches():
    seasons = {"data": [{"code": "E2099", "year": 2099, "startDate": "2099-07-01T00:00:00", "endDate": "2100-06-30T23:59:59"}]}
    assert euroleague.fetch(FakeSession(route_factory(seasons=seasons)), TODAY, BESIKTAS) == []


@pytest.mark.parametrize("bad_date", [None, "", "yarın"])
def test_game_without_a_readable_date_is_skipped_with_a_warning(bad_date, capsys, monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    game = deepcopy(fixture_json("euroleague_games.json")["data"][1])
    game["utcDate"] = bad_date
    assert euroleague.parse_game(game, "EuroLeague", BESIKTAS) is None
    assert "tarihi okunamadı" in capsys.readouterr().out


def test_a_missing_date_key_is_handled_like_any_other_unreadable_date(capsys, monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    game = deepcopy(fixture_json("euroleague_games.json")["data"][1])
    del game["utcDate"]
    assert euroleague.parse_game(game, "EuroLeague", BESIKTAS) is None


def test_nothing_readable_at_all_means_the_source_format_changed():
    games = fixture_json("euroleague_games.json")
    undated = deepcopy(games["data"][0])
    del undated["utcDate"]
    payload = {"data": [dict(undated, identifier=f"E2026_{n}") for n in range(3)]}
    with pytest.raises(SourceError, match="biçimi değişmiş"):
        euroleague.fetch(FakeSession(route_factory(games=payload)), TODAY, BESIKTAS)


def test_unexpected_response_shape_is_an_error():
    with pytest.raises(SourceError, match="beklenmeyen"):
        euroleague.fetch(FakeSession(route_factory(games=[1, 2, 3])), TODAY, BESIKTAS)
