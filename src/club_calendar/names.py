"""Türkçe büyük harfli kulüp ve salon adlarını okunur hale getirir."""

from __future__ import annotations

import re
import unicodedata

# Başlık biçimine çevrilmemesi gereken kısaltmalar.
KEEP_UPPER = {"FK", "SK", "KK", "TED", "MCT", "BB", "İBB", "GSK"}
# Türkçe kurallarla yanlış küçülen yabancı sözcükler (büyük I noktasız ı olurdu: "Technıc").
WORD_OVERRIDES = {"TECHNIC": "Technic"}
_CORPORATE_SUFFIX = re.compile(r"\s+A\.\s?Ş\.?$", re.IGNORECASE)
_DOTTED_ACRONYM = re.compile(r"(?:[^\W\d_]\.)+[^\W\d_]?")  # G.O.G.


def tr_lower(text: str) -> str:
    return text.replace("İ", "i").replace("I", "ı").lower()


def tr_upper(text: str) -> str:
    return text.replace("i", "İ").replace("ı", "I").upper()


def fold(text: str) -> str:
    """Karşılaştırma için: küçük harf ve aksansız ASCII (Çaykur Rizespor -> caykur rizespor)."""
    lowered = tr_lower(text).replace("ı", "i")
    decomposed = unicodedata.normalize("NFKD", lowered)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def _capitalize(word: str) -> str:
    lower = tr_lower(word)
    return tr_upper(lower[:1]) + lower[1:]


def _title_token(token: str) -> str:
    if token in WORD_OVERRIDES:
        return WORD_OVERRIDES[token]
    if token in KEEP_UPPER or _DOTTED_ACRONYM.fullmatch(token) or any(ch.isdigit() for ch in token):
        return token
    parts = re.split(r"([-/'])", token)
    return "".join(part if part in {"-", "/", "'"} else _capitalize(part) for part in parts)


def display_name(raw: str) -> str:
    """"KASIMPAŞA A.Ş." -> "Kasımpaşa"; zaten karışık harfli adları olduğu gibi bırakır."""
    text = _CORPORATE_SUFFIX.sub("", " ".join((raw or "").split()))
    if not text or text != tr_upper(text):
        return text
    return " ".join(_title_token(token) for token in text.split(" "))


def english_title(raw: str) -> str:
    """İngilizce büyük harfli adlar (ör. EuroLeague salonları) için başlık biçimi."""
    text = " ".join((raw or "").split())
    return text.title() if text and text == text.upper() else text


def join_parts(*parts: str) -> str:
    return ", ".join(part for part in parts if part)
