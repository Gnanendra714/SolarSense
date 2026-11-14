
from datetime import timezone


def interval_energy_wh(previous, current):
    """
    Calculate energy using trapezoidal integration.
    Ignore invalid intervals and gaps exceeding 15 minutes.
    """

    if previous is None:
        return 0.0

    previous_time = previous.timestamp
    current_time = current.timestamp

    # Normalize both timestamps to UTC.
    if previous_time.tzinfo is None:
        previous_time = previous_time.replace(tzinfo=timezone.utc)
    else:
        previous_time = previous_time.astimezone(timezone.utc)

    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone.utc)
    else:
        current_time = current_time.astimezone(timezone.utc)

    seconds = (current_time - previous_time).total_seconds()

    if seconds <= 0 or seconds > 900:
        return 0.0

    average_power = (previous.power_w + current.power_w) / 2

    return max(0.0, average_power * seconds / 3600)
