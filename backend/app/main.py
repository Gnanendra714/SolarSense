from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from sqlalchemy import text

from app.core.config import settings
from app.database.session import Base, engine
from app.api.routes import router
from app.models import tables  # noqa: F401
from app.machine_learning.inference.api import router as ml_router


def validate_production_settings() -> None:
    if not settings.is_production:
        return
    if not settings.device_api_key or settings.device_api_key.startswith("replace-with-"):
        raise RuntimeError("DEVICE_API_KEY must be configured in production.")
    if not settings.admin_api_key or settings.admin_api_key.startswith("replace-with-"):
        raise RuntimeError("ADMIN_API_KEY must be configured in production.")
    if not settings.allowed_origins or any("localhost" in origin for origin in settings.allowed_origins):
        raise RuntimeError("CORS_ORIGINS must contain the deployed dashboard origin in production.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_production_settings()
    # Creates missing tables on a fresh database. Existing schema changes must be
    # applied with the documented migration command before deploying a new version.
    Base.metadata.create_all(bind=engine)
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    yield
    engine.dispose()


app = FastAPI(
    title="SolarSense API",
    version="2.2.0",
    description="Solar panel energy monitoring API",
    lifespan=lifespan,
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None if settings.is_production else "/redoc",
    openapi_url=None if settings.is_production else "/openapi.json",
)

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response: Response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Cache-Control", "no-store")
        if settings.is_production:
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response


app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-Device-Key", "X-Admin-Key"],
)

app.include_router(router)
app.include_router(ml_router)


@app.get("/")
def root():
    return {"service": "SolarSense API", "docs": None if settings.is_production else "/docs", "health": "/api/v1/health"}
