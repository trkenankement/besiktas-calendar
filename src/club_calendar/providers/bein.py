"""Keep the published Süper Lig fixture current if TFF cannot be read."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from ..club import Club
from ..console import log
from ..http import SourceError, get_html, get_json
from ..models import TURKEY_TZ, Match
from ..names import display_name
from ._league_history import read_league_history, recent_weeks, same_teams, season_start

FIXTURE_URL = "https://www.beinsports.com.tr/lig/super-lig/fikstur"
API_URL = "https://www.beinsports.com.tr/api/fixture"
ORG_ID = 18


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
    if row["round"] != week or not same_teams(old, home, away):
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


def fetch_super_lig(
    session: requests.Session, today: date, club: Club, previous: Path, *, recent: bool = False,
) -> list[Match]:
    try:
        history = read_league_history(previous, today, club)
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
        selected = recent_weeks(history, today) if recent else rounds
        log(f"beIN SPORTS · Süper Lig: {len(selected)}/{len(rounds)} hafta sorgulanıyor.")
        matches = dict(history)
        for week in selected:
            rows = get_json(session, API_URL, a="l", o=ORG_ID, s=season["id"], r=week, st=0)["Data"]
            if not isinstance(rows, list) or not 8 <= len(rows) <= 12:
                raise SourceError(f"beIN SPORTS: {week}. haftanın fikstürü eksik veya geçersiz")
            matches[week] = _updated_match(history[week], rows, week, club)
        return list(matches.values())
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        raise SourceError(f"beIN SPORTS: fikstür veya önceki takvim okunamadı: {exc}") from exc
