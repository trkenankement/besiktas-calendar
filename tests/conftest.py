import pytest


@pytest.fixture(autouse=True)
def no_request_pause(monkeypatch):
    """Kaynak sitelere karşı kullanılan kibar bekleme testleri yavaşlatmasın."""
    monkeypatch.setattr("besiktas_calendar.http.REQUEST_PAUSE_SECONDS", 0)
