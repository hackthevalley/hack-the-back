from app.config import AppConfig
from app.main import get_application


def test_api_docs_are_enabled_by_default(monkeypatch):
    monkeypatch.setattr(AppConfig, "ENABLE_API_DOCS", True)
    app = get_application()

    assert app.docs_url == "/docs"
    assert app.redoc_url == "/redoc"
    assert app.openapi_url == "/openapi.json"


def test_api_docs_can_be_disabled_for_production(monkeypatch):
    monkeypatch.setattr(AppConfig, "ENABLE_API_DOCS", False)
    app = get_application()

    assert app.docs_url is None
    assert app.redoc_url is None
    assert app.openapi_url is None
