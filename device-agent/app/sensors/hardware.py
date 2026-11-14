"""Raspberry Pi sensor adapter for INA219, DS18B20 and BH1750.

Hardware-only imports are lazy so this module can be inspected on Windows.
No synthetic fallback is used: failed sensors are reported as unhealthy.
"""
import glob
import logging
import math
import time
from pathlib import Path

log = logging.getLogger("solarsense.sensors.hardware")


class HardwareSensor:
    def __init__(
        self,
        shunt_ohms=0.1,
        max_expected_amps=0.82,
        i2c_bus=1,
        ina219_address=0x40,
        bh1750_address=0x23,
        w1_base_dir="/sys/bus/w1/devices",
        ds18b20_id="",
    ):
        try:
            from ina219 import INA219
        except ImportError as exc:
            raise RuntimeError(
                "Hardware mode requires pi-ina219. Install requirements-hardware.txt on the Raspberry Pi."
            ) from exc
        try:
            from smbus2 import SMBus, i2c_msg
        except ImportError as exc:
            raise RuntimeError(
                "Hardware mode requires smbus2. Install requirements-hardware.txt on the Raspberry Pi."
            ) from exc

        self.ina = INA219(
            shunt_ohms,
            max_expected_amps=max_expected_amps,
            busnum=i2c_bus,
            address=ina219_address,
        )
        self.ina.configure()
        self.bus = SMBus(i2c_bus)
        self._i2c_msg = i2c_msg
        self.bh1750_address = bh1750_address
        self.w1_base_dir = Path(w1_base_dir)
        self.ds18b20_id = ds18b20_id.strip()
        self._temperature_file = self._resolve_temperature_file()
        # BH1750 continuous high-resolution mode.
        self.bus.write_byte(self.bh1750_address, 0x10)
        time.sleep(0.18)

    def _resolve_temperature_file(self):
        if self.ds18b20_id:
            candidate = self.w1_base_dir / self.ds18b20_id / "w1_slave"
            if not candidate.is_file():
                raise RuntimeError(f"Configured DS18B20 device not found: {candidate}")
            return candidate
        candidates = sorted(Path(p) / "w1_slave" for p in glob.glob(str(self.w1_base_dir / "28-*")))
        if not candidates:
            raise RuntimeError(
                "No DS18B20 found under /sys/bus/w1/devices. Enable 1-Wire and verify the probe."
            )
        if len(candidates) > 1:
            raise RuntimeError(
                "Multiple DS18B20 probes found; set DS18B20_ID in .env to select one."
            )
        return candidates[0]

    def _read_temperature(self):
        lines = self._temperature_file.read_text(encoding="ascii").strip().splitlines()
        if len(lines) < 2 or not lines[0].rstrip().endswith("YES"):
            raise RuntimeError("DS18B20 CRC check failed or sensor data is incomplete")
        marker = "t="
        if marker not in lines[1]:
            raise RuntimeError("DS18B20 temperature field missing")
        temp_c = int(lines[1].split(marker, 1)[1]) / 1000.0
        if temp_c == 85.0:
            raise RuntimeError("DS18B20 returned its power-on default; reading rejected")
        return temp_c

    def _read_light(self):
        # BH1750 high-resolution mode returns lux = raw / 1.2.
        message = self._i2c_msg.read(self.bh1750_address, 2)
        self.bus.i2c_rdwr(message)
        data = list(message)
        raw = (data[0] << 8) | data[1]
        return raw / 1.2

    def read(self):
        values = {}
        health = {"ina219_ok": False, "ds18b20_ok": False, "bh1750_ok": False}
        errors = {}

        try:
            voltage = float(self.ina.voltage())
            current = float(self.ina.current()) / 1000.0  # library reports mA
            if not math.isfinite(voltage) or not math.isfinite(current):
                raise RuntimeError("INA219 returned a non-finite measurement")
            values.update(voltage_v=voltage, current_a=current)
            health["ina219_ok"] = True
        except Exception as exc:
            errors["ina219"] = str(exc)

        try:
            temperature = float(self._read_temperature())
            if not math.isfinite(temperature) or not -55.0 <= temperature <= 125.0:
                raise RuntimeError(f"DS18B20 temperature out of sensor range: {temperature}")
            values["panel_temp_c"] = temperature
            health["ds18b20_ok"] = True
        except Exception as exc:
            errors["ds18b20"] = str(exc)

        try:
            light = float(self._read_light())
            if not math.isfinite(light) or light < 0:
                raise RuntimeError(f"BH1750 returned an invalid lux value: {light}")
            values["light_lux"] = light
            health["bh1750_ok"] = True
        except Exception as exc:
            errors["bh1750"] = str(exc)

        return {
            "values": values,
            "sensor_health": health,
            "sensor_errors": errors,
        }

    def close(self):
        try:
            self.bus.close()
        except Exception:
            pass
