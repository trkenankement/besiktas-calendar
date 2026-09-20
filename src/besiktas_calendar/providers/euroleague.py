"""EuroLeague Basketball resmi API'si: EuroLeague ve EuroCup."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

import requests

from ..http import SourceError, get_json
from ..models import BASKETBALL, TURKEY_TZ, Match
from ..names import english_title

API_URL = "https://api-live.euroleague.net/v2/competitions"
BESIKTAS_CODE = "BES"
COMPETITIONS = (("E", "EuroLeague"), ("U", "EuroCup"))


def _club_name(side: dict[str, Any]) -> str:
    club = side.get("club") or {}
    if club.get("code") == BESIKTAS_CODE:
        return "Beşiktaş"
    return club.get("abbreviatedName") or club.get("name") or "?"


def _round_label(game: dict[str, Any]) -> str:
    phase = game.get("phaseType") or {}
    if phase.get("code") == "RS" and game.get("round"):
        return f"{game['round']}. Hafta"
    return game.get("roundName") or phase.get("name") or ""


def parse_game(game: dict[str, Any], competition: str) -> Match:
    kickoff = datetime.fromisoformat(game["utcDate"].replace("Z", "+00:00")).astimezone(TURKEY_TZ)
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
        home=_club_name(local),
        away=_club_name(road),
        venue=english_title((game.get("venue") or {}).get("name") or ""),
        result=result,
    )


def _current_season(session: requests.Session, code: str, today: date) -> str | None:
    seasons = get_json(session, f"{API_URL}/{code}/seasons").get("data") or []
    started = [s for s in seasons if str(s.get("startDate", ""))[:10] <= today.isoformat()]
    if not started:
        return None
    return max(started, key=lambda s: s.get("year", 0))["code"]


def fetch(session: requests.Session, today: date) -> list[Match]:
    matches: list[Match] = []
    for code, competition in COMPETITIONS:
        season = _current_season(session, code, today)
        if season is None:
            continue
        payload = get_json(session, f"{API_URL}/{code}/seasons/{season}/games", teamCode=BESIKTAS_CODE)
        if not isinstance(payload, dict):
            raise SourceError("EuroLeague beklenmeyen yanıt biçimi döndürdü")
        matches += [parse_game(game, competition) for game in payload.get("data") or []]
    return matches
