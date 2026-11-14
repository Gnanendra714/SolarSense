
from datetime import datetime

from sqlalchemy import (
    String, Float, DateTime, Integer,
    ForeignKey, Index
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.session import Base


class DemoSession(Base):
    __tablename__ = "demo_sessions"

    session_id: Mapped[str] = mapped_column(
        String(36), primary_key=True
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    last_generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    stopped_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class DemoReading(Base):
    __tablename__ = "demo_readings"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, index=True
    )
    session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("demo_sessions.session_id", ondelete="CASCADE"),
        index=True
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    voltage_v: Mapped[float] = mapped_column(Float, nullable=False)
    current_a: Mapped[float] = mapped_column(Float, nullable=False)
    power_w: Mapped[float] = mapped_column(Float, nullable=False)
    panel_temp_c: Mapped[float] = mapped_column(Float, nullable=False)
    light_lux: Mapped[float] = mapped_column(Float, nullable=False)
    energy_wh: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0
    )

    __table_args__ = (
        Index(
            "ix_demo_readings_session_timestamp",
            "session_id",
            "timestamp"
        ),
    )
