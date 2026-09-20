"""Güvenlik regresyon testleri.

Kaynak siteler bizim denetimimizde değil: onlardan gelen metin yayınladığımız ICS ve HTML çıktısını
bozamamalı. İş akışı da en az yetkiyle ve değiştirilemez (sabitlenmiş) eylemlerle çalışmalı.
"""

import base64
import hashlib
import re
import time
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path

import yaml
from helpers import BESIKTAS
from icalendar import Calendar

from club_calendar.ics import escape_text, render_calendar
from club_calendar.models import FOOTBALL, TURKEY_TZ, Match
from club_calendar.names import display_name
from club_calendar.site import CONTENT_SECURITY_POLICY, SCRIPT, STALE_AFTER_HOURS, render_index

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "update-calendar.yml"
STAMP = datetime(2026, 9, 20, 12, 0, tzinfo=UTC)
NOW = datetime(2026, 9, 20, 15, 0, tzinfo=TURKEY_TZ)

ICS_PAYLOAD = "Evil\r\nATTENDEE:mailto:evil@example.com\r\nX-INJECT:1\nEND:VEVENT\nBEGIN:VEVENT"
HTML_PAYLOAD = "<img src=x onerror=alert(1)><script>alert(2)</script>"


def match_with(text: str) -> Match:
    return Match(
        source="tff",
        source_id="1",
        sport=FOOTBALL,
        competition=text,
        round_label=text,
        start=datetime(2026, 10, 11, 19, 0, tzinfo=TURKEY_TZ),
        home=text,
        away=text,
        venue=text,
        broadcast=text,
        result=text,
    )


# --- ICS ---------------------------------------------------------------------------------------


def test_source_text_cannot_inject_ics_properties_or_events():
    text = render_calendar([match_with(ICS_PAYLOAD)], "Test", "", BESIKTAS, stamp=STAMP)
    lines = text.replace("\r\n ", "").split("\r\n")  # katlanmış satırları birleştir

    assert sum(line == "BEGIN:VEVENT" for line in lines) == 1
    assert sum(line == "END:VEVENT" for line in lines) == 1
    assert not any(line.startswith(("ATTENDEE", "X-INJECT")) for line in lines)

    calendar = Calendar.from_ical(text.encode("utf-8"))
    (event,) = [c for c in calendar.walk() if c.name == "VEVENT"]
    assert "ATTENDEE" not in event and "X-INJECT" not in event


def test_calendar_level_text_is_escaped_too():
    text = render_calendar([], "Ad\r\nX-INJECT:1", "Açıklama\r\nX-INJECT:2", BESIKTAS, stamp=STAMP)
    assert not any(line.startswith("X-INJECT") for line in text.replace("\r\n ", "").split("\r\n"))


def test_control_characters_are_removed_but_tab_is_kept():
    assert escape_text("a\x00b\x07c\x1bd\x7fe\tf") == "abcde\tf"


def test_output_never_contains_bare_control_characters():
    text = render_calendar([match_with("x\x00y\x07z\x1b")], "Test", "", BESIKTAS, stamp=STAMP)
    assert not re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", text)


# --- Web sayfası --------------------------------------------------------------------------------


class _TagCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []
        self.attributes = []
        self.elements = []  # (etiket, {öznitelik: değer})

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        self.attributes += [name for name, _ in attrs]
        self.elements.append((tag, dict(attrs)))


def _parse(html: str) -> _TagCollector:
    collector = _TagCollector()
    collector.feed(html)
    return collector


def test_page_escapes_every_dynamic_field():
    page = render_index([match_with(HTML_PAYLOAD)], NOW, BESIKTAS)
    parsed = _parse(page)
    assert parsed.tags.count("img") == 1  # yalnızca bağış QR'ı; kaynak verisinden gelen bir <img> yok
    assert parsed.tags.count("script") == 1  # yalnızca kendi betiğimiz
    assert "&lt;img src=x onerror=alert(1)&gt;" in page


def test_page_has_no_inline_event_handlers_or_external_resources():
    page = render_index([match_with("Rakip")], NOW, BESIKTAS)
    parsed = _parse(page)
    assert not [a for a in parsed.attributes if a.startswith("on")]
    assert not {"iframe", "object", "embed", "form", "input"} & set(parsed.tags)
    (image,) = [attrs for tag, attrs in parsed.elements if tag == "img"]
    assert "://" not in image["src"] and not image["src"].startswith("//")  # yalnızca aynı siteden
    assert "<script src" not in page
    assert 'rel="stylesheet"' not in page


def test_csp_allows_exactly_the_inline_script_and_style_that_the_page_contains():
    page = render_index([match_with("Rakip")], NOW, BESIKTAS)

    def source_hash(tag: str) -> str:
        (content,) = re.findall(rf"<{tag}>(.*?)</{tag}>", page, re.DOTALL)
        digest = hashlib.sha256(content.encode("utf-8")).digest()
        return "'sha256-" + base64.b64encode(digest).decode("ascii") + "'"

    assert f'content="{CONTENT_SECURITY_POLICY}"' in page
    assert f"script-src {source_hash('script')}" in CONTENT_SECURITY_POLICY
    assert f"style-src {source_hash('style')}" in CONTENT_SECURITY_POLICY


def test_csp_is_restrictive():
    assert CONTENT_SECURITY_POLICY.startswith("default-src 'none'")
    assert "unsafe-inline" not in CONTENT_SECURITY_POLICY
    assert "unsafe-eval" not in CONTENT_SECURITY_POLICY
    assert "base-uri 'none'" in CONTENT_SECURITY_POLICY
    assert "form-action 'none'" in CONTENT_SECURITY_POLICY
    assert "connect-src 'self'" in CONTENT_SECURITY_POLICY  # yalnızca last_check.txt ve stats
    assert "img-src 'self' data:" in CONTENT_SECURITY_POLICY  # yalnızca aynı siteden görsel (bağış QR'ı)


def test_page_warns_when_the_last_check_is_stale():
    page = render_index([match_with("Rakip")], NOW, BESIKTAS)
    assert 'id="stale"' in page and 'role="alert"' in page
    assert f"hours > {STALE_AFTER_HOURS}" in SCRIPT
    assert "textContent" in SCRIPT and "innerHTML" not in SCRIPT


def test_external_link_cannot_leak_the_opener_or_referrer():
    page = render_index([match_with("Rakip")], NOW, BESIKTAS)
    assert 'rel="noopener noreferrer"' in page
    assert '<meta name="referrer" content="no-referrer">' in page


def test_every_link_that_opens_another_tab_carries_noopener_noreferrer():
    parsed = _parse(render_index([match_with("Rakip")], NOW, BESIKTAS))
    new_tab_links = [attrs for tag, attrs in parsed.elements if tag == "a" and "target" in attrs]
    assert new_tab_links, "Google Takvim düğmeleri yeni sekmede açılmalı"
    assert all(attrs["target"] == "_blank" and attrs["rel"] == "noopener noreferrer" for attrs in new_tab_links)


def test_subscription_links_are_built_only_from_our_own_file_names():
    """Betik `data-feed`/`data-google` değerini adrese ekler; bu değerler yalnızca düz dosya adı olabilir."""
    parsed = _parse(render_index([match_with("Rakip")], NOW, BESIKTAS))
    values = [attrs[name] for _, attrs in parsed.elements for name in ("data-feed", "data-google", "data-url") if name in attrs]
    assert len(values) == 9  # 3 akış x (Apple, Google, adres kutusu)
    assert all(re.fullmatch(r"[a-z0-9]+-[a-z]+\.ics", value) for value in values)


def test_script_only_adds_a_fixed_https_prefix_and_never_evaluates_text():
    assert "'https://calendar.google.com/calendar/r?cid=webcal://' + url.host + url.pathname" in SCRIPT
    for forbidden in ("eval(", "Function(", "document.write", "innerHTML", "insertAdjacentHTML", "setAttribute('on"):
        assert forbidden not in SCRIPT


# --- Girdi dayanıklılığı -----------------------------------------------------------------------


def test_name_normalisation_stays_fast_on_pathological_input():
    nasty = [
        "A. " * 60000 + "A.Ş.",
        " " * 200000 + "X",
        "A." * 100000,
        "Ş" * 300000,
        "-" * 100000 + "'" * 100000,
    ]
    started = time.perf_counter()
    for text in nasty:
        display_name(text)
    assert time.perf_counter() - started < 5


# --- İş akışı politikası ------------------------------------------------------------------------


def _workflow():
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def test_every_action_is_pinned_to_a_full_commit_sha():
    uses = re.findall(r"^\s*(?:-\s*)?uses:\s*(\S+)", WORKFLOW.read_text(encoding="utf-8"), re.MULTILINE)
    assert uses, "iş akışında hiç eylem bulunamadı"
    for reference in uses:
        assert re.fullmatch(r"[\w.-]+/[\w./-]+@[0-9a-f]{40}", reference), f"sabitlenmemiş eylem: {reference}"


def test_checkout_does_not_persist_the_token():
    steps = _workflow()["jobs"]["build"]["steps"]
    (checkout,) = [s for s in steps if s.get("uses", "").startswith("actions/checkout@")]
    assert checkout["with"]["persist-credentials"] is False


def test_token_is_given_only_to_the_trusted_gh_and_git_steps():
    """Proje kodunu ve paket kurulumunu çalıştıran adımlar belirteci hiç görmez."""
    trusted = {"Fetch repository stats", "Commit changes"}
    for job in _workflow()["jobs"].values():
        for step in job["steps"]:
            has_token = "github.token" in str(step.get("env", {})) or "GITHUB_TOKEN" in str(step.get("with", {}))
            assert has_token == (step["name"] in trusted), step["name"]


def test_token_steps_run_no_project_code():
    for job in _workflow()["jobs"].values():
        for step in job["steps"]:
            if "github.token" in str(step.get("env", {})):
                script = step["run"]
                assert not re.search(r"\b(python|pip|pytest|club-calendar)\b", script), step["name"]


def test_permissions_follow_least_privilege():
    workflow = _workflow()
    assert workflow["permissions"] == {"contents": "read"}
    assert workflow["jobs"]["build"]["permissions"] == {"contents": "write"}
    assert workflow["jobs"]["deploy"]["permissions"] == {"pages": "write", "id-token": "write"}


def test_workflow_avoids_dangerous_triggers_and_secrets():
    workflow = _workflow()
    triggers = set(workflow.get("on", workflow.get(True)))
    assert triggers == {"push", "schedule", "workflow_dispatch"}
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "secrets." not in text and "secrets: inherit" not in text


def test_shell_scripts_do_not_interpolate_github_expressions():
    """`run:` içinde ${{ }} kullanmak şablon enjeksiyonuna yol açar; değerler env ile verilir."""
    for job in _workflow()["jobs"].values():
        for step in job["steps"]:
            assert "${{" not in step.get("run", ""), step["name"]


def test_data_is_refreshed_once_a_day_shortly_after_midnight_turkey_time():
    """Türkiye UTC+3'tür: 21:xx UTC = gece 00:xx. Saatlik ya da sık bir zamanlama yanlışlıkla eklenemez."""
    workflow = _workflow()
    schedule = workflow.get("on", workflow.get(True))["schedule"]
    assert len(schedule) == 1
    minute, hour, day, month, weekday = schedule[0]["cron"].split()
    assert (day, month, weekday) == ("*", "*", "*")  # her gün
    assert hour == "21"  # 00:xx Türkiye saati
    assert minute.isdigit() and minute != "0"  # tam :00 yoğun; GitHub o dakikadaki işleri geciktirebilir ya da düşürebilir


def test_runners_are_pinned_to_a_specific_image():
    for job in _workflow()["jobs"].values():
        assert not job["runs-on"].endswith("-latest")
