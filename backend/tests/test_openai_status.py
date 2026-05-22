from types import SimpleNamespace

from app.services import openai_status


def test_validate_openai_model_reports_missing_key(monkeypatch) -> None:
    openai_status.validate_openai_model.cache_clear()
    monkeypatch.setattr(
        openai_status,
        "get_settings",
        lambda: SimpleNamespace(openai_api_key=None, openai_model="gpt-test"),
    )
    status = openai_status.validate_openai_model()
    assert status["openai_configured"] is False
    assert status["model_validated"] is False
    assert "OPENAI_API_KEY" in status["error"]
    openai_status.validate_openai_model.cache_clear()

