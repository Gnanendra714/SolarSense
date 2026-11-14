import math
import random
import time

class SimulatedSensor:
    # Synthetic values for software testing only.
    def __init__(self):
        self.started = time.monotonic()
        self.rng = random.Random()

    def read(self):
        elapsed = time.monotonic() - self.started
        daylight = max(0.0, math.sin((elapsed / 180.0) * math.pi))
        light_lux = 8000.0 + 42000.0 * daylight + self.rng.uniform(-1200, 1200)
        voltage_v = 7.2 + 1.8 * daylight + self.rng.uniform(-0.12, 0.12)
        current_a = 0.03 + 0.68 * daylight + self.rng.uniform(-0.025, 0.025)
        panel_temp_c = 30.0 + 16.0 * daylight + self.rng.uniform(-0.6, 0.6)

        return {
            "voltage_v": max(0.0, voltage_v),
            "current_a": max(0.0, current_a),
            "panel_temp_c": panel_temp_c,
            "light_lux": max(0.0, light_lux),
        }
