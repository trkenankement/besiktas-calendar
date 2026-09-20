"""Kulüp profilleri: kayıt defteri, club.toml okuma, ad eşleştirme ve her kulübün kendi verisiyle çalışması."""

from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from helpers import BESIKTAS, FIXTURES, FakeSession, fixture_json, fixture_text
from icalendar import Calendar

from club_calendar.club import CLUBS, Club, get_club, load_club
from club_calendar.feeds import feeds_for
from club_calendar.ics import render_calendar
from club_calendar.models import FOOTBALL, TURKEY_TZ, Match
from club_calendar.names import fold
from club_calendar.providers import euroleague, providers_for, tbf, tff, uefa
from club_calendar.site import render_index

FENERBAHCE = get_club("fenerbahce")
GALATASARAY = get_club("galatasaray")
ROOT = Path(__file__).parent.parent
SRC = ROOT / "src" / "club_calendar"
TODAY = date(2026, 9, 20)
NOW = datetime(2026, 9, 20, 15, 0, tzinfo=TURKEY_TZ)
STAMP = datetime(2026, 9, 20, 12, 0, tzinfo=UTC)

every_club = pytest.mark.parametrize("club", list(CLUBS.values()), ids=list(CLUBS))


# --- Kayıt defteri ve doğrulama ---------------------------------------------------------------


def test_registry_keys_match_the_profiles_and_identifiers_are_unique():
    assert all(key == club.key for key, club in CLUBS.items())
    assert len({club.uefa_team_id for club in CLUBS.values()}) == len(CLUBS)
    codes = [club.euroleague_code for club in CLUBS.values() if club.euroleague_code]
    assert len(set(codes)) == len(codes)


def test_get_club_rejects_unknown_keys():
    with pytest.raises(ValueError, match="Bilinmeyen kulüp 'trabzonspor'"):
        get_club("trabzonspor")


@pytest.mark.parametrize("key", ["", "Besiktas", "beşiktaş", "bes-iktas", "1besiktas"])
def test_club_key_must_be_lowercase_ascii(key):
    with pytest.raises(ValueError, match="anahtarı"):
        Club(key, "X", ("x",), uefa_team_id="1")


@pytest.mark.parametrize("terms", [(), ("",), ("Besiktas",), ("beşiktaş",)])
def test_match_terms_must_be_folded_ascii(terms):
    with pytest.raises(ValueError, match="match_terms"):
        Club("besiktas", "Beşiktaş", terms, uefa_team_id="1")


def test_uefa_team_id_must_be_numeric():
    with pytest.raises(ValueError, match="UEFA"):
        Club("besiktas", "Beşiktaş", ("besiktas",), uefa_team_id="abc")


# --- Ad eşleştirme ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("club", "name"),
    [
        (BESIKTAS, "BEŞİKTAŞ A.Ş."),
        (BESIKTAS, "Beşiktaş"),
        (BESIKTAS, "Besiktas Istanbul"),
        (FENERBAHCE, "FENERBAHÇE A.Ş."),
        (FENERBAHCE, "FENERBAHÇE TARFİN"),
        (FENERBAHCE, "Fenerbahce Beko Istanbul"),
        (GALATASARAY, "GALATASARAY A.Ş."),
        (GALATASARAY, "GALATASARAY MCT TECHNIC"),
        (GALATASARAY, "Galatasaray"),
    ],
)
def test_each_club_recognises_its_own_spellings_and_writes_them_uniformly(club, name):
    assert club.matches(name)
    assert club.team_name(name) == club.name


@every_club
@pytest.mark.parametrize("name", ["Kasımpaşa", "KOCAELİSPOR", "Trabzonspor A.Ş.", "", None])
def test_unrelated_names_never_match(club, name):
    assert not club.matches(name)


def test_a_club_never_claims_another_clubs_name():
    for club in CLUBS.values():
        for other in CLUBS.values():
            if other is not club:
                assert not club.matches(other.name), (club.key, other.name)


def test_opponents_are_tidied_but_keep_their_own_name():
    assert BESIKTAS.team_name("KASIMPAŞA A.Ş.") == "Kasımpaşa"
    assert GALATASARAY.team_name("FENERBAHÇE A.Ş.") == "Fenerbahçe"
    assert FENERBAHCE.team_name("Galatasaray MCT Technic") == "Galatasaray MCT Technic"  # sponsor adı rakipte korunur


# --- club.toml --------------------------------------------------------------------------------


def test_load_club_reads_club_toml(tmp_path):
    path = tmp_path / "club.toml"
    path.write_text('# yorum\nclub = "galatasaray"\n', encoding="utf-8")
    assert load_club(path) is GALATASARAY


@pytest.mark.parametrize(
    ("content", "message"),
    [
        (None, "bulunamadı"),
        ("club = ", "okunamadı"),
        ("baska = 1\n", "club ="),
        ("club = 7\n", "club ="),
        ('club = "trabzonspor"\n', "Bilinmeyen kulüp"),
    ],
)
def test_load_club_explains_what_is_wrong(tmp_path, content, message):
    path = tmp_path / "club.toml"
    if content is not None:
        path.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        load_club(path)


def test_the_repository_names_its_club_in_club_toml():
    assert load_club(ROOT / "club.toml") in CLUBS.values()


# --- Dosya adları, takvim ve sayfa kimliği ----------------------------------------------------


def sample(club):
    return Match(
        source="tff",
        source_id="7",
        sport=FOOTBALL,
        competition="Trendyol Süper Lig",
        round_label="7. Hafta",
        start=datetime(2026, 10, 3, 20, 0, tzinfo=TURKEY_TZ),
        home=club.name,
        away="Rakip",
    )


@every_club
def test_feeds_are_named_after_the_club(club):
    feeds = feeds_for(club)
    assert [feed.filename for feed in feeds] == [f"{club.key}-all.ics", f"{club.key}-football.ics", f"{club.key}-basketball.ics"]
    assert all(feed.calendar_name.startswith(club.name) for feed in feeds)


@every_club
def test_feed_slugs_name_the_page_sections(club):
    assert [feed.slug for feed in feeds_for(club)] == ["all", "football", "basketball"]


@every_club
def test_calendar_events_carry_the_club_identity(club):
    text = render_calendar([sample(club)], f"{club.name} Tüm Maçlar", "açıklama", club, stamp=STAMP)
    calendar = Calendar.from_ical(text.encode("utf-8"))
    (event,) = [c for c in calendar.walk() if c.name == "VEVENT"]

    assert str(calendar["prodid"]) == f"-//{club.uid_domain}//TR"
    assert str(event["uid"]) == f"{sample(club).uid}@{club.uid_domain}"
    assert club.name in event["categories"].to_ical().decode("utf-8")


def test_the_same_match_gets_a_different_uid_in_each_clubs_calendar():
    """Fenerbahçe-Galatasaray gibi ortak maçlar iki takvimde de bulunur; kimlikleri çakışmamalı."""
    match = sample(BESIKTAS)
    uids = set()
    for club in CLUBS.values():
        calendar = Calendar.from_ical(render_calendar([match], "T", "A", club, stamp=STAMP).encode("utf-8"))
        (event,) = calendar.walk("VEVENT")
        uids.add(str(event["uid"]))
    assert len(uids) == len(CLUBS)


@every_club
def test_page_and_calendar_mention_only_their_own_club(club):
    page = render_index([sample(club)], NOW, club)
    calendar = render_calendar([sample(club)], "Takvim", "Açıklama", club, stamp=STAMP)
    for text in (page, calendar):
        folded = fold(text)
        assert fold(club.name) in folded
        for other in CLUBS.values():
            if other is not club:
                assert fold(other.name) not in folded, (club.key, other.key)
    assert f"<title>{club.name} Maç Takvimi</title>" in page
    assert all(f'data-feed="{feed.filename}"' in page for feed in feeds_for(club))


@every_club
def test_the_page_names_euroleague_only_for_clubs_that_play_there(club):
    assert ("EuroLeague" in render_index([], NOW, club)) == bool(club.euroleague_code)


# --- Kaynaklar --------------------------------------------------------------------------------


@every_club
def test_euroleague_is_queried_only_for_clubs_with_a_team_code(club):
    ids = [provider.id for provider in providers_for(club)]
    assert ("euroleague" in ids) == bool(club.euroleague_code)
    assert {"tff-super-lig", "uefa", "tbf-bsl"} <= set(ids)


def test_euroleague_fetch_without_a_team_code_asks_nothing():
    session = FakeSession(lambda url, params: None)
    assert euroleague.fetch(session, TODAY, GALATASARAY) == []
    assert session.requests == []


@pytest.mark.parametrize(
    ("club", "week", "expected"),
    [
        (FENERBAHCE, 6, ("Fenerbahçe", "Eyüpspor")),
        (FENERBAHCE, 7, ("Çaykur Rizespor", "Fenerbahçe")),
        (GALATASARAY, 6, ("Trabzonspor", "Galatasaray")),
        (GALATASARAY, 7, ("Galatasaray", "Kasımpaşa")),
    ],
    ids=["fenerbahce-6", "fenerbahce-7", "galatasaray-6", "galatasaray-7"],
)
def test_super_lig_weeks_yield_the_clubs_own_fixture(club, week, expected):
    (fixture,) = tff.parse_week(fixture_text(f"tff_week_{week}.html"), club)
    match = tff._to_match(fixture, "Trendyol Süper Lig", f"{week}. Hafta", club)
    assert (match.home, match.away) == expected
    assert match.sport == FOOTBALL and match.source == "tff"


def test_super_lig_fetch_finds_every_week_for_each_club():
    def route(url, params):
        if params.get("pageId") == 29:
            return fixture_text("tff_match_page.html")
        if params.get("pageID") == 198:
            week = params.get("hafta")
            if week is None:
                return fixture_text("tff_overview.html")
            name = f"tff_week_{week}.html"
            return fixture_text(name) if (FIXTURES / name).exists() else "<html><body></body></html>"
        return None

    for club in (FENERBAHCE, GALATASARAY):
        matches = tff.fetch_super_lig(FakeSession(route), TODAY, club)
        assert [m.round_label for m in matches] == ["1. Hafta", "6. Hafta", "7. Hafta", "20. Hafta"]
        assert all(club.name in (m.home, m.away) for m in matches)


def bsl_route(url, params):
    if url.endswith("get-leagues-and-seasons-by-prefix"):
        return fixture_json("tbf_seasons.json")
    if url.endswith("get-league-weeks"):
        return fixture_json("tbf_weeks.json")
    if url.endswith("get-all-matches-for-filter"):
        return fixture_json("tbf_week_1_clubs.json") if params["WeekFilter"] == "1" else {"data": []}
    return None


@pytest.mark.parametrize(
    ("club", "expected"),
    [
        (FENERBAHCE, [("Bahçeşehir Koleji", "Fenerbahçe")]),
        (GALATASARAY, [("Galatasaray", "Çayırova Belediyesi")]),
        (BESIKTAS, []),
    ],
    ids=["fenerbahce", "galatasaray", "besiktas"],
)
def test_basketball_league_rows_are_picked_by_club(club, expected):
    matches = tbf.fetch_bsl(FakeSession(bsl_route), TODAY, club)
    assert [(m.home, m.away) for m in matches] == expected


@pytest.mark.parametrize(
    ("club", "expected"),
    [
        (
            FENERBAHCE,
            [
                ("Fenerbahçe", "Górnik Zabrze", "1-0", datetime(2026, 7, 21, 21, 0, tzinfo=TURKEY_TZ)),
                ("Górnik Zabrze", "Fenerbahçe", "1-1", datetime(2026, 7, 29, 21, 0, tzinfo=TURKEY_TZ)),
            ],
        ),
        (
            GALATASARAY,
            [
                ("Sporting CP", "Galatasaray", "3-1", datetime(2026, 9, 9, 22, 0, tzinfo=TURKEY_TZ)),
                ("Galatasaray", "Barcelona", "", datetime(2026, 10, 13, 22, 0, tzinfo=TURKEY_TZ)),
            ],
        ),
    ],
    ids=["fenerbahce", "galatasaray"],
)
def test_uefa_asks_for_the_clubs_own_team_id(club, expected):
    def route(url, params):
        return fixture_json(f"uefa_matches_{club.key}.json") if params["competitionId"] == "1" else []

    session = FakeSession(route)
    matches = uefa.fetch(session, TODAY, club)

    assert [(m.home, m.away, m.result, m.start) for m in matches] == expected
    assert {p["teamId"] for _, p in session.requests} == {club.uefa_team_id}


def test_euroleague_games_are_filtered_by_the_clubs_team_code():
    def route(url, params):
        if url.endswith("/E/seasons"):
            return fixture_json("euroleague_seasons.json")
        if url.endswith("/U/seasons"):
            return {"data": []}
        return fixture_json("euroleague_games_fenerbahce.json") if url.endswith("/games") else None

    session = FakeSession(route)
    matches = euroleague.fetch(session, TODAY, FENERBAHCE)

    assert [(m.home, m.away) for m in matches] == [("Fenerbahçe", "Virtus Bologna"), ("Panathinaikos", "Fenerbahçe")]
    assert [p for url, p in session.requests if url.endswith("/games")] == [{"teamCode": "ULK"}]


# --- Motor kulüpten bağımsız kalmalı ----------------------------------------------------------


def test_only_the_club_registry_names_clubs():
    """Üç depo aynı kodu paylaşır; bir kulübün adı başka bir yere sabitlenirse diğerleri bozulur."""
    names = {fold(club.name) for club in CLUBS.values()} | {term for club in CLUBS.values() for term in club.match_terms}
    offenders = [
        f"{path.relative_to(SRC)}: {name}"
        for path in sorted(SRC.rglob("*.py"))
        if path.name != "club.py"
        for name in sorted(names)
        if name in fold(path.read_text(encoding="utf-8"))
    ]
    assert not offenders
