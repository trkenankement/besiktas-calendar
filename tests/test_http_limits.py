import pytest

from helpers import FakeSession
from club_calendar import http


def test_response_limit_rejects_large_body_and_keeps_small_json(monkeypatch):
    monkeypatch.setattr(http, "MAX_RESPONSE_BYTES", 12)
    session = FakeSession(lambda url, params: {"ok": True})
    assert http.get_json(session, "https://example.test") == {"ok": True}

    with pytest.raises(http.SourceError, match="bayt sınırını aştı"):
        http.get_html(FakeSession(lambda url, params: "x" * 13), "https://example.test")
