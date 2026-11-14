import math

# Software sanity limits, not panel operating guarantees.
# Negative current is rejected because the cloud ReadingIn schema accepts
# non-negative current only. A negative value can indicate reversed wiring.
LIMITS = {
    "voltage_v": (0.0, 26.0),
    "current_a": (0.0, 3.2),
    "panel_temp_c": (-40.0, 125.0),
    "light_lux": (0.0, 200000.0),
}


def validate_measurement(values):
    errors = []
    for field, (minimum, maximum) in LIMITS.items():
        value = values.get(field)
        if not isinstance(value, (int, float)) or not math.isfinite(value):
            errors.append(f"{field} is missing or not finite")
        elif not minimum <= value <= maximum:
            errors.append(
                f"{field}={value} outside sanity limits [{minimum}, {maximum}]"
            )
    return errors
