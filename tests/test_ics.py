from datetime import UTC, date, datetime, timedelta

from helpers import BESIKTAS
from icalendar import Calendar

from club_calendar.ics import escape_text, fold_line, render_calendar, write_if_changed
from club_calendar.models import BASKETBALL, FOOTBALL, TURKEY_TZ, Match

STAMP = datetime(2026, 9, 20, 12, 0, tzinfo=UTC)


def football(**overrides):
    fields = {
        "source": "tff",
        "source_id": "317845",
        "sport": FOOTBALL,
        "competition": "Trendyol Süper Lig",
        "round_label": "7. Hafta",
        "start": datetime(2026, 10, 11, 19, 0, tzinfo=TURKEY_TZ),
        "home": "Beşiktaş",
        "away": "Kocaelispor",
        "venue": "Beşiktaş Park, İstanbul",
        "info_url": "https://www.tff.org/Default.aspx?pageId=29&macId=317845",
    }
    fields.update(overrides)
    return Match(**fields)


def basketball_tbd(**overrides):
    fields = {
        "source": "tbf",
        "source_id": "346320",
        "sport": BASKETBALL,
        "competition": "Türkiye Sigorta Basketbol Süper Ligi",
        "round_label": "6. Hafta",
        "start": date(2026, 10, 31),
        "home": "Beşiktaş",
        "away": "Çayırova Belediyesi",
    }
    fields.update(overrides)
    return Match(**fields)


def parse(text):
    calendar = Calendar.from_ical(text.encode("utf-8"))
    return calendar, [c for c in calendar.walk() if c.name == "VEVENT"]


def test_fold_line_uses_octets_not_characters_and_round_trips():
    line = "DESCRIPTION:" + "Beşiktaş " * 30
    folded = fold_line(line)
    assert all(len(part.encode("utf-8")) <= 75 for part in folded.split("\r\n"))
    assert folded.replace("\r\n ", "") == line


def test_fold_line_never_splits_a_multibyte_character():
    folded = fold_line("SUMMARY:" + "ş" * 100)
    for part in folded.split("\r\n"):
        part.encode("utf-8").decode("utf-8")  # geçerli UTF-8 kalmalı
    assert all(len(part.encode("utf-8")) <= 75 for part in folded.split("\r\n"))


def test_short_lines_are_left_alone():
    assert fold_line("SUMMARY:Beşiktaş - Rakip") == "SUMMARY:Beşiktaş - Rakip"


def test_escape_text_follows_rfc_5545():
    assert escape_text("a,b;c\\d\ne") == "a\\,b\\;c\\\\d\\ne"


def test_calendar_is_valid_and_uses_crlf_only():
    text = render_calendar([football(), basketball_tbd()], "Test", "Açıklama", BESIKTAS, stamp=STAMP)
    assert text.count("\r\n") == text.count("\n")
    calendar, events = parse(text)
    assert calendar["VERSION"] == "2.0"
    assert calendar["X-WR-CALNAME"] == "Test"
    assert len(events) == 2


def test_confirmed_match_is_written_in_utc_with_a_duration():
    _, events = parse(render_calendar([football()], "Test", "", BESIKTAS, stamp=STAMP))
    event = events[0]
    assert event["DTSTART"].dt == datetime(2026, 10, 11, 16, 0, tzinfo=UTC)  # 19:00 TSİ
    assert event["DTEND"].dt - event["DTSTART"].dt == timedelta(hours=2, minutes=15)
    assert str(event["STATUS"]) == "CONFIRMED"
    assert str(event["SUMMARY"]) == "Beşiktaş - Kocaelispor"
    assert str(event["LOCATION"]) == "Beşiktaş Park, İstanbul"


def test_basketball_games_last_two_hours():
    match = basketball_tbd(start=datetime(2026, 10, 11, 18, 0, tzinfo=TURKEY_TZ))
    _, events = parse(render_calendar([match], "Test", "", BESIKTAS, stamp=STAMP))
    assert events[0]["DTEND"].dt - events[0]["DTSTART"].dt == timedelta(hours=2)


def test_unknown_time_becomes_a_tentative_all_day_event_not_a_midnight_match():
    text = render_calendar([basketball_tbd()], "Test", "", BESIKTAS, stamp=STAMP)
    assert "DTSTART;VALUE=DATE:20261031" in text
    assert "DTEND;VALUE=DATE:20261101" in text
    assert "T000000" not in text
    _, events = parse(text)
    assert str(events[0]["STATUS"]) == "TENTATIVE"
    assert str(events[0]["TRANSP"]) == "TRANSPARENT"
    assert "saati henüz açıklanmadı" in str(events[0]["DESCRIPTION"])


def test_categories_are_separate_values():
    text = render_calendar([football()], "Test", "", BESIKTAS, stamp=STAMP)
    assert "CATEGORIES:Beşiktaş,Futbol,Trendyol Süper Lig" in text
    _, events = parse(text)
    assert events[0]["CATEGORIES"].cats == ["Beşiktaş", "Futbol", "Trendyol Süper Lig"]


def test_description_lists_result_source_and_broadcast():
    match = football(result="2-1", broadcast="beIN Sports")
    _, events = parse(render_calendar([match], "Test", "", BESIKTAS, stamp=STAMP))
    description = str(events[0]["DESCRIPTION"])
    assert "Sonuç: 2-1" in description
    assert "Yayın: beIN Sports" in description
    assert "Kaynak: TFF" in description
    assert "macId=317845" in description


def test_events_are_sorted_by_start():
    late = football(source_id="2", start=datetime(2026, 11, 1, 20, 0, tzinfo=TURKEY_TZ))
    early = football(source_id="1", start=datetime(2026, 10, 1, 20, 0, tzinfo=TURKEY_TZ))
    _, events = parse(render_calendar([late, early], "Test", "", BESIKTAS, stamp=STAMP))
    assert [e["DTSTART"].dt.month for e in events] == [10, 11]


def test_empty_calendar_is_still_valid():
    _, events = parse(render_calendar([], "Boş", "", BESIKTAS, stamp=STAMP))
    assert events == []


def test_write_if_changed_ignores_dtstamp_only_differences(tmp_path):
    path = tmp_path / "feed.ics"
    first = render_calendar([football()], "Test", "", BESIKTAS, stamp=STAMP)
    assert write_if_changed(path, first) is True
    later = render_calendar([football()], "Test", "", BESIKTAS, stamp=STAMP + timedelta(days=1))
    assert later != first
    assert write_if_changed(path, later) is False
    assert path.read_bytes() == first.encode("utf-8")


def test_write_if_changed_rewrites_when_content_changes_and_keeps_crlf(tmp_path):
    path = tmp_path / "feed.ics"
    write_if_changed(path, render_calendar([football()], "Test", "", BESIKTAS, stamp=STAMP))
    changed = render_calendar([football(result="1-0")], "Test", "", BESIKTAS, stamp=STAMP)
    assert write_if_changed(path, changed) is True
    raw = path.read_bytes()
    assert b"\r\n" in raw and raw.count(b"\r\n") == raw.count(b"\n")
