import sys
import tempfile
import unittest
from pathlib import Path

import joblib
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from solarsense_inference.predictor import (
    FEATURE_NAMES, PredictionError, SolarSensePredictor, build_feature_vector
)


class FakeClassifier:
    classes_ = np.array(["normal", "partial_shading", "dust_accumulation", "electrical_fault"])
    feature_names_in_ = np.array(FEATURE_NAMES)

    def predict(self, x):
        return np.array(["normal"])

    def predict_proba(self, x):
        return np.array([[0.8, 0.1, 0.05, 0.05]])


class PredictorTests(unittest.TestCase):
    def test_feature_order_and_power(self):
        vector = build_feature_vector({
            "voltage_v": 9.0, "current_a": 0.5,
            "panel_temp_c": 31, "light_lux": 12000
        })
        self.assertEqual(vector.shape, (1, 5))
        self.assertAlmostEqual(vector[0, 4], 4.5)

    def test_missing_field_rejected(self):
        with self.assertRaises(PredictionError):
            build_feature_vector({"voltage_v": 9, "current_a": 0.5, "panel_temp_c": 31})

    def test_negative_current_rejected(self):
        with self.assertRaises(PredictionError):
            build_feature_vector({
                "voltage_v": 9, "current_a": -0.1,
                "panel_temp_c": 31, "light_lux": 100
            })

    def test_model_missing_is_not_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            predictor = SolarSensePredictor(Path(tmp) / "missing.joblib")
            self.assertFalse(predictor.is_ready)

    def test_prediction_with_test_double(self):
        with tempfile.TemporaryDirectory() as tmp:
            model_path = Path(tmp) / "model.joblib"
            joblib.dump(FakeClassifier(), model_path)
            predictor = SolarSensePredictor(model_path)
            self.assertTrue(predictor.is_ready)
            result = predictor.predict({
                "voltage_v": 9, "current_a": 0.5,
                "panel_temp_c": 31, "light_lux": 10000
            })
            self.assertEqual(result.predicted_class, "normal")
            self.assertAlmostEqual(result.confidence, 0.8)
            self.assertEqual(result.model_version, "unversioned")


if __name__ == "__main__":
    unittest.main()
