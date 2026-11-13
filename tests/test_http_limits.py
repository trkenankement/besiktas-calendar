import pytest
from urllib3.response import HTTPResponse

from helpers import FakeSession
from club_calendar import http


@pytest.mark.parametrize("header,expected", [("1200", 30), ("5", 5), ("Wed, 21 Oct 2099 07:28:00 GMT", 30)])
def test_retry_after_is_bounded_and_short_delays_are_preserved(header, expected):
    retry = http.new_session().get_adapter("https://example.test").max_retries
    response = HTTPResponse(headers={"Retry-After": header})
    assert retry.get_retry_after(response) == expected


def test_retry_after_has_a_shared_session_budget(monkeypatch):
    slept = []
    monkeypatch.setattr(http.time, "sleep", slept.append)
    base = http.new_session().get_adapter("https://example.test").max_retries
    retry = base
    response = HTTPResponse(status=503, headers={"Retry-After": "1200"})
    for _ in range(2):
        retry = retry.increment(method="GET", url="https://example.test", response=response)
        assert retry.sleep_for_retry(response)
    assert slept == [30, 30]
    # A fresh request reuses the adapter's budget, rather than resetting it.
    fresh = base.new()
    with pytest.raises(http.SourceError, match="bekleme sınırı"):
        fresh.sleep_for_retry(response)


def test_response_limit_rejects_large_body_and_keeps_small_json(monkeypatch):
    monkeypatch.setattr(http, "MAX_RESPONSE_BYTES", 12)
    session = FakeSession(lambda url, params: {"ok": True})
    assert http.get_json(session, "https://example.test") == {"ok": True}

    with pytest.raises(http.SourceError, match="bayt sınırını aştı"):
        http.get_html(FakeSession(lambda url, params: "x" * 13), "https://example.test")
