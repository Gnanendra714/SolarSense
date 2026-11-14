export type Reading = {
  timestamp: string;
  voltage_v: number;
  current_a: number;
  power_w: number;
  panel_temp_c: number;
  light_lux: number;
  energy_wh: number;
  source?: "hardware" | "simulated" | "legacy";
};

export type Alert = {
  id: string;
  severity: "info" | "warning" | "critical";
  title: string;
  message: string;
  timestamp: string;
  acknowledged: boolean;
};

export type Dashboard = {
  summary: {
    latest: Reading;
    health_score: number;
    health_label: string;
    daily_energy_wh: number;
    peak_power_w: number;
    uptime_pct: number;
    sensor_status: Record<string, boolean>;
    data_source: "hardware" | "simulated" | "legacy" | "none";
    device_online: boolean;
    last_device_seen: string | null;
    prediction: { status: string; explanation: string };
  };
  history: Reading[];
  alerts: Alert[];
};

export type AnalyticsSummary = {
  device_id: string;
  period: "24h" | "7d" | "30d";
  from: string;
  to: string;
  readings_count: number;
  energy_wh: number;
  energy_kwh: number;
  average_power_w: number;
  peak_power_w: number;
  average_panel_temp_c: number;
  average_light_lux: number;
};

export type DailyAnalyticsItem = {
  date: string;
  energy_wh: number;
  energy_kwh: number;
  average_power_w: number;
  peak_power_w: number;
  readings_count: number;
};

export type DailyAnalytics = {
  device_id: string;
  days: number;
  timezone: string;
  items: DailyAnalyticsItem[];
};

export type DeviceSystem = {
  device_id: string;
  last_seen: string | null;
  online: boolean;
  status: string;
  source: string;
  agent_version: string | null;
  sensor_errors: Record<string, string>;
  sensors: Record<string, boolean>;
};

export type MlHealth = {
  ready: boolean;
  model_version: string;
  message: string;
};
export type MlPrediction = {
  device_id: string;
  reading_timestamp: string;
  reading_source: string;
  predicted_class: string;
  confidence: number;
  probabilities: Record<string, number>;
  prediction_timestamp: string;
  model_version: string;
  source: string;
  warning: string;
};

export type ReadingsResponse = {
  items: Reading[];
  total: number;
  limit: number;
  offset: number;
};

const base = (
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000/api/v1"
).replace(/\/+$/, "");

async function apiRequest<T>(path: string): Promise<T> {
  const response = await fetch(`${base}${path}`, {
    signal: AbortSignal.timeout(7000),
  });

  if (!response.ok) {
    throw new Error(`Backend returned HTTP ${response.status}`);
  }

  return response.json();
}

export function loadDashboard(): Promise<Dashboard> {
  return apiRequest<Dashboard>("/dashboard");
}

export function loadDeviceSystem(): Promise<DeviceSystem> {
  return apiRequest<DeviceSystem>("/system");
}

export function loadMlHealth(): Promise<MlHealth> {
  return apiRequest<MlHealth>("/ml/health");
}

export function loadLatestPrediction(): Promise<MlPrediction> {
  return apiRequest<MlPrediction>("/ml/latest-prediction");
}

export function loadAnalyticsSummary(
  period: "24h" | "7d" | "30d",
  deviceId = "solar-panel-01",
): Promise<AnalyticsSummary> {
  const params = new URLSearchParams({
    period,
    device_id: deviceId,
  });

  return apiRequest<AnalyticsSummary>(
    `/analytics/summary?${params.toString()}`,
  );
}

export function loadDailyAnalytics(
  days = 7,
  deviceId = "solar-panel-01",
  timezone = "Asia/Kolkata",
): Promise<DailyAnalytics> {
  const params = new URLSearchParams({
    days: String(days),
    device_id: deviceId,
    timezone,
  });

  return apiRequest<DailyAnalytics>(`/analytics/daily?${params.toString()}`);
}

export function loadReadings(
  options: {
    limit?: number;
    offset?: number;
    start?: string;
    end?: string;
    deviceId?: string;
  } = {},
): Promise<ReadingsResponse> {
  const params = new URLSearchParams({
    limit: String(options.limit ?? 500),
    offset: String(options.offset ?? 0),
  });

  if (options.deviceId) {
    params.set("device_id", options.deviceId);
  }

  if (options.start) {
    params.set("start", options.start);
  }

  if (options.end) {
    params.set("end", options.end);
  }

  return apiRequest<ReadingsResponse>(`/readings?${params.toString()}`);
}

export type DemoStartResponse = {
  session_id: string;
  status: "running";
  started_at: string;
  expires_at: string;
  refresh_interval_seconds: number;
  message: string;
};

async function demoPost<T>(path: string): Promise<T> {
  const response = await fetch(`${base}${path}`, {
    method: "POST",
    signal: AbortSignal.timeout(10000),
  });

  if (!response.ok) {
    let detail = `Backend returned HTTP ${response.status}`;

    try {
      const body = await response.json();
      if (body.detail) detail = String(body.detail);
    } catch {
      // Keep the HTTP status message.
    }

    throw new Error(detail);
  }

  return response.json();
}

export function startCloudDemo(): Promise<DemoStartResponse> {
  return demoPost<DemoStartResponse>("/demo/start");
}

export function stopCloudDemo(
  sessionId: string,
): Promise<{ session_id: string; status: string }> {
  return demoPost(`/demo/stop?session_id=${encodeURIComponent(sessionId)}`);
}

export function loadCloudDemoDashboard(sessionId: string): Promise<Dashboard> {
  return apiRequest(
    `/demo/dashboard?session_id=${encodeURIComponent(sessionId)}`,
  );
}
