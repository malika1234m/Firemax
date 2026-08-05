# FiremeX

Fire and hazard detection for CCTV. Camera streams are analysed by a YOLOv8-based
detector; confirmed incidents raise alerts in the dashboard, trigger Home Assistant
automations (lights, locks, sirens), and notify staff and authorities by email/SMS.

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full system design.

## Repository layout

| Path           | What it is                                                        |
| -------------- | ----------------------------------------------------------------- |
| `backend/`     | FastAPI control plane — auth, orgs, sites, alerts, billing, WebSocket feed |
| `frontend/`    | React + Vite + Tailwind operator dashboard                        |
| `edge/`        | On-site agent that runs detection locally and reports to the cloud |
| `backend-mock/`| Tiny Node stub of the API, for frontend work without the backend   |
| `demo_server.py` | Self-contained demo server used for presentations                |
| `docker-compose.yml` | Mongo + backend + frontend + Home Assistant, all wired up    |
| `ha_automation.yaml` | Example Home Assistant automation for hazard webhooks        |

## Prerequisites

- Python 3.11+
- Node.js 18+
- MongoDB 7 (local, or the `mongo` service in `docker-compose.yml`)

## Setup

### 1. Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # then fill in the values — see "Configuration" below
uvicorn app.main:app --reload --port 8000
```

API docs are then served at http://localhost:8000/docs.

### 2. Frontend

```bash
cd frontend
npm install
npm run dev               # http://localhost:5173
```

### 3. Edge agent (optional)

```bash
cd edge
pip install -r requirements.txt
cp .env.example .env      # set AGENT_TOKEN from FiremeX → Sites → Create Site
python agent.py
```

### Everything in Docker

```bash
cp backend/.env.example backend/.env   # fill it in first
docker compose up --build
```

Frontend on `:3000`, backend on `:8000`, Home Assistant on `:8123`, Mongo on `:27017`.

## Model weights

Model weights (`*.pt`) are **not** in this repository — they are large binaries and
are distributed out-of-band. Place them at:

```
backend/models/fire_model.pt
```

and point `MODEL_PATH` at that file. A stock `yolov8n.pt` from Ultralytics works for
smoke-testing the pipeline. The edge agent can also be run with `DETECTOR_MODE=mock`
to exercise everything without any weights present.

## Configuration

All configuration comes from environment variables. `backend/.env.example` and
`edge/.env.example` document every key; copy them to `.env` and fill in the values.

Nothing sensitive belongs in the repo. `.env` files, keys, certificates and model
weights are all covered by `.gitignore`. In particular you will need your own:

- `JWT_SECRET` and `SECRETS_ENCRYPTION_KEY` (random per install)
- MongoDB connection string
- Home Assistant long-lived access token
- Twilio credentials (SMS/voice to authorities)
- Stripe test keys (billing)
- SMTP credentials (email alerts)

## Tests

```bash
cd backend
pip install -r requirements-dev.txt
pytest
```

## Seeding demo data

```bash
cd backend
python scripts/seed_demo_data.py
```
