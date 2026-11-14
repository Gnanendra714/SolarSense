"""Authenticated, acknowledgement-based cloud sync for readings and heartbeats."""
import json
import logging
import urllib.error
import urllib.request


class CloudSyncClient:
    def __init__(self, base_url, api_key, timeout_seconds=10):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.log = logging.getLogger("solarsense.sync")

    @property
    def enabled(self):
        return bool(self.base_url and self.api_key)

    def _post(self, path, payload):
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}{path}", data=body,
            headers={"Content-Type": "application/json", "X-Device-Key": self.api_key},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            raise RuntimeError(f"Cloud sync HTTP {exc.code}: {detail}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise RuntimeError(f"Cloud sync connection failed: {exc}") from exc

    def upload_batch(self, records):
        if not self.enabled or not records:
            return set()
        items = [{
            "reading_id": row["reading_id"], "device_id": row["device_id"],
            "timestamp": row["timestamp"], "voltage_v": row["voltage_v"],
            "current_a": row["current_a"], "power_w": row["power_w"],
            "panel_temp_c": row["panel_temp_c"], "light_lux": row["light_lux"],
            "energy_wh": row["energy_wh"], "source": row["source"],
            "ina219_ok": True, "ds18b20_ok": True, "bh1750_ok": True,
        } for row in records]
        result = self._post("/readings/batch", {"items": items})
        acknowledged = set(result.get("accepted_reading_ids", [])) | set(result.get("duplicate_reading_ids", []))
        expected = {row["reading_id"] for row in records}
        if not acknowledged.issubset(expected):
            raise RuntimeError("Cloud returned unknown reading IDs; refusing to mark queue synced")
        return acknowledged

    def upload_heartbeat(self, heartbeat):
        if not self.enabled:
            return False
        payload = {key: heartbeat[key] for key in (
            "heartbeat_id", "device_id", "timestamp", "source", "agent_version",
            "status", "ina219_ok", "ds18b20_ok", "bh1750_ok", "sensor_errors",
        )}
        result = self._post("/devices/heartbeat", payload)
        return result.get("heartbeat_id") == heartbeat.get("heartbeat_id")
