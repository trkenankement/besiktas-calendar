import pytest

from besiktas_calendar.names import display_name, english_title, fold, is_besiktas, join_parts


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("BEŞİKTAŞ A.Ş.", "Beşiktaş"),
        ("GAZİANTEP FUTBOL KULÜBÜ A.Ş.", "Gaziantep Futbol Kulübü"),
        ("İSTANBUL BAŞAKŞEHİR FK", "İstanbul Başakşehir FK"),
        ("ÇAYKUR RİZESPOR A.Ş.", "Çaykur Rizespor"),
        ("AMED SPORTİF FAALİYETLER", "Amed Sportif Faaliyetler"),
        ("1923 AFYONKARAHİSAR SPOR KULÜBÜ", "1923 Afyonkarahisar Spor Kulübü"),
        ("GALATASARAY MCT TECHNIC", "Galatasaray MCT Technic"),
        ("PİZZABULLS BORDO BANDIRMA", "Pizzabulls Bordo Bandırma"),
        ("IĞDIR", "Iğdır"),
        ("İSTANBUL", "İstanbul"),
        ("Turkcell Basketbol Gelişim Merkezi", "Turkcell Basketbol Gelişim Merkezi"),
        ("Real Madrid", "Real Madrid"),
        ("", ""),
    ],
)
def test_display_name(raw, expected):
    assert display_name(raw) == expected


def test_display_name_keeps_dotted_abbreviations():
    assert display_name("GAZİEMİR G.O.G. SPOR YAT. A.Ş.") == "Gaziemir G.O.G. Spor Yat."


@pytest.mark.parametrize("name", ["BEŞİKTAŞ A.Ş.", "Beşiktaş", "Besiktas Istanbul", "BEŞİKTAŞ"])
def test_is_besiktas_recognises_every_spelling(name):
    assert is_besiktas(name)


@pytest.mark.parametrize("name", ["Kasımpaşa", "FENERBAHÇE A.Ş.", "", None])
def test_is_besiktas_rejects_other_clubs(name):
    assert not is_besiktas(name)


def test_fold_removes_turkish_accents():
    assert fold("ÇAĞRI ÖZŞİŞLİ ıİ") == "cagri ozsisli ii"


def test_english_title_only_touches_all_caps():
    assert english_title("TURKCELL BASKETBALL DEVELOPMENT CENTER") == "Turkcell Basketball Development Center"
    assert english_title("Buesa Arena") == "Buesa Arena"


def test_join_parts_skips_empty_values():
    assert join_parts("Stadyum", "", "Şehir") == "Stadyum, Şehir"
    assert join_parts("", "") == ""
