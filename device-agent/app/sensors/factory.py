from app.config import settings
from app.sensors.simulator import SimulatedSensor


def create_sensor():
    mode = settings.sensor_mode
    if mode == "simulated":
        return SimulatedSensor(), "simulated"
    if mode == "hardware":
        from app.sensors.hardware import HardwareSensor
        sensor = HardwareSensor(
            shunt_ohms=settings.ina219_shunt_ohms,
            max_expected_amps=settings.ina219_max_expected_amps,
            i2c_bus=settings.i2c_bus,
            ina219_address=settings.ina219_address,
            bh1750_address=settings.bh1750_address,
            w1_base_dir=settings.w1_base_dir,
            ds18b20_id=settings.ds18b20_id,
        )
        return sensor, "hardware"
    raise ValueError("SENSOR_MODE must be either 'simulated' or 'hardware'")
