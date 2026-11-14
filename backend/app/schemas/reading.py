from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class ReadingIn(BaseModel):
    reading_id: str = Field(default_factory=lambda: str(uuid4()), min_length=36, max_length=36)
    device_id: str = Field(default="solar-panel-01", min_length=1, max_length=80)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    voltage_v: float = Field(ge=0, le=30)
    current_a: float = Field(ge=0, le=5)
    power_w: float = Field(ge=0, le=150)
    panel_temp_c: float = Field(ge=-40, le=125)
    light_lux: float = Field(ge=0, le=200000)
    source: str = Field(default="hardware", pattern="^(hardware|simulated|legacy)$")
    ina219_ok: bool = True
    ds18b20_ok: bool = True
    bh1750_ok: bool = True


class ReadingBatchIn(BaseModel):
    items: list[ReadingIn] = Field(min_length=1, max_length=500)


class ReadingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    timestamp: datetime
    voltage_v: float
    current_a: float
    power_w: float
    panel_temp_c: float
    light_lux: float
    energy_wh: float


class DeviceHeartbeatIn(BaseModel):
    heartbeat_id: str = Field(min_length=36, max_length=36)
    device_id: str = Field(min_length=1, max_length=80)
    timestamp: datetime
    source: str = Field(pattern="^(hardware|simulated)$")
    agent_version: str = Field(min_length=1, max_length=32)
    status: str = Field(pattern="^(healthy|degraded|failed)$")
    ina219_ok: bool
    ds18b20_ok: bool
    bh1750_ok: bool
    sensor_errors: dict[str, str] = Field(default_factory=dict)
