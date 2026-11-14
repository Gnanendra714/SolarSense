from typing import Protocol

class Sensor(Protocol):
    def read(self) -> dict[str, float]:
        # Return voltage_v, current_a, panel_temp_c and light_lux.
        ...
