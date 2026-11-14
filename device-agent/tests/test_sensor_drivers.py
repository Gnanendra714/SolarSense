import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from app.sensors.hardware import HardwareSensor


class FakeMessage:
    def __init__(self, values):
        self.values = values
    def __iter__(self):
        return iter(self.values)


class FakeI2CMessageFactory:
    @staticmethod
    def read(_address, _length):
        return FakeMessage([0x1B, 0x58])  # 7000 / 1.2 lux


class HardwareDriverTests(unittest.TestCase):
    def make_sensor_without_hardware(self):
        sensor = HardwareSensor.__new__(HardwareSensor)
        return sensor

    def test_ds18b20_parses_temperature_after_valid_crc(self):
        sensor = self.make_sensor_without_hardware()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "w1_slave"
            path.write_text("aa bb cc crc=5e YES\naa t=25312\n", encoding="ascii")
            sensor._temperature_file = path
            self.assertAlmostEqual(sensor._read_temperature(), 25.312)

    def test_ds18b20_rejects_crc_failure(self):
        sensor = self.make_sensor_without_hardware()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "w1_slave"
            path.write_text("aa bb cc crc=5e NO\naa t=25312\n", encoding="ascii")
            sensor._temperature_file = path
            with self.assertRaisesRegex(RuntimeError, "CRC"):
                sensor._read_temperature()

    def test_ds18b20_rejects_power_on_default_temperature(self):
        sensor = self.make_sensor_without_hardware()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "w1_slave"
            path.write_text("aa bb cc crc=5e YES\naa t=85000\n", encoding="ascii")
            sensor._temperature_file = path
            with self.assertRaisesRegex(RuntimeError, "power-on default"):
                sensor._read_temperature()

    def test_bh1750_converts_raw_value_to_lux(self):
        sensor = self.make_sensor_without_hardware()
        sensor.bh1750_address = 0x23
        sensor.bus = Mock()
        sensor._i2c_msg = FakeI2CMessageFactory
        self.assertAlmostEqual(sensor._read_light(), (0x1B58) / 1.2)

    def test_failed_sensor_is_marked_unhealthy_without_fake_values(self):
        sensor = self.make_sensor_without_hardware()
        sensor.ina = Mock()
        sensor.ina.voltage.side_effect = OSError("INA219 unavailable")
        sensor._read_temperature = Mock(return_value=31.5)
        sensor._read_light = Mock(return_value=1000.0)
        result = sensor.read()
        self.assertFalse(result["sensor_health"]["ina219_ok"])
        self.assertTrue(result["sensor_health"]["ds18b20_ok"])
        self.assertTrue(result["sensor_health"]["bh1750_ok"])
        self.assertNotIn("voltage_v", result["values"])
        self.assertIn("ina219", result["sensor_errors"])


    def test_ina219_non_finite_value_is_unhealthy(self):
        sensor = self.make_sensor_without_hardware()
        sensor.ina = Mock()
        sensor.ina.voltage.return_value = float("nan")
        sensor._read_temperature = Mock(return_value=30.0)
        sensor._read_light = Mock(return_value=1000.0)
        result = sensor.read()
        self.assertFalse(result["sensor_health"]["ina219_ok"])
        self.assertIn("ina219", result["sensor_errors"])

if __name__ == "__main__":
    unittest.main()
