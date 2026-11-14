import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertTriangle,
  ArrowDownRight,
  ArrowUpRight,
  BarChart3,
  BatteryCharging,
  CheckCircle2,
  ChevronDown,
  CloudSun,
  Database,
  Download,
  Gauge,
  LayoutDashboard,
  Lightbulb,
  Radio,
  RefreshCw,
  ShieldCheck,
  Sun,
  Thermometer,
  Wifi,
  Zap,
  Clock3,
  Server,
  CalendarDays,
  Filter,
  Check,
  Info,
  Menu,
  X,
} from "lucide-react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  loadDashboard,
  loadAnalyticsSummary,
  loadDailyAnalytics,
  loadReadings,
  loadDeviceSystem,
  loadMlHealth,
  loadLatestPrediction,
  startCloudDemo,
  stopCloudDemo,
  loadCloudDemoDashboard,
  type DeviceSystem,
  type MlHealth,
  type MlPrediction,
  type Dashboard,
  type Reading,
  type AnalyticsSummary,
  type DailyAnalytics,
} from "./api";

type Page =
  | "Overview"
  | "Live Monitoring"
  | "Performance"
  | "Panel Health"
  | "ML Insights"
  | "Alerts"
  | "System";
const nav: [Page, any][] = [
  ["Overview", LayoutDashboard],
  ["Live Monitoring", Activity],
  ["Performance", BarChart3],
  ["Panel Health", ShieldCheck],
  ["ML Insights", Lightbulb],
  ["Alerts", AlertTriangle],
  ["System", Radio],
];
const fmt = (n: number, d = 2) => Number(n || 0).toFixed(d);
const time = (s: string) =>
  new Date(s).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

function Metric({
  label,
  value,
  unit,
  icon: Icon,
  note,
}: {
  label: string;
  value: string;
  unit?: string;
  icon: any;
  note: string;
}) {
  return (
    <article className="metric card">
      <div className="metric-top">
        <span>{label}</span>
        <span className="metric-icon">
          <Icon size={18} />
        </span>
      </div>
      <div className="metric-value">
        {value}
        <small>{unit}</small>
      </div>
      <div className="metric-note">{note}</div>
    </article>
  );
}
function EmptyNotice({ children }: { children: string }) {
  return (
    <div className="notice">
      <Info size={17} />
      <span>{children}</span>
    </div>
  );
}
export default function App() {
  const [data, setData] = useState<Dashboard | null>(null),
    [page, setPage] = useState<Page>("Overview");
  const [error, setError] = useState(""),
    [loading, setLoading] = useState(true),
    [updated, setUpdated] = useState(new Date());
  const [range, setRange] = useState("24h"),
    [mobileNav, setMobileNav] = useState(false);
  const [analytics, setAnalytics] = useState<AnalyticsSummary | null>(null);
  const [historicalReadings, setHistoricalReadings] = useState<Reading[]>([]);
  const [dailyAnalytics, setDailyAnalytics] = useState<DailyAnalytics | null>(
    null,
  );
  const [performanceLoading, setPerformanceLoading] = useState(false);
  const [performanceError, setPerformanceError] = useState("");
  const [deviceSystem, setDeviceSystem] = useState<DeviceSystem | null>(null);
  const [mlHealth, setMlHealth] = useState<MlHealth | null>(null);
  const [mlPrediction, setMlPrediction] = useState<MlPrediction | null>(null);
  const [mlPredictionError, setMlPredictionError] = useState("");
  const [demoSessionId, setDemoSessionId] = useState<string | null>(() =>
    window.localStorage.getItem("solarsense_demo_session"),
  );
  const [demoBusy, setDemoBusy] = useState(false);
  async function refresh() {
    try {
      let d: Dashboard;
      if (demoSessionId) {
        try {
          d = await loadCloudDemoDashboard(demoSessionId);
        } catch (demoError) {
          const message = demoError instanceof Error ? demoError.message : "";
          if (message.includes("HTTP 404") || message.includes("HTTP 410")) {
            window.localStorage.removeItem("solarsense_demo_session");
            setDemoSessionId(null);
            d = await loadDashboard();
          } else {
            throw demoError;
          }
        }
      } else {
        d = await loadDashboard();
      }
      setData(d);
      setError("");
      setUpdated(new Date());
      const [systemResult, modelResult] = await Promise.allSettled([
        loadDeviceSystem(),
        loadMlHealth(),
      ]);
      setDeviceSystem(
        systemResult.status === "fulfilled" ? systemResult.value : null,
      );
      setMlHealth(
        modelResult.status === "fulfilled" ? modelResult.value : null,
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not reach API");
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    void refresh();
    const t = setInterval(() => void refresh(), 10000);
    return () => clearInterval(t);
  }, [demoSessionId]);
  useEffect(() => {
    if (page !== "Performance") return;

    let cancelled = false;

    async function loadPerformance() {
      setPerformanceLoading(true);
      setPerformanceError("");

      try {
        const now = new Date();
        const duration =
          range === "24h" ? 24 : range === "7d" ? 7 * 24 : 30 * 24;

        const start = new Date(
          now.getTime() - duration * 60 * 60 * 1000,
        ).toISOString();

        const end = now.toISOString();

        const [summary, readings, daily] = await Promise.all([
          loadAnalyticsSummary(range as "24h" | "7d" | "30d"),
          loadReadings({
            limit: 5000,
            start,
            end,
            deviceId: "solar-panel-01",
          }),
          loadDailyAnalytics(
            range === "24h" ? 1 : range === "7d" ? 7 : 30,
            "solar-panel-01",
            "Asia/Kolkata",
          ),
        ]);

        if (!cancelled) {
          setAnalytics(summary);
          setHistoricalReadings(readings.items);
          setDailyAnalytics(daily);
        }
      } catch (error) {
        if (!cancelled) {
          setPerformanceError(
            error instanceof Error
              ? error.message
              : "Could not load historical analytics",
          );
        }
      } finally {
        if (!cancelled) {
          setPerformanceLoading(false);
        }
      }
    }

    loadPerformance();

    return () => {
      cancelled = true;
    };
  }, [page, range]);
  async function handleStartDemo() {
    setDemoBusy(true);
    setError("");
    try {
      const session = await startCloudDemo();
      window.localStorage.setItem(
        "solarsense_demo_session",
        session.session_id,
      );
      setDemoSessionId(session.session_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not start cloud demo");
    } finally {
      setDemoBusy(false);
    }
  }

  async function handleStopDemo() {
    if (!demoSessionId) return;
    setDemoBusy(true);
    try {
      await stopCloudDemo(demoSessionId);
      window.localStorage.removeItem("solarsense_demo_session");
      setDemoSessionId(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not stop cloud demo");
    } finally {
      setDemoBusy(false);
    }
  }

  const summary = data?.summary,
    latest = summary?.latest;
  const chartData = useMemo(
    () => data?.history.map((r) => ({ ...r, label: time(r.timestamp) })) ?? [],
    [data],
  );
  const demo =
    import.meta.env.VITE_DEMO_MODE === "true" ||
    !summary ||
    summary.data_source !== "hardware" ||
    !summary.device_online;
  const activeAlerts = data?.alerts ?? [];
  function downloadCsv() {
    if (!data) return;
    const rows = [
      [
        "timestamp",
        "voltage_v",
        "current_a",
        "power_w",
        "panel_temp_c",
        "light_lux",
        "energy_wh",
        "source",
      ],
      ...data.history.map((r) => [
        r.timestamp,
        r.voltage_v,
        r.current_a,
        r.power_w,
        r.panel_temp_c,
        r.light_lux,
        r.energy_wh,
        r.source ?? "unknown",
      ]),
    ];
    const csv = rows.map((row) => row.join(",")).join("\n"),
      url = URL.createObjectURL(new Blob([csv], { type: "text/csv" })),
      a = document.createElement("a");
    a.href = url;
    a.download = "solarsense-readings.csv";
    a.click();
    URL.revokeObjectURL(url);
  }
  const changePage = (p: Page) => {
    setPage(p);
    setMobileNav(false);
  };
  const heading: Record<Page, string> = {
    Overview: "Solar overview",
    "Live Monitoring": "Live sensor monitoring",
    Performance: "Performance analytics",
    "Panel Health": "Panel health assessment",
    "ML Insights": "Machine learning insights",
    Alerts: "Alert centre",
    System: "System status",
  };
  return (
    <div className="shell">
      <aside className={`sidebar ${mobileNav ? "mobile-open" : ""}`}>
        <div className="brand">
          <div className="brand-mark">
            <Sun size={23} />
          </div>
          <div>
            <b>SolarSense</b>
            <span>ENERGY INTELLIGENCE</span>
          </div>
          <button className="mobile-close" onClick={() => setMobileNav(false)}>
            <X size={18} />
          </button>
        </div>
        <div className="device-card">
          <span className="device-dot" />
          <div>
            <b>Solar Panel 01</b>
            <small>ROCK LIGHT · RL-SP06 · 7W</small>
          </div>
          <ChevronDown size={15} />
        </div>
        <div className="nav-label">WORKSPACE</div>
        <nav>
          {nav.map(([name, Icon]) => (
            <button
              key={name}
              className={`nav-item ${page === name ? "active" : ""}`}
              onClick={() => changePage(name)}
            >
              <Icon size={18} />
              <span>{name}</span>
              {name === "Alerts" &&
                activeAlerts.some((a) => !a.acknowledged) && (
                  <i className="nav-dot" />
                )}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="connection">
            <span className={`pulse ${error ? "offline" : ""}`} />
            <div>
              <b>Backend connection</b>
              <small>{error ? "Disconnected" : "API reachable"}</small>
            </div>
          </div>
          <small className="version">SOLARSENSE · VERSION 1.0</small>
        </div>
      </aside>
      <main className="main">
        <header className="topbar">
          <button className="mobile-menu" onClick={() => setMobileNav(true)}>
            <Menu size={20} />
          </button>
          <div className="breadcrumb">
            Workspace <span>/</span> {page}
          </div>
          <div className="top-actions">
            <span className={`connection-label ${error ? "bad" : ""}`}>
              <i /> {error ? "OFFLINE" : "API CONNECTED"}
            </span>
            <span className="updated">
              Updated{" "}
              {updated.toLocaleTimeString([], {
                hour: "2-digit",
                minute: "2-digit",
              })}
            </span>
            <button className="icon-button" onClick={refresh} title="Refresh">
              <RefreshCw size={16} />
            </button>
          </div>
        </header>
        <section className="content">
          <div className="page-heading">
            <div>
              <div className="eyebrow">SOLAR PERFORMANCE PLATFORM</div>
              <h1>{heading[page]}</h1>
              <p>
                {page === "Overview"
                  ? "Monitor energy production, panel conditions and system health."
                  : page === "Live Monitoring"
                    ? "Inspect the latest measurements from each connected sensor."
                    : page === "Performance"
                      ? "Review energy output and electrical performance over time."
                      : page === "Panel Health"
                        ? "Understand temperature, output and potential performance concerns."
                        : page === "ML Insights"
                          ? "Review model availability and anomaly estimates."
                          : page === "Alerts"
                            ? "Review system events and operational warnings."
                            : "Check backend, storage and sensor integration status."}
              </p>
            </div>
            <div className="heading-actions">
              <button
                className="outline-button"
                onClick={downloadCsv}
                disabled={!data}
              >
                <Download size={15} /> Export CSV
              </button>
              <span className="today-pill">
                <CalendarDays size={14} /> Today
              </span>
            </div>
          </div>
          {error && (
            <div className="error-banner">
              <AlertTriangle size={17} />
              <span>
                <b>Backend unavailable.</b> {error}. Check the FastAPI server
                and API URL.
              </span>
            </div>
          )}
          {data && (
            <div className="demo-banner">
              <Info size={17} />
              <span>
                <b>
                  {demoSessionId
                    ? "CLOUD DEMO RUNNING"
                    : summary?.data_source === "hardware" &&
                        summary.device_online
                      ? "HARDWARE DATA ACTIVE"
                      : "SIMULATED / FALLBACK DATA"}
                </b>
                {" — "}
                {demoSessionId
                  ? "Cloud-generated readings are updating every 10 seconds. These are not physical sensor measurements."
                  : summary?.data_source === "hardware" && summary.device_online
                    ? "Physical sensor readings are active. You can start an isolated cloud demo without changing the hardware stream."
                    : "Start the cloud demo to generate a separate stream of simulated readings."}
              </span>
              <button
                className="demo-control-button"
                type="button"
                onClick={demoSessionId ? handleStopDemo : handleStartDemo}
                disabled={demoBusy}
              >
                {demoBusy
                  ? "PLEASE WAIT…"
                  : demoSessionId
                    ? "STOP DEMO"
                    : "START DEMO"}
              </button>
            </div>
          )}
          {loading && !data ? (
            <div className="loading-state">
              <RefreshCw className="spin" /> Connecting to SolarSense API…
            </div>
          ) : !data ? (
            <div className="empty-state">
              No data received. Start the backend and refresh.
            </div>
          ) : (
            <>
              {page === "Overview" && (
                <Overview
                  data={data}
                  chartData={chartData}
                  demo={!!demo}
                  onNavigate={changePage}
                />
              )}
              {page === "Live Monitoring" && (
                <LiveMonitoring data={data} demo={!!demo} />
              )}
              {page === "Performance" && (
                <Performance
                  data={data}
                  chartData={chartData}
                  range={range}
                  setRange={setRange}
                  onExport={downloadCsv}
                  analytics={analytics}
                  historicalReadings={historicalReadings}
                  dailyAnalytics={dailyAnalytics}
                  loading={performanceLoading}
                  error={performanceError}
                />
              )}
              {page === "Panel Health" && (
                <PanelHealth data={data} demo={!!demo} />
              )}
              {page === "ML Insights" && (
                <MLInsights
                  data={data}
                  demo={!!demo}
                  model={mlHealth}
                  prediction={mlPrediction}
                  predictionError={mlPredictionError}
                  onRunPrediction={async () => {
                    setMlPredictionError("");
                    try {
                      setMlPrediction(await loadLatestPrediction());
                    } catch (e) {
                      setMlPrediction(null);
                      setMlPredictionError(
                        e instanceof Error
                          ? e.message
                          : "Prediction unavailable",
                      );
                    }
                  }}
                />
              )}
              {page === "Alerts" && <AlertsPage alerts={activeAlerts} />}
              {page === "System" && (
                <SystemPage
                  data={data}
                  error={error}
                  demo={!!demo}
                  system={deviceSystem}
                  model={mlHealth}
                />
              )}
            </>
          )}
          <footer>
            <span>SolarSense · Solar Energy & Health Monitoring</span>
            <span>Raspberry Pi · FastAPI · React</span>
          </footer>
        </section>
      </main>
    </div>
  );
}
function Overview({
  data,
  chartData,
  demo,
  onNavigate,
}: {
  data: Dashboard;
  chartData: any[];
  demo: boolean;
  onNavigate: (p: Page) => void;
}) {
  const s = data.summary,
    r = s.latest;
  return (
    <>
      <div className={`system-banner ${demo ? "banner-demo" : ""}`}>
        <div className="banner-icon">
          {demo ? <Info size={20} /> : <CheckCircle2 size={20} />}
        </div>
        <div>
          <b>
            {demo ? "Demo data is being displayed" : "Backend data received"}
          </b>
          <span>
            {demo
              ? "Hardware readings and ML predictions are not connected yet."
              : "The API returned stored sensor readings. Confirm sensor freshness before relying on them."}
          </span>
        </div>
        <span className="status-tag">{demo ? "DEMO MODE" : "API DATA"}</span>
      </div>
      <Section
        title="Live performance"
        subtitle="Latest electrical and environmental readings"
        meta="AUTO-REFRESH · 10 SEC"
      />
      <div className="metrics-grid">
        <Metric
          label="Panel voltage"
          value={fmt(r.voltage_v)}
          unit="V"
          icon={Zap}
          note="INA219 bus voltage"
        />
        <Metric
          label="Current"
          value={fmt(r.current_a, 3)}
          unit="A"
          icon={Activity}
          note="Measured current"
        />
        <Metric
          label="Output power"
          value={fmt(r.power_w)}
          unit="W"
          icon={BatteryCharging}
          note="Voltage × current"
        />
        <Metric
          label="Panel temperature"
          value={fmt(r.panel_temp_c, 1)}
          unit="°C"
          icon={Thermometer}
          note="DS18B20 surface probe"
        />
      </div>
      <div className="two-column overview-charts">
        <Panel
          title="Power generation"
          subtitle="Recorded power output over the returned history"
          meta="WATTS"
        >
          <PowerChart data={chartData} />
        </Panel>
        <Panel
          title="Energy summary"
          subtitle="Energy represented by returned records"
        >
          <div className="energy-total">
            {fmt(s.daily_energy_wh, 2)} <small>Wh</small>
          </div>
          <div className="energy-track">
            <i
              style={{
                width: `${Math.min(100, (s.daily_energy_wh / 35) * 100)}%`,
              }}
            />
          </div>
          <div className="data-pair">
            <span>Peak recorded power</span>
            <b>{fmt(s.peak_power_w)} W</b>
          </div>
          <div className="data-pair">
            <span>Uptime</span>
            <b>{s.uptime_pct ? fmt(s.uptime_pct, 1) + "%" : "Not measured"}</b>
          </div>
          <p className="small-muted">
            Energy calculation depends on the backend's sampling and integration
            logic.
          </p>
        </Panel>
      </div>
      <div className="two-column lower-grid">
        <Panel
          title="Environmental conditions"
          subtitle="Ambient conditions affecting panel output"
        >
          <div className="environment-grid">
            <Env
              icon={Sun}
              label="Light intensity"
              value={`${r.light_lux.toLocaleString()} lux`}
            />
            <Env
              icon={Thermometer}
              label="Panel temperature"
              value={`${fmt(r.panel_temp_c, 1)} °C`}
            />
            <Env icon={Zap} label="Panel rated peak" value="7 W" />
          </div>
        </Panel>
        <Panel
          title="Sensor availability"
          subtitle="Configured sensor channels"
        >
          <SensorList sensors={s.sensor_status} />
        </Panel>
      </div>
      <Section
        title="Recent alerts"
        subtitle="Latest events reported by the backend"
        action="View all"
        onAction={() => onNavigate("Alerts")}
      />
      <AlertList alerts={data.alerts.slice(0, 4)} />
    </>
  );
}
function LiveMonitoring({ data, demo }: { data: Dashboard; demo: boolean }) {
  const r = data.summary.latest,
    sensors = [
      ["INA219 · Voltage", `${fmt(r.voltage_v)} V`, "Electrical measurement"],
      [
        "INA219 · Current",
        `${fmt(r.current_a, 3)} A`,
        "Electrical measurement",
      ],
      ["Calculated power", `${fmt(r.power_w)} W`, "Voltage × current"],
      [
        "DS18B20 · Panel temperature",
        `${fmt(r.panel_temp_c, 1)} °C`,
        "Panel surface temperature",
      ],
      [
        "BH1750 · Light intensity",
        `${r.light_lux.toLocaleString()} lux`,
        "Illuminance, not calibrated irradiance",
      ],
    ];
  return (
    <>
      <Section
        title="Current sensor readings"
        subtitle="Latest values returned by the API"
      />
      <div className="sensor-grid">
        {sensors.map(([name, value, desc], i) => (
          <article className="card sensor-card" key={name}>
            <div className="sensor-card-top">
              <span className="sensor-number">0{i + 1}</span>
              <span className="reading-state">
                {demo ? "SAMPLE" : "API VALUE"}
              </span>
            </div>
            <b>{name}</b>
            <strong>{value}</strong>
            <small>{desc}</small>
          </article>
        ))}
      </div>
      <Panel
        title="Recent sensor trends"
        subtitle="Voltage, current and panel temperature across available history"
      >
        <MultiChart data={data.history} />
      </Panel>
      <EmptyNotice>
        {demo
          ? "No physical sensor is connected to the backend yet. These are generated sample readings."
          : "The backend currently provides stored records. Continuous live streaming and per-sensor freshness timestamps can be added behind this API."}
      </EmptyNotice>
    </>
  );
}

function Performance({
  data,
  range,
  setRange,
  onExport,
  analytics,
  historicalReadings,
  dailyAnalytics,
  loading,
  error,
}: {
  data: Dashboard;
  chartData: any[];
  range: string;
  setRange: (v: string) => void;
  onExport: () => void;
  analytics: AnalyticsSummary | null;
  historicalReadings: Reading[];
  dailyAnalytics: DailyAnalytics | null;
  loading: boolean;
  error: string;
}) {
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [dayReadings, setDayReadings] = useState<Reading[]>([]);
  const [dayLoading, setDayLoading] = useState(false);
  const [dayError, setDayError] = useState("");

  const filtered = historicalReadings.map((r) => ({
    ...r,
    label: time(r.timestamp),
  }));

  const total = analytics?.energy_wh ?? 0;
  const peak = analytics?.peak_power_w ?? 0;

  async function selectDay(date: string, count: number) {
    if (count === 0) return;

    if (selectedDate === date) {
      setSelectedDate(null);
      setDayReadings([]);
      setDayError("");
      return;
    }

    setSelectedDate(date);
    setDayReadings([]);
    setDayError("");
    setDayLoading(true);

    try {
      // India local midnight converted to UTC.
      const start = new Date(`${date}T00:00:00+05:30`);

      const end = new Date(start.getTime() + 24 * 60 * 60 * 1000);

      const result = await loadReadings({
        limit: 5000,
        deviceId: "solar-panel-01",
        start: start.toISOString(),
        end: end.toISOString(),
      });

      setDayReadings(
        result.items.sort(
          (a, b) =>
            new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime(),
        ),
      );
    } catch (error) {
      setDayError(
        error instanceof Error
          ? error.message
          : "Could not load readings for this date",
      );
    } finally {
      setDayLoading(false);
    }
  }

  function exportHistoricalCsv() {
    if (!historicalReadings.length) {
      onExport();
      return;
    }

    const rows = [
      [
        "timestamp",
        "voltage_v",
        "current_a",
        "power_w",
        "panel_temp_c",
        "light_lux",
        "energy_wh",
      ],
      ...historicalReadings.map((r) => [
        r.timestamp,
        r.voltage_v,
        r.current_a,
        r.power_w,
        r.panel_temp_c,
        r.light_lux,
        r.energy_wh,
      ]),
    ];

    const csv = rows.map((row) => row.join(",")).join("\n");
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));

    const a = document.createElement("a");
    a.href = url;
    a.download = `solarsense-${range}-readings.csv`;
    a.click();

    URL.revokeObjectURL(url);
  }

  return (
    <>
      <div className="toolbar">
        <div className="segmented">
          {["24h", "7d", "30d"].map((x) => (
            <button
              className={range === x ? "selected" : ""}
              onClick={() => setRange(x)}
              key={x}
            >
              {x}
            </button>
          ))}
        </div>

        <button
          className="outline-button"
          onClick={exportHistoricalCsv}
          disabled={loading || !historicalReadings.length}
        >
          <Download size={14} /> Export readings
        </button>
      </div>

      {loading && (
        <div className="notice">
          <RefreshCw size={17} />
          <span>Loading {range} historical analytics…</span>
        </div>
      )}

      {error && (
        <div className="error-banner">
          <AlertTriangle size={17} />
          <span>{error}</span>
        </div>
      )}

      <div className="metrics-grid three">
        <Metric
          label={`Energy · ${range}`}
          value={fmt(total, 4)}
          unit="Wh"
          icon={BatteryCharging}
          note="Backend analytics summary"
        />

        <Metric
          label="Peak recorded power"
          value={fmt(peak)}
          unit="W"
          icon={Zap}
          note="Selected period"
        />

        <Metric
          label="Data points"
          value={String(analytics?.readings_count ?? 0)}
          unit="records"
          icon={Database}
          note="Selected period"
        />
      </div>

      <Panel title="Power output" subtitle="Power versus timestamp" meta="W">
        {filtered.length ? (
          <PowerChart data={filtered} />
        ) : (
          <EmptyNotice>
            No historical readings are available for this period.
          </EmptyNotice>
        )}
      </Panel>

      <div className="two-column">
        <Panel title="Voltage history" subtitle="INA219 voltage readings">
          <SingleLine
            data={filtered}
            field="voltage_v"
            color="#3986c8"
            unit="V"
          />
        </Panel>

        <Panel title="Current history" subtitle="INA219 current readings">
          <SingleLine
            data={filtered}
            field="current_a"
            color="#d99a42"
            unit="A"
          />
        </Panel>
      </div>

      {dailyAnalytics && (
        <Panel
          title="Daily energy records"
          subtitle={`Daily aggregation · ${dailyAnalytics.timezone}`}
        >
          {dailyAnalytics.items.map((item) => {
            const selected = selectedDate === item.date;
            const hasReadings = item.readings_count > 0;

            return (
              <div key={item.date}>
                <button
                  type="button"
                  disabled={!hasReadings}
                  onClick={() => selectDay(item.date, item.readings_count)}
                  aria-expanded={selected}
                  style={{
                    width: "100%",
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    padding: "12px 4px",
                    border: 0,
                    borderBottom: "1px solid #e9eef2",
                    background: selected ? "#f0f8f8" : "transparent",
                    color: "inherit",
                    textAlign: "left",
                    cursor: hasReadings ? "pointer" : "default",
                    opacity: hasReadings ? 1 : 0.65,
                  }}
                >
                  <span>
                    {item.date}
                    {hasReadings && (
                      <small
                        style={{
                          display: "block",
                          color: "#16a394",
                          marginTop: 4,
                        }}
                      >
                        {selected ? "Hide readings" : "View readings"}
                      </small>
                    )}
                  </span>

                  <span style={{ textAlign: "right" }}>
                    <b>{fmt(item.energy_wh, 4)} Wh</b>
                    <small
                      style={{
                        display: "block",
                        color: "#8998a5",
                        marginTop: 4,
                      }}
                    >
                      {item.readings_count} readings
                    </small>
                  </span>
                </button>

                {selected && (
                  <div
                    style={{
                      padding: "14px 8px",
                      background: "#f8fafc",
                    }}
                  >
                    {dayLoading ? (
                      <div className="notice">
                        <RefreshCw size={16} />
                        Loading readings for {item.date}…
                      </div>
                    ) : dayError ? (
                      <div className="error-banner">{dayError}</div>
                    ) : dayReadings.length === 0 ? (
                      <EmptyNotice>
                        No readings were returned for this date.
                      </EmptyNotice>
                    ) : (
                      <>
                        <h3 style={{ marginBottom: 12 }}>
                          Readings for {item.date}
                        </h3>

                        <div
                          style={{
                            overflowX: "auto",
                            width: "100%",
                          }}
                        >
                          <table
                            style={{
                              width: "100%",
                              borderCollapse: "collapse",
                              fontSize: 13,
                              textAlign: "left",
                            }}
                          >
                            <thead>
                              <tr>
                                {[
                                  "Time",
                                  "Voltage",
                                  "Current",
                                  "Power",
                                  "Temperature",
                                  "Light",
                                  "Energy",
                                ].map((label) => (
                                  <th
                                    key={label}
                                    style={{
                                      padding: "10px 8px",
                                      borderBottom: "1px solid #dce4ed",
                                      whiteSpace: "nowrap",
                                    }}
                                  >
                                    {label}
                                  </th>
                                ))}
                              </tr>
                            </thead>

                            <tbody>
                              {dayReadings.map((r, index) => (
                                <tr key={`${r.timestamp}-${index}`}>
                                  <td style={{ padding: 8 }}>
                                    {time(r.timestamp)}
                                  </td>
                                  <td style={{ padding: 8 }}>
                                    {fmt(r.voltage_v)} V
                                  </td>
                                  <td style={{ padding: 8 }}>
                                    {fmt(r.current_a, 3)} A
                                  </td>
                                  <td style={{ padding: 8 }}>
                                    {fmt(r.power_w)} W
                                  </td>
                                  <td style={{ padding: 8 }}>
                                    {fmt(r.panel_temp_c, 1)} °C
                                  </td>
                                  <td style={{ padding: 8 }}>
                                    {fmt(r.light_lux, 0)} lux
                                  </td>
                                  <td style={{ padding: 8 }}>
                                    {fmt(r.energy_wh, 4)} Wh
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </Panel>
      )}

      {!loading && !error && (
        <EmptyNotice>
          Analytics are calculated from records stored by the backend.
          Historical accuracy depends on sampling frequency and data
          availability.
        </EmptyNotice>
      )}
    </>
  );
}

function PanelHealth({ data, demo }: { data: Dashboard; demo: boolean }) {
  const r = data.summary.latest,
    s = data.summary;
  return (
    <>
      <div className="health-hero card">
        <div className="health-score">
          <div>
            <b>{demo ? "—" : s.health_score}</b>
            <small>{demo ? "NOT VALIDATED" : "/ 100"}</small>
          </div>
        </div>
        <div>
          <span className="eyebrow">PANEL CONDITION</span>
          <h2>{demo ? "Health score not validated" : s.health_label}</h2>
          <p>
            {demo
              ? "A trustworthy health score requires measured baseline data, irradiance-aware normalization and validated thresholds."
              : "This score is supplied by the backend. Review the supporting measurements before interpreting it as a diagnosis."}
          </p>
        </div>
      </div>
      <div className="two-column">
        <Panel
          title="Temperature observation"
          subtitle="Latest panel surface temperature"
        >
          <div className="big-reading">
            {fmt(r.panel_temp_c, 1)} <small>°C</small>
          </div>
          <p className="small-muted">
            Temperature alone cannot determine panel health. Compare output at
            similar light levels and ambient conditions.
          </p>
        </Panel>
        <Panel
          title="Electrical observation"
          subtitle="Latest measured electrical values"
        >
          <div className="health-facts">
            <div>
              <span>Voltage</span>
              <b>{fmt(r.voltage_v)} V</b>
            </div>
            <div>
              <span>Current</span>
              <b>{fmt(r.current_a, 3)} A</b>
            </div>
            <div>
              <span>Power</span>
              <b>{fmt(r.power_w)} W</b>
            </div>
          </div>
        </Panel>
      </div>
      <EmptyNotice>
        Panel degradation detection is not implemented yet. We need calibrated
        irradiance data, repeatable reference conditions and a validated model
        before assigning a real health grade.
      </EmptyNotice>
    </>
  );
}
function MLInsights({
  data,
  demo,
  model,
  prediction,
  predictionError,
  onRunPrediction,
}: {
  data: Dashboard;
  demo: boolean;
  model: MlHealth | null;
  prediction: MlPrediction | null;
  predictionError: string;
  onRunPrediction: () => void;
}) {
  return (
    <>
      <div className="ml-banner">
        <Lightbulb size={22} />
        <div>
          <b>{model?.ready ? "ML model loaded" : "ML model not deployed"}</b>
          <span>
            {model?.ready
              ? `Model version ${model.model_version}. Run inference on the latest stored reading.`
              : model?.message ||
                "No validated model artifact is installed. Predictions remain unavailable."}
          </span>
        </div>
      </div>
      <div className="two-column">
        <Panel title="Model readiness" subtitle="Backend inference service">
          <div className="ml-status">
            <span
              className={`large-status ${model?.ready ? "available" : "pending"}`}
            >
              {model?.ready ? "READY" : "NOT DEPLOYED"}
            </span>
            <p>{model?.model_version || "No model version"}</p>
          </div>
        </Panel>
        <Panel
          title="Latest fault classification"
          subtitle="Prediction from the latest stored reading"
        >
          {prediction ? (
            <div className="ml-status">
              <b>{prediction.predicted_class.replace(/_/g, " ")}</b>
              <p>Confidence: {fmt(prediction.confidence * 100, 1)}%</p>
              <small>
                Model {prediction.model_version} · {prediction.reading_source}{" "}
                data
              </small>
            </div>
          ) : (
            <div className="ml-status">
              <span className="large-status pending">NO PREDICTION</span>
              <p>
                {predictionError ||
                  "No inference has been run in this session."}
              </p>
            </div>
          )}
          <button
            className="outline-button"
            type="button"
            disabled={!model?.ready || demo}
            onClick={onRunPrediction}
          >
            Run latest prediction
          </button>
        </Panel>
      </div>
      {prediction && (
        <Panel
          title="Class probabilities"
          subtitle="Model-reported probabilities; not a guarantee of fault diagnosis"
        >
          {Object.entries(prediction.probabilities).map(
            ([label, probability]) => (
              <div className="system-row" key={label}>
                <b>{label.replace(/_/g, " ")}</b>
                <span>{fmt(probability * 100, 1)}%</span>
              </div>
            ),
          )}
          <p className="small-muted">{prediction.warning}</p>
        </Panel>
      )}
      <EmptyNotice>
        {demo
          ? "Latest readings are not confirmed as physical hardware data. Prediction is disabled for simulated or legacy readings."
          : "ML predictions are advisory. Fault classification must be validated on independent, labelled physical test sessions before operational use."}
      </EmptyNotice>
    </>
  );
}
function AlertsPage({ alerts }: { alerts: any[] }) {
  return (
    <>
      <Section
        title="Alert history"
        subtitle="Events received from the backend"
        meta={`${alerts.length} EVENTS`}
      />
      {alerts.length ? (
        <AlertList alerts={alerts} />
      ) : (
        <div className="empty-state card">
          <CheckCircle2 size={28} />
          <b>No alerts returned</b>
          <span>The API has not supplied any alert records.</span>
        </div>
      )}
      <EmptyNotice>
        Alert generation rules, severity thresholds and acknowledgement
        persistence must be completed in the backend. The current interface
        displays backend-provided alerts.
      </EmptyNotice>
    </>
  );
}
function SystemPage({
  data,
  error,
  demo,
  system,
  model,
}: {
  data: Dashboard;
  error: string;
  demo: boolean;
  system: DeviceSystem | null;
  model: MlHealth | null;
}) {
  const rows = [
    ["FastAPI backend", error ? "Disconnected" : "Responding", !error],
    ["Dashboard API", "Data received", true],
    ["Database", error ? "Unavailable" : "API database check passed", !error],
    [
      "Device agent",
      system?.online ? `Online · ${system.status}` : "Offline / no heartbeat",
      !!system?.online,
    ],
    [
      "INA219",
      system?.sensors?.INA219 ? "Healthy" : "Unhealthy / unknown",
      !!system?.sensors?.INA219,
    ],
    [
      "DS18B20",
      system?.sensors?.DS18B20 ? "Healthy" : "Unhealthy / unknown",
      !!system?.sensors?.DS18B20,
    ],
    [
      "BH1750",
      system?.sensors?.BH1750 ? "Healthy" : "Unhealthy / unknown",
      !!system?.sensors?.BH1750,
    ],
    [
      "ML inference",
      model?.ready ? `Ready · ${model.model_version}` : "Model unavailable",
      !!model?.ready,
    ],
  ];
  return (
    <>
      <Section
        title="System components"
        subtitle="Connection and integration readiness"
      />
      <div className="system-list card">
        {rows.map(([name, status, ok]) => (
          <div className="system-row" key={String(name)}>
            <span className="system-icon">
              <Server size={17} />
            </span>
            <b>{name}</b>
            <span>{status}</span>
            <i className={ok ? "ok" : "pending"}>{ok ? "READY" : "PENDING"}</i>
          </div>
        ))}
      </div>
      <div className="two-column">
        <Panel
          title="Device heartbeat"
          subtitle="Latest Raspberry Pi agent status"
        >
          <div className="health-facts">
            <div>
              <span>Device ID</span>
              <b>{system?.device_id || "Not registered"}</b>
            </div>
            <div>
              <span>Agent version</span>
              <b>{system?.agent_version || "Unknown"}</b>
            </div>
            <div>
              <span>Data source</span>
              <b>{system?.source || data.summary.data_source}</b>
            </div>
            <div>
              <span>Last heartbeat</span>
              <b>
                {system?.last_seen
                  ? new Date(system.last_seen).toLocaleString()
                  : "Never received"}
              </b>
            </div>
          </div>
          {system && Object.keys(system.sensor_errors || {}).length > 0 && (
            <div className="notice">
              Sensor errors:{" "}
              {Object.entries(system.sensor_errors)
                .map(([sensor, message]) => `${sensor}: ${message}`)
                .join(" · ")}
            </div>
          )}
        </Panel>
        <Panel title="Backend information" subtitle="API connection">
          <div className="health-facts">
            <div>
              <span>Service</span>
              <b>SolarSense API</b>
            </div>
            <div>
              <span>API version</span>
              <b>2.1.0</b>
            </div>
            <div>
              <span>Refresh interval</span>
              <b>10 seconds</b>
            </div>
          </div>
        </Panel>
        <Panel title="Latest record" subtitle="Timestamp supplied by backend">
          <div className="big-reading date-reading">
            {new Date(data.summary.latest.timestamp).toLocaleString()}
          </div>
          <p className="small-muted">
            Confirm that incoming timestamps are current and that sensor
            readings are not stale.
          </p>
        </Panel>
      </div>
    </>
  );
}
function Section({
  title,
  subtitle,
  meta,
  action,
  onAction,
}: {
  title: string;
  subtitle: string;
  meta?: string;
  action?: string;
  onAction?: () => void;
}) {
  return (
    <div className="section-head">
      <div>
        <h2>{title}</h2>
        <p>{subtitle}</p>
      </div>
      {action ? (
        <button className="text-action" onClick={onAction}>
          {action} →
        </button>
      ) : (
        meta && <span className="section-meta">{meta}</span>
      )}
    </div>
  );
}
function Panel({
  title,
  subtitle,
  meta,
  children,
}: {
  title: string;
  subtitle: string;
  meta?: string;
  children: any;
}) {
  return (
    <section className="card panel">
      <div className="panel-head">
        <div>
          <h3>{title}</h3>
          <p>{subtitle}</p>
        </div>
        {meta && <span className="section-meta">{meta}</span>}
      </div>
      {children}
    </section>
  );
}
function PowerChart({ data }: { data: any[] }) {
  return (
    <div className="chart">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data}>
          <defs>
            <linearGradient id="powerArea" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#16ad99" stopOpacity={0.24} />
              <stop offset="100%" stopColor="#16ad99" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid
            strokeDasharray="3 5"
            vertical={false}
            stroke="#e9eef2"
          />
          <XAxis
            dataKey="label"
            tick={{ fontSize: 10, fill: "#8998a5" }}
            axisLine={false}
            tickLine={false}
            interval="preserveStartEnd"
          />
          <YAxis
            tick={{ fontSize: 10, fill: "#8998a5" }}
            axisLine={false}
            tickLine={false}
            width={36}
          />
          <Tooltip />
          <Area
            dataKey="power_w"
            name="Power"
            type="monotone"
            stroke="#16ad99"
            strokeWidth={2.4}
            fill="url(#powerArea)"
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
function MultiChart({ data }: { data: Reading[] }) {
  const d = data.map((r) => ({ ...r, label: time(r.timestamp) }));
  return (
    <div className="chart tall">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={d}>
          <CartesianGrid
            strokeDasharray="3 5"
            vertical={false}
            stroke="#e9eef2"
          />
          <XAxis
            dataKey="label"
            tick={{ fontSize: 10 }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            yAxisId="left"
            tick={{ fontSize: 10 }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip />
          <Legend />
          <Line
            yAxisId="left"
            dataKey="voltage_v"
            name="Voltage (V)"
            stroke="#3986c8"
            dot={false}
          />
          <Line
            yAxisId="left"
            dataKey="panel_temp_c"
            name="Temperature (°C)"
            stroke="#dc9650"
            dot={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
function SingleLine({
  data,
  field,
  color,
  unit,
}: {
  data: any[];
  field: string;
  color: string;
  unit: string;
}) {
  return (
    <div className="chart">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data}>
          <CartesianGrid
            strokeDasharray="3 5"
            vertical={false}
            stroke="#e9eef2"
          />
          <XAxis
            dataKey="label"
            tick={{ fontSize: 10 }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis tick={{ fontSize: 10 }} axisLine={false} tickLine={false} />
          <Tooltip />
          <Line
            dataKey={field}
            name={unit}
            stroke={color}
            strokeWidth={2}
            dot={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
function Env({
  icon: Icon,
  label,
  value,
}: {
  icon: any;
  label: string;
  value: string;
}) {
  return (
    <div className="env-item">
      <span>
        <Icon size={18} />
      </span>
      <small>{label}</small>
      <b>{value}</b>
    </div>
  );
}
function SensorList({ sensors }: { sensors: Record<string, boolean> }) {
  return (
    <div className="sensor-list">
      {Object.entries(sensors).map(([name, ok]) => (
        <div key={name}>
          <span className={ok ? "sensor-ok" : "sensor-off"} />
          <b>{name}</b>
          <small>{ok ? "Reported by API" : "Not reporting"}</small>
        </div>
      ))}
    </div>
  );
}
function AlertList({ alerts }: { alerts: any[] }) {
  return (
    <div className="alert-list">
      {alerts.map((a) => (
        <div className="alert-row" key={a.id}>
          <span className={`alert-icon ${a.severity}`}>
            <AlertTriangle size={17} />
          </span>
          <div className="alert-copy">
            <b>{a.title}</b>
            <small>{a.message}</small>
          </div>
          <time>{new Date(a.timestamp).toLocaleString()}</time>
          <span className={`severity ${a.severity}`}>{a.severity}</span>
        </div>
      ))}
    </div>
  );
}
