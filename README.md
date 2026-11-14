# SolarSense — Integrated Project

SolarSense is a solar-panel energy and condition monitoring system built from four connected parts:

- `device-agent/` — Raspberry Pi sensor acquisition, validation, SQLite outbox, and authenticated cloud synchronization.
- `backend/` — FastAPI service, PostgreSQL/SQLite persistence, analytics, alerts, device health, and optional ML inference.
- `frontend/` — React + TypeScript dashboard with seven pages.
- `ml-training/` — physical-data validation, grouped-session training, evaluation, and model artifact generation.

**Important:** The included simulator is for software testing only. No included readings establish real solar-panel performance. No trained model is bundled because the supplied labelled physical dataset is not sufficient.

## Local setup (Windows PowerShell)

### 1. Backend

```powershell
cd backend
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Backend health: `http://127.0.0.1:8000/api/v1/health`

Development API docs: `http://127.0.0.1:8000/docs`

### 2. Dashboard (second terminal)

```powershell
cd frontend
npm ci
Copy-Item .env.example .env
npm run build
npm run dev
```

Open `http://localhost:5173`.

Set `VITE_API_BASE_URL=http://127.0.0.1:8000/api/v1` in `frontend/.env` for local backend access. Never place device/admin API secrets in `VITE_*` variables; frontend environment variables are public in the browser bundle.

### 3. Device agent (third terminal)

```powershell
cd device-agent
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python -m app
```

Keep `SENSOR_MODE=simulated` on Windows. Simulated readings are not real sensor readings. For cloud sync, configure `API_BASE_URL` including `/api/v1` and the same `DEVICE_API_KEY` configured in the backend.

### 4. Run tests

```powershell
# Backend
cd backend
python -m pytest -q

# Device agent
cd ..\device-agent
python -m pytest -q

# ML pipeline and inference
cd ..\ml-training
python -m pytest -q tests
```

## Key API endpoints

- `GET /api/v1/health` — database-aware health check.
- `GET /api/v1/dashboard` — dashboard summary and history.
- `GET /api/v1/system` — device heartbeat and sensor status.
- `POST /api/v1/devices/heartbeat` — authenticated device health heartbeat.
- `POST /api/v1/readings` and `/api/v1/readings/batch` — authenticated reading ingestion.
- `GET /api/v1/readings`, `/analytics/summary`, `/analytics/daily` — historical data and analytics.
- `GET /api/v1/ml/health` — model readiness.
- `GET /api/v1/ml/latest-prediction` — inference on latest physical hardware reading only.
- `POST /api/v1/ml/predict` — authenticated direct inference.

## Database migration for an existing database

Back up and verify the database first. From `backend/` with the intended `DATABASE_URL` configured:

```powershell
python -m scripts.migrate_cloud_sync
python -m scripts.migrate_device_health
```

New databases are created at application startup. `create_all()` does not alter existing tables; the migration scripts are required for existing databases.

## Production deployment

See `PHASE3_4_5_COMPLETION_GUIDE.md`. Configure Render environment variables `DATABASE_URL`, `DEVICE_API_KEY`, `ADMIN_API_KEY`, `CORS_ORIGINS`, and `ENVIRONMENT=production`. Configure Vercel `VITE_API_BASE_URL` to the Render API base URL. Do not expose secrets in frontend environment variables.

The current release leaves GET readings/analytics/system endpoints public and does not provide user login or browser-side alert acknowledgement. Add authenticated user sessions, device-scoped authorization, and rate limiting before multi-user or sensitive production use.

## ML training

Training accepts labelled physical hardware measurements only. It requires all four classes across independent sessions and uses grouped-by-session evaluation. See `ml-training/README.md` and `ml-training/LABELLED_DATA_COLLECTION_GUIDE.md`. A model is not bundled; do not train from simulated/legacy readings or claim accuracy without independent physical validation.

## Hardware boundary

The Raspberry Pi and sensors must be physically connected and commissioned separately. Verify board logic levels, I2C addresses, DS18B20 wiring, INA219 shunt resistance, panel voltage/current limits, and measurements against reference instruments. Never connect the panel output directly to Raspberry Pi GPIO.


## One-repository cloud deployment

See [`DEPLOYMENT_GUIDE.md`](DEPLOYMENT_GUIDE.md). The repository root includes `render.yaml`; the frontend includes `frontend/vercel.json`.
