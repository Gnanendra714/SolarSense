import os
from dataclasses import dataclass
from urllib.parse import urlparse
from pathlib import Path
from dotenv import load_dotenv

PROJECT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_DIR / ".env")

AGENT_VERSION = "2.1.0"


def _int_env(name, default):
    raw = os.getenv(name, str(default)).strip()
    return int(raw, 0) if name.endswith("_ADDRESS") else int(raw)


@dataclass(frozen=True)
class Settings:
    device_id: str = os.getenv("DEVICE_ID", "solar-panel-01").strip()
    sensor_mode: str = os.getenv("SENSOR_MODE", "simulated").strip().lower()
    sample_interval_seconds: int = int(os.getenv("SAMPLE_INTERVAL_SECONDS", "10"))
    database_path: str = os.getenv("DATABASE_PATH", "data/solarsense_device.db").strip()
    log_level: str = os.getenv("LOG_LEVEL", "INFO").strip().upper()
    api_base_url: str = os.getenv("API_BASE_URL", "").strip().rstrip("/")
    device_api_key: str = os.getenv("DEVICE_API_KEY", "").strip()
    sync_interval_seconds: int = int(os.getenv("SYNC_INTERVAL_SECONDS", "15"))
    sync_batch_size: int = int(os.getenv("SYNC_BATCH_SIZE", "100"))
    http_timeout_seconds: int = int(os.getenv("HTTP_TIMEOUT_SECONDS", "10"))
    ina219_shunt_ohms: float = float(os.getenv("INA219_SHUNT_OHMS", "0.1"))
    ina219_max_expected_amps: float = float(os.getenv("INA219_MAX_EXPECTED_AMPS", "0.82"))
    i2c_bus: int = int(os.getenv("I2C_BUS", "1"))
    ina219_address: int = _int_env("INA219_ADDRESS", "0x40")
    bh1750_address: int = _int_env("BH1750_ADDRESS", "0x23")
    w1_base_dir: str = os.getenv("W1_BASE_DIR", "/sys/bus/w1/devices")
    ds18b20_id: str = os.getenv("DS18B20_ID", "").strip()


settings = Settings()

if not settings.device_id:
    raise ValueError("DEVICE_ID cannot be empty")
if settings.sensor_mode not in {"simulated", "hardware"}:
    raise ValueError("SENSOR_MODE must be 'simulated' or 'hardware'")
if settings.sample_interval_seconds < 1:
    raise ValueError("SAMPLE_INTERVAL_SECONDS must be at least 1")
if settings.sync_interval_seconds < 1:
    raise ValueError("SYNC_INTERVAL_SECONDS must be at least 1")
if not 1 <= settings.sync_batch_size <= 500:
    raise ValueError("SYNC_BATCH_SIZE must be between 1 and 500")
if settings.http_timeout_seconds < 1:
    raise ValueError("HTTP_TIMEOUT_SECONDS must be at least 1")
if settings.ina219_shunt_ohms <= 0 or settings.ina219_max_expected_amps <= 0:
    raise ValueError("INA219 shunt resistance and expected current must be positive")
if not settings.database_path:
    raise ValueError("DATABASE_PATH cannot be empty")
if bool(settings.api_base_url) != bool(settings.device_api_key):
    raise ValueError("Set both API_BASE_URL and DEVICE_API_KEY to enable cloud sync")
if settings.api_base_url:
    parsed = urlparse(settings.api_base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("API_BASE_URL must be an absolute http:// or https:// URL")
    if parsed.scheme != "https" and parsed.hostname not in {"localhost", "127.0.0.1"}:
        raise ValueError("Cloud API_BASE_URL must use HTTPS outside localhost")
