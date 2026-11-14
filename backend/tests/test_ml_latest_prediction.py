from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.session import Base
from app.models.tables import Reading, DeviceState
from app.machine_learning.inference import api as ml_api


def make_session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def add_reading(db, source="simulated"):
    row = Reading(
        device_id="pi-test", reading_id="12345678-1234-5678-1234-567812345678",
        source=source, timestamp=datetime.now(timezone.utc), voltage_v=8.0,
        current_a=0.5, power_w=4.0, panel_temp_c=30.0, light_lux=12000.0,
        energy_wh=0.01,
    )
    db.add(row)
    db.add(DeviceState(
        device_id="pi-test", last_seen=datetime.now(timezone.utc),
        ina219_ok=True, ds18b20_ok=True, bh1750_ok=True,
        agent_version="test", sensor_mode="hardware", status="healthy", sensor_errors="{}",
    ))
    db.commit()


def test_latest_prediction_rejects_simulated_reading_even_if_model_ready(monkeypatch):
    class ReadyPredictor:
        is_ready = True

    monkeypatch.setattr(ml_api, "predictor", ReadyPredictor())
    db = make_session()
    try:
        add_reading(db, "simulated")
        with pytest.raises(HTTPException) as exc:
            ml_api.predict_latest("pi-test", db)
        assert exc.value.status_code == 409
    finally:
        db.close()


def test_latest_prediction_returns_503_when_model_missing(monkeypatch):
    class MissingPredictor:
        is_ready = False

    monkeypatch.setattr(ml_api, "predictor", MissingPredictor())
    db = make_session()
    try:
        with pytest.raises(HTTPException) as exc:
            ml_api.predict_latest("pi-test", db)
        assert exc.value.status_code == 503
    finally:
        db.close()


def test_latest_prediction_uses_only_latest_hardware_reading(monkeypatch):
    class Prediction:
        predicted_class = "normal"
        confidence = 0.91
        probabilities = {"normal": 0.91, "partial_shading": 0.03, "dust_accumulation": 0.03, "electrical_fault": 0.03}
        timestamp = datetime.now(timezone.utc).isoformat()
        model_version = "test-1"

    class ReadyPredictor:
        is_ready = True
        def predict(self, reading):
            assert reading["voltage_v"] == 8.0
            return Prediction()

    monkeypatch.setattr(ml_api, "predictor", ReadyPredictor())
    db = make_session()
    try:
        add_reading(db, "hardware")
        result = ml_api.predict_latest("pi-test", db)
        assert result["predicted_class"] == "normal"
        assert result["reading_source"] == "hardware"
        assert result["model_version"] == "test-1"
    finally:
        db.close()


def test_latest_prediction_rejects_offline_or_degraded_device(monkeypatch):
    class ReadyPredictor:
        is_ready = True

    monkeypatch.setattr(ml_api, "predictor", ReadyPredictor())
    db = make_session()
    try:
        add_reading(db, "hardware")
        state = db.get(DeviceState, "pi-test")
        state.status = "degraded"
        db.commit()
        with pytest.raises(HTTPException) as exc:
            ml_api.predict_latest("pi-test", db)
        assert exc.value.status_code == 409
    finally:
        db.close()
