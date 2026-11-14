def calculate_power_w(voltage_v, current_a):
    return max(0.0, voltage_v * current_a)

def calculate_interval_energy_wh(previous_power_w, current_power_w, elapsed_seconds):
    # Trapezoidal integration across one sampling interval.
    if elapsed_seconds <= 0:
        return 0.0
    average_power_w = (previous_power_w + current_power_w) / 2.0
    return max(0.0, average_power_w * elapsed_seconds / 3600.0)
