from copy import deepcopy
from datetime import date, datetime

import pytest
from helpers import FakeSession, fixture_json

from besiktas_calendar.http import SourceError
from besiktas_calendar.models import BASKETBALL, TURKEY_TZ
from besiktas_calendar.providers import tbf

TODAY = date(2026, 9, 20)
NEW_LEAGUE, OLD_LEAGUE = 22214, 20728


def route_factory(empty_leagues=()):
    def route(url, params):
        if url.endswith("get-leagues-and-seasons-by-prefix"):
            return fixture_json("tbf_seasons.json")
        if url.endswith("get-league-weeks"):
            return {"data": []} if params["leagueId"] in empty_leagues else fixture_json("tbf_weeks.json")
        if url.endswith("get-all-matches-for-filter"):
            name = f"tbf_week_{params['WeekFilter']}.json"
            try:
                return fixture_json(name)
            except FileNotFoundError:
                return {"data": []}
        return None

    return route


def rows(week):
    return fixture_json(f"tbf_week_{week}.json")["data"]


def besiktas_row(week):
    return next(r for r in rows(week) if "BEŞİKTAŞ" in (r["homeTeam"]["name"] + r["awayTeam"]["name"]))


def test_row_is_converted_with_normalised_names_venue_and_broadcast():
    match = tbf.parse_row(besiktas_row("1"))
    assert match.sport == BASKETBALL
    assert (match.home, match.away) == ("Anadolu Efes", "Beşiktaş")
    assert match.start == datetime(2026, 9, 27, 20, 30, tzinfo=TURKEY_TZ)
    assert match.competition == "Türkiye Sigorta Basketbol Süper Ligi"
    assert match.round_label == "1. Hafta"
    assert match.venue == "Turkcell Basketbol Gelişim Merkezi, İstanbul"
    assert match.broadcast == "beINSports"
    assert match.result == ""
    assert match.source == "tbf" and match.source_id == "346278"


def test_midnight_placeholder_means_the_time_is_not_announced_yet():
    match = tbf.parse_row(besiktas_row("6"))
    assert (match.home, match.away) == ("Beşiktaş", "Çayırova Belediyesi")
    assert not match.time_confirmed
    assert match.day == date(2026, 10, 31)


def test_played_game_reports_the_score():
    row = deepcopy(besiktas_row("1"))
    row["homeTeam"]["score"], row["awayTeam"]["score"] = "78", "84"
    assert tbf.parse_row(row).result == "78-84"


def test_row_without_a_date_is_an_error():
    row = deepcopy(besiktas_row("1"))
    row["matchDate"] = None
    with pytest.raises(SourceError, match="tarihi yok"):
        tbf.parse_row(row)


def test_fetch_returns_only_besiktas_games_from_the_newest_season():
    session = FakeSession(route_factory())
    matches = tbf.fetch_bsl(session, TODAY)

    assert [m.round_label for m in matches] == ["1. Hafta", "6. Hafta"]
    assert all("Beşiktaş" in (m.home, m.away) for m in matches)  # diğer takımların satırları elenir

    match_requests = [p for url, p in session.requests if url.endswith("get-all-matches-for-filter")]
    assert [p["WeekFilter"] for p in match_requests] == ["1", "2", "6"]
    assert all(p["ActivityId"] == NEW_LEAGUE and "HalfValue" not in p for p in match_requests)


def test_previous_season_is_used_while_the_new_fixture_list_is_not_published():
    session = FakeSession(route_factory(empty_leagues={NEW_LEAGUE}))
    tbf.fetch_bsl(session, TODAY)
    match_requests = [p for url, p in session.requests if url.endswith("get-all-matches-for-filter")]
    assert match_requests and all(p["ActivityId"] == OLD_LEAGUE for p in match_requests)


def test_no_fixture_list_in_either_season_is_an_error():
    session = FakeSession(route_factory(empty_leagues={NEW_LEAGUE, OLD_LEAGUE}))
    with pytest.raises(SourceError, match="hafta listesi"):
        tbf.fetch_bsl(session, TODAY)


def test_empty_season_list_is_an_error():
    session = FakeSession(lambda url, params: {"data": []})
    with pytest.raises(SourceError, match="sezon listesi boş"):
        tbf.fetch_bsl(session, TODAY)


# --- Kupalar ----------------------------------------------------------------------------------

CUP_LEAGUE = 23538  # Erkekler Cumhurbaşkanlığı Kupası 2026-2027
ETK_OLD_LEAGUE = 22157  # Erkekler Türkiye Kupası 2025-2026 (2026-2027 turnuvası henüz oluşturulmamış)


def cup_route(weeks=None):
    def route(url, params):
        if url.endswith("get-leagues-and-seasons-by-prefix"):
            return {
                "bsl": fixture_json("tbf_seasons.json"),
                "cbek": fixture_json("tbf_cup_seasons.json"),
                "etk": fixture_json("tbf_etk_seasons.json"),
            }.get(params["prefix"], {"data": []})
        if url.endswith("get-league-weeks"):
            if params["leagueId"] == CUP_LEAGUE:
                return weeks if weeks is not None else fixture_json("tbf_cup_weeks.json")
            return fixture_json("tbf_weeks.json")
        if url.endswith("get-all-matches-for-filter"):
            if params["ActivityId"] == CUP_LEAGUE:
                return fixture_json("tbf_cup_week_1.json") if params["WeekFilter"] == "1" else {"data": []}
            return {"data": []}
        return None

    return route


def test_cup_match_of_the_current_edition_is_read_and_older_editions_are_ignored():
    session = FakeSession(cup_route())
    (match,) = tbf.fetch_cups(session, TODAY)

    # Sorgu önceki yılların maçlarını da döndürür (2025'te "Fenerbahçe Beko - Beşiktaş Gain" gibi)
    assert (match.home, match.away) == ("Fenerbahçe Tarfin", "Beşiktaş")
    assert match.start == datetime(2026, 9, 22, 20, 0, tzinfo=TURKEY_TZ)
    assert match.competition == "Cumhurbaşkanlığı Kupası"
    assert match.round_label == ""  # tek turluk turnuvada "1. Hafta" anlamsız
    assert match.venue == "Sinan Erdem Spor Salonu, İstanbul"
    assert match.source == "tbf" and match.source_id == "346272"


def test_cup_without_an_edition_for_the_current_season_is_skipped():
    session = FakeSession(cup_route())
    tbf.fetch_cups(session, TODAY)
    league_ids = {p.get("leagueId") or p.get("ActivityId") for _, p in session.requests}
    assert ETK_OLD_LEAGUE not in league_ids  # geçen sezonun Türkiye Kupası'na bakılmaz


def test_round_labels_are_kept_for_cups_with_several_rounds():
    weeks = {"data": [{"sezon_Hafta": "1", "devre_ID": 1}, {"sezon_Hafta": "2", "devre_ID": 1}]}
    (match,) = tbf.fetch_cups(FakeSession(cup_route(weeks=weeks)), TODAY)
    assert match.round_label == "1. Hafta"


def test_competition_name_drops_gender_prefix_and_season_suffix():
    row = deepcopy(fixture_json("tbf_cup_week_1.json")["data"][1])
    assert tbf.parse_row(row).competition == "Cumhurbaşkanlığı Kupası"
    row["activityName"] = "Erkekler Türkiye Kupası 2026-2027"
    assert tbf.parse_row(row).competition == "Türkiye Kupası"
    row["activityDisplayName"] = "Türkiye Sigorta Basketbol Süper Ligi"
    assert tbf.parse_row(row).competition == "Türkiye Sigorta Basketbol Süper Ligi"


def test_rows_without_season_information_are_trusted():
    assert tbf._in_season({"seasonId": 174.0}, 174)
    assert not tbf._in_season({"seasonId": 172.0}, 174)
    assert tbf._in_season({}, 174)


def test_half_value_is_sent_for_phases_other_than_the_two_regular_halves():
    def route(url, params):
        if url.endswith("get-league-weeks"):
            return {"data": [{"sezon_Hafta": "1", "devre_ID": 3.0, "devre_Deger": "PO"}]}
        if url.endswith("get-all-matches-for-filter"):
            return {"data": []}
        return fixture_json("tbf_seasons.json")

    session = FakeSession(route)
    tbf.fetch_bsl(session, TODAY)
    (params,) = [p for url, p in session.requests if url.endswith("get-all-matches-for-filter")]
    assert params["HalfValue"] == "PO"
