"""Add device heartbeat metadata to an existing SolarSense database.

Run from the backend directory after taking a database backup:
    python -m scripts.migrate_device_health
"""
from sqlalchemy import inspect, text
from app.database.session import engine

COLUMNS = {
    "agent_version": "VARCHAR(32) NOT NULL DEFAULT 'unknown'",
    "sensor_mode": "VARCHAR(16) NOT NULL DEFAULT 'unknown'",
    "status": "VARCHAR(16) NOT NULL DEFAULT 'unknown'",
    "sensor_errors": "TEXT NOT NULL DEFAULT '{}'",
}


def main():
    inspector = inspect(engine)
    if "device_state" not in inspector.get_table_names():
        raise RuntimeError("device_state table does not exist. Start the API once before this migration.")
    existing = {column["name"] for column in inspector.get_columns("device_state")}
    with engine.begin() as connection:
        for name, ddl in COLUMNS.items():
            if name not in existing:
                connection.execute(text(f"ALTER TABLE device_state ADD COLUMN {name} {ddl}"))
    print("Device-health migration complete. Existing device state was preserved.")


if __name__ == "__main__":
    main()
