import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock
from types import SimpleNamespace

from app.sensors.factory import create_sensor
from app.sensors.simulator import SimulatedSensor
from app.storage.sqlite_store import SQLiteStore
from app.sync.client import CloudSyncClient


class FactoryAndStorageTests(unittest.TestCase):
    def test_factory_selects_simulator(self):
        with patch("app.sensors.factory.settings", SimpleNamespace(sensor_mode="simulated")):
            sensor, source = create_sensor()
        self.assertIsInstance(sensor, SimulatedSensor)
        self.assertEqual(source, "simulated")

    def test_simulator_returns_complete_measurement_fields(self):
        sensor = SimulatedSensor()
        reading = sensor.read()
        self.assertEqual(
            set(reading),
            {"voltage_v", "current_a", "panel_temp_c", "light_lux"},
        )

    def test_sqlite_persists_and_queues_reading(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "agent.db"
            store = SQLiteStore(str(db_path))
            try:
                store.initialize()
                record = {
                    "device_id": "test-device",
                    "timestamp": "2026-11-13T12:00:00+00:00",
                    "voltage_v": 8.0,
                    "current_a": 0.25,
                    "power_w": 2.0,
                    "panel_temp_c": 32.0,
                    "light_lux": 9000.0,
                    "energy_wh": 0.0,
                    "source": "simulated",
                }
                reading_id = store.insert_reading(record)
                pending = store.pending_readings()
                self.assertEqual(len(pending), 1)
                self.assertEqual(pending[0]["reading_id"], reading_id)
                store.mark_synced({reading_id})
                self.assertEqual(store.pending_readings(), [])
            finally:
                store.close()


    def test_sqlite_persists_health_heartbeat_until_acknowledged(self):
        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteStore(str(Path(directory) / "agent.db"))
            try:
                store.initialize()
                heartbeat = {
                    "device_id": "test-device", "timestamp": "2026-11-13T12:00:00+00:00",
                    "source": "hardware", "agent_version": "2.1.0", "status": "degraded",
                    "ina219_ok": True, "ds18b20_ok": False, "bh1750_ok": True,
                    "sensor_errors": {"ds18b20": "CRC check failed"},
                }
                heartbeat_id = store.insert_heartbeat(heartbeat)
                pending = store.pending_heartbeats()
                self.assertEqual(len(pending), 1)
                self.assertEqual(pending[0]["heartbeat_id"], heartbeat_id)
                self.assertFalse(pending[0]["ds18b20_ok"])
                self.assertEqual(pending[0]["sensor_errors"]["ds18b20"], "CRC check failed")
                store.mark_heartbeats_synced({heartbeat_id})
                self.assertEqual(store.pending_heartbeats(), [])
            finally:
                store.close()

    def test_cloud_client_requires_server_ack_for_heartbeat(self):
        client = CloudSyncClient("https://example.invalid/api/v1", "device-secret")
        client._post = Mock(return_value={"heartbeat_id": "12345678-1234-5678-1234-567812345678"})
        heartbeat = {
            "heartbeat_id": "12345678-1234-5678-1234-567812345678",
            "device_id": "test-device", "timestamp": "2026-11-13T12:00:00+00:00",
            "source": "hardware", "agent_version": "2.1.0", "status": "healthy",
            "ina219_ok": True, "ds18b20_ok": True, "bh1750_ok": True, "sensor_errors": {},
            "id": 99, "synced": 0,
        }
        self.assertTrue(client.upload_heartbeat(heartbeat))
        sent_payload = client._post.call_args.args[1]
        self.assertNotIn("id", sent_payload)
        self.assertNotIn("synced", sent_payload)

if __name__ == "__main__":
    unittest.main()
