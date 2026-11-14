"""Optional FastAPI router for adding inference to the existing backend.

Mount this router only after confirming your backend's import/package layout.
It intentionally does not write to the database or create alerts.
"""
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
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


@router.post("/predict")
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
