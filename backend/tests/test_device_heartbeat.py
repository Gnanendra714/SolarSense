from datetime import datetime, timezone, timedelta
import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.session import Base
from app.models.tables import DeviceState
from app.schemas.reading import DeviceHeartbeatIn
from app.api.routes import device_heartbeat, system


def make_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_heartbeat_updates_device_state_and_sensor_errors():
    db = make_session()
    try:
        now = datetime.now(timezone.utc)
        payload = DeviceHeartbeatIn(
            heartbeat_id="12345678-1234-5678-1234-567812345678",
            device_id="pi-test", timestamp=now, source="hardware", agent_version="2.1.0",
            status="degraded", ina219_ok=True, ds18b20_ok=False, bh1750_ok=True,
            sensor_errors={"ds18b20": "CRC check failed"},
        )
        result = device_heartbeat(payload, db)
        assert result["accepted"] is True
        state = db.get(DeviceState, "pi-test")
        assert state is not None
        assert state.ina219_ok is True
        assert state.ds18b20_ok is False
        assert state.status == "degraded"
        assert json.loads(state.sensor_errors)["ds18b20"] == "CRC check failed"
    finally:
        db.close()


def test_old_heartbeat_cannot_overwrite_newer_device_state():
    db = make_session()
    try:
        newer = datetime.now(timezone.utc)
        state = DeviceState(
            device_id="pi-test", last_seen=newer, ina219_ok=True,
            ds18b20_ok=True, bh1750_ok=True, status="healthy",
            sensor_mode="hardware", agent_version="2.1.0", sensor_errors="{}",
        )
        db.add(state)
        db.commit()
        older_payload = DeviceHeartbeatIn(
            heartbeat_id="12345678-1234-5678-1234-567812345679",
            device_id="pi-test", timestamp=newer - timedelta(minutes=5),
            source="hardware", agent_version="2.1.0", status="failed",
            ina219_ok=False, ds18b20_ok=False, bh1750_ok=False,
            sensor_errors={"ina219": "old event"},
        )
        device_heartbeat(older_payload, db)
        db.refresh(state)
        assert state.status == "healthy"
        assert state.ina219_ok is True
    finally:
        db.close()
