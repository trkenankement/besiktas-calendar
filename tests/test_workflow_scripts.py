"""İş akışındaki kabuk betiklerini gerçekten çalıştırır (yerel bir git deposu ve sahte `gh` ile).

GitHub'da ancak veri değiştiğinde ya da 45 gün geçtiğinde çalışan yollar (commit, yeniden deneme, "zamanlamayı canlı
tut" commit'i) burada her seferinde denenir.
"""

import json
import os
import shutil
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = yaml.safe_load((ROOT / ".github" / "workflows" / "update-calendar.yml").read_text(encoding="utf-8"))
MASKED_VALUE = "dummy-" * 3  # uydurma değer; günlükte görünmemesi sınanır
ENV = {"GITHUB_TOKEN": MASKED_VALUE, "OWNER": "octo", "OWNER_ID": "42", "GITHUB_REPOSITORY": "octo/repo", "GH_TOKEN": MASKED_VALUE}


def _find_bash():
    git = shutil.which("git")
    if os.name == "nt":  # Windows'ta WSL'in bash.exe'si yerine Git for Windows'un bash'i kullanılır
        if not git:
            return None
        exec_path = subprocess.run([git, "--exec-path"], capture_output=True, text=True, check=False).stdout.strip()
        candidate = Path(exec_path).parents[2] / "bin" / "bash.exe"
        return str(candidate) if candidate.exists() else None
    return shutil.which("bash")


BASH = _find_bash()
pytestmark = pytest.mark.skipif(BASH is None or shutil.which("git") is None, reason="bash ve git gerekir")


def step_script(name: str) -> str:
    return next(step["run"] for step in WORKFLOW["jobs"]["build"]["steps"] if step["name"] == name)


def run_bash(code: str, cwd: Path, env: dict[str, str] | None = None):
    return subprocess.run(
        [BASH, "-c", code], cwd=cwd, env={**os.environ, **(env or {})}, capture_output=True, text=True, encoding="utf-8", check=False
    )


def git(*args: str, cwd: Path, env: dict[str, str] | None = None) -> str:
    result = subprocess.run(
        ["git", *args], cwd=cwd, env={**os.environ, **(env or {})}, capture_output=True, text=True, encoding="utf-8", check=True
    )
    return result.stdout.strip()


def make_repo(tmp_path: Path, age_days: float = 0):
    """Uzak (bare) depo + bir klon; ilk commit `age_days` gün önce atılmış gibi tarihlenir."""
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", "-b", "main", str(remote)], check=True, capture_output=True)
    work = tmp_path / "work"
    subprocess.run(["git", "clone", str(remote), str(work)], check=True, capture_output=True)
    git("symbolic-ref", "HEAD", "refs/heads/main", cwd=work)
    (work / "docs").mkdir()
    (work / "docs" / "a.txt").write_text("1\n", encoding="utf-8")
    when = (datetime.now(UTC) - timedelta(days=age_days)).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    dates = {"GIT_AUTHOR_DATE": when, "GIT_COMMITTER_DATE": when}
    git("add", ".", cwd=work)
    git("-c", "user.name=Kurulum", "-c", "user.email=kurulum@example.com", "commit", "-m", "ilk", cwd=work, env=dates)
    git("push", "origin", "main", cwd=work)
    return remote, work


def remote_log(remote: Path) -> list[str]:
    return git("log", "main", "--format=%an <%ae>|%s", cwd=remote).splitlines()


def run_commit_step(work: Path):
    return run_bash(step_script("Commit changes"), work, ENV)


# --- "Commit changes" ------------------------------------------------------------------------------


def test_changed_docs_are_committed_under_the_owners_identity_and_pushed(tmp_path):
    remote, work = make_repo(tmp_path)
    (work / "docs" / "a.txt").write_text("2\n", encoding="utf-8")

    result = run_commit_step(work)

    assert result.returncode == 0, result.stderr
    assert remote_log(remote)[0] == "octo <42+octo@users.noreply.github.com>|chore: update calendars"
    assert len(remote_log(remote)) == 2


def test_the_token_never_appears_in_the_output(tmp_path):
    _, work = make_repo(tmp_path)
    (work / "docs" / "a.txt").write_text("2\n", encoding="utf-8")

    result = run_commit_step(work)

    assert MASKED_VALUE not in result.stdout + result.stderr
    assert "::add-mask::" in result.stdout  # kodlanmış biçimi de günlükte gizlenir


def test_nothing_is_committed_when_docs_did_not_change(tmp_path):
    remote, work = make_repo(tmp_path, age_days=1)

    result = run_commit_step(work)

    assert result.returncode == 0, result.stderr
    assert "commit atılmadı" in result.stdout
    assert len(remote_log(remote)) == 1


@pytest.mark.parametrize(("age_days", "expect_keepalive"), [(44, False), (46, True), (90, True)])
def test_an_empty_commit_keeps_the_schedule_alive_only_after_45_quiet_days(tmp_path, age_days, expect_keepalive):
    remote, work = make_repo(tmp_path, age_days=age_days)

    result = run_commit_step(work)

    assert result.returncode == 0, result.stderr
    log = remote_log(remote)
    assert (len(log) == 2) is expect_keepalive
    if expect_keepalive:
        assert log[0] == "octo <42+octo@users.noreply.github.com>|chore: keep scheduled workflow active"


def test_a_rejected_push_is_retried_after_rebasing(tmp_path):
    """Çalışma sürerken `main`'e başka bir commit geldiyse betik yeniden dener."""
    remote, work = make_repo(tmp_path)
    other = tmp_path / "other"
    subprocess.run(["git", "clone", str(remote), str(other)], check=True, capture_output=True)
    (other / "docs" / "b.txt").write_text("baska\n", encoding="utf-8")
    git("add", ".", cwd=other)
    git("-c", "user.name=Baska", "-c", "user.email=baska@example.com", "commit", "-m", "araya giren commit", cwd=other)
    git("push", "origin", "main", cwd=other)
    (work / "docs" / "a.txt").write_text("2\n", encoding="utf-8")

    result = run_commit_step(work)

    assert result.returncode == 0, result.stderr
    log = remote_log(remote)
    assert [entry.split("|")[1] for entry in log] == ["chore: update calendars", "araya giren commit", "ilk"]


# --- "Fetch repository stats" ----------------------------------------------------------------------


def test_stats_are_written_when_gh_succeeds(tmp_path):
    (tmp_path / "docs").mkdir()
    fake_gh = "gh() { echo '{\"stars\":3,\"watchers\":2}'; }\n"

    result = run_bash(fake_gh + step_script("Fetch repository stats"), tmp_path, ENV)

    assert result.returncode == 0, result.stderr
    assert json.loads((tmp_path / "docs" / "stats.json").read_text(encoding="utf-8")) == {"stars": 3, "watchers": 2}
    assert not (tmp_path / "stats.tmp").exists()


def test_previous_stats_survive_a_failing_gh_and_the_job_goes_on(tmp_path):
    (tmp_path / "docs").mkdir()
    previous = '{"stars":1,"watchers":1}'
    (tmp_path / "docs" / "stats.json").write_text(previous, encoding="utf-8")
    fake_gh = "gh() { echo 'yarım kalan çıktı'; return 1; }\n"

    result = run_bash(fake_gh + step_script("Fetch repository stats"), tmp_path, ENV)

    assert result.returncode == 0, result.stderr  # istatistik alınamaması takvim güncellemesini durdurmaz
    assert (tmp_path / "docs" / "stats.json").read_text(encoding="utf-8") == previous
    assert not (tmp_path / "stats.tmp").exists()
    assert "::warning::" in result.stdout
