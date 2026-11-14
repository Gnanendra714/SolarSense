import logging
import signal
import time
import uuid
from datetime import datetime, timezone

from app.config import AGENT_VERSION, settings
from app.processing.energy import calculate_power_w, calculate_interval_energy_wh
from app.sensors.factory import create_sensor
from app.storage.sqlite_store import SQLiteStore
from app.sync.client import CloudSyncClient
from app.validation import validate_measurement


def configure_logging():
    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def _heartbeat(device_id, source, timestamp, health, errors):
    ok_count = sum(bool(value) for value in health.values())
    status = "healthy" if ok_count == 3 else ("failed" if ok_count == 0 else "degraded")
    return {
        "heartbeat_id": str(uuid.uuid4()),
        "device_id": device_id,
        "timestamp": timestamp.isoformat(),
        "source": source,
        "agent_version": AGENT_VERSION,
        "status": status,
        "ina219_ok": bool(health.get("ina219_ok", False)),
        "ds18b20_ok": bool(health.get("ds18b20_ok", False)),
        "bh1750_ok": bool(health.get("bh1750_ok", False)),
        "sensor_errors": {str(k): str(v)[:300] for k, v in errors.items()},
    }


def main():
    configure_logging()
    log = logging.getLogger("solarsense.device")
    store = SQLiteStore(settings.database_path)
    store.initialize()
    sync_client = CloudSyncClient(settings.api_base_url, settings.device_api_key, settings.http_timeout_seconds)
    source = settings.sensor_mode
    sensor = None
    sensor_retry_at = 0.0
    try:
        sensor, source = create_sensor()
    except Exception as exc:
        log.exception("Sensor initialization failed; agent will continue reporting failed health heartbeats.")
        startup_sensor_error = str(exc)[:300]
    else:
        startup_sensor_error = ""
    previous_timestamp = None
    previous_power_w = None
    next_sync_at = 0.0
    sync_backoff = 5
    running = True

    def stop(_signum, _frame):
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, stop)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, stop)

    log.info("SolarSense device agent started | device_id=%s | mode=%s | version=%s", settings.device_id, source.upper(), AGENT_VERSION)
    if source == "simulated":
        log.warning("SIMULATED DATA: these values are not measurements from your solar panel.")
    if sync_client.enabled:
        log.info("Cloud sync enabled | endpoint=%s", settings.api_base_url)
    else:
        log.warning("Cloud sync disabled; data and health events will remain in the local SQLite outbox.")

    try:
        while running:
            timestamp = datetime.now(timezone.utc)
            health = {"ina219_ok": False, "ds18b20_ok": False, "bh1750_ok": False}
            errors = {}
            try:
                if sensor is None:
                    now_mono = time.monotonic()
                    if now_mono >= sensor_retry_at:
                        try:
                            sensor, source = create_sensor()
                            startup_sensor_error = ""
                            log.info("Sensor initialization recovered.")
                        except Exception as init_exc:
                            startup_sensor_error = str(init_exc)[:300]
                            sensor_retry_at = now_mono + 60
                    if sensor is None:
                        raise RuntimeError(startup_sensor_error or "Sensor initialization is unavailable")
                raw = sensor.read()
                if source == "simulated":
                    measurement = raw
                    health = {"ina219_ok": True, "ds18b20_ok": True, "bh1750_ok": True}
                else:
                    measurement = raw.get("values", {})
                    health = raw.get("sensor_health", health)
                    errors = raw.get("sensor_errors", {})

                unhealthy = [name for name, ok in health.items() if not ok]
                if errors:
                    log.warning("Sensor read errors: %s", "; ".join(f"{name}: {message}" for name, message in errors.items()))
                if unhealthy:
                    log.error("Incomplete sample; unhealthy sensors: %s. No simulated fallback is used.", ", ".join(unhealthy))
                else:
                    validation_errors = validate_measurement(measurement)
                    if validation_errors:
                        log.error("Rejected measurement: %s", "; ".join(validation_errors))
                    else:
                        power_w = calculate_power_w(measurement["voltage_v"], measurement["current_a"])
                        energy_wh = 0.0
                        if previous_timestamp is not None and previous_power_w is not None:
                            elapsed = (timestamp - previous_timestamp).total_seconds()
                            if 0 < elapsed <= 900:
                                energy_wh = calculate_interval_energy_wh(previous_power_w, power_w, elapsed)
                        record = {
                            "device_id": settings.device_id, "timestamp": timestamp.isoformat(),
                            **measurement, "power_w": power_w, "energy_wh": energy_wh, "source": source,
                        }
                        store.insert_reading(record)
                        log.info("%s | V=%.2f V | I=%.3f A | P=%.2f W | Temp=%.1f C | Light=%.0f lux | interval_energy=%.5f Wh",
                                 source.upper(), record["voltage_v"], record["current_a"], record["power_w"],
                                 record["panel_temp_c"], record["light_lux"], record["energy_wh"])
                        previous_timestamp, previous_power_w = timestamp, power_w
            except Exception as exc:
                errors["acquisition"] = str(exc)[:300]
                log.exception("Acquisition cycle failed; health event will still be queued.")

            # Health is recorded even when a sensor fails or no complete reading exists.
            heartbeat = _heartbeat(settings.device_id, source, timestamp, health, errors)
            store.insert_heartbeat(heartbeat)
            if heartbeat["status"] != "healthy":
                log.error("Device health=%s | sensors=%s", heartbeat["status"], health)

            now = time.monotonic()
            if sync_client.enabled and now >= next_sync_at:
                sync_failed = False
                pending = store.pending_readings(settings.sync_batch_size)
                if pending:
                    try:
                        acked = sync_client.upload_batch(pending)
                        store.mark_synced(acked)
                        log.info("Cloud sync acknowledged %d/%d readings", len(acked), len(pending))
                    except Exception as exc:
                        sync_failed = True
                        log.warning("Reading sync failed; readings remain queued: %s", exc)
                pending_health = store.pending_heartbeats(settings.sync_batch_size)
                for item in pending_health:
                    try:
                        accepted = sync_client.upload_heartbeat(item)
                        if accepted:
                            store.mark_heartbeats_synced({item["heartbeat_id"]})
                    except Exception as exc:
                        sync_failed = True
                        log.warning("Health heartbeat sync failed; event remains queued: %s", exc)
                        break
                if pending_health:
                    log.info("Cloud sync attempted %d queued health events", len(pending_health))
                if sync_failed:
                    next_sync_at = now + sync_backoff
                    sync_backoff = min(sync_backoff * 2, 300)
                else:
                    sync_backoff = 5
                    next_sync_at = now + settings.sync_interval_seconds
            store.prune_synced(retention_days=30)

            # Interruptible wait makes shutdown responsive without busy looping.
            deadline = time.monotonic() + settings.sample_interval_seconds
            while running and time.monotonic() < deadline:
                time.sleep(min(0.25, max(0.0, deadline - time.monotonic())))
    finally:
        close = getattr(sensor, "close", None) if sensor is not None else None
        if callable(close):
            try:
                close()
            except Exception:
                log.exception("Sensor cleanup failed")
        store.close()
        log.info("SolarSense device agent stopped.")


if __name__ == "__main__":
    main()
