"""Aynı maç her kulübün takviminde aynı adla, mevcut kimliği ve zamanı ile görünmeli."""

import unicodedata
from copy import deepcopy
from dataclasses import replace
from datetime import UTC, date, datetime
from itertools import permutations

import pytest
from helpers import fixture_json, fixture_text
from icalendar import Calendar

from club_calendar.club import CLUBS, TEAM_ALIASES, canonical_team_name, get_club
from club_calendar.feeds import feeds_for
from club_calendar.ics import render_calendar
from club_calendar.names import display_name, tr_upper
from club_calendar.providers import euroleague, tbf, tff, uefa

STAMP = datetime(2026, 11, 5, tzinfo=UTC)
PAIRS = list(permutations(CLUBS.values(), 2))


@pytest.mark.parametrize("owner", list(CLUBS.values()), ids=list(CLUBS))
@pytest.mark.parametrize("team", list(CLUBS.values()), ids=list(CLUBS))
def test_aliases_are_canonical_for_every_calendar(owner, team):
    for alias in (team.name, *TEAM_ALIASES[team.key]):
        for raw in (alias, tr_upper(alias), unicodedata.normalize("NFD", alias), f"  {alias}  "):
            assert owner.team_name(raw) == team.name
    assert owner.team_name(f"{tr_upper(team.name)} A.Ş.") == team.name


@pytest.mark.parametrize(
    "raw",
    ["Fenerbahçe Koleji", "Galatasaray Üniversitesi", "Beşiktaş Belediyesi", "Real Madrid", "", None],
)
def test_unknown_names_are_not_claimed_by_a_club(raw):
    assert canonical_team_name(raw) is None
    for owner in CLUBS.values():
        assert owner.team_name(raw) == display_name(raw)


def event(match, owner):
    text = render_calendar([match], "Takvim", "Açıklama", owner, stamp=STAMP)
    return Calendar.from_ical(text.encode()).walk("VEVENT")[0]


def without_summary(item):
    return {key: value.to_ical() for key, value in item.items() if key != "SUMMARY"}


@pytest.mark.parametrize("home,away", PAIRS, ids=[f"{h.key}-{a.key}" for h, a in PAIRS])
@pytest.mark.parametrize("when", ["2026-11-22T20:30:00", "2027-02-06T00:00:00"])
def test_tbf_derby_has_same_title_and_preserves_identity_and_time(home, away, when):
    row = deepcopy(fixture_json("tbf_week_1_clubs.json")["data"][1])
    row["matchDate"] = when
    row["homeTeam"]["name"] = TEAM_ALIASES[home.key][-1]
    row["awayTeam"]["name"] = TEAM_ALIASES[away.key][-1]
    first = tbf.parse_row(row, home)
    second = tbf.parse_row(row, away)
    assert (first.home, first.away) == (second.home, second.away) == (home.name, away.name)
    assert first.source_id == second.source_id == "346274"
    assert first.uid == second.uid
    assert first.start == second.start
    assert first.time_confirmed == ("20:30" in when)

    previous = replace(first, home=row["homeTeam"]["name"], away=row["awayTeam"]["name"])
    assert without_summary(event(previous, home)) == without_summary(event(first, home))
    assert str(event(first, home)["UID"]) == f"{previous.uid}@{home.uid_domain}"
    assert str(event(first, away)["UID"]) == f"{previous.uid}@{away.uid_domain}"


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("confirmed", [False, True])
def test_euroleague_derby_is_independent_of_followed_club(reverse, confirmed):
    game = deepcopy(fixture_json("euroleague_games.json")["data"][1])
    teams = [
        {"code": "BES", "abbreviatedName": "Besiktas", "name": "Besiktas Gain Istanbul"},
        {"code": "ULK", "abbreviatedName": "Fenerbahce", "name": "Fenerbahce Beko Istanbul"},
    ]
    if reverse:
        teams.reverse()
    game["local"]["club"], game["road"]["club"] = teams
    game["confirmedHour"] = confirmed
    first = euroleague.parse_game(game, "EuroLeague", get_club("besiktas"))
    second = euroleague.parse_game(game, "EuroLeague", get_club("fenerbahce"))
    expected = ("Fenerbahçe", "Beşiktaş") if reverse else ("Beşiktaş", "Fenerbahçe")
    assert (first.home, first.away) == (second.home, second.away) == expected
    assert first.source_id == second.source_id == game["identifier"]
    assert first.uid == second.uid and first.start == second.start
    assert first.time_confirmed == confirmed
    previous = replace(first, home=teams[0]["abbreviatedName"], away=teams[1]["abbreviatedName"])
    assert without_summary(event(previous, get_club("besiktas"))) == without_summary(event(first, get_club("besiktas")))


@pytest.mark.parametrize(
    "entity,expected",
    [
        ({"code": "ULK", "abbreviatedName": "FB", "name": "Changed sponsor"}, "Fenerbahçe"),
        ({"abbreviatedName": "Fenerbahce"}, "Fenerbahçe"),
        ({"abbreviatedName": "FB", "name": "Fenerbahce Beko Istanbul"}, "Fenerbahçe"),
        ({"code": "XXX", "abbreviatedName": "Valencia", "name": "Valencia Basket"}, "Valencia"),
        ({}, "?"),
    ],
)
def test_euroleague_prefers_known_codes_and_preserves_unknown_short_names(entity, expected):
    for owner in CLUBS.values():
        assert euroleague._club_name({"club": entity}, owner) == expected


def test_uefa_derby_uses_the_same_names_from_either_calendar():
    item = deepcopy(fixture_json("uefa_matches.json")[0])
    item["homeTeam"]["internationalName"] = "Besiktas"
    item["awayTeam"]["internationalName"] = "Fenerbahce"
    first = uefa.parse_match(item, "UEFA Avrupa Ligi", get_club("besiktas"))
    second = uefa.parse_match(item, "UEFA Avrupa Ligi", get_club("fenerbahce"))
    assert (first.home, first.away) == (second.home, second.away) == ("Beşiktaş", "Fenerbahçe")
    assert (first.source_id, first.start) == (second.source_id, second.start)


def test_tff_derby_uses_the_same_names_from_either_calendar():
    (fixture,) = tff.parse_week(fixture_text("tff_week_6.html"), get_club("fenerbahce"))
    fixture = replace(fixture, home="BEŞİKTAŞ A.Ş.", away="FENERBAHÇE A.Ş.")
    first = tff._to_match(fixture, "Süper Lig", "6. Hafta", get_club("besiktas"))
    second = tff._to_match(fixture, "Süper Lig", "6. Hafta", get_club("fenerbahce"))
    assert (first.home, first.away) == (second.home, second.away) == ("Beşiktaş", "Fenerbahçe")
    assert (first.source_id, first.start) == (second.source_id, second.start)


@pytest.mark.parametrize("owner", list(CLUBS.values()), ids=list(CLUBS))
def test_subscription_identity_and_refresh_contract_are_unchanged(owner):
    assert owner.uid_domain == f"{owner.key}-calendar"
    assert [feed.filename for feed in feeds_for(owner)] == [
        f"{owner.key}-all.ics", f"{owner.key}-football.ics", f"{owner.key}-basketball.ics",
    ]
    text = render_calendar([], "Takvim", "Açıklama", owner, stamp=STAMP)
    assert f"PRODID:-//{owner.key}-calendar//TR" in text
    assert "REFRESH-INTERVAL;VALUE=DURATION:PT12H" in text
    assert "X-PUBLISHED-TTL:PT12H" in text


def test_all_day_derby_stays_on_its_original_day():
    row = deepcopy(fixture_json("tbf_week_1_clubs.json")["data"][1])
    row["matchDate"] = "2027-02-06T00:00:00"
    row["homeTeam"]["name"] = "Galatasaray MCT Technic"
    row["awayTeam"]["name"] = "Fenerbahce Tarfin"
    match = tbf.parse_row(row, get_club("galatasaray"))
    result = event(match, get_club("galatasaray"))
    assert result.decoded("DTSTART") == date(2027, 2, 6)
    assert result.decoded("DTEND") == date(2027, 2, 7)
    assert str(result["STATUS"]) == "TENTATIVE"
    assert str(result["TRANSP"]) == "TRANSPARENT"
