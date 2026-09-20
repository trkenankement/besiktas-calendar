"""TBF (Türkiye Basketbol Federasyonu) web API'si: Basketbol Süper Ligi ve erkek kupaları."""

from __future__ import annotations

import re
from dataclasses import replace
from datetime import date, datetime
from typing import Any

import requests

from ..club import Club
from ..console import warn
from ..http import SourceError, get_json
from ..models import BASKETBALL, Match, kickoff_or_day
from ..names import display_name, join_parts
from ._common import guard_skipped

API_URL = "https://miniappapi.tbf.org.tr/webapi-service/api"
LEAGUE_PREFIX = "bsl"
# Erkekler: Cumhurbaşkanlığı Kupası, Türkiye Kupası, Federasyon Kupası
CUP_PREFIXES = ("cbek", "etk", "efk")

_SEASON_SUFFIX = re.compile(r"\s*\d{4}-\d{4}\s*$")
_GENERIC_ROUND = re.compile(r"\d+\.\s*Hafta")


def _score(side: dict[str, Any]) -> str:
    return str(side.get("score") or "").strip()


def _competition_name(row: dict[str, Any]) -> str:
    name = (row.get("activityDisplayName") or "").strip()
    if not name:  # kupa kayıtlarında yalnızca "Erkekler Türkiye Kupası 2026-2027" gibi bir ad gelir
        name = re.sub(r"^Erkekler\s+", "", _SEASON_SUFFIX.sub("", row.get("activityName") or ""))
    return name or "Basketbol"


def parse_row(row: dict[str, Any], club: Club) -> Match | None:
    """Maçı ortak biçime çevirir; tarihi yoksa (ör. ertelenmiş) uyarı verip None döndürür."""
    home, away = row["homeTeam"], row["awayTeam"]
    try:
        moment = datetime.fromisoformat(row["matchDate"])  # Türkiye yerel saati, saat dilimsiz
    except (KeyError, TypeError, ValueError):
        warn(f"TBF: '{home.get('name')} - {away.get('name')}' maçının tarihi yok ({row.get('matchDate')!r}); bu maç takvime eklenmedi")
        return None
    home_score, away_score = _score(home), _score(away)
    return Match(
        source="tbf",
        source_id=str(int(row["matchId"])),
        sport=BASKETBALL,
        competition=_competition_name(row),
        round_label=row.get("week") or "",
        start=kickoff_or_day(moment.date(), moment.hour, moment.minute),
        home=club.team_name(home["name"]),
        away=club.team_name(away["name"]),
        venue=join_parts(display_name(row.get("salonAdi") or ""), display_name(row.get("il") or "")),
        result=f"{home_score}-{away_score}" if home_score and away_score else "",
        broadcast=row.get("broadcastChannel") or "",
    )


def _seasons(session: requests.Session, prefix: str) -> list[dict[str, Any]]:
    data = get_json(session, f"{API_URL}/League/get-leagues-and-seasons-by-prefix", prefix=prefix).get("data") or []
    return sorted(data, key=lambda s: s["sezon_ID"], reverse=True)


def _weeks(session: requests.Session, league_id: int, season_id: int) -> list[dict[str, Any]]:
    return get_json(session, f"{API_URL}/League/get-league-weeks", seasonId=season_id, leagueId=league_id).get("data") or []


def _in_season(row: dict[str, Any], season_id: int) -> bool:
    """Kupa sorguları önceki yılların maçlarını da döndürür; yalnızca güncel sezon alınır."""
    try:
        return int(float(row["seasonId"])) == season_id
    except (KeyError, TypeError, ValueError):
        return True  # sezon bilgisi yoksa sorgunun kendisine güven


def _club_matches(session: requests.Session, club: Club, league_id: int, season_id: int, weeks: list[dict[str, Any]]) -> list[Match]:
    matches: list[Match] = []
    skipped = 0
    for week in weeks:
        params: dict[str, Any] = {"ActivityId": league_id, "WeekFilter": week["sezon_Hafta"], "Page": 1, "PageSize": -1}
        half = week.get("devre_Deger")
        if int(week.get("devre_ID") or 1) not in (1, 2) and half:
            params["HalfValue"] = half
        rows = get_json(session, f"{API_URL}/Match/get-all-matches-for-filter", **params).get("data") or []
        for row in rows:
            teams = (row.get("homeTeam") or {}).get("name", ""), (row.get("awayTeam") or {}).get("name", "")
            if not _in_season(row, season_id) or not any(club.matches(name) for name in teams):
                continue
            match = parse_row(row, club)
            if match is None:
                skipped += 1
            else:
                matches.append(match)
    guard_skipped("TBF", skipped, len(matches))
    if len(weeks) == 1:  # tek turluk turnuvalarda "1. Hafta" etiketi anlamsız
        matches = [replace(m, round_label="") if _GENERIC_ROUND.fullmatch(m.round_label) else m for m in matches]
    return matches


def _current_season(session: requests.Session) -> tuple[int, int, list[dict[str, Any]]]:
    """TBF'nin güncel sezonu: Basketbol Süper Ligi'nin en yeni sezonu (programı açıklanmadıysa bir öncekisi)."""
    seasons = _seasons(session, LEAGUE_PREFIX)
    if not seasons:
        raise SourceError("TBF lig/sezon listesi boş döndü")
    for season in seasons[:2]:
        league_id, season_id = int(season["faaliyet_ID"]), int(season["sezon_ID"])
        weeks = _weeks(session, league_id, season_id)
        if weeks:
            return league_id, season_id, weeks
    raise SourceError("TBF: Basketbol Süper Ligi için hafta listesi bulunamadı")


def fetch_bsl(session: requests.Session, today: date, club: Club) -> list[Match]:
    league_id, season_id, weeks = _current_season(session)
    return _club_matches(session, club, league_id, season_id, weeks)


def fetch_cups(session: requests.Session, today: date, club: Club) -> list[Match]:
    """Cumhurbaşkanlığı, Türkiye ve Federasyon kupaları; turnuva bu sezon için henüz oluşturulmadıysa atlanır."""
    _, season_id, _ = _current_season(session)
    matches: list[Match] = []
    for prefix in CUP_PREFIXES:
        edition = next((s for s in _seasons(session, prefix) if int(s["sezon_ID"]) == season_id), None)
        if edition is None:
            continue
        league_id = int(edition["faaliyet_ID"])
        matches += _club_matches(session, club, league_id, season_id, _weeks(session, league_id, season_id))
    return matches
