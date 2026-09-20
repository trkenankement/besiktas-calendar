import re
from datetime import date, datetime

import pytest
from helpers import BESIKTAS, EMPTY_PAGE, FIXTURES, FakeSession, fixture_text

from club_calendar.http import SourceError
from club_calendar.models import FOOTBALL, TURKEY_TZ
from club_calendar.providers import tff

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
    (fixture,) = tff.parse_week(fixture_text("tff_week_6.html"), BESIKTAS)
    assert fixture.home == "AMED SPORTİF FAALİYETLER"
    assert fixture.away == "BEŞİKTAŞ A.Ş."
    assert (fixture.day, fixture.hour, fixture.minute) == (date(2026, 9, 20), 20, 0)
    assert fixture.mac_id == "317832"
    assert fixture.score == ""


def test_played_fixture_carries_the_score():
    (fixture,) = tff.parse_week(fixture_text("tff_week_1.html"), BESIKTAS)
    assert (fixture.home, fixture.away, fixture.score) == ("BEŞİKTAŞ A.Ş.", "EYÜPSPOR", "1-0")


def test_far_future_week_has_a_date_but_no_time():
    (fixture,) = tff.parse_week(fixture_text("tff_week_20.html"), BESIKTAS)
    assert fixture.day == date(2027, 2, 7)
    assert fixture.hour is None and fixture.minute is None
    match = tff._to_match(fixture, "Trendyol Süper Lig", "20. Hafta", BESIKTAS)
    assert not match.time_confirmed
    assert match.day == date(2027, 2, 7)


def test_a_fixture_with_an_unreadable_date_is_skipped_with_a_warning(capsys, monkeypatch):
    """Ertelenmiş tek bir maç yüzünden bütün günlük güncelleme durmamalı."""
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    broken = fixture_text("tff_week_6.html").replace("20.09.2026", "belirsiz")

    assert tff.parse_week(broken, BESIKTAS) == []

    warning = capsys.readouterr().out
    assert "UYARI" in warning and "AMED SPORTİF FAALİYETLER - BEŞİKTAŞ A.Ş." in warning and "belirsiz" in warning
    assert len(tff.parse_week(fixture_text("tff_week_7.html"), BESIKTAS)) == 1  # diğer haftalar etkilenmez


def test_match_is_converted_to_the_common_model():
    (fixture,) = tff.parse_week(fixture_text("tff_week_7.html"), BESIKTAS)
    match = tff._to_match(fixture, "Trendyol Süper Lig", "7. Hafta", BESIKTAS)
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
    matches = tff.fetch_super_lig(session, TODAY, BESIKTAS)

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

    matches = tff.fetch_super_lig(FakeSession(route), TODAY, BESIKTAS)
    assert len(matches) == 4
    assert all(m.venue == "" for m in matches)


def test_a_missing_week_page_fails_the_provider():
    with pytest.raises(SourceError):
        tff.fetch_super_lig(FakeSession(league_route(missing_weeks={3})), TODAY, BESIKTAS)


# --- Süper Kupa -------------------------------------------------------------------------------


def test_season_start_is_july_first():
    assert tff.season_start(date(2026, 9, 20)) == date(2026, 7, 1)
    assert tff.season_start(date(2027, 1, 10)) == date(2026, 7, 1)
    assert tff.season_start(date(2027, 7, 1)) == date(2027, 7, 1)


def test_super_cup_archive_yields_only_besiktas_matches_of_the_current_season():
    (match,) = tff.parse_super_cup(fixture_text("tff_super_cup.html"), since=date(2024, 7, 1), club=BESIKTAS)
    assert (match.home, match.away) == ("Galatasaray", "Beşiktaş")
    assert match.competition == "Süper Kupa"
    assert match.day == date(2024, 8, 3)
    assert not match.time_confirmed  # arşiv tablosunda saat yoktur
    assert match.result == "0-5"
    assert match.venue == "Atatürk Olimpiyat"
    assert match.source == "tff" and match.source_id == "264343"


def test_super_cup_shootout_is_reported_and_other_clubs_are_ignored():
    matches = tff.parse_super_cup(fixture_text("tff_super_cup.html"), since=date(2021, 7, 1), club=BESIKTAS)
    assert [m.day for m in matches] == [date(2024, 8, 3), date(2022, 1, 5)]  # 10.01.2026 Galatasaray-Fenerbahçe yok
    assert matches[1].result == "1-1 (pen. 4-2)"


def test_super_cup_matches_of_earlier_seasons_are_not_published():
    assert tff.parse_super_cup(fixture_text("tff_super_cup.html"), since=date(2025, 7, 1), club=BESIKTAS) == []


def test_super_cup_row_without_a_match_page_still_gets_a_stable_id():
    html = re.sub(r'href="[^"]*macID=264343"', "", fixture_text("tff_super_cup.html"))
    (match,) = tff.parse_super_cup(html, since=date(2024, 7, 1), club=BESIKTAS)
    assert match.source_id == "super-kupa-2024-galatasaray-besiktas"
    assert match.info_url == ""


def test_fetch_super_cup_uses_the_current_football_season():
    session = FakeSession(lambda url, params: fixture_text("tff_super_cup.html") if params.get("pageID") == 329 else None)
    (match,) = tff.fetch_super_cup(session, date(2024, 9, 1), BESIKTAS)
    assert match.day == date(2024, 8, 3)


# --- Ziraat Türkiye Kupası --------------------------------------------------------------------


def test_cup_page_without_besiktas_yields_nothing():
    assert tff.parse_cup(fixture_text("tff_cup_real.html"), BESIKTAS) == []


def test_cup_page_besiktas_row_is_parsed_with_round_and_turkish_date():
    (match,) = tff.parse_cup(fixture_text("tff_cup_with_besiktas.html"), BESIKTAS)
    assert match.competition == "Ziraat Türkiye Kupası"
    assert match.round_label == "2. Tur"
    assert (match.home, match.away) == ("Beşiktaş", "Örnek Spor Kulübü")
    assert match.start == datetime(2026, 10, 7, 20, 30, tzinfo=TURKEY_TZ)
    assert match.source_id == "999001"
    assert match.result == ""


def test_cup_row_without_a_time_is_all_day():
    html = fixture_text("tff_cup_with_besiktas.html").replace("07 Ekim 2026 20:30", "07 Ekim 2026")
    (match,) = tff.parse_cup(html, BESIKTAS)
    assert not match.time_confirmed
    assert match.day == date(2026, 10, 7)


def test_cup_row_with_an_unknown_month_is_skipped_with_a_warning(capsys, monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    html = fixture_text("tff_cup_with_besiktas.html").replace("07 Ekim 2026 20:30", "07 Foo 2026 20:30")
    assert tff.parse_cup(html, BESIKTAS) == []
    assert "tarihi okunamadı" in capsys.readouterr().out


def test_fetch_cup_adds_venue_for_upcoming_match():
    def route(url, params):
        if params.get("pageId") == 29:
            return fixture_text("tff_match_page.html")
        return fixture_text("tff_cup_with_besiktas.html")

    (match,) = tff.fetch_cup(FakeSession(route), TODAY, BESIKTAS)
    assert match.venue == "Diyarbakır Stadyumu, Diyarbakır"
