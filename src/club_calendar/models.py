"""Ortak veri modeli: tüm kaynaklardaki maçlar bu biçime çevrilir."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone

# Türkiye 2016'dan beri yıl boyunca UTC+3 kullanıyor (yaz saati uygulaması yok).
TURKEY_TZ = timezone(timedelta(hours=3), "TRT")

FOOTBALL = "football"
BASKETBALL = "basketball"

SPORT_LABELS = {FOOTBALL: "Futbol", BASKETBALL: "Basketbol"}
MATCH_DURATION = {
    FOOTBALL: timedelta(hours=2, minutes=15),
    BASKETBALL: timedelta(hours=2),
}
SOURCE_LABELS = {
    "tff": "TFF (Türkiye Futbol Federasyonu)",
    "uefa": "UEFA",
    "euroleague": "EuroLeague Basketball",
    "tbf": "TBF (Türkiye Basketbol Federasyonu)",
}


def kickoff_or_day(day: date, hour: int | None, minute: int | None) -> date | datetime:
    """Saat belliyse Türkiye saatiyle tam zamanı, değilse yalnızca günü döndürür.

    Kaynaklar henüz kesinleşmemiş saatleri boş bırakır ya da 00:00 yer tutucusu
    olarak yazar; ikisi de "saat belli değil" anlamına gelir.
    """
    if hour is None or (hour == 0 and not minute):
        return day
    return datetime(day.year, day.month, day.day, hour, minute or 0, tzinfo=TURKEY_TZ)


@dataclass(frozen=True)
class Match:
    """Takip edilen kulübün tek bir maçı."""

    source: str  # "tff", "uefa", "euroleague", "tbf"
    source_id: str  # maçın kaynak içindeki kalıcı kimliği (UID buradan türetilir)
    sport: str
    competition: str
    round_label: str
    start: date  # saat kesinse Türkiye saatli datetime, değilse yalnızca tarih
    home: str
    away: str
    venue: str = ""
    result: str = ""  # oynandıktan sonra "2-1"
    info_url: str = ""
    broadcast: str = ""

    @property
    def time_confirmed(self) -> bool:
        return isinstance(self.start, datetime)

    @property
    def day(self) -> date:
        if isinstance(self.start, datetime):
            return self.start.astimezone(TURKEY_TZ).date()
        return self.start

    @property
    def uid(self) -> str:
        """Etkinliğin kalıcı kimliği (24 onaltılık karakter); takvim dosyasında `@<kulüp>-calendar` ile tamamlanır.

        Tarih/saat değişse bile aynı kalır; takvim uygulaması etkinliği güncelleyip çoğaltmaz.
        SHA1 burada yalnızca kararlı bir kimlik üretir, güvenlik amacıyla kullanılmaz.
        """
        key = f"{self.source}:{self.source_id}".encode()
        return hashlib.sha1(key, usedforsecurity=False).hexdigest()[:24]

    @property
    def sort_key(self) -> tuple:
        kickoff = self.start.astimezone(TURKEY_TZ).time() if self.time_confirmed else time.min
        return (self.day, kickoff, self.uid)
