"""One-time, non-destructive migration for Cloud Sync v1.

Run from the backend directory:
    python -m scripts.migrate_cloud_sync

Back up the database before running. Existing readings are retained and tagged
as source='legacy'; every historical row receives a stable UUID reading_id.
"""
import uuid
from sqlalchemy import inspect, text
from app.database.session import engine


def main():
    inspector = inspect(engine)
    if "readings" not in inspector.get_table_names():
        raise RuntimeError("readings table does not exist; start the existing API once first.")

    columns = {column["name"] for column in inspector.get_columns("readings")}
    dialect = engine.dialect.name

    with engine.begin() as connection:
        if "reading_id" not in columns:
            connection.execute(text("ALTER TABLE readings ADD COLUMN reading_id VARCHAR(36)"))
        if "source" not in columns:
            if dialect == "sqlite":
                connection.execute(text(
                    "ALTER TABLE readings ADD COLUMN source VARCHAR(16) NOT NULL DEFAULT 'legacy'"
                ))
            else:
                connection.execute(text(
                    "ALTER TABLE readings ADD COLUMN source VARCHAR(16) NOT NULL DEFAULT 'legacy'"
                ))

        rows = connection.execute(text(
            "SELECT id FROM readings WHERE reading_id IS NULL"
        )).fetchall()
        for row in rows:
            connection.execute(
                text("UPDATE readings SET reading_id = :rid WHERE id = :row_id"),
                {"rid": str(uuid.uuid4()), "row_id": row[0]},
            )
        connection.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_readings_device_reading_id "
            "ON readings (device_id, reading_id)"
        ))

    print("Cloud Sync migration complete. Existing readings were preserved.")


if __name__ == "__main__":
    main()
