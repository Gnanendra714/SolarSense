"""Optional FastAPI router for adding inference to the existing backend.

Mount this router only after confirming your backend's import/package layout.
It intentionally does not write to the database or create alerts.
"""
from pathlib import Path
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, desc
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.tables import Reading, DeviceState
from app.api.deps import require_device_key
from pydantic import BaseModel, Field

from .predictor import SolarSensePredictor, PredictionError

router = APIRouter(prefix="/api/v1/ml", tags=["machine-learning"])
MODEL_DIR = Path(__file__).resolve().parents[1] / "models"
predictor = SolarSensePredictor(
    MODEL_DIR / "model.joblib",
    MODEL_DIR / "model_metadata.json",
)


class ReadingForPrediction(BaseModel):
    voltage_v: float = Field(ge=0)
    current_a: float = Field(ge=0)
    panel_temp_c: float
    light_lux: float = Field(ge=0)


@router.get("/health")
def ml_health() -> dict[str, Any]:
    return {
        "ready": predictor.is_ready,
        "model_version": predictor.model_version,
        "message": "Model loaded." if predictor.is_ready else predictor.load_error,
    }


@router.post("/predict", dependencies=[Depends(require_device_key)])
def predict_fault(reading: ReadingForPrediction) -> dict[str, Any]:
    if not predictor.is_ready:
        raise HTTPException(status_code=503, detail="ML model is not trained or installed.")
    try:
        result = predictor.predict(reading.model_dump())
    except PredictionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return {
        "predicted_class": result.predicted_class,
        "confidence": result.confidence,
        "probabilities": result.probabilities,
        "timestamp": result.timestamp,
        "model_version": result.model_version,
        "source": "model_prediction",
    }


@router.get("/latest-prediction")
def predict_latest(
    device_id: str = Query("solar-panel-01", min_length=1, max_length=80),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Run inference against the newest stored reading; never fabricate a result."""
    if not predictor.is_ready:
        raise HTTPException(status_code=503, detail="ML model is not trained or installed.")
    reading = db.scalar(
        select(Reading).where(Reading.device_id == device_id)
        .order_by(desc(Reading.timestamp)).limit(1)
    )
    if reading is None:
        raise HTTPException(status_code=404, detail="No readings are available for this device.")
    if reading.source != "hardware":
        raise HTTPException(
            status_code=409,
            detail=f"Inference is disabled for {reading.source} readings. A physical hardware reading is required.",
        )
    state = db.get(DeviceState, device_id)
    now = datetime.now(timezone.utc)
    if state is None or state.last_seen is None:
        raise HTTPException(status_code=409, detail="A current device heartbeat is required before inference.")
    last_seen = state.last_seen
    if last_seen.tzinfo is None:
        last_seen = last_seen.replace(tzinfo=timezone.utc)
    if (now - last_seen).total_seconds() > 120 or state.status != "healthy":
        raise HTTPException(status_code=409, detail="Device heartbeat is stale or device health is degraded; inference is disabled.")
    if not (state.ina219_ok and state.ds18b20_ok and state.bh1750_ok):
        raise HTTPException(status_code=409, detail="One or more required sensors are unhealthy; inference is disabled.")
    try:
        result = predictor.predict({
            "voltage_v": reading.voltage_v,
            "current_a": reading.current_a,
            "panel_temp_c": reading.panel_temp_c,
            "light_lux": reading.light_lux,
        })
    except PredictionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "device_id": device_id,
        "reading_timestamp": reading.timestamp.isoformat(),
        "reading_source": reading.source,
        "predicted_class": result.predicted_class,
        "confidence": result.confidence,
        "probabilities": result.probabilities,
        "prediction_timestamp": result.timestamp,
        "model_version": result.model_version,
        "source": "model_prediction",
        "warning": "Prediction is advisory and only valid to the extent supported by the model's physical validation dataset.",
    }
