from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import json
import math

import joblib
import numpy as np

FEATURE_NAMES = (
    "voltage_v",
    "current_a",
    "panel_temp_c",
    "light_lux",
    "power_w",
)
SUPPORTED_CLASSES = {
    "normal",
    "partial_shading",
    "dust_accumulation",
    "electrical_fault",
}


class PredictionError(ValueError):
    """Raised when a reading cannot be safely passed to the classifier."""


@dataclass(frozen=True)
class Prediction:
    predicted_class: str
    confidence: float
    probabilities: dict[str, float]
    timestamp: str
    model_version: str


def build_feature_vector(reading: dict[str, Any]) -> np.ndarray:
    """Validate one reading and return features in the fixed training order."""
    required = ("voltage_v", "current_a", "panel_temp_c", "light_lux")
    values: dict[str, float] = {}

    for name in required:
        if name not in reading or reading[name] is None:
            raise PredictionError(f"Missing required field: {name}")
        try:
            value = float(reading[name])
        except (TypeError, ValueError):
            raise PredictionError(f"Field '{name}' must be numeric.") from None
        if not math.isfinite(value):
            raise PredictionError(f"Field '{name}' must be finite.")
        values[name] = value

    if values["voltage_v"] < 0:
        raise PredictionError("voltage_v cannot be negative.")
    if values["current_a"] < 0:
        raise PredictionError("current_a cannot be negative.")
    if values["light_lux"] < 0:
        raise PredictionError("light_lux cannot be negative.")

    power_w = values["voltage_v"] * values["current_a"]
    return np.asarray([[
        values["voltage_v"],
        values["current_a"],
        values["panel_temp_c"],
        values["light_lux"],
        power_w,
    ]], dtype=float)


class SolarSensePredictor:
    """Loads a trained sklearn-compatible classifier and serves predictions.

    Expected artifact: a joblib-serialized estimator trained with FEATURE_NAMES
    in exactly this order and supporting predict() and predict_proba().
    """

    def __init__(self, model_path: str | Path, metadata_path: str | Path | None = None):
        self.model_path = Path(model_path)
        self.metadata_path = Path(metadata_path) if metadata_path else self.model_path.with_name("model_metadata.json")
        self.model = None
        self.model_version = "unavailable"
        self.load_error: str | None = None
        self._load()

    @property
    def is_ready(self) -> bool:
        return self.model is not None

    def _load(self) -> None:
        if not self.model_path.is_file():
            self.load_error = f"Model artifact not found: {self.model_path}"
            return
        try:
            model = joblib.load(self.model_path)
            if not callable(getattr(model, "predict", None)):
                raise TypeError("Loaded artifact does not implement predict().")
            if not callable(getattr(model, "predict_proba", None)):
                raise TypeError("Classifier must implement predict_proba().")

            if self.metadata_path.is_file():
                metadata = json.loads(self.metadata_path.read_text(encoding="utf-8"))
                version = str(metadata.get("model_version", "unversioned"))
                metadata_features = metadata.get("feature_names")
                if metadata_features and tuple(metadata_features) != FEATURE_NAMES:
                    raise ValueError("Model metadata feature_names do not match inference schema.")
            else:
                version = "unversioned"

            model_features = getattr(model, "feature_names_in_", None)
            if model_features is not None and tuple(str(x) for x in model_features) != FEATURE_NAMES:
                raise ValueError("Model feature_names_in_ do not match inference schema.")

            classes = {str(x) for x in getattr(model, "classes_", [])}
            if classes and not classes.issubset(SUPPORTED_CLASSES):
                raise ValueError(f"Model contains unsupported classes: {sorted(classes)}")

            self.model = model
            self.model_version = version
            self.load_error = None
        except Exception as exc:
            self.model = None
            self.load_error = f"{type(exc).__name__}: {exc}"

    def predict(self, reading: dict[str, Any]) -> Prediction:
        if self.model is None:
            raise PredictionError(f"Model is not ready: {self.load_error or 'unknown load error'}")

        features = build_feature_vector(reading)
        try:
            predicted = str(self.model.predict(features)[0])
            raw_probabilities = self.model.predict_proba(features)[0]
            classes = [str(x) for x in self.model.classes_]
        except Exception as exc:
            raise PredictionError(f"Model inference failed: {type(exc).__name__}: {exc}") from exc

        if predicted not in SUPPORTED_CLASSES:
            raise PredictionError(f"Model returned unsupported class: {predicted}")

        probabilities = {name: float(prob) for name, prob in zip(classes, raw_probabilities)}
        if any(not math.isfinite(p) or p < 0 or p > 1 for p in probabilities.values()):
            raise PredictionError("Model returned invalid probability values.")

        confidence = probabilities.get(predicted, 0.0)
        return Prediction(
            predicted_class=predicted,
            confidence=confidence,
            probabilities=probabilities,
            timestamp=datetime.now(timezone.utc).isoformat(),
            model_version=self.model_version,
        )
