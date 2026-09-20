"""Bağış bilgileri para gönderimini ilgilendirir ve geri alınamaz: adres her yerde birebir aynı olmalı."""

import hashlib
import re
from datetime import UTC, datetime
from pathlib import Path

import pytest
from helpers import BESIKTAS

from club_calendar import donate
from club_calendar.site import render_index

ROOT = Path(__file__).resolve().parents[1]
README = (ROOT / "README.md").read_text(encoding="utf-8")
QR_FILE = ROOT / "docs" / donate.QR_FILENAME
PAGE = render_index([], datetime(2026, 9, 20, 15, 0, tzinfo=UTC), BESIKTAS)

# Adres ve QR bilerek burada da sabitlenir: değiştirmek için üç yeri (adres, QR dosyası, bu özet) elle güncellemek gerekir.
EXPECTED_ADDRESS = "0x315f79cb95f784c18387c3009798d1a617dac8b2"
EXPECTED_QR_SHA256 = "002a8f717cc7000f58b73f1d3b2bd7ecc8ed613c375ed9b3a5ed182e8434cce0"
ADDRESS_PATTERN = re.compile(r"0x[0-9a-fA-F]{40}")


def test_address_is_the_one_the_owner_gave():
    assert donate.USDT_ADDRESS == EXPECTED_ADDRESS


def test_address_has_the_evm_format():
    assert re.fullmatch(r"0x[0-9a-f]{40}", donate.USDT_ADDRESS)


@pytest.mark.parametrize("text", [README, PAGE], ids=["README", "web sayfası"])
def test_only_the_expected_address_is_published(text):
    assert ADDRESS_PATTERN.findall(text) == [EXPECTED_ADDRESS]


@pytest.mark.parametrize("text", [README, PAGE], ids=["README", "web sayfası"])
def test_the_network_and_the_warning_are_shown_next_to_the_address(text):
    assert "BSC" in text and "BEP-20" in text
    assert "USDT" in text
    assert "geri alınamaz" in text


@pytest.mark.parametrize("text", [README, PAGE], ids=["README", "web sayfası"])
def test_no_other_payment_links_are_published(text):
    """Binance Pay kaldırıldı: yalnızca doğrudan USDT gönderimi var."""
    assert "binance" not in text.lower()


def test_page_offers_a_copy_button_and_a_stable_anchor():
    assert f'id="{donate.ANCHOR}"' in PAGE
    assert 'id="copy-address"' in PAGE
    assert f'<code id="usdt-address">{EXPECTED_ADDRESS}</code>' in PAGE


def test_page_and_readme_point_to_the_qr_file():
    assert f'src="{donate.QR_FILENAME}"' in PAGE
    assert f"docs/{donate.QR_FILENAME}" in README


def test_qr_file_is_the_verified_one():
    """QR, adresten üretilip geri çözülerek doğrulandı (sonuç birebir aynı adres); dosya sessizce değişemez."""
    raw = QR_FILE.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == EXPECTED_QR_SHA256


def test_qr_file_scales_and_is_static_content_only():
    svg = QR_FILE.read_text(encoding="utf-8")
    assert 'viewBox="0 0 328 328"' in svg  # <img> içinde ölçeklenebilsin
    assert "<script" not in svg.lower() and "onload" not in svg.lower() and "href" not in svg.lower()
