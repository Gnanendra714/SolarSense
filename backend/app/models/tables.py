from sqlalchemy import String, Float, Boolean, DateTime, Integer, Index, Text
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime, timezone
from app.database.session import Base


def utcnow():
    return datetime.now(timezone.utc)


class Reading(Base):
    __tablename__ = "readings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    device_id: Mapped[str] = mapped_column(String(80), index=True, default="solar-panel-01")
    # Nullable only to preserve compatibility with pre-migration historical rows.
    # The migration backfills IDs; all new ingestion paths require one.
    reading_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="hardware")
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    voltage_v: Mapped[float] = mapped_column(Float)
    current_a: Mapped[float] = mapped_column(Float)
    power_w: Mapped[float] = mapped_column(Float)
    panel_temp_c: Mapped[float] = mapped_column(Float)
    light_lux: Mapped[float] = mapped_column(Float)
    energy_wh: Mapped[float] = mapped_column(Float, default=0)

    __table_args__ = (
        Index("ix_readings_device_timestamp", "device_id", "timestamp"),
    )


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    device_id: Mapped[str] = mapped_column(String(80), index=True)
    severity: Mapped[str] = mapped_column(String(16))
    title: Mapped[str] = mapped_column(String(160))
    message: Mapped[str] = mapped_column(String(500))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, default=utcnow)
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)


class DeviceState(Base):
    __tablename__ = "device_state"

    device_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ina219_ok: Mapped[bool] = mapped_column(Boolean, default=False)
    ds18b20_ok: Mapped[bool] = mapped_column(Boolean, default=False)
    bh1750_ok: Mapped[bool] = mapped_column(Boolean, default=False)
    agent_version: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    sensor_mode: Mapped[str] = mapped_column(String(16), nullable=False, default="unknown")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="unknown")
    sensor_errors: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
