"""Veri kaynakları. Her sağlayıcı kulübün maçlarını ortak `Match` biçiminde döndürür."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

import requests

from ..club import Club
from ..models import Match
from . import euroleague, tbf, tff, uefa


@dataclass(frozen=True)
class Provider:
    id: str
    name: str
    fetch: Callable[[requests.Session, date, Club], list[Match]]
    required: bool = True  # True: hata verirse yayın durdurulur; False: yalnızca uyarı verilir
    min_matches: int = 0  # bulunması beklenen en az maç; altı sayfa yapısı bozulmuş demektir


def providers_for(club: Club) -> tuple[Provider, ...]:
    """Kulüp için kullanılacak kaynaklar (EuroLeague yalnızca orada oynayan kulüplerde)."""
    # required=False olanlar editöryel HTML sayfalarıdır (yapıları haber duyurusuna göre değişebilir);
    # bozulurlarsa yalnızca uyarı verilir, diğer müsabakalar yayınlanmaya devam eder.
    providers = [
        Provider("tff-super-lig", "TFF · Trendyol Süper Lig", tff.fetch_super_lig, min_matches=30),
        Provider("tff-kupa", "TFF · Ziraat Türkiye Kupası", tff.fetch_cup, required=False),
        Provider("tff-super-kupa", "TFF · Süper Kupa", tff.fetch_super_cup, required=False),
        Provider("uefa", "UEFA · Avrupa kupaları", uefa.fetch),
    ]
    if club.euroleague_code:
        providers.append(Provider("euroleague", "EuroLeague Basketball", euroleague.fetch))
    providers += [
        Provider("tbf-bsl", "TBF · Basketbol Süper Ligi", tbf.fetch_bsl, min_matches=20),
        Provider("tbf-kupalar", "TBF · Basketbol kupaları", tbf.fetch_cups),
    ]
    return tuple(providers)
