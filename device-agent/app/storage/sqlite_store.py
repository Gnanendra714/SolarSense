"""Durable SQLite outbox for measurements and device-health heartbeats."""
import json
import sqlite3
import uuid
from pathlib import Path


class SQLiteStore:
    def __init__(self, database_path):
        path = Path(database_path)
        if not path.is_absolute():
            path = Path(__file__).resolve().parents[2] / path
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path, timeout=30)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("PRAGMA synchronous=FULL")
        self.connection.execute("PRAGMA foreign_keys=ON")
        self.connection.execute("PRAGMA busy_timeout=30000")

    def initialize(self):
        self.connection.execute("""
            CREATE TABLE IF NOT EXISTS readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reading_id TEXT,
                device_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                voltage_v REAL NOT NULL,
                current_a REAL NOT NULL,
                power_w REAL NOT NULL,
                panel_temp_c REAL NOT NULL,
                light_lux REAL NOT NULL,
                energy_wh REAL NOT NULL,
                source TEXT NOT NULL CHECK(source IN ('simulated', 'hardware')),
                synced INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(device_id, timestamp)
            )
        """)
        columns = {row["name"] for row in self.connection.execute("PRAGMA table_info(readings)")}
        if "reading_id" not in columns:
            self.connection.execute("ALTER TABLE readings ADD COLUMN reading_id TEXT")
        old_rows = self.connection.execute("SELECT id FROM readings WHERE reading_id IS NULL").fetchall()
        for row in old_rows:
            self.connection.execute("UPDATE readings SET reading_id=? WHERE id=?", (str(uuid.uuid4()), row["id"]))
        self.connection.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_local_reading_id ON readings(device_id, reading_id)")
        self.connection.execute("CREATE INDEX IF NOT EXISTS idx_readings_sync ON readings(synced, id)")
        self.connection.execute("CREATE INDEX IF NOT EXISTS idx_readings_time ON readings(device_id, timestamp)")
        self.connection.execute("""
            CREATE TABLE IF NOT EXISTS device_heartbeats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                heartbeat_id TEXT NOT NULL UNIQUE,
                device_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                source TEXT NOT NULL CHECK(source IN ('simulated', 'hardware')),
                agent_version TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('healthy', 'degraded', 'failed')),
                ina219_ok INTEGER NOT NULL,
                ds18b20_ok INTEGER NOT NULL,
                bh1750_ok INTEGER NOT NULL,
                sensor_errors TEXT NOT NULL DEFAULT '{}',
                synced INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.connection.execute("CREATE INDEX IF NOT EXISTS idx_heartbeats_sync ON device_heartbeats(synced, id)")
        self.connection.execute("CREATE INDEX IF NOT EXISTS idx_heartbeats_device_time ON device_heartbeats(device_id, timestamp)")
        self.connection.commit()

    def insert_reading(self, record):
        reading_id = record.get("reading_id") or str(uuid.uuid4())
        self.connection.execute("""
            INSERT OR IGNORE INTO readings (
                reading_id, device_id, timestamp, voltage_v, current_a, power_w,
                panel_temp_c, light_lux, energy_wh, source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (reading_id, record["device_id"], record["timestamp"], record["voltage_v"],
              record["current_a"], record["power_w"], record["panel_temp_c"],
              record["light_lux"], record["energy_wh"], record["source"]))
        self.connection.commit()
        return reading_id

    def pending_readings(self, limit=100):
        rows = self.connection.execute(
            "SELECT * FROM readings WHERE synced=0 ORDER BY timestamp, id LIMIT ?", (limit,)
        ).fetchall()
        return [dict(row) for row in rows]

    def mark_synced(self, reading_ids):
        if not reading_ids:
            return
        placeholders = ",".join("?" for _ in reading_ids)
        self.connection.execute(f"UPDATE readings SET synced=1 WHERE reading_id IN ({placeholders})", list(reading_ids))
        self.connection.commit()

    def insert_heartbeat(self, heartbeat):
        heartbeat_id = heartbeat.get("heartbeat_id") or str(uuid.uuid4())
        self.connection.execute("""
            INSERT OR IGNORE INTO device_heartbeats (
                heartbeat_id, device_id, timestamp, source, agent_version, status,
                ina219_ok, ds18b20_ok, bh1750_ok, sensor_errors
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (heartbeat_id, heartbeat["device_id"], heartbeat["timestamp"], heartbeat["source"],
              heartbeat["agent_version"], heartbeat["status"], int(heartbeat["ina219_ok"]),
              int(heartbeat["ds18b20_ok"]), int(heartbeat["bh1750_ok"]),
              json.dumps(heartbeat.get("sensor_errors", {}), separators=(",", ":"))))
        self.connection.commit()
        return heartbeat_id

    def pending_heartbeats(self, limit=100):
        rows = self.connection.execute(
            "SELECT * FROM device_heartbeats WHERE synced=0 ORDER BY timestamp, id LIMIT ?", (limit,)
        ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["ina219_ok"] = bool(item["ina219_ok"])
            item["ds18b20_ok"] = bool(item["ds18b20_ok"])
            item["bh1750_ok"] = bool(item["bh1750_ok"])
            item["sensor_errors"] = json.loads(item["sensor_errors"] or "{}")
            result.append(item)
        return result

    def mark_heartbeats_synced(self, heartbeat_ids):
        if not heartbeat_ids:
            return
        placeholders = ",".join("?" for _ in heartbeat_ids)
        self.connection.execute(
            f"UPDATE device_heartbeats SET synced=1 WHERE heartbeat_id IN ({placeholders})",
            list(heartbeat_ids),
        )
        self.connection.commit()


    def prune_synced(self, retention_days=30):
        """Bound local disk use without ever deleting readings awaiting acknowledgement."""
        self.connection.execute(
            "DELETE FROM readings WHERE synced=1 AND created_at < datetime('now', ?)",
            (f"-{int(retention_days)} days",),
        )
        self.connection.execute(
            "DELETE FROM device_heartbeats WHERE synced=1 AND created_at < datetime('now', ?)",
            (f"-{int(retention_days)} days",),
        )
        self.connection.commit()

    def close(self):
        self.connection.close()
