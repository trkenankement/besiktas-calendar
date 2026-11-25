"""Keep the published Süper Lig fixture current if TFF cannot be read."""

from __future__ import annotations

import json
import re
from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from .. import ics
from ..club import Club
from ..http import SourceError, get_html, get_json
from ..models import FOOTBALL, SOURCE_LABELS, TURKEY_TZ, Match
from ..names import display_name, fold
from .tff import DEFAULT_LEAGUE_NAME, season_start

FIXTURE_URL = "https://www.beinsports.com.tr/lig/super-lig/fikstur"
API_URL = "https://www.beinsports.com.tr/api/fixture"
ORG_ID = 18
_LEAGUE_WEEK = re.compile(rf"^Futbol · {DEFAULT_LEAGUE_NAME} · ([0-9]+)\. Hafta$")
_UID = re.compile(r"[0-9a-f]{24}")


def _unescape(value: str) -> str:
    return re.sub(r"\\([,;\\nN])", lambda m: "\n" if m[1] in "nN" else m[1], value)


def _previous_matches(path: Path, today: date, club: Club) -> dict[int, Match]:
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


def _updated_match(old: Match, rows: list[dict], week: int, club: Club) -> Match:
    candidates = [
        row for row in rows
        if club.matches(row["homeTeam"]["name"]) or club.matches(row["awayTeam"]["name"])
    ]
    if len(candidates) != 1:
        raise SourceError(f"beIN SPORTS: {week}. haftada kulübün tek maçı bulunamadı")
    row = candidates[0]
    home = club.team_name(row["homeTeam"]["name"])
    away = club.team_name(row["awayTeam"]["name"])
    if row["round"] != week or (_team_key(home), _team_key(away)) != (_team_key(old.home), _team_key(old.away)):
        raise SourceError(f"beIN SPORTS: {week}. haftanın eşleşmesi önceki takvimden farklı")

    kickoff = datetime.fromisoformat(row["matchDate"])
    if kickoff.tzinfo is None:
        kickoff = kickoff.replace(tzinfo=UTC)  # beIN API sends these ISO match dates in UTC.
    kickoff = kickoff.astimezone(TURKEY_TZ)
    state = row["liteMatchStatus"]
    if state not in {"matchEnded", "preMatch"} or (old.result and state == "preMatch"):
        return old

    # Unscheduled rounds give every fixture the same default kickoff.
    scheduled = len({item["matchDate"] for item in rows}) > 1
    start = kickoff if state == "matchEnded" or scheduled else old.start
    if old.result and old.time_confirmed:
        # TFF records actual past kickoffs; beIN can still show the scheduled time.
        start = old.start
    result = old.result
    if state == "matchEnded":
        score = row["score"]
        home_score, away_score = score["homeScore"], score["awayScore"]
        if type(home_score) is not int or type(away_score) is not int or min(home_score, away_score) < 0:
            raise SourceError(f"beIN SPORTS: {week}. haftanın maç sonucu geçersiz")
        result = f"{home_score}-{away_score}"
    venue = old.venue
    if start != old.start or result != old.result:
        venue = display_name(row["venue"]) or venue
        return replace(old, source="bein", start=start, result=result, venue=venue, info_url=FIXTURE_URL)
    return old


def fetch_super_lig(session: requests.Session, today: date, club: Club, previous: Path) -> list[Match]:
    try:
        history = _previous_matches(previous, today, club)
        soup = BeautifulSoup(get_html(session, FIXTURE_URL, encoding="utf-8"), "html.parser")
        script = soup.find("script", id="__NEXT_DATA__", type="application/json")
        if script is None or script.string is None:
            raise SourceError("beIN SPORTS: fikstür bilgisi bulunamadı")
        fixture = json.loads(script.string)["props"]["pageProps"]["orgData"]
        season = fixture["activeSeason"]
        year = season_start(today).year
        if fixture["activeOrganization"]["id"] != ORG_ID or season["name"] != f"{year}/{year + 1}":
            raise SourceError("beIN SPORTS: lig veya sezon doğrulanamadı")
        rounds = [item["round"] for item in fixture["rounds"]]
        if not 30 <= len(rounds) <= 50 or sorted(rounds) != list(range(1, len(rounds) + 1)):
            raise SourceError("beIN SPORTS: hafta listesi eksik veya geçersiz")
        if history.keys() != set(rounds):
            raise SourceError("Yedek fikstür için aynı sezonun eksiksiz yayımlanmış Süper Lig takvimi gerekli")
        matches = []
        for week in rounds:
            rows = get_json(session, API_URL, a="l", o=ORG_ID, s=season["id"], r=week, st=0)["Data"]
            if not isinstance(rows, list) or not 8 <= len(rows) <= 12:
                raise SourceError(f"beIN SPORTS: {week}. haftanın fikstürü eksik veya geçersiz")
            matches.append(_updated_match(history[week], rows, week, club))
        return matches
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        raise SourceError(f"beIN SPORTS: fikstür veya önceki takvim okunamadı: {exc}") from exc
