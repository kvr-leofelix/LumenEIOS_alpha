# LumenEIOS Deployment & Operations Guide

## 1. Quick Start: Local Zero-Dependency Execution

LumenEIOS is engineered to run locally out-of-the-box with zero paid cloud subscriptions, GPU hardware, or external database instances required.

### 1.1 Prerequisites
- Python 3.12+ (or 3.15)
- Node.js 18+ and npm

### 1.2 Start Backend
```bash
# 1. Install backend requirements
python -m pip install -r backend/requirements.txt

# 2. Start FastAPI server with automatic DB initialization and seed data
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```
The backend initializes the local database at `./lumeneios.db` and populates the 5 schools and demo accounts.
- API Documentation (Swagger): `http://localhost:8000/api/v1/docs`
- Health Endpoint: `http://localhost:8000/health`

### 1.3 Start Frontend
```bash
# 1. Install dependencies (if not already done)
npm install

# 2. Run Vite dev server
npm run dev
```
Open `http://localhost:3000` to interact with the system.

---

## 2. Production Docker Compose Deployment

For containerized multi-node environments:

```bash
cd infrastructure
docker-compose up -d --build
```

### Services Started:
- **`lumeneios-backend`**: FastAPI application container (Port 8000).
- **`lumeneios-postgres`**: PostgreSQL 16 with pgvector extension (Port 5432).
- **`lumeneios-redis`**: Redis 7 cache and message broker (Port 6379).
- **`lumeneios-minio`**: S3-compatible object storage (Port 9000 & 9001 console).

---

## 3. Environment Variables Reference

| Variable | Default Value | Description |
|:---|:---:|:---|
| `APP_ENV` | `development` | Runtime environment (`development`, `staging`, `production`). |
| `DEBUG` | `true` | Debug mode toggle. |
| `DATABASE_URL` | `sqlite+aiosqlite:///./lumeneios.db` | SQLAlchemy connection URI. |
| `SECRET_KEY` | `(32-char string)` | Secret key used for signing JWT tokens. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `120` | JWT expiration duration in minutes. |
| `DEMO_MODE` | `true` | Allows instant demo switching across the 5 fictional personas. |

---

## 4. Automated Testing & Verification

Run the full automated test suite containing 26 unit and integration test specs:

```bash
python -m pytest backend/tests -v
```

All 26 test specs verify role permissions, tenant isolation, pacing calculations, 60/40 compression invariants, OCR extractions, CER/WER formulas, and API endpoints.

