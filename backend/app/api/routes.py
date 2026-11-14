from collections import defaultdict
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, desc
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.tables import Reading, Alert, DeviceState
from app.schemas.reading import ReadingIn, ReadingBatchIn, DeviceHeartbeatIn
from app.api.deps import require_device_key, require_admin_key
from app.services.energy import interval_energy_wh
from app.services.alerts import evaluate_alerts

router = APIRouter(prefix="/api/v1")


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def format_timestamp(value: datetime) -> str:
    return as_utc(value).isoformat()


def reading_dict(r):
    return {
        "timestamp": format_timestamp(r.timestamp),
        "voltage_v": r.voltage_v,
        "current_a": r.current_a,
        "power_w": r.power_w,
        "panel_temp_c": r.panel_temp_c,
        "light_lux": r.light_lux,
        "energy_wh": r.energy_wh,
        "source": getattr(r, "source", "legacy"),
        "reading_id": getattr(r, "reading_id", None),
    }


def alert_dict(a):
    return {
        "id": a.id, "severity": a.severity, "title": a.title,
        "message": a.message, "timestamp": format_timestamp(a.timestamp),
        "acknowledged": a.acknowledged
    }


def _insert_one(db: Session, payload: ReadingIn):
    """Insert one reading idempotently and repair the next interval if data arrives late."""
    timestamp = as_utc(payload.timestamp)
    existing = db.scalar(select(Reading).where(
        Reading.device_id == payload.device_id,
        Reading.reading_id == payload.reading_id
    ))
    if existing is not None:
        return "duplicate", existing

    power = payload.voltage_v * payload.current_a
    previous = db.scalar(select(Reading).where(
        Reading.device_id == payload.device_id,
        Reading.timestamp < timestamp
    ).order_by(desc(Reading.timestamp)).limit(1))

    obj = Reading(
        device_id=payload.device_id,
        reading_id=payload.reading_id,
        source=payload.source,
        timestamp=timestamp,
        voltage_v=payload.voltage_v,
        current_a=payload.current_a,
        power_w=power,
        panel_temp_c=payload.panel_temp_c,
        light_lux=payload.light_lux,
        energy_wh=0.0,
    )
    obj.energy_wh = interval_energy_wh(previous, obj)
    db.add(obj)
    db.flush()  # makes this ID visible to subsequent items in the same batch

    # If an older/offline reading is inserted between two existing readings,
    # recalculate the successor's interval so energy is not double-counted.
    successor = db.scalar(select(Reading).where(
        Reading.device_id == payload.device_id,
        Reading.timestamp > timestamp
    ).order_by(Reading.timestamp).limit(1))
    if successor is not None:
        successor.energy_wh = interval_energy_wh(obj, successor)

    state = db.get(DeviceState, payload.device_id)
    if state is None:
        state = DeviceState(device_id=payload.device_id, last_seen=timestamp)
        db.add(state)
    elif as_utc(state.last_seen) < timestamp:
        state.last_seen = timestamp

    # Sensor flags reflect the latest chronological sample only.
    if state.last_seen is not None and as_utc(state.last_seen) == timestamp:
        state.ina219_ok = payload.ina219_ok
        state.ds18b20_ok = payload.ds18b20_ok
        state.bh1750_ok = payload.bh1750_ok

    evaluate_alerts(db, obj)
    return "accepted", obj


@router.get("/health")
def health(db: Session = Depends(get_db)):
    # Include a lightweight DB round-trip so the hosting platform does not
    # mark the service healthy while its primary datastore is unavailable.
    from sqlalchemy import text

    db.execute(text("SELECT 1"))
    return {
        "status": "ok",
        "database": "connected",
        "service": "SolarSense API",
        "timestamp": format_timestamp(datetime.now(timezone.utc)),
    }


@router.post("/devices/heartbeat", dependencies=[Depends(require_device_key)])
def device_heartbeat(payload: DeviceHeartbeatIn, db: Session = Depends(get_db)):
    """Accept an idempotent latest-state heartbeat, including unhealthy sensor states."""
    timestamp = as_utc(payload.timestamp)
    state = db.get(DeviceState, payload.device_id)
    if state is None:
        state = DeviceState(device_id=payload.device_id, last_seen=timestamp)
        db.add(state)
    if state.last_seen is None or as_utc(state.last_seen) <= timestamp:
        state.last_seen = timestamp
        state.ina219_ok = payload.ina219_ok
        state.ds18b20_ok = payload.ds18b20_ok
        state.bh1750_ok = payload.bh1750_ok
        state.agent_version = payload.agent_version
        state.sensor_mode = payload.source
        state.status = payload.status
        # Bound error text to prevent an untrusted device from storing oversized payloads.
        import json
        state.sensor_errors = json.dumps(payload.sensor_errors, separators=(",", ":"))[:2000]
    db.commit()
    return {"accepted": True, "heartbeat_id": payload.heartbeat_id, "device_id": payload.device_id}


@router.post("/readings", dependencies=[Depends(require_device_key)])
def ingest(payload: ReadingIn, db: Session = Depends(get_db)):
    try:
        status, obj = _insert_one(db, payload)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {
        "saved": status == "accepted",
        "status": status,
        "reading_id": payload.reading_id,
        "device_id": payload.device_id,
        "timestamp": format_timestamp(as_utc(payload.timestamp)),
        "power_w": obj.power_w,
        "interval_energy_wh": obj.energy_wh,
    }


@router.post("/readings/batch", dependencies=[Depends(require_device_key)])
def ingest_batch(payload: ReadingBatchIn, db: Session = Depends(get_db)):
    # Stable chronological order is important for interval-energy integration.
    items = sorted(payload.items, key=lambda item: (item.device_id, as_utc(item.timestamp)))
    accepted_ids = []
    duplicate_ids = []
    try:
        for item in items:
            status, _ = _insert_one(db, item)
            if status == "accepted":
                accepted_ids.append(item.reading_id)
            else:
                duplicate_ids.append(item.reading_id)
        db.commit()
    except Exception:
        db.rollback()
        # No IDs are acknowledged on a failed transaction; the device retries safely.
        raise

    return {
        "device_id": items[0].device_id if len({x.device_id for x in items}) == 1 else None,
        "accepted_reading_ids": accepted_ids,
        "duplicate_reading_ids": duplicate_ids,
        "accepted_count": len(accepted_ids),
        "duplicate_count": len(duplicate_ids),
    }


@router.get("/readings")
def get_readings(
    device_id: str = "solar-panel-01",
    limit: int = Query(100, ge=1, le=5000),
    offset: int = Query(0, ge=0),
    start: datetime | None = None,
    end: datetime | None = None,
    db: Session = Depends(get_db)
):
    q = select(Reading).where(Reading.device_id == device_id)
    if start:
        q = q.where(Reading.timestamp >= as_utc(start))
    if end:
        q = q.where(Reading.timestamp < as_utc(end))
    total = len(db.scalars(q).all())
    rows = db.scalars(q.order_by(desc(Reading.timestamp)).offset(offset).limit(limit)).all()
    return {"items": [reading_dict(r) for r in reversed(rows)],
            "total": total, "limit": limit, "offset": offset}


@router.get("/analytics/summary")
def analytics_summary(
    period: str = Query("24h", pattern="^(24h|7d|30d)$"),
    device_id: str = "solar-panel-01",
    db: Session = Depends(get_db)
):
    now = datetime.now(timezone.utc)
    duration = {"24h": timedelta(hours=24), "7d": timedelta(days=7),
                "30d": timedelta(days=30)}[period]
    start = now - duration
    rows = db.scalars(select(Reading).where(
        Reading.device_id == device_id,
        Reading.timestamp >= start,
        Reading.timestamp <= now
    ).order_by(Reading.timestamp)).all()
    if not rows:
        return {"device_id": device_id, "period": period, "from": format_timestamp(start),
                "to": format_timestamp(now), "readings_count": 0, "energy_wh": 0.0,
                "energy_kwh": 0.0, "average_power_w": 0.0, "peak_power_w": 0.0,
                "average_panel_temp_c": None, "average_light_lux": None}
    energy = sum(max(0.0, r.energy_wh or 0.0) for r in rows)
    return {"device_id": device_id, "period": period, "from": format_timestamp(start),
            "to": format_timestamp(now), "readings_count": len(rows),
            "energy_wh": round(energy, 6), "energy_kwh": round(energy / 1000, 9),
            "average_power_w": round(sum(r.power_w for r in rows) / len(rows), 4),
            "peak_power_w": round(max(r.power_w for r in rows), 4),
            "average_panel_temp_c": round(sum(r.panel_temp_c for r in rows) / len(rows), 2),
            "average_light_lux": round(sum(r.light_lux for r in rows) / len(rows), 2)}


@router.get("/analytics/daily")
def analytics_daily(
    days: int = Query(7, ge=1, le=90),
    device_id: str = "solar-panel-01",
    timezone_name: str = Query("Asia/Kolkata", alias="timezone"),
    db: Session = Depends(get_db)
):
    try:
        report_tz = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        raise HTTPException(400, f"Unknown timezone: {timezone_name}")
    now_utc = datetime.now(timezone.utc)
    today_local = now_utc.astimezone(report_tz).date()
    first_day = today_local - timedelta(days=days - 1)
    start_local = datetime.combine(first_day, datetime.min.time(), tzinfo=report_tz)
    start_utc = start_local.astimezone(timezone.utc)
    rows = db.scalars(select(Reading).where(
        Reading.device_id == device_id,
        Reading.timestamp >= start_utc,
        Reading.timestamp <= now_utc
    ).order_by(Reading.timestamp)).all()
    grouped = defaultdict(lambda: {"energy_wh": 0.0, "power_sum": 0.0,
                                   "peak_power_w": 0.0, "count": 0})
    for reading in rows:
        ts = reading.timestamp
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        day = ts.astimezone(report_tz).date().isoformat()
        item = grouped[day]
        item["energy_wh"] += max(0.0, reading.energy_wh or 0.0)
        item["power_sum"] += reading.power_w
        item["peak_power_w"] = max(item["peak_power_w"], reading.power_w)
        item["count"] += 1
    result = []
    for index in range(days):
        day = (first_day + timedelta(days=index)).isoformat()
        item = grouped[day]
        count = item["count"]
        result.append({
            "date": day, "energy_wh": round(item["energy_wh"], 6),
            "energy_kwh": round(item["energy_wh"] / 1000, 9),
            "average_power_w": round(item["power_sum"] / count, 4) if count else 0.0,
            "peak_power_w": round(item["peak_power_w"], 4),
            "readings_count": count
        })
    return {"device_id": device_id, "days": days, "timezone": timezone_name, "items": result}


@router.get("/dashboard")
def dashboard(device_id: str = "solar-panel-01", db: Session = Depends(get_db)):
    rows = db.scalars(select(Reading).where(
        Reading.device_id == device_id
    ).order_by(desc(Reading.timestamp)).limit(1440)).all()
    rows = list(reversed(rows))
    if not rows:
        return {"summary": {"latest": {
            "timestamp": format_timestamp(datetime.now(timezone.utc)), "voltage_v": 0,
            "current_a": 0, "power_w": 0, "panel_temp_c": 0, "light_lux": 0, "energy_wh": 0
        }, "health_score": 0, "health_label": "No data", "daily_energy_wh": 0,
            "peak_power_w": 0, "uptime_pct": 0,
            "sensor_status": {"INA219": False, "DS18B20": False, "BH1750": False},
            "data_source": "none",
            "device_online": False,
            "last_device_seen": None,
            "prediction": {"status": "unavailable", "explanation": "Waiting for real sensor readings."}},
            "history": [], "alerts": []}
    latest = rows[-1]
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    recent = [r for r in rows if as_utc(r.timestamp) >= since]
    energy = sum(max(0.0, r.energy_wh or 0.0) for r in recent)
    state = db.get(DeviceState, device_id)
    alerts = db.scalars(select(Alert).where(
        Alert.device_id == device_id
    ).order_by(desc(Alert.timestamp)).limit(20)).all()
    return {"summary": {"latest": reading_dict(latest), "health_score": 0,
            "health_label": "Not assessed", "daily_energy_wh": round(energy, 4),
            "peak_power_w": round(max((r.power_w for r in recent), default=0), 3),
            "uptime_pct": 0,
            "sensor_status": {"INA219": bool(state and state.ina219_ok),
                              "DS18B20": bool(state and state.ds18b20_ok),
                              "BH1750": bool(state and state.bh1750_ok)},
            "data_source": latest.source,
            "device_online": bool(state and (datetime.now(timezone.utc) - as_utc(state.last_seen)).total_seconds() < 120),
            "last_device_seen": format_timestamp(state.last_seen) if state else None,
            "prediction": {"status": "available_via_ml_endpoint",
                           "explanation": "Use the ML endpoint to obtain a prediction. No prediction is fabricated in the dashboard summary."}},
            "history": [reading_dict(r) for r in rows],
            "alerts": [alert_dict(a) for a in alerts]}


@router.get("/alerts")
def alerts(device_id: str = "solar-panel-01", db: Session = Depends(get_db)):
    return {"items": [alert_dict(a) for a in db.scalars(select(Alert).where(
        Alert.device_id == device_id
    ).order_by(desc(Alert.timestamp))).all()]}


@router.post(
    "/alerts/{alert_id}/acknowledge",
    dependencies=[Depends(require_admin_key)],
)
def acknowledge(alert_id: str, db: Session = Depends(get_db)):
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(404, "Alert not found")
    alert.acknowledged = True
    db.commit()
    return {"acknowledged": True, "id": alert_id}


@router.get("/system")
def system(device_id: str = "solar-panel-01", db: Session = Depends(get_db)):
    state = db.get(DeviceState, device_id)
    online = bool(state and (
        datetime.now(timezone.utc) - as_utc(state.last_seen)
    ).total_seconds() < 120)
    import json
    try:
        sensor_errors = json.loads(state.sensor_errors or "{}") if state else {}
    except (TypeError, ValueError):
        sensor_errors = {}
    return {"device_id": device_id,
            "last_seen": format_timestamp(state.last_seen) if state else None,
            "online": online,
            "status": state.status if state else "unknown",
            "source": state.sensor_mode if state else "unknown",
            "agent_version": state.agent_version if state else None,
            "sensor_errors": sensor_errors,
            "sensors": {"INA219": bool(state and state.ina219_ok),
                        "DS18B20": bool(state and state.ds18b20_ok),
                        "BH1750": bool(state and state.bh1750_ok)}}
