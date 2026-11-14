from types import SimpleNamespace
from datetime import datetime,timezone,timedelta
from app.services.energy import interval_energy_wh
def test_trapezoid_energy():
    t=datetime.now(timezone.utc)
    a=SimpleNamespace(timestamp=t,power_w=10)
    b=SimpleNamespace(timestamp=t+timedelta(seconds=60),power_w=10)
    assert interval_energy_wh(a,b)==10*60/3600
def test_first_reading_zero():
    assert interval_energy_wh(None,SimpleNamespace(timestamp=datetime.now(timezone.utc),power_w=10))==0
def test_large_gap_ignored():
    t=datetime.now(timezone.utc)
    a=SimpleNamespace(timestamp=t,power_w=10)
    b=SimpleNamespace(timestamp=t+timedelta(hours=1),power_w=10)
    assert interval_energy_wh(a,b)==0
