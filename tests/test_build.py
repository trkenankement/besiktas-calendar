from dataclasses import replace
from datetime import date, datetime, timedelta
from pathlib import Path

from helpers import BESIKTAS
from icalendar import Calendar

from club_calendar import build, cli
from club_calendar.http import SourceError
from club_calendar.models import BASKETBALL, FOOTBALL, TURKEY_TZ, Match
from club_calendar.providers import Provider

NOW = datetime(2026, 9, 20, 15, 0, tzinfo=TURKEY_TZ)


def make_matches(sport, count, *, source="tff", first_id=1):
    return [
        Match(
            source=source,
            source_id=str(first_id + i),
            sport=sport,
            competition="Test Ligi",
            round_label=f"{i + 1}. Hafta",
            start=datetime(2026, 10, 1, 20, 0, tzinfo=TURKEY_TZ) + timedelta(days=7 * i),
            home="Beşiktaş",
            away=f"Rakip {i}",
        )
        for i in range(count)
    ]


def provider(name, matches=(), *, error=None, required=True, min_matches=0):
    def fetch(session, today, club):
        if error is not None:
            raise error
        return list(matches)

    return Provider(name, name, fetch, required=required, min_matches=min_matches)


def working_providers():
    return [
        provider("futbol", make_matches(FOOTBALL, 6)),
        provider("basketbol", make_matches(BASKETBALL, 6, source="tbf")),
    ]


def events_in(path: Path):
    calendar = Calendar.from_ical(path.read_bytes())
    return [c for c in calendar.walk() if c.name == "VEVENT"]


def test_successful_run_writes_every_output_and_splits_the_feeds_by_sport(tmp_path, monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    assert build.run(tmp_path, BESIKTAS, providers=working_providers(), session=object(), now=NOW) == 0

    assert len(events_in(tmp_path / "besiktas-all.ics")) == 12
    assert len(events_in(tmp_path / "besiktas-football.ics")) == 6
    assert len(events_in(tmp_path / "besiktas-basketball.ics")) == 6
    assert "Sıradaki maçlar" in (tmp_path / "index.html").read_text(encoding="utf-8")
    assert (tmp_path / "last_check.txt").read_text(encoding="utf-8") == "20.09.2026 15:00 (TSİ)\n"


def test_output_folder_is_created_when_missing(tmp_path):
    out = tmp_path / "yeni" / "docs"
    assert build.run(out, BESIKTAS, providers=working_providers(), session=object(), now=NOW) == 0
    assert (out / "besiktas-all.ics").exists()


def test_a_second_run_with_unchanged_data_rewrites_nothing_but_the_check_time(tmp_path):
    build.run(tmp_path, BESIKTAS, providers=working_providers(), session=object(), now=NOW)
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir() if p.name != "last_check.txt"}

    later = NOW + timedelta(minutes=30)
    assert build.run(tmp_path, BESIKTAS, providers=working_providers(), session=object(), now=later) == 0

    assert {p.name: p.read_bytes() for p in tmp_path.iterdir() if p.name != "last_check.txt"} == before
    assert (tmp_path / "last_check.txt").read_text(encoding="utf-8") == "20.09.2026 15:30 (TSİ)\n"


def test_a_failing_required_source_keeps_the_last_good_files(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    last_good = tmp_path / "besiktas-all.ics"
    last_good.write_text("SON SAĞLAM SÜRÜM", encoding="utf-8")
    providers = working_providers() + [provider("bozuk", error=SourceError("erişilemedi"))]

    assert build.run(tmp_path, BESIKTAS, providers=providers, session=object(), now=NOW) == 1

    assert last_good.read_text(encoding="utf-8") == "SON SAĞLAM SÜRÜM"
    assert not (tmp_path / "index.html").exists()
    output = capsys.readouterr().out
    assert "bozuk" in output and "erişilemedi" in output


def test_a_failing_optional_source_only_warns(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    providers = working_providers() + [provider("kupa", error=SourceError("sayfa değişti"), required=False)]

    assert build.run(tmp_path, BESIKTAS, providers=providers, session=object(), now=NOW) == 0

    assert "UYARI" in capsys.readouterr().out
    assert len(events_in(tmp_path / "besiktas-all.ics")) == 12


def test_unexpected_exceptions_are_reported_as_source_failures(tmp_path):
    outcomes = build.collect([provider("x", error=KeyError("alan"))], session=object(), today=date(2026, 9, 20), club=BESIKTAS)
    assert outcomes[0].error is not None and "KeyError" in outcomes[0].error


def test_too_few_matches_from_a_source_is_treated_as_a_broken_source(tmp_path):
    providers = [provider("futbol", make_matches(FOOTBALL, 6), min_matches=30), working_providers()[1]]
    assert build.run(tmp_path, BESIKTAS, providers=providers, session=object(), now=NOW) == 1
    assert not (tmp_path / "besiktas-all.ics").exists()


def test_each_sport_needs_a_minimum_number_of_matches(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    only_football = [provider("futbol", make_matches(FOOTBALL, 6))]

    assert build.run(tmp_path, BESIKTAS, providers=only_football, session=object(), now=NOW) == 1
    assert "Basketbol" in capsys.readouterr().out


def test_implausible_dates_stop_the_publication(tmp_path, capsys, monkeypatch):
    """Yanlış okunmuş bir yıl (ör. 1970) yayınlanmadan yakalanır."""
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    weird = replace(make_matches(FOOTBALL, 1, source="x", first_id=99)[0], start=datetime(1970, 1, 1, 12, 0, tzinfo=TURKEY_TZ))
    providers = [*working_providers(), provider("bozuk-tarih", [weird])]

    assert build.run(tmp_path, BESIKTAS, providers=providers, session=object(), now=NOW) == 1

    assert "mantıksız" in capsys.readouterr().out
    assert not (tmp_path / "besiktas-all.ics").exists()


def test_dates_within_a_season_are_plausible():
    matches = make_matches(FOOTBALL, 6)
    assert build.date_problems(matches, NOW.date()) == []


def test_the_same_match_from_two_sources_is_published_once(tmp_path):
    duplicate = make_matches(FOOTBALL, 6)
    providers = [provider("a", duplicate), provider("b", duplicate), working_providers()[1]]
    build.run(tmp_path, BESIKTAS, providers=providers, session=object(), now=NOW)
    assert len(events_in(tmp_path / "besiktas-football.ics")) == 6


def test_github_actions_gets_annotations_and_a_step_summary(tmp_path, capsys, monkeypatch):
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    providers = working_providers() + [provider("bozuk", error=SourceError("erişilemedi"))]

    assert build.run(tmp_path / "docs", BESIKTAS, providers=providers, session=object(), now=NOW) == 1

    assert "::error::" in capsys.readouterr().out
    text = summary.read_text(encoding="utf-8")
    assert "| futbol | ✅ | 6 |" in text
    assert "| bozuk | ❌ | 0 |" in text


def test_cli_forwards_the_output_folder_and_the_club(monkeypatch, tmp_path):
    received = []
    monkeypatch.setattr(cli, "run", lambda out, club: received.append((out, club.key)) or 0)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "club.toml").write_text('club = "fenerbahce"\n', encoding="utf-8")

    assert cli.main(["--out", "cikti"]) == 0  # kulüp club.toml dosyasından gelir
    assert cli.main(["--club", "galatasaray"]) == 0  # komut satırı club.toml'u geçersiz kılar
    assert received == [(Path("cikti"), "fenerbahce"), (Path("docs"), "galatasaray")]
