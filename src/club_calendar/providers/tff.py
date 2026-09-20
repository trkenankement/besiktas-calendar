"""TFF (Türkiye Futbol Federasyonu): Trendyol Süper Lig, Ziraat Türkiye Kupası ve Süper Kupa."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import date

import requests
from bs4 import BeautifulSoup, Tag

from ..club import Club
from ..console import warn
from ..http import SourceError, get_html
from ..models import FOOTBALL, Match, kickoff_or_day
from ..names import display_name, fold, join_parts, tr_lower

BASE_URL = "https://www.tff.org/Default.aspx"
ENCODING = "windows-1254"  # TFF sayfaları Windows-1254 ile yayınlanır
LEAGUE_PAGE = 198  # lig fikstürü; "Haftanın Maçları" bileşeni ?hafta=N ile değişir
CUP_PAGE = 598  # Türkiye Kupası fikstürü
SUPER_CUP_PAGE = 329  # Süper Kupa arşivi (yeni maç belli olunca aynı tabloya eklenir)
MATCH_PAGE = 29  # maç detayı (stadyum burada)
DEFAULT_LEAGUE_NAME = "Trendyol Süper Lig"
CUP_NAME = "Ziraat Türkiye Kupası"
SUPER_CUP_NAME = "Süper Kupa"  # sponsor adı her yıl değişir; sponsorsuz ad kullanılır

_DATE = re.compile(r"(\d{2})\.(\d{2})\.(\d{4})")
_PENALTIES = re.compile(r"\((\d+)\s*-\s*(\d+)\s*P\.?\)", re.IGNORECASE)
_TIME = re.compile(r"(\d{1,2}):(\d{2})")
_MAC_ID = re.compile(r"macId=(\d+)", re.IGNORECASE)
_SCORE = re.compile(r"(\d+)\s*-\s*(\d+)")
_WEEK_LABEL = re.compile(r"\d+\.\s*Hafta")
_CUP_DATE = re.compile(r"(\d{1,2})\s+([^\d\s]+)\s+(\d{4})(?:\s+(\d{1,2}):(\d{2}))?")
_TR_MONTHS = {
    "ocak": 1, "şubat": 2, "mart": 3, "nisan": 4, "mayıs": 5, "haziran": 6,
    "temmuz": 7, "ağustos": 8, "eylül": 9, "ekim": 10, "kasım": 11, "aralık": 12,
}


@dataclass(frozen=True)
class Fixture:
    mac_id: str
    day: date
    hour: int | None
    minute: int | None
    home: str
    away: str
    score: str


def _text(node: Tag | None) -> str:
    return " ".join(node.get_text(" ", strip=True).split()) if node else ""


def _score(text: str) -> str:
    found = _SCORE.search(text)  # "0 - 0" -> "0-0"; "-" -> ""; "1-1 (Uzt. 2-1)" -> "1-1"
    return f"{found.group(1)}-{found.group(2)}" if found else ""


def _mac_id(node: Tag | None) -> str:
    """Maç kimliğini, düğümün kendisi ya da içindeki bağlantıdan alır."""
    if node is None:
        return ""
    link = node if node.name == "a" and node.has_attr("href") else node.find("a", href=True)
    found = _MAC_ID.search(link["href"]) if link else None
    return found.group(1) if found else ""


def _to_match(fixture: Fixture, competition: str, round_label: str, club: Club) -> Match:
    source_id = fixture.mac_id or f"{competition}-{round_label}-{fold(fixture.home)}-{fold(fixture.away)}"
    return Match(
        source="tff",
        source_id=source_id,
        sport=FOOTBALL,
        competition=competition,
        round_label=round_label,
        start=kickoff_or_day(fixture.day, fixture.hour, fixture.minute),
        home=club.team_name(fixture.home),
        away=club.team_name(fixture.away),
        result=fixture.score,
        info_url=f"{BASE_URL}?pageId={MATCH_PAGE}&macId={fixture.mac_id}" if fixture.mac_id else "",
    )


# --- Süper Lig -------------------------------------------------------------------------------


def parse_league_overview(html: str) -> tuple[str, int]:
    """Lig adını ve sezondaki hafta sayısını döndürür."""
    soup = BeautifulSoup(html, "html.parser")
    weeks = [cell for cell in soup.select("td.belirginYazi") if _WEEK_LABEL.fullmatch(_text(cell))]
    if not weeks:
        raise SourceError("TFF: sezon fikstür tablosu bulunamadı (sayfa yapısı değişmiş olabilir)")
    title = _text(soup.title)
    name = re.sub(r"\s+Fikstürü.*$", "", title).strip() or DEFAULT_LEAGUE_NAME
    return name, len(weeks)


def parse_week(html: str, club: Club) -> list[Fixture]:
    """"Haftanın Maçları" bileşeninden yalnızca kulübün maçlarını çıkarır."""
    soup = BeautifulSoup(html, "html.parser")
    fixtures: list[Fixture] = []
    for row in soup.select("tr.haftaninMaclariTr"):
        home = _text(row.select_one("td.haftaninMaclariEv"))
        away = _text(row.select_one("td.haftaninMaclariDeplasman"))
        if not (club.matches(home) or club.matches(away)):
            continue
        date_text = _text(row.find("span", id=re.compile(r"lblTarih$")))
        time_text = _text(row.find("span", id=re.compile(r"lblSaat$")))
        day = _DATE.search(date_text)
        if not day:  # ör. ertelenmiş maç: tek bir maç yüzünden bütün güncelleme durmasın
            warn(f"TFF: '{home} - {away}' maçının tarihi okunamadı ({date_text!r}); bu maç takvime eklenmedi")
            continue
        clock = _TIME.search(time_text)  # saat henüz belli değilse boş gelir
        score_cell = row.select_one("td.haftaninMaclariSkor")
        fixtures.append(
            Fixture(
                mac_id=_mac_id(score_cell),
                day=date(int(day.group(3)), int(day.group(2)), int(day.group(1))),
                hour=int(clock.group(1)) if clock else None,
                minute=int(clock.group(2)) if clock else None,
                home=home,
                away=away,
                score=_score(_text(score_cell)),
            )
        )
    return fixtures


def parse_venue(html: str) -> str:
    """Maç detay sayfasından "Stadyum, Şehir" bilgisini çıkarır."""
    link = BeautifulSoup(html, "html.parser").find("a", id=re.compile(r"lnkStad$"))
    stadium, _, city = _text(link).partition(" - ")
    return join_parts(display_name(stadium), display_name(city))


def _with_venues(session: requests.Session, matches: list[Match]) -> list[Match]:
    """Oynanmamış maçlar için stadyum bilgisini maç sayfasından ekler (alınamazsa boş bırakılır)."""
    enriched: list[Match] = []
    for match in matches:
        if match.result or not match.source_id.isdigit():
            enriched.append(match)
            continue
        try:
            venue = parse_venue(get_html(session, BASE_URL, encoding=ENCODING, pageId=MATCH_PAGE, macId=match.source_id))
        except SourceError:
            venue = ""
        enriched.append(replace(match, venue=venue) if venue else match)
    return enriched


def fetch_super_lig(session: requests.Session, today: date, club: Club) -> list[Match]:
    overview = get_html(session, BASE_URL, encoding=ENCODING, pageID=LEAGUE_PAGE)
    competition, weeks = parse_league_overview(overview)
    matches: list[Match] = []
    for week in range(1, weeks + 1):
        html = get_html(session, BASE_URL, encoding=ENCODING, pageID=LEAGUE_PAGE, hafta=week)
        matches += [_to_match(fixture, competition, f"{week}. Hafta", club) for fixture in parse_week(html, club)]
    return _with_venues(session, matches)


# --- Ziraat Türkiye Kupası -------------------------------------------------------------------


def _cup_round(text: str) -> str:
    text = re.sub(r"\s*Maçları\s*$", "", text, flags=re.IGNORECASE)
    return re.sub(r"(\d)\.(?=\S)", r"\1. ", text).strip()


def parse_cup(html: str, club: Club) -> list[Match]:
    """Kupa sayfasındaki güncel tur listesinden kulübün maçlarını çıkarır."""
    soup = BeautifulSoup(html, "html.parser")
    matches: list[Match] = []
    round_label = ""
    for span in soup.find_all("span", id=re.compile(r"(lblGrup|lblTarih)$")):
        if span["id"].endswith("lblGrup"):
            round_label = _cup_round(_text(span)) or round_label
            continue
        row = span.find_parent("tr")
        if row is None:
            continue
        home = _text(row.find(id=re.compile(r"lblTakim1$")))
        away = _text(row.find(id=re.compile(r"lblTakim2$")))
        if not (club.matches(home) or club.matches(away)):
            continue
        found = _CUP_DATE.search(_text(span))
        month = _TR_MONTHS.get(tr_lower(found.group(2))) if found else None
        if not found or month is None:
            warn(f"TFF kupa: '{home} - {away}' maçının tarihi okunamadı ({_text(span)!r}); bu maç takvime eklenmedi")
            continue
        score_cell = row.find(id=re.compile(r"lblSkor$"))
        fixture = Fixture(
            mac_id=_mac_id(score_cell),
            day=date(int(found.group(3)), month, int(found.group(1))),
            hour=int(found.group(4)) if found.group(4) else None,
            minute=int(found.group(5)) if found.group(5) else None,
            home=home,
            away=away,
            score=_score(_text(score_cell)),
        )
        matches.append(_to_match(fixture, CUP_NAME, round_label, club))
    return matches


def fetch_cup(session: requests.Session, today: date, club: Club) -> list[Match]:
    html = get_html(session, BASE_URL, encoding=ENCODING, pageID=CUP_PAGE)
    return _with_venues(session, parse_cup(html, club))


# --- Süper Kupa ------------------------------------------------------------------------------


def season_start(today: date) -> date:
    """Futbol sezonu temmuzda başlar."""
    return date(today.year if today.month >= 7 else today.year - 1, 7, 1)


def parse_super_cup(html: str, since: date, club: Club) -> list[Match]:
    """Arşiv tablosundan (tarih | stat | 1. takım | skor | 2. takım) güncel sezondaki kulüp maçlarını çıkarır.

    Tabloda saat yoktur; maç tüm gün etkinliği olarak yayınlanır. Eski sezonlar takvime girmez.
    """
    matches: list[Match] = []
    for row in BeautifulSoup(html, "html.parser").find_all("tr"):
        cells = row.find_all("td")
        if len(cells) != 5:
            continue
        day = _DATE.fullmatch(_text(cells[0]))
        home, away = _text(cells[2]), _text(cells[4])
        if not day or not (club.matches(home) or club.matches(away)):
            continue
        played = date(int(day.group(3)), int(day.group(2)), int(day.group(1)))
        if played < since:
            continue
        score_text = _text(cells[3])
        result = _score(score_text)
        shootout = _PENALTIES.search(score_text)
        if result and shootout:
            result += f" (pen. {shootout.group(1)}-{shootout.group(2)})"
        fixture = Fixture(mac_id=_mac_id(cells[3]), day=played, hour=None, minute=None, home=home, away=away, score=result)
        match = _to_match(fixture, SUPER_CUP_NAME, "", club)
        if not fixture.mac_id:  # henüz maç sayfası yoksa kimlik sezondan ve takımlardan türetilir
            match = replace(match, source_id=f"super-kupa-{since.year}-{fold(home)}-{fold(away)}")
        matches.append(replace(match, venue=display_name(_text(cells[1]))))
    return matches


def fetch_super_cup(session: requests.Session, today: date, club: Club) -> list[Match]:
    html = get_html(session, BASE_URL, encoding=ENCODING, pageID=SUPER_CUP_PAGE)
    return parse_super_cup(html, season_start(today), club)
