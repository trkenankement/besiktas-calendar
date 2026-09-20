"""TBF (Türkiye Basketbol Federasyonu) web API'si: Basketbol Süper Ligi."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

import requests

from ..http import SourceError, get_json
from ..models import BASKETBALL, Match, kickoff_or_day
from ..names import display_name, is_besiktas, join_parts

API_URL = "https://miniappapi.tbf.org.tr/webapi-service/api"
LEAGUE_PREFIX = "bsl"


def _score(side: dict[str, Any]) -> str:
    return str(side.get("score") or "").strip()


def parse_row(row: dict[str, Any]) -> Match:
    if not row.get("matchDate"):
        raise SourceError(f"TBF: {row.get('matchId')} numaralı maçın tarihi yok")
    moment = datetime.fromisoformat(row["matchDate"])  # Türkiye yerel saati, saat dilimsiz
    home, away = row["homeTeam"], row["awayTeam"]
    home_score, away_score = _score(home), _score(away)
    return Match(
        source="tbf",
        source_id=str(int(row["matchId"])),
        sport=BASKETBALL,
        competition=row.get("activityDisplayName") or "Basketbol Süper Ligi",
        round_label=row.get("week") or "",
        start=kickoff_or_day(moment.date(), moment.hour, moment.minute),
        home=display_name(home["name"]),
        away=display_name(away["name"]),
        venue=join_parts(display_name(row.get("salonAdi") or ""), display_name(row.get("il") or "")),
        result=f"{home_score}-{away_score}" if home_score and away_score else "",
        broadcast=row.get("broadcastChannel") or "",
    )


def _season_with_fixtures(session: requests.Session) -> tuple[int, int, list[dict[str, Any]]]:
    """En yeni sezonu seçer; programı henüz açıklanmadıysa bir öncekine bakar."""
    seasons = get_json(session, f"{API_URL}/League/get-leagues-and-seasons-by-prefix", prefix=LEAGUE_PREFIX).get("data") or []
    if not seasons:
        raise SourceError("TBF lig/sezon listesi boş döndü")
    for season in sorted(seasons, key=lambda s: s["sezon_ID"], reverse=True)[:2]:
        league_id, season_id = int(season["faaliyet_ID"]), int(season["sezon_ID"])
        weeks = get_json(session, f"{API_URL}/League/get-league-weeks", seasonId=season_id, leagueId=league_id).get("data") or []
        if weeks:
            return league_id, season_id, weeks
    raise SourceError("TBF: Basketbol Süper Ligi için hafta listesi bulunamadı")


def fetch_bsl(session: requests.Session, today: date) -> list[Match]:
    league_id, _season_id, weeks = _season_with_fixtures(session)
    matches: list[Match] = []
    for week in weeks:
        params: dict[str, Any] = {"ActivityId": league_id, "WeekFilter": week["sezon_Hafta"], "Page": 1, "PageSize": -1}
        half = week.get("devre_Deger")
        if int(week.get("devre_ID") or 1) not in (1, 2) and half:
            params["HalfValue"] = half
        rows = get_json(session, f"{API_URL}/Match/get-all-matches-for-filter", **params).get("data") or []
        matches += [
            parse_row(row)
            for row in rows
            if is_besiktas((row.get("homeTeam") or {}).get("name", "")) or is_besiktas((row.get("awayTeam") or {}).get("name", ""))
        ]
    return matches
