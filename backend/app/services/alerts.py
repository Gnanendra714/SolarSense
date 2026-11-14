from uuid import uuid4
from datetime import timezone
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models.tables import Alert, Reading
from app.core.config import settings
def evaluate_alerts(db:Session, reading:Reading):
    created=[]
    def add(severity,title,message):
        # avoid duplicate same-title active alerts for this device
        existing=db.scalar(select(Alert).where(Alert.device_id==reading.device_id,Alert.title==title,Alert.acknowledged==False))
        if existing is None:
            a=Alert(id=str(uuid4()),device_id=reading.device_id,severity=severity,title=title,message=message,timestamp=reading.timestamp)
            db.add(a);created.append(a)
    if reading.panel_temp_c>=settings.max_panel_temp_c:
        add("warning","Panel temperature high",f"Panel temperature reached {reading.panel_temp_c:.1f} °C.")
    if reading.light_lux>=settings.min_light_for_output_lux and reading.power_w<settings.min_power_ratio*7:
        add("warning","Low output under bright light",f"Output is {reading.power_w:.2f} W while light level is {reading.light_lux:.0f} lux. Check shading, wiring and measurements.")
    if reading.voltage_v>10.5:
        add("warning","Panel voltage above expected open-circuit range",f"Measured voltage is {reading.voltage_v:.2f} V. Check measurement wiring and panel specifications.")
    return created
