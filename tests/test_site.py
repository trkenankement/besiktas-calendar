import re
from datetime import date, datetime, timedelta

from helpers import BESIKTAS

from club_calendar.models import BASKETBALL, FOOTBALL, TURKEY_TZ, Match
from club_calendar.site import CSS, SCRIPT, UPCOMING_LIMIT, format_when, render_index, upcoming

NOW = datetime(2026, 9, 20, 15, 0, tzinfo=TURKEY_TZ)


def match(source_id, start, *, sport=FOOTBALL, home="Beşiktaş", away="Rakip", **extra):
    return Match(
        source="tff",
        source_id=str(source_id),
        sport=sport,
        competition="Trendyol Süper Lig",
        round_label="7. Hafta",
        start=start,
        home=home,
        away=away,
        **extra,
    )


def at(day, hour, minute=0):
    return datetime(2026, 9, day, hour, minute, tzinfo=TURKEY_TZ)


def test_upcoming_drops_finished_matches_but_keeps_unfinished_and_all_day_ones():
    finished = match(1, at(20, 12))  # 14:15'te bitti
    tonight = match(2, at(20, 20))
    all_day_today = match(3, date(2026, 9, 20))
    all_day_yesterday = match(4, date(2026, 9, 19))
    tomorrow = match(5, at(21, 19))

    result = upcoming([tomorrow, finished, all_day_yesterday, tonight, all_day_today], NOW)

    assert [m.source_id for m in result] == ["3", "2", "5"]


def test_a_match_in_progress_still_counts_as_upcoming():
    in_progress = match(1, at(20, 14))  # 16:15'e kadar sürer
    assert upcoming([in_progress], NOW) == [in_progress]


def test_upcoming_is_limited():
    matches = [match(i, at(21, 12) + timedelta(days=i)) for i in range(UPCOMING_LIMIT + 5)]
    result = upcoming(matches, NOW)
    assert len(result) == UPCOMING_LIMIT
    assert result == sorted(result, key=lambda m: m.sort_key)


def test_format_when_uses_turkish_weekdays_and_flags_unknown_times():
    assert format_when(match(1, at(20, 20))) == "Pazar 20.09.2026 · 20:00"
    assert format_when(match(2, date(2026, 10, 31))) == "Cumartesi 31.10.2026 · saat belli değil"


def test_index_lists_feeds_matches_and_source_information():
    html = render_index(
        [match(1, at(20, 20), home="Amed Sportif Faaliyetler", away="Beşiktaş", venue="Diyarbakır Stadyumu, Diyarbakır")],
        NOW,
        BESIKTAS,
    )
    for filename in ("besiktas-all.ics", "besiktas-football.ics", "besiktas-basketball.ics"):
        assert f'data-feed="{filename}"' in html
    assert "Amed Sportif Faaliyetler - Beşiktaş" in html
    assert "Diyarbakır Stadyumu, Diyarbakır" in html
    assert "last_check.txt" in html
    assert '<html lang="tr">' in html


def test_each_feed_has_an_apple_button_a_google_button_and_a_separate_download_link():
    html = render_index([], NOW, BESIKTAS)
    cards = re.findall(r'<section class="feed"><h3>.*?</section>', html, re.DOTALL)
    assert len(cards) == 3  # bağış bölümü <h3> ile başlamaz
    for card, kind in zip(cards, ("all", "football", "basketball"), strict=True):
        filename = f"besiktas-{kind}.ics"
        assert f'data-feed="{filename}"' in card and "Apple Takvim'e abone ol" in card
        assert f'data-google="{filename}"' in card and "Google Takvim'e abone ol" in card
        assert f'<a class="dl" href="{filename}" download>.ics indir</a>' in card


def test_apple_and_google_parts_are_tagged_so_each_device_sees_only_its_own():
    html = render_index([], NOW, BESIKTAS)
    assert html.count('class="btn for-apple" data-feed=') == 3
    assert html.count('class="btn for-google" data-google=') == 3
    assert html.count('<li class="for-apple">') == 1 and html.count('<li class="for-google">') == 1
    assert '[data-platform="android"] .for-apple,[data-platform="apple"] .for-google{display:none}' in CSS
    # indirme bağlantısı ve adres kutusu her cihazda görünür kalır
    assert html.count('<a class="dl" href=') == 3 and html.count("<code data-url=") == 3


def test_script_detects_apple_and_android_and_leaves_both_buttons_on_computers():
    assert "/iPhone|iPad|iPod/.test(ua)" in SCRIPT and "/Android/.test(ua)" in SCRIPT
    assert "navigator.maxTouchPoints > 1" in SCRIPT  # iPadOS masaüstü tarayıcı kimliğiyle gelir
    assert "document.documentElement.dataset.platform = platform" in SCRIPT
    assert "if (platform !== 'other')" in SCRIPT and "a.textContent = 'Takvime abone ol'" in SCRIPT


def test_page_explains_why_android_goes_through_google_calendars_web_page():
    html = render_index([], NOW, BESIKTAS)
    assert "Google Takvim uygulaması telefonda URL ile abone olmayı desteklemez" in html
    assert "Masaüstü sitesi" in html
    assert "yalnızca bir kez ekler" in html  # .ics indirmek abonelik değildir


def test_index_escapes_team_names():
    html = render_index([match(1, at(20, 20), away="<script>alert(1)</script>")], NOW, BESIKTAS)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html


def test_index_without_upcoming_matches_says_so():
    html = render_index([match(1, at(1, 20))], NOW, BESIKTAS)
    assert "Yaklaşan maç bulunamadı." in html


def test_index_has_social_preview_and_accessibility_basics():
    html = render_index([], NOW, BESIKTAS)
    assert '<meta property="og:title" content="Beşiktaş Maç Takvimi">' in html
    assert '<meta property="og:locale" content="tr_TR">' in html
    assert '<html lang="tr">' in html
    assert html.count("<h1>") == 1  # tek ana başlık
    assert '<meta name="viewport" content="width=device-width,initial-scale=1">' in html


def test_index_is_deterministic_for_the_same_input():
    matches = [match(1, at(20, 20)), match(2, at(25, 20), sport=BASKETBALL)]
    assert render_index(matches, NOW, BESIKTAS) == render_index(matches, NOW, BESIKTAS)
