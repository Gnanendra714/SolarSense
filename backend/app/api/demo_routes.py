
import math
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select, func, delete
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.demo import DemoSession, DemoReading

router = APIRouter(prefix="/api/v1/demo", tags=["cloud-demo"])

TICK_SECONDS = 10
SESSION_MINUTES = 30
MAX_ACTIVE_SESSIONS = 20
MAX_HISTORY = 180


def _utc(value):
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _reading_payload(row):
    return {
        "timestamp": _utc(row.timestamp).isoformat(),
        "voltage_v": row.voltage_v,
        "current_a": row.current_a,
        "power_w": row.power_w,
        "panel_temp_c": row.panel_temp_c,
        "light_lux": row.light_lux,
        "energy_wh": row.energy_wh,
        "source": "simulated",
        "reading_id": f"demo-{row.id}",
    }


def _active_session(db, session_id):
    session = db.scalar(
        select(DemoSession)
        .where(DemoSession.session_id == session_id)
        .with_for_update()
    )

    if session is None:
        raise HTTPException(404, "Demo session not found")

    now = datetime.now(timezone.utc)

    if session.stopped_at is not None:
        raise HTTPException(410, "Demo session has stopped")

    if _utc(session.expires_at) <= now:
        session.stopped_at = now
        db.commit()
        raise HTTPException(
            410, "Demo session expired; start a new demo"
        )

    return session


def _generate_reading(db, session, now):
    elapsed = max(
        0.0,
        (now - _utc(session.started_at)).total_seconds()
    )

    daylight = max(
        0.08,
        math.sin((elapsed % 180.0) / 180.0 * math.pi)
    )

    ripple = math.sin(elapsed / 13.0)

    voltage = 7.05 + 2.05 * daylight + 0.08 * ripple

    current = min(
        0.76,
        max(
            0.015,
            0.04 + 0.70 * daylight *
            (0.92 + 0.06 * math.sin(elapsed / 8.0))
        )
    )

    power = voltage * current

    temperature = (
        29.0 + 15.0 * daylight +
        1.2 * math.sin(elapsed / 35.0)
    )

    lux = 4500.0 + 52000.0 * daylight

    previous = db.scalar(
        select(DemoReading)
        .where(DemoReading.session_id == session.session_id)
        .order_by(desc(DemoReading.timestamp))
        .limit(1)
    )

    energy = power * TICK_SECONDS / 3600.0 if previous else 0.0

    row = DemoReading(
        session_id=session.session_id,
        timestamp=now,
        voltage_v=round(voltage, 3),
        current_a=round(current, 4),
        power_w=round(power, 3),
        panel_temp_c=round(temperature, 2),
        light_lux=round(lux, 1),
        energy_wh=round(energy, 6),
    )

    db.add(row)
    session.last_generated_at = now
    db.flush()

    count = db.scalar(
        select(func.count())
        .select_from(DemoReading)
        .where(DemoReading.session_id == session.session_id)
    ) or 0

    if count > MAX_HISTORY:
        old_rows = db.scalars(
            select(DemoReading)
            .where(DemoReading.session_id == session.session_id)
            .order_by(DemoReading.timestamp)
            .limit(count - MAX_HISTORY)
        ).all()

        for old in old_rows:
            db.delete(old)

    return row


@router.post("/start")
def start_demo(db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)

    retention_cutoff = now - timedelta(days=1)

    old_session_ids = select(DemoSession.session_id).where(
        DemoSession.expires_at < retention_cutoff
    )

    db.execute(
        delete(DemoReading).where(
            DemoReading.session_id.in_(old_session_ids)
        )
    )

    db.execute(
        delete(DemoSession).where(
            DemoSession.expires_at < retention_cutoff
        )
    )

    abandoned = db.scalars(
        select(DemoSession).where(
            DemoSession.stopped_at.is_(None),
            DemoSession.expires_at <= now
        )
    ).all()

    for session in abandoned:
        session.stopped_at = now

    active_count = db.scalar(
        select(func.count())
        .select_from(DemoSession)
        .where(
            DemoSession.stopped_at.is_(None),
            DemoSession.expires_at > now
        )
    ) or 0

    if active_count >= MAX_ACTIVE_SESSIONS:
        db.commit()
        raise HTTPException(
            429,
            "Demo is busy. Please try again in a few minutes."
        )

    session = DemoSession(
        session_id=str(uuid.uuid4()),
        started_at=now,
        last_generated_at=now,
        expires_at=now + timedelta(minutes=SESSION_MINUTES)
    )

    db.add(session)
    _generate_reading(db, session, now)
    db.commit()

    return {
        "session_id": session.session_id,
        "status": "running",
        "started_at": now.isoformat(),
        "expires_at": session.expires_at.isoformat(),
        "refresh_interval_seconds": TICK_SECONDS,
        "message": (
            "Simulated demo session started. "
            "These are not physical sensor measurements."
        )
    }


@router.post("/stop")
def stop_demo(
    session_id: str = Query(..., min_length=36, max_length=36),
    db: Session = Depends(get_db)
):
    session = db.get(DemoSession, session_id)

    if session is None:
        raise HTTPException(404, "Demo session not found")

    if session.stopped_at is None:
        session.stopped_at = datetime.now(timezone.utc)
        db.commit()

    return {
        "session_id": session_id,
        "status": "stopped"
    }


@router.get("/dashboard")
def demo_dashboard(
    session_id: str = Query(..., min_length=36, max_length=36),
    db: Session = Depends(get_db)
):
    session = _active_session(db, session_id)
    now = datetime.now(timezone.utc)

    if (
        now - _utc(session.last_generated_at)
    ).total_seconds() >= TICK_SECONDS:
        _generate_reading(db, session, now)
        db.commit()

    rows = db.scalars(
        select(DemoReading)
        .where(DemoReading.session_id == session_id)
        .order_by(desc(DemoReading.timestamp))
        .limit(MAX_HISTORY)
    ).all()

    rows = list(reversed(rows))

    if not rows:
        raise HTTPException(
            503, "Demo readings are not available yet"
        )

    latest = rows[-1]

    total_energy = sum(
        max(0.0, row.energy_wh) for row in rows
    )

    return {
        "summary": {
            "latest": _reading_payload(latest),
            "health_score": 0,
            "health_label": "Simulation only",
            "daily_energy_wh": round(total_energy, 5),
            "peak_power_w": round(
                max(row.power_w for row in rows), 3
            ),
            "uptime_pct": 0,
            "sensor_status": {
                "INA219": False,
                "DS18B20": False,
                "BH1750": False
            },
            "data_source": "simulated",
            "device_online": False,
            "last_device_seen": None,
            "prediction": {
                "status": "unavailable",
                "explanation": (
                    "ML predictions are disabled for "
                    "simulated demo readings."
                )
            }
        },
        "history": [_reading_payload(row) for row in rows],
        "alerts": [],
        "demo": {
            "status": "running",
            "expires_at": _utc(session.expires_at).isoformat(),
            "refresh_interval_seconds": TICK_SECONDS,
            "generated_at": _utc(latest.timestamp).isoformat()
        }
    }
