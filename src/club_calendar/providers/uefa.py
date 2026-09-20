"""UEFA resmi maç API'si: Şampiyonlar Ligi, Avrupa Ligi ve Konferans Ligi."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

import requests

from ..club import Club
from ..console import warn
from ..http import SourceError, get_json
from ..models import FOOTBALL, TURKEY_TZ, Match
from ..names import join_parts
from ._common import guard_skipped

API_URL = "https://match.uefa.com/v5/matches"
PAGE_SIZE = 100
COMPETITIONS = (
    ("1", "UEFA Şampiyonlar Ligi"),
    ("14", "UEFA Avrupa Ligi"),
    ("2019", "UEFA Konferans Ligi"),
)
ROUND_NAMES_TR = {
    "First qualifying round": "1. Ön Eleme Turu",
    "Second qualifying round": "2. Ön Eleme Turu",
    "Third qualifying round": "3. Ön Eleme Turu",
    "Play-Offs": "Play-Off",
    "Knockout phase play-offs": "Play-Off Turu",
    "Round of 16": "Son 16 Turu",
    "Quarter-finals": "Çeyrek Final",
    "Semi-finals": "Yarı Final",
    "Final": "Final",
}


def season_year_for(today: date) -> int:
    """UEFA sezonu bitiş yılıyla adlandırır (2026/27 -> 2027); yeni sezon temmuzda başlar."""
    return today.year + 1 if today.month >= 7 else today.year


def _translated(entity: dict[str, Any], key: str) -> str:
    return ((entity.get("translations") or {}).get(key) or {}).get("EN") or ""


def _round_label(item: dict[str, Any]) -> str:
    meta = (item.get("round") or {}).get("metaData") or {}
    name = meta.get("name") or ""
    if meta.get("type") == "GROUP_STANDINGS" or name == "League Phase":
        number = (item.get("matchday") or {}).get("sequenceNumber")
        return f"Lig Aşaması {number}. Hafta" if number else "Lig Aşaması"
    return ROUND_NAMES_TR.get(name, name)


def _result(item: dict[str, Any]) -> str:
    if item.get("status") != "FINISHED":
        return ""
    score = item.get("score") or {}
    total = score.get("total") or {}
    if total.get("home") is None or total.get("away") is None:
        return ""
    result = f"{total['home']}-{total['away']}"
    penalty = score.get("penalty") or {}
    if penalty.get("home") is not None and penalty.get("away") is not None:
        result += f" (pen. {penalty['home']}-{penalty['away']})"
    return result


def _kickoff(item: dict[str, Any]) -> date | datetime | None:
    """Saat belliyse Türkiye saatiyle tam zaman, yalnızca tarih belliyse tarih; hiçbiri yoksa None."""
    kickoff = item.get("kickOffTime") or {}
    try:
        if kickoff.get("dateTime"):
            return datetime.fromisoformat(kickoff["dateTime"].replace("Z", "+00:00")).astimezone(TURKEY_TZ)
        if kickoff.get("date"):
            return date.fromisoformat(kickoff["date"])
    except (TypeError, ValueError):
        pass
    return None


def parse_match(item: dict[str, Any], competition: str, club: Club) -> Match | None:
    """Maçı ortak biçime çevirir; tarihi okunamıyorsa uyarı verip None döndürür."""
    start = _kickoff(item)
    if start is None:
        warn(f"UEFA: {item.get('id')} numaralı maçın tarihi okunamadı; bu maç takvime eklenmedi")
        return None
    stadium = item.get("stadium") or {}
    return Match(
        source="uefa",
        source_id=str(item["id"]),
        sport=FOOTBALL,
        competition=competition,
        round_label=_round_label(item),
        start=start,
        home=club.team_name(item["homeTeam"]["internationalName"]),
        away=club.team_name(item["awayTeam"]["internationalName"]),
        venue=join_parts(_translated(stadium, "name"), _translated(stadium.get("city") or {}, "name")),
        result=_result(item),
    )


def fetch(session: requests.Session, today: date, club: Club) -> list[Match]:
    season_year = season_year_for(today)
    matches: list[Match] = []
    skipped = 0
    for competition_id, competition in COMPETITIONS:
        offset = 0
        while True:
            page = get_json(
                session,
                API_URL,
                competitionId=competition_id,
                seasonYear=season_year,
                teamId=club.uefa_team_id,
                limit=PAGE_SIZE,
                offset=offset,
                order="ASC",
            )
            if not isinstance(page, list):
                raise SourceError(f"UEFA beklenmeyen yanıt biçimi döndürdü ({type(page).__name__})")
            for item in page:
                match = parse_match(item, competition, club)
                if match is None:
                    skipped += 1
                else:
                    matches.append(match)
            if len(page) < PAGE_SIZE:
                break
            offset += PAGE_SIZE
    guard_skipped("UEFA", skipped, len(matches))
    return matches
