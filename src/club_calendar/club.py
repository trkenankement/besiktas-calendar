"""Takip edilen kulüp: hangi takımın maçlarının hangi kaynaklarda hangi kimlikle aranacağı.

Motorun geri kalanı kulüpten bağımsızdır. Bir depo hangi kulübü takip ettiğini kökündeki `club.toml` dosyasıyla
söyler (`club = "besiktas"`); yeni bir kulüp eklemek için buraya bir profil eklemek yeterlidir.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

from .names import display_name, fold


@dataclass(frozen=True)
class Club:
    key: str  # dosya adları ve UID alanı için ASCII ad, ör. "besiktas"
    name: str  # başlıklarda ve maç özetlerinde görünen ad, ör. "Beşiktaş"
    match_terms: tuple[str, ...]  # kaynaklardaki takım adında aranan ASCII ve küçük harfli parçalar
    uefa_team_id: str  # match.uefa.com takım kimliği (kulüp o sezon Avrupa'da oynamıyorsa da geçerlidir)
    euroleague_code: str | None = None  # EuroLeague/EuroCup takım kodu; kulüp orada oynamıyorsa None

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[a-z][a-z0-9]*", self.key):
            raise ValueError(f"Kulüp anahtarı küçük harfli ASCII olmalı: {self.key!r}")
        if not self.match_terms or any(term != fold(term) or not term for term in self.match_terms):
            raise ValueError(f"{self.key}: match_terms boş olmamalı ve ASCII, küçük harfli parçalardan oluşmalı")
        if not self.uefa_team_id.isdigit():
            raise ValueError(f"{self.key}: UEFA takım kimliği sayı olmalı: {self.uefa_team_id!r}")

    @property
    def uid_domain(self) -> str:
        """Takvim etkinliklerinin UID alanı; değişirse aboneler etkinlikleri yeniden yükler, o yüzden sabit kalmalı."""
        return f"{self.key}-calendar"

    def matches(self, team_name: str) -> bool:
        folded = fold(team_name or "")
        return any(term in folded for term in self.match_terms)

    def team_name(self, raw: str) -> str:
        """Kulübün kendi tarafı her kaynakta aynı ve sponsorsuz adla yazılır; rakipler düzeltilmiş adlarıyla."""
        return self.name if self.matches(raw) else display_name(raw)


CLUBS: dict[str, Club] = {
    club.key: club
    for club in (
        Club("besiktas", "Beşiktaş", ("besiktas",), uefa_team_id="50157", euroleague_code="BES"),
        Club("fenerbahce", "Fenerbahçe", ("fenerbahce",), uefa_team_id="52692", euroleague_code="ULK"),
        Club("galatasaray", "Galatasaray", ("galatasaray",), uefa_team_id="50067"),
    )
}


def get_club(key: str) -> Club:
    try:
        return CLUBS[key]
    except KeyError:
        raise ValueError(f"Bilinmeyen kulüp {key!r}; seçenekler: {', '.join(sorted(CLUBS))}") from None


def load_club(path: Path = Path("club.toml")) -> Club:
    """Deponun kökündeki `club.toml` dosyasından takip edilen kulübü okur."""
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ValueError(f"{path} bulunamadı; içine örneğin `club = \"besiktas\"` yazın ya da --club verin") from None
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"{path} okunamadı: {exc}") from exc
    if not isinstance(data.get("club"), str):
        raise ValueError(f"{path} içinde `club = \"...\"` satırı olmalı")
    return get_club(data["club"])
