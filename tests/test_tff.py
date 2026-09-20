from datetime import date, datetime

import pytest
from helpers import EMPTY_PAGE, FIXTURES, FakeSession, fixture_text

from besiktas_calendar.http import SourceError
from besiktas_calendar.models import FOOTBALL, TURKEY_TZ
from besiktas_calendar.providers import tff

TODAY = date(2026, 9, 20)


def league_route(missing_weeks=()):
    def route(url, params):
        if params.get("pageId") == 29:  # maç detayı
            return fixture_text("tff_match_page.html")
        if params.get("pageID") == 198:
            week = params.get("hafta")
            if week is None:
                return fixture_text("tff_overview.html")
            if week in missing_weeks:
                return None
            name = f"tff_week_{week}.html"
            return fixture_text(name) if (FIXTURES / name).exists() else EMPTY_PAGE
        return None

    return route


def test_overview_reports_league_name_and_number_of_weeks():
    assert tff.parse_league_overview(fixture_text("tff_overview.html")) == ("Trendyol Süper Lig", 34)


def test_overview_without_the_season_table_is_an_error():
    with pytest.raises(SourceError, match="fikstür tablosu"):
        tff.parse_league_overview(EMPTY_PAGE)


def test_week_page_yields_only_besiktas_fixture_with_date_time_and_id():
    (fixture,) = tff.parse_week(fixture_text("tff_week_6.html"))
    assert fixture.home == "AMED SPORTİF FAALİYETLER"
    assert fixture.away == "BEŞİKTAŞ A.Ş."
    assert (fixture.day, fixture.hour, fixture.minute) == (date(2026, 9, 20), 20, 0)
    assert fixture.mac_id == "317832"
    assert fixture.score == ""


def test_played_fixture_carries_the_score():
    (fixture,) = tff.parse_week(fixture_text("tff_week_1.html"))
    assert (fixture.home, fixture.away, fixture.score) == ("BEŞİKTAŞ A.Ş.", "EYÜPSPOR", "1-0")


def test_far_future_week_has_a_date_but_no_time():
    (fixture,) = tff.parse_week(fixture_text("tff_week_20.html"))
    assert fixture.day == date(2027, 2, 7)
    assert fixture.hour is None and fixture.minute is None
    match = tff._to_match(fixture, "Trendyol Süper Lig", "20. Hafta")
    assert not match.time_confirmed
    assert match.day == date(2027, 2, 7)


def test_unreadable_date_of_a_besiktas_fixture_is_an_error_not_a_silent_skip():
    broken = fixture_text("tff_week_6.html").replace("20.09.2026", "belirsiz")
    with pytest.raises(SourceError, match="tarihi okunamadı"):
        tff.parse_week(broken)


def test_match_is_converted_to_the_common_model():
    (fixture,) = tff.parse_week(fixture_text("tff_week_7.html"))
    match = tff._to_match(fixture, "Trendyol Süper Lig", "7. Hafta")
    assert match.sport == FOOTBALL
    assert (match.home, match.away) == ("Beşiktaş", "Kocaelispor")
    assert match.start == datetime(2026, 10, 11, 19, 0, tzinfo=TURKEY_TZ)
    assert match.source == "tff" and match.source_id == "317845"
    assert match.info_url.endswith("pageId=29&macId=317845")


def test_venue_comes_from_the_match_page():
    assert tff.parse_venue(fixture_text("tff_match_page.html")) == "Diyarbakır Stadyumu, Diyarbakır"
    assert tff.parse_venue(EMPTY_PAGE) == ""


def test_fetch_super_lig_reads_every_week_and_looks_up_venues_only_for_unplayed_matches():
    session = FakeSession(league_route())
    matches = tff.fetch_super_lig(session, TODAY)

    assert [m.round_label for m in matches] == ["1. Hafta", "6. Hafta", "7. Hafta", "20. Hafta"]
    by_round = {m.round_label: m for m in matches}
    assert by_round["1. Hafta"].result == "1-0"
    assert by_round["1. Hafta"].venue == ""  # oynanmış maç: stadyum aranmaz
    assert by_round["6. Hafta"].venue == "Diyarbakır Stadyumu, Diyarbakır"

    week_requests = [p["hafta"] for _, p in session.requests if "hafta" in p]
    assert week_requests == list(range(1, 35))
    venue_lookups = sorted(p["macId"] for _, p in session.requests if p.get("pageId") == 29)
    assert venue_lookups == ["317832", "317845", "317962"]


def test_a_failed_venue_lookup_does_not_lose_the_match():
    def route(url, params):
        return None if params.get("pageId") == 29 else league_route()(url, params)

    matches = tff.fetch_super_lig(FakeSession(route), TODAY)
    assert len(matches) == 4
    assert all(m.venue == "" for m in matches)


def test_a_missing_week_page_fails_the_provider():
    with pytest.raises(SourceError):
        tff.fetch_super_lig(FakeSession(league_route(missing_weeks={3})), TODAY)


# --- Ziraat Türkiye Kupası --------------------------------------------------------------------


def test_cup_page_without_besiktas_yields_nothing():
    assert tff.parse_cup(fixture_text("tff_cup_real.html")) == []


def test_cup_page_besiktas_row_is_parsed_with_round_and_turkish_date():
    (match,) = tff.parse_cup(fixture_text("tff_cup_with_besiktas.html"))
    assert match.competition == "Ziraat Türkiye Kupası"
    assert match.round_label == "2. Tur"
    assert (match.home, match.away) == ("Beşiktaş", "Örnek Spor Kulübü")
    assert match.start == datetime(2026, 10, 7, 20, 30, tzinfo=TURKEY_TZ)
    assert match.source_id == "999001"
    assert match.result == ""


def test_cup_row_without_a_time_is_all_day():
    html = fixture_text("tff_cup_with_besiktas.html").replace("07 Ekim 2026 20:30", "07 Ekim 2026")
    (match,) = tff.parse_cup(html)
    assert not match.time_confirmed
    assert match.day == date(2026, 10, 7)


def test_cup_row_with_an_unknown_month_is_an_error():
    html = fixture_text("tff_cup_with_besiktas.html").replace("07 Ekim 2026 20:30", "07 Foo 2026 20:30")
    with pytest.raises(SourceError, match="tarihi okunamadı"):
        tff.parse_cup(html)


def test_fetch_cup_adds_venue_for_upcoming_match():
    def route(url, params):
        if params.get("pageId") == 29:
            return fixture_text("tff_match_page.html")
        return fixture_text("tff_cup_with_besiktas.html")

    (match,) = tff.fetch_cup(FakeSession(route), TODAY)
    assert match.venue == "Diyarbakır Stadyumu, Diyarbakır"
