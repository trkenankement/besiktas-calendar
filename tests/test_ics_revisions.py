"""Event revision regressions through the real multi-feed output pipeline."""

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

import pytest
from icalendar import Calendar

from club_calendar import build, ics
from club_calendar.club import get_club
from club_calendar.feeds import feeds_for
from club_calendar.models import BASKETBALL, FOOTBALL, Match

FIRST = datetime(2026, 11, 9, 12, tzinfo=UTC)
SECOND = FIRST + timedelta(days=1)


def fixtures():
    return [
        Match("tff", "1", FOOTBALL, "Lig", "1", FIRST + timedelta(days=3), "Ev", "Rakip", venue="İstanbul " * 30),
        Match("uefa", "2", FOOTBALL, "Avrupa", "2", FIRST + timedelta(days=4), "Ev", "Rakip 2"),
        Match("tbf", "3", BASKETBALL, "Basketbol", "3", date(2026, 11, 20), "Ev", "Rakip 3"),
        Match("euroleague", "4", BASKETBALL, "EuroLeague", "4", FIRST + timedelta(days=5), "Ev", "Rakip 4"),
    ]


def events(raw):
    return {str(e["UID"]): e for e in Calendar.from_ical(raw).walk("VEVENT")}


def snapshots(path, club):
    return {feed.filename: (path / feed.filename).read_bytes() for feed in feeds_for(club)}


@pytest.mark.parametrize("club_key", ["galatasaray", "fenerbahce", "besiktas"])
@pytest.mark.parametrize("scenario", ["result", "time", "confirmed_time", "new", "deleted", "unchanged"])
def test_only_changed_events_receive_new_revision_metadata(tmp_path, club_key, scenario):
    club = get_club(club_key)
    original = fixtures()
    build.write_outputs(tmp_path, original, FIRST, club)
    before = snapshots(tmp_path, club)
    mtimes = {name: (tmp_path / name).stat().st_mtime_ns for name in before}
    updated = list(original)
    target = original[0]
    if scenario == "result":
        updated[0] = replace(target, result="2-1")
    elif scenario == "time":
        updated[0] = replace(target, start=target.start + timedelta(hours=2))
    elif scenario == "confirmed_time":
        target = original[2]
        updated[2] = replace(target, start=datetime(2026, 11, 20, 17, tzinfo=UTC))
    elif scenario == "new":
        target = replace(target, source_id="99")
        updated.append(target)
    elif scenario == "deleted":
        updated.remove(target)
    uid = f"{target.uid}@{club.uid_domain}"
    changed = build.write_outputs(tmp_path, updated, SECOND, club)
    after = snapshots(tmp_path, club)
    for name in before:
        old, new = events(before[name]), events(after[name])
        feed = next(f for f in feeds_for(club) if f.filename == name)
        assert set(new) == {f"{m.uid}@{club.uid_domain}" for m in feed.select(updated)}
        for key in old.keys() & new.keys():
            if key == uid and scenario in {"result", "time", "confirmed_time"}:
                assert new[key]["DTSTAMP"].dt == SECOND
                assert new[key]["LAST-MODIFIED"].dt == SECOND
                assert int(new[key]["SEQUENCE"]) == 1
                assert new[key]["UID"] == old[key]["UID"]
                if scenario == "result":
                    assert "Sonuç: 2-1" in str(new[key]["DESCRIPTION"])
                else:
                    assert new[key]["DTSTART"].dt == next(m.start for m in updated if m.uid == target.uid)
            else:
                assert new[key].to_ical() == old[key].to_ical()
        if scenario == "new" and uid in new:
            assert int(new[uid]["SEQUENCE"]) == 0
            assert new[uid]["DTSTAMP"].dt == new[uid]["LAST-MODIFIED"].dt == SECOND
        if before[name] == after[name]:
            assert changed[name] is False
            assert (tmp_path / name).stat().st_mtime_ns == mtimes[name]
        assert b"METHOD:PUBLISH\r\n" in after[name]
        assert after[name].count(b"\r\n") == after[name].count(b"\n")
    build.write_outputs(tmp_path, updated, SECOND + timedelta(days=1), club)
    assert snapshots(tmp_path, club) == after


@pytest.mark.parametrize("club_key", ["galatasaray", "fenerbahce", "besiktas"])
def test_legacy_migration_does_not_touch_unchanged_events(tmp_path, club_key):
    club, matches = get_club(club_key), fixtures()
    build.write_outputs(tmp_path, matches, FIRST, club)
    for feed in feeds_for(club):
        path = tmp_path / feed.filename
        raw = path.read_bytes()
        raw = b"\r\n".join(line for line in raw.split(b"\r\n") if not line.startswith((b"LAST-MODIFIED:", b"SEQUENCE:")))
        path.write_bytes(raw)
    legacy = snapshots(tmp_path, club)
    build.write_outputs(tmp_path, matches, SECOND, club)
    assert snapshots(tmp_path, club) == legacy
    build.write_outputs(tmp_path, [replace(matches[0], result="1-0"), *matches[1:]], SECOND, club)
    for name, raw in snapshots(tmp_path, club).items():
        old, new = events(legacy[name]), events(raw)
        for uid in new:
            if uid.startswith(matches[0].uid):
                assert int(new[uid]["SEQUENCE"]) == 1
                assert new[uid]["LAST-MODIFIED"].dt == SECOND
            else:
                assert new[uid].to_ical() == old[uid].to_ical()
                assert "LAST-MODIFIED" not in new[uid] and "SEQUENCE" not in new[uid]


@pytest.mark.parametrize("index", range(4))
def test_all_providers_and_repeated_revisions(index):
    club, matches = get_club("besiktas"), fixtures()
    text = ics.render_calendar(matches, "Test", "", club, stamp=FIRST)
    uid = f"{matches[index].uid}@{club.uid_domain}"
    for sequence, result in enumerate(["1-0", "2-0"], start=1):
        matches[index] = replace(matches[index], result=result)
        text = ics.render_calendar(matches, "Test", "", club, stamp=FIRST, previous=text)
        event = events(text)[uid]
        assert int(event["SEQUENCE"]) == sequence
        assert event["DTSTAMP"].dt == FIRST + timedelta(seconds=sequence)
        assert event["LAST-MODIFIED"].dt == event["DTSTAMP"].dt


def test_invalid_history_does_not_partially_overwrite_feeds(tmp_path):
    club, matches = get_club("besiktas"), fixtures()
    build.write_outputs(tmp_path, matches, FIRST, club)
    (tmp_path / feeds_for(club)[-1].filename).write_text("broken", encoding="utf-8")
    before = snapshots(tmp_path, club)
    with pytest.raises(ValueError, match="Invalid previous calendar"):
        build.write_outputs(tmp_path, [replace(matches[0], result="1-0"), *matches[1:]], SECOND, club)
    assert snapshots(tmp_path, club) == before


@pytest.mark.parametrize("bad", ["duplicate", "timestamp", "sequence", "truncated"])
def test_invalid_event_history_is_rejected(bad):
    club = get_club("besiktas")
    text = ics.render_calendar(fixtures()[:1], "Test", "", club, stamp=FIRST)
    if bad == "duplicate":
        block = text[text.index("BEGIN:VEVENT"):text.index("END:VEVENT") + len("END:VEVENT\r\n")]
        text = text.replace("END:VCALENDAR", block + "END:VCALENDAR")
    elif bad == "timestamp":
        text = text.replace("DTSTAMP:20261109T120000Z", "DTSTAMP:invalid")
    elif bad == "sequence":
        text = text.replace("SEQUENCE:0", "SEQUENCE:-1")
    else:
        text = text.replace("END:VEVENT\r\n", "")
    with pytest.raises(ValueError):
        ics.render_calendar(fixtures(), "Test", "", club, stamp=SECOND, previous=text)


def test_explicit_metadata_changes_are_not_ignored_by_writer(tmp_path):
    path = tmp_path / "feed.ics"
    text = ics.render_calendar(fixtures(), "Test", "", get_club("besiktas"), stamp=FIRST)
    assert ics.write_if_changed(path, text)
    assert ics.write_if_changed(path, text.replace("SEQUENCE:0", "SEQUENCE:1"))
