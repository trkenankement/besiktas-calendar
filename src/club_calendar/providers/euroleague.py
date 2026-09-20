"""EuroLeague Basketball resmi API'si: EuroLeague ve EuroCup."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

import requests

from ..club import Club
from ..console import warn
from ..http import SourceError, get_json
from ..models import BASKETBALL, TURKEY_TZ, Match
from ..names import english_title
from ._common import guard_skipped

API_URL = "https://api-live.euroleague.net/v2/competitions"
COMPETITIONS = (("E", "EuroLeague"), ("U", "EuroCup"))


def _club_name(side: dict[str, Any], own: Club) -> str:
    club = side.get("club") or {}
    if own.euroleague_code and club.get("code") == own.euroleague_code:
        return own.name
    return club.get("abbreviatedName") or club.get("name") or "?"


def _round_label(game: dict[str, Any]) -> str:
    phase = game.get("phaseType") or {}
    if phase.get("code") == "RS" and game.get("round"):
        return f"{game['round']}. Hafta"
    return game.get("roundName") or phase.get("name") or ""


def parse_game(game: dict[str, Any], competition: str, club: Club) -> Match | None:
    """Maçı ortak biçime çevirir; tarihi okunamıyorsa uyarı verip None döndürür."""
    try:
        kickoff = datetime.fromisoformat(game["utcDate"].replace("Z", "+00:00")).astimezone(TURKEY_TZ)
    except (KeyError, AttributeError, TypeError, ValueError):
        warn(f"EuroLeague: {game.get('identifier') or game.get('id')} maçının tarihi okunamadı; bu maç takvime eklenmedi")
        return None
    confirmed = bool(game.get("confirmedDate")) and bool(game.get("confirmedHour"))
    local, road = game["local"], game["road"]
    result = f"{local.get('score')}-{road.get('score')}" if game.get("played") else ""
    return Match(
        source="euroleague",
        source_id=str(game.get("identifier") or game["id"]),
        sport=BASKETBALL,
        competition=competition,
        round_label=_round_label(game),
        start=kickoff if confirmed else kickoff.date(),
        home=_club_name(local, club),
        away=_club_name(road, club),
        venue=english_title((game.get("venue") or {}).get("name") or ""),
        result=result,
    )


def _current_season(session: requests.Session, code: str, today: date) -> str | None:
    seasons = get_json(session, f"{API_URL}/{code}/seasons").get("data") or []
    started = [s for s in seasons if str(s.get("startDate", ""))[:10] <= today.isoformat()]
    if not started:
        return None
    return max(started, key=lambda s: s.get("year", 0))["code"]


def fetch(session: requests.Session, today: date, club: Club) -> list[Match]:
    if not club.euroleague_code:  # kulüp EuroLeague/EuroCup'ta oynamıyor
        return []
    matches: list[Match] = []
    skipped = 0
    for code, competition in COMPETITIONS:
        season = _current_season(session, code, today)
        if season is None:
            continue
        payload = get_json(session, f"{API_URL}/{code}/seasons/{season}/games", teamCode=club.euroleague_code)
        if not isinstance(payload, dict):
            raise SourceError("EuroLeague beklenmeyen yanıt biçimi döndürdü")
        for game in payload.get("data") or []:
            match = parse_game(game, competition, club)
            if match is None:
                skipped += 1
            else:
                matches.append(match)
    guard_skipped("EuroLeague", skipped, len(matches))
    return matches
