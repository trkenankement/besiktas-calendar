import json
from datetime import datetime

import pytest
from helpers import BESIKTAS

from club_calendar import build
from club_calendar.models import BASKETBALL, FOOTBALL, TURKEY_TZ, Match
from club_calendar.providers import Provider
from club_calendar.site import render_index
from club_calendar.stats import RepoStats, load_stats

NOW = datetime(2026, 9, 20, 15, 0, tzinfo=TURKEY_TZ)


def write(path, payload):
    path.write_text(payload if isinstance(payload, str) else json.dumps(payload), encoding="utf-8")
    return path


def test_valid_stats_are_loaded(tmp_path):
    assert load_stats(write(tmp_path / "stats.json", {"stars": 3, "watchers": 2})) == RepoStats(stars=3, watchers=2)


def test_zero_counts_are_valid(tmp_path):
    assert load_stats(write(tmp_path / "stats.json", {"stars": 0, "watchers": 0})) == RepoStats(0, 0)


def test_missing_file_means_no_stats(tmp_path):
    assert load_stats(tmp_path / "stats.json") is None


@pytest.mark.parametrize(
    "payload",
    [
        "not json",
        "[]",
        "null",
        {"stars": 1},
        {"watchers": 1},
        {"stars": "3", "watchers": 2},
        {"stars": 3.5, "watchers": 2},
        {"stars": True, "watchers": 2},
        {"stars": -1, "watchers": 2},
        {"stars": None, "watchers": 2},
        {"stars": "<script>alert(1)</script>", "watchers": 2},
    ],
)
def test_anything_but_plain_non_negative_integers_is_rejected(tmp_path, payload):
    assert load_stats(write(tmp_path / "stats.json", payload)) is None


def test_page_shows_the_counts_when_available():
    page = render_index([], NOW, BESIKTAS, RepoStats(stars=3, watchers=2))
    assert '<p class="muted" id="stats">' in page
    assert "<strong>2</strong> takipçi" in page
    assert "<strong>3</strong> yıldız" in page


def test_page_without_stats_shows_no_stats_line():
    assert 'id="stats"' not in render_index([], NOW, BESIKTAS)
    assert 'id="stats"' not in render_index([], NOW, BESIKTAS, None)


def _matches(sport, count, source):
    return [
        Match(
            source=source,
            source_id=str(i),
            sport=sport,
            competition="Test",
            round_label="",
            start=datetime(2026, 10, 1 + i, 20, 0, tzinfo=TURKEY_TZ),
            home="Beşiktaş",
            away=f"Rakip {i}",
        )
        for i in range(count)
    ]


def test_build_reads_stats_json_from_the_output_folder(tmp_path):
    write(tmp_path / "stats.json", {"stars": 7, "watchers": 4})
    providers = [
        Provider("f", "futbol", lambda session, today, club: _matches(FOOTBALL, 6, "tff")),
        Provider("b", "basketbol", lambda session, today, club: _matches(BASKETBALL, 6, "tbf")),
    ]

    assert build.run(tmp_path, BESIKTAS, providers=providers, session=object(), now=NOW) == 0

    page = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert "<strong>4</strong> takipçi" in page and "<strong>7</strong> yıldız" in page
    assert json.loads((tmp_path / "stats.json").read_text(encoding="utf-8")) == {"stars": 7, "watchers": 4}


def test_a_broken_stats_file_never_breaks_the_build(tmp_path):
    write(tmp_path / "stats.json", "{bozuk")
    providers = [
        Provider("f", "futbol", lambda session, today, club: _matches(FOOTBALL, 6, "tff")),
        Provider("b", "basketbol", lambda session, today, club: _matches(BASKETBALL, 6, "tbf")),
    ]

    assert build.run(tmp_path, BESIKTAS, providers=providers, session=object(), now=NOW) == 0
    assert 'id="stats"' not in (tmp_path / "index.html").read_text(encoding="utf-8")
