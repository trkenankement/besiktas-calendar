"""Read the published league schedule and select the weeks to refresh."""

from __future__ import annotations

import re
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from .. import ics
from ..club import Club
from ..http import SourceError
from ..models import FOOTBALL, SOURCE_LABELS, TURKEY_TZ, Match
from ..names import fold

DEFAULT_LEAGUE_NAME = "Trendyol Süper Lig"
RECENT_DAYS = 7
UPCOMING_DAYS = 21
_LEAGUE_WEEK = re.compile(rf"^Futbol · {DEFAULT_LEAGUE_NAME} · ([0-9]+)\. Hafta$")
_UID = re.compile(r"[0-9a-f]{24}")


def season_start(today: date) -> date:
    return date(today.year if today.month >= 7 else today.year - 1, 7, 1)


def recent_weeks(history: dict[int, Match], today: date) -> list[int]:
    first = today - timedelta(days=RECENT_DAYS)
    last = today + timedelta(days=UPCOMING_DAYS)
    return sorted(week for week, match in history.items() if first <= match.day <= last)


def _unescape(value: str) -> str:
    return re.sub(r"\\([,;\\nN])", lambda m: "\n" if m[1] in "nN" else m[1], value)


def read_league_history(path: Path, today: date, club: Club) -> dict[int, Match]:
    matches: dict[int, Match] = {}
    start_of_season = season_start(today)
    for uid, event in ics._previous_events(path.read_text(encoding="utf-8")).items():
        description = _unescape(ics._property(event, "DESCRIPTION") or "").splitlines()
        week_label = _LEAGUE_WEEK.fullmatch(description[0]) if description else None
        if week_label is None:
            continue
        timestamp = ics._property(event, "DTSTART")
        if timestamp:
            start = datetime.strptime(timestamp, "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC).astimezone(TURKEY_TZ)
        else:
            start = datetime.strptime(ics._property(event, "DTSTART;VALUE=DATE") or "", "%Y%m%d").date()
        day = start.date() if isinstance(start, datetime) else start
        if not start_of_season <= day < date(start_of_season.year + 1, 7, 1):
            continue
        week = int(week_label[1])
        home, sep, away = _unescape(ics._property(event, "SUMMARY") or "").partition(" - ")
        digest, _, domain = uid.partition("@")
        if not sep or not home or not away or week in matches or not _UID.fullmatch(digest) or domain != club.uid_domain:
            raise SourceError("Önceki Süper Lig takviminde geçersiz veya mükerrer maç kaydı")
        details = dict(line.split(": ", 1) for line in description[1:] if ": " in line)
        label, _, url = details.get("Kaynak", "").partition(" — ")
        source = next((key for key in ("tff", "bein") if SOURCE_LABELS[key] == label), "")
        if not source:
            raise SourceError("Önceki Süper Lig takvimindeki kaynak tanınamadı")
        matches[week] = Match(
            source=source, source_id=str(week), sport=FOOTBALL, competition=DEFAULT_LEAGUE_NAME,
            round_label=f"{week}. Hafta", start=start, home=home, away=away, calendar_uid=digest,
            venue=_unescape(ics._property(event, "LOCATION") or ""), result=details.get("Sonuç", ""),
            broadcast=details.get("Yayın", ""), info_url=url,
        )
    return matches


def _team_key(name: str) -> str:
    # Only documented display differences between the two fixture sources.
    name = fold(name)
    return {"gaziantep futbol kulubu": "gaziantep fk", "istanbul basaksehir fk": "istanbul basaksehir"}.get(name, name)


def same_teams(match: Match, home: str, away: str) -> bool:
    return (_team_key(match.home), _team_key(match.away)) == (_team_key(home), _team_key(away))
