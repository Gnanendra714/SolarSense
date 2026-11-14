import unittest
from app.validation import validate_measurement


VALID = {
    "voltage_v": 8.5,
    "current_a": 0.4,
    "panel_temp_c": 35.0,
    "light_lux": 12000.0,
}


class ValidationTests(unittest.TestCase):
    def test_accepts_valid_measurement(self):
        self.assertEqual(validate_measurement(VALID), [])

    def test_rejects_negative_current(self):
        sample = {**VALID, "current_a": -0.01}
        errors = validate_measurement(sample)
        self.assertTrue(any("current_a" in error for error in errors))

    def test_rejects_missing_and_non_finite_values(self):
        sample = {**VALID, "light_lux": float("nan")}
        errors = validate_measurement(sample)
        self.assertTrue(any("light_lux" in error for error in errors))
        del sample["panel_temp_c"]
        errors = validate_measurement(sample)
        self.assertTrue(any("panel_temp_c" in error for error in errors))

    def test_rejects_values_outside_sanity_limits(self):
        sample = {**VALID, "voltage_v": 27.0}
        self.assertTrue(any("voltage_v" in e for e in validate_measurement(sample)))


    def test_heartbeat_status_reflects_sensor_health(self):
        from datetime import datetime, timezone
        from app.__main__ import _heartbeat
        timestamp = datetime(2026, 11, 13, tzinfo=timezone.utc)
        health = {"ina219_ok": True, "ds18b20_ok": False, "bh1750_ok": True}
        heartbeat = _heartbeat("test-device", "hardware", timestamp, health, {"ds18b20": "CRC failure"})
        self.assertEqual(heartbeat["status"], "degraded")
        self.assertFalse(heartbeat["ds18b20_ok"])
        self.assertEqual(heartbeat["sensor_errors"]["ds18b20"], "CRC failure")

if __name__ == "__main__":
    unittest.main()
