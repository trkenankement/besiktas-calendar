"""RFC 5545 (iCalendar) uyumlu ICS üretimi."""

from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .club import Club
from .models import MATCH_DURATION, SOURCE_LABELS, SPORT_LABELS, Match

TIMEZONE_ID = "Europe/Istanbul"
CRLF = "\r\n"
# RFC 5545 TEXT içinde yasak olan denetim karakterleri (sekme ve satır sonları hariç).
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def escape_text(value: str) -> str:
    """TEXT değerini RFC 5545'e göre kaçışlar; kaynaktan gelen veri yeni bir özellik ekleyemez."""
    value = _CONTROL_CHARS.sub("", value)
    return (
        value.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .replace("\n", "\\n")
    )


def fold_line(line: str) -> str:
    """Satırları 75 oktette katlar (karakterde değil); UTF-8 dizilerini asla bölmez."""
    if len(line.encode("utf-8")) <= 75:
        return line
    chunks: list[str] = []
    current: list[str] = []
    size, limit = 0, 75
    for char in line:
        width = len(char.encode("utf-8"))
        if size + width > limit:
            chunks.append("".join(current))
            current, size, limit = [], 0, 74  # devam satırı bir boşlukla başlar
        current.append(char)
        size += width
    chunks.append("".join(current))
    return (CRLF + " ").join(chunks)


def _utc(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def _description(match: Match) -> str:
    lines = [" · ".join(p for p in (SPORT_LABELS[match.sport], match.competition, match.round_label) if p)]
    if match.result:
        lines.append(f"Sonuç: {match.result}")
    if match.broadcast:
        lines.append(f"Yayın: {match.broadcast}")
    if not match.time_confirmed:
        lines.append(
            "Maç saati henüz açıklanmadı; takvimde tüm gün etkinliği olarak görünür. "
            "Saat kesinleşince etkinlik otomatik güncellenir."
        )
    source = SOURCE_LABELS.get(match.source, match.source)
    lines.append(f"Kaynak: {source}" + (f" — {match.info_url}" if match.info_url else ""))
    return "\n".join(lines)


def event_lines(match: Match, stamp: str, club: Club) -> list[str]:
    categories = ",".join(escape_text(c) for c in (club.name, SPORT_LABELS[match.sport], match.competition))
    lines = [
        "BEGIN:VEVENT",
        f"UID:{match.uid}@{club.uid_domain}",
        f"DTSTAMP:{stamp}",
        f"SUMMARY:{escape_text(f'{match.home} - {match.away}')}",
        f"CATEGORIES:{categories}",
    ]
    if match.time_confirmed:
        start = match.start.astimezone(UTC)
        lines += [
            f"DTSTART:{_utc(start)}",
            f"DTEND:{_utc(start + MATCH_DURATION[match.sport])}",
            "STATUS:CONFIRMED",
        ]
    else:
        day = match.day
        lines += [
            f"DTSTART;VALUE=DATE:{day:%Y%m%d}",
            f"DTEND;VALUE=DATE:{day + timedelta(days=1):%Y%m%d}",
            "STATUS:TENTATIVE",
            "TRANSP:TRANSPARENT",
        ]
    if match.venue:
        lines.append(f"LOCATION:{escape_text(match.venue)}")
    lines.append(f"DESCRIPTION:{escape_text(_description(match))}")
    lines.append("END:VEVENT")
    return lines


def render_calendar(
    matches: Iterable[Match], name: str, description: str, club: Club, *, stamp: datetime | None = None
) -> str:
    stamp_text = _utc(stamp or datetime.now(UTC))
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:-//{club.uid_domain}//TR",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"NAME:{escape_text(name)}",
        f"X-WR-CALNAME:{escape_text(name)}",
        f"X-WR-CALDESC:{escape_text(description)}",
        f"X-WR-TIMEZONE:{TIMEZONE_ID}",
        "REFRESH-INTERVAL;VALUE=DURATION:PT12H",
        "X-PUBLISHED-TTL:PT12H",
    ]
    for match in sorted(matches, key=lambda m: m.sort_key):
        lines += event_lines(match, stamp_text, club)
    lines.append("END:VCALENDAR")
    return CRLF.join(fold_line(line) for line in lines) + CRLF


def write_if_changed(path: Path, content: str, *, ignore_prefixes: tuple[str, ...] = ("DTSTAMP:",)) -> bool:
    """İçerik gerçekten değiştiyse yazar (DTSTAMP gibi her çalışmada değişen satırlar sayılmaz)."""

    def comparable(text: str) -> list[str]:
        return [line for line in text.splitlines() if not line.startswith(ignore_prefixes)] if ignore_prefixes else text.splitlines()

    if path.exists() and comparable(path.read_text(encoding="utf-8")) == comparable(content):
        return False
    path.write_text(content, encoding="utf-8", newline="")  # newline="" -> CRLF olduğu gibi kalır
    return True
