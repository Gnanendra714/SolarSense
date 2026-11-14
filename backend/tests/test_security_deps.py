import pytest
from fastapi import HTTPException

from app.api.deps import _verify_secret


def test_configured_secret_rejects_missing_value(monkeypatch):
    monkeypatch.setattr("app.api.deps.settings.environment", "development")
    with pytest.raises(HTTPException) as exc:
        _verify_secret(None, "a-real-secret", "device API key")
    assert exc.value.status_code == 401


def test_configured_secret_accepts_matching_value(monkeypatch):
    monkeypatch.setattr("app.api.deps.settings.environment", "development")
    assert _verify_secret("a-real-secret", "a-real-secret", "device API key") is None


def test_unconfigured_secret_fails_closed_in_production(monkeypatch):
    monkeypatch.setattr("app.api.deps.settings.environment", "production")
    with pytest.raises(HTTPException) as exc:
        _verify_secret(None, "replace-with-secret", "admin API key")
    assert exc.value.status_code == 503
