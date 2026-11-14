import hmac

from fastapi import Header, HTTPException

from app.core.config import settings


def _verify_secret(provided: str | None, configured: str, label: str) -> None:
    if not configured or configured.startswith("replace-with-"):
        if settings.is_production:
            raise HTTPException(status_code=503, detail=f"{label} is not configured")
        # Local development remains convenient, but any configured key is still enforced.
        return
    if not provided or not hmac.compare_digest(provided, configured):
        raise HTTPException(status_code=401, detail=f"Invalid {label}")


def require_device_key(x_device_key: str | None = Header(default=None)):
    _verify_secret(x_device_key, settings.device_api_key, "device API key")


def require_admin_key(x_admin_key: str | None = Header(default=None)):
    _verify_secret(x_admin_key, settings.admin_api_key, "admin API key")
