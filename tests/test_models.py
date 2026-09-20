import re
from datetime import UTC, date, datetime, timedelta

from club_calendar.models import BASKETBALL, FOOTBALL, TURKEY_TZ, Match, kickoff_or_day


def make_match(**overrides):
    fields = {
        "source": "tff",
        "source_id": "1",
        "sport": FOOTBALL,
        "competition": "Trendyol Süper Lig",
        "round_label": "1. Hafta",
        "start": datetime(2026, 10, 11, 19, 0, tzinfo=TURKEY_TZ),
        "home": "Beşiktaş",
        "away": "Kocaelispor",
    }
    fields.update(overrides)
    return Match(**fields)


def test_turkey_is_a_fixed_utc_plus_three():
    assert TURKEY_TZ.utcoffset(None) == timedelta(hours=3)


def test_kickoff_or_day_returns_a_datetime_when_the_time_is_known():
    assert kickoff_or_day(date(2026, 10, 11), 19, 30) == datetime(2026, 10, 11, 19, 30, tzinfo=TURKEY_TZ)


def test_kickoff_or_day_treats_missing_time_and_midnight_placeholder_as_unknown():
    assert kickoff_or_day(date(2026, 10, 31), None, None) == date(2026, 10, 31)
    assert kickoff_or_day(date(2026, 10, 31), 0, 0) == date(2026, 10, 31)


def test_a_real_match_just_after_midnight_is_still_timed():
    assert isinstance(kickoff_or_day(date(2026, 10, 31), 0, 15), datetime)


def test_uid_is_stable_when_date_and_time_change():
    original = make_match()
    moved = make_match(start=datetime(2026, 10, 12, 20, 0, tzinfo=TURKEY_TZ))
    assert original.uid == moved.uid
    assert re.fullmatch(r"[0-9a-f]{24}", original.uid)


def test_uid_differs_between_matches_and_sources():
    assert make_match(source_id="1").uid != make_match(source_id="2").uid
    assert make_match(source="tff").uid != make_match(source="uefa").uid


def test_day_uses_turkey_time_not_utc():
    late = make_match(start=datetime(2026, 10, 11, 23, 30, tzinfo=TURKEY_TZ))
    assert late.start.astimezone(UTC).date() == date(2026, 10, 11)
    assert late.day == date(2026, 10, 11)
    early = make_match(start=datetime(2026, 10, 12, 0, 30, tzinfo=TURKEY_TZ))
    assert early.start.astimezone(UTC).date() == date(2026, 10, 11)
    assert early.day == date(2026, 10, 12)


def test_all_day_match_is_not_time_confirmed():
    match = make_match(sport=BASKETBALL, start=date(2026, 10, 31))
    assert not match.time_confirmed
    assert match.day == date(2026, 10, 31)


def test_sort_key_orders_by_day_then_time_with_all_day_first():
    timed = make_match(source_id="a", start=datetime(2026, 10, 11, 18, 0, tzinfo=TURKEY_TZ))
    later = make_match(source_id="b", start=datetime(2026, 10, 11, 21, 0, tzinfo=TURKEY_TZ))
    all_day = make_match(source_id="c", start=date(2026, 10, 11))
    assert sorted([later, timed, all_day], key=lambda m: m.sort_key) == [all_day, timed, later]
