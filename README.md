# LumenEIOS — Adaptive EdTech Ecosystem (NEP 2020)

> **Complete Multi-Role Adaptive Learning & School Management Platform**  
> Aligned with India's National Education Policy (NEP 2020) Competency-Based Education framework.

---

## 1. Executive Summary & Vision

**LumenEIOS** is a high-fidelity web application engineered to demonstrate an AI-inspired adaptive learning and school management ecosystem. 

Traditional school software blindly prioritizes textbook chapter completion over actual student comprehension. When unexpected disruptions occur (extreme weather closures, state election duties, public health camps, and census surveys), classrooms are forced to rush through lessons, leaving severe learning gaps.

LumenEIOS introduces the **Time-Aware Pedagogical Engine**:
1. **Measures 4 Essential Competency Dimensions**:
   - **LU**: Language Understanding (interpreting terminology & clauses)
   - **CU**: Concept Understanding (fundamental mental models & proofs)
   - **AU**: Application Understanding (practical real-world problem-solving)
   - **CT**: Critical Thinking (evaluating claims, detecting fallacies)
2. **Dynamic Calendar Compacting (60/40 Strategy)**:
   - **Protects 100% of Core Competencies** (60% essential curriculum).
   - Reassigns supplementary topics (40%) to guided flipped inquiry, home labs, and cross-curricular synergy projects.
3. **Multi-Infrastructure Tier Telemetry**:
   - Seamlessly supports **High-Tech Private**, **Standard Blended**, and **Low-Tech Rural Government** schools (with offline optical worksheet scan review).
4. **Unified Stakeholder Experience**:
   - Role-specific workflows for **Administrators**, **Principals**, **Teachers**, **Students**, and **Parents**.

---

## 2. Tech Stack

- **Framework**: React 18 with TypeScript
- **Build Tool**: Vite 5
- **Styling**: Tailwind CSS 3 (Inter typography, custom Navy `#142A43` & Teal `#16A085` palette)
- **Routing**: React Router DOM v6
- **Data Visualization**: Recharts (Radar charts, Grouped bar charts, Heatmaps, Pacing bars)
- **Icons**: Lucide React
- **Persistence**: Centralized `DataContext` with `LocalStorage` synchronization and Demo Reset

---

## 3. Demo Credentials & Personas

The application features **1-Click Demo Login** buttons directly on the login screen (`/login`) and a persistent **Stakeholder Role Switcher Banner** at the top of every page.

| Role | Demo Email | Password | Name & Title | Campus Context |
| :--- | :--- | :--- | :--- | :--- |
| **Admin** | `admin@lumeneios.demo` | `demo123` | **Dr. Rajesh Sharma** (Academic Innovation Director) | Statewide (All 5 Campuses) |
| **Principal** | `principal@lumeneios.demo` | `demo123` | **Dr. Sunita Deshmukh** (Principal) | Sunrise Public School (`school-1`) |
| **Teacher** | `teacher@lumeneios.demo` | `demo123` | **Vikram Sengupta** (Lead TGT Educator) | Class 8-A & 9-B (Maths & Science) |
| **Student** | `student@lumeneios.demo` | `demo123` | **Aarav Patel** (Grade 8 Student) | Class 8-A (Roll #14) |
| **Parent** | `parent@lumeneios.demo` | `demo123` | **Meera Patel** (Guardian) | Linked to Aarav & Ananya Patel |

---

## 4. Multi-School Infrastructure Tiers

The ecosystem is seeded with 5 fictional Indian schools across different infrastructure capabilities:

1. **Sunrise Public School** (`school-1`) — *High-Tech Private* (Bengaluru, Karnataka): Digital smart boards, 1:1 student tablets, fiber broadband.
2. **Green Valley Academy** (`school-2`) — *Standard Blended* (Pune, Maharashtra): Projector classrooms and shared computer laboratories.
3. **Pragati Government Senior Secondary School** (`school-3`) — *Low-Tech Government* (Jaipur, Rajasthan): Printed workbooks, mobile camera OCR scans, community solar lanterns.
4. **Vidya Niketan School** (`school-4`) — *Standard Blended* (Lucknow, Uttar Pradesh): Blended tinkering labs and structured peer learning.
5. **Udaan Learning Government School** (`school-5`) — *Low-Tech Government* (Ranchi, Jharkhand): Physical worksheets, vernacular audio aids, foundational numeracy focus.

---

## 5. End-to-End Stakeholder Demonstration Scenario

Follow this workflow to demonstrate the complete power of LumenEIOS:

1. **Admin Platform Overview** (`/admin/dashboard`):
   - Review multi-school comparative benchmarks.
   - Spot that rural government campuses (Pragati Govt & Udaan) suffer from English Language Understanding (LU) deficits in word problems despite having good conceptual understanding (CU).
2. **Principal Oversight** (`/principal/dashboard`):
   - Switch persona to **Principal**.
   - Notice that Class 8-A has accumulated **16 lost teaching days** due to election duty, weather closures, and health camps.
   - Inspect teacher workloads and reassign faculty.
3. **Teacher Time-Aware Pedagogical Engine** (`/teacher/time-aware`):
   - Switch persona to **Teacher** (Vikram Sengupta).
   - Review the **Pacing Progress Bar**: 16 lost days have turned the calendar buffer negative (-4 days).
   - Click **"Record Lost Teaching Days"** to simulate adding another disruption.
   - Review the **Cross-Curricular Synergy Detection**: Accept the *Rainfall Data Modeling* project (merging Mathematics, Science, and English) to recover 3.5 teaching hours.
   - Click **"Preview Syllabus Compression"**:
     - Inspect the before-and-after schedule.
     - Note that 100% of Core Competencies are strictly protected.
     - Click **"Accept Proposed Plan"**: Recovers 14 days, restores a safe calendar buffer, and records an audit log entry!
4. **Handwritten document upload** (`/upload`):
   - Open **Upload** as a teacher or student and run OCR on a photo or PDF.
   - Sign in as a student to see saved extracts under **History** and class, subjects, and linked parents under **Profile**.
5. **Differentiated Remediation** (`/teacher/remediation`):
   - View personalized assignments. A student weak in LU receives bilingual word problem scaffolding; a student weak in AU receives hands-on measurement tasks.
6. **Student Learning Mission** (`/student/dashboard`):
   - Switch persona to **Student** (Aarav Patel).
   - View "Today's Learning Mission" (Day 104: Mensuration & Volume).
   - Click **"Start Today's Quiz"**, select the correct volume option (6 hours and 40 minutes), and submit to receive instant mastery feedback!
   - Complete and submit assigned homework.
7. **Parent Holistic Card** (`/parent/dashboard`):
   - Switch persona to **Parent** (Meera Patel).
   - View Aarav's progress in reassuring plain language (free of technical jargon).
   - Toggle between children (Aarav and Ananya).
   - Read teacher feedback and actionable suggestions for home learning.
   - Click **"Download Holistic Card"** to generate an official print/PDF export.

---

## 6. Route Directory

- `/login` — Demo Login Portal
- `/admin/dashboard` — Platform Command Center & Governance
- `/admin/schools` — School Network Directory & Onboarding CRUD
- `/admin/users` — User Directory & Role Assignments
- `/admin/academic-config` — Statutory Working Days & Compaction Rules
- `/admin/audit-logs` — Immutable Audit & Security Trail
- `/principal/dashboard` — Campus Executive Dashboard
- `/principal/teachers` — Faculty Section Allocations
- `/principal/curriculum` — Subject Curriculum Progress
- `/principal/reports` — Institutional Compliance Transcripts
- `/teacher/dashboard` — Educator Dashboard & Pacing Radar
- `/teacher/classes` — Student Roster & Classroom Heatmap Matrix
- `/teacher/time-aware` — **Signature Feature**: Time-Aware Pedagogical Engine
- `/teacher/curriculum-180` — 180-Day Daily Micro-Curriculum (VARK & Bloom's)
- `/teacher/assessments-beta` — AI Question Studio Beta
- `/upload` — OCR text extraction for teachers and students
- `/student/history` — Saved OCR extracts for the signed-in student
- `/student/profile` — Student details, class, subjects, and linked parents
- `/teacher/remediation` — Differentiated Homework Manager
- `/student/dashboard` — Student Missions, Practice Lab & Achievements
- `/parent/dashboard` — Family Holistic Card & Plain-Language Growth

---

## 7. Backend Architecture & API

The backend is implemented using **Python FastAPI** and **SQLAlchemy 2.x (Async)** with full support for zero-dependency local SQLite execution and production PostgreSQL with pgvector.

### Backend Tech Stack
- **Framework**: FastAPI (Async)
- **Validation**: Pydantic v2
- **ORM & Database**: SQLAlchemy 2.x Async (`sqlite+aiosqlite` for zero-setup local runs; `postgresql+asyncpg` with pgvector for production)
- **Security & RBAC**: JWT (HS256) + bcrypt password hashing + tenant isolation across 5 schools
- **Testing**: Pytest + pytest-asyncio + HTTPX
- **Storage**: S3 / MinIO abstraction with local fallback
- **OCR Engine**: Qwen2.5-VL server-side extraction preview, simulated provider, and teacher verification workflows

---

## 8. Local Setup & Startup

### Prerequisites
- Node.js (v18+) and npm
- Python 3.12+ (or 3.15)

On Windows, run `run.bat` from the project folder to start the backend/API and frontend. It installs the regular app dependencies if needed. The Qwen model loads on the first OCR request and requires the optional CUDA setup below.

### 8.1 Backend Setup
```bash
# 1. Install backend dependencies
python -m pip install -r backend/requirements.txt

# 2. Run backend server (auto-seeds database on first launch)
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```
- Interactive API Documentation (Swagger): **`http://localhost:8000/api/v1/docs`**
- Alternative ReDoc: **`http://localhost:8000/api/v1/redoc`**
- System Health: **`http://localhost:8000/health`**

#### Optional: Qwen OCR developer mode (CUDA)

The OCR preview runs in the FastAPI backend, not in the browser. The model loads when an OCR request uses Qwen. During development, run the backend on the laptop with its CUDA-capable GPU; production runs the same model in the backend server process.

1. Install a CUDA-enabled PyTorch build compatible with the laptop's GPU and driver using the [PyTorch install selector](https://pytorch.org/get-started/locally/).
2. Install the optional OCR packages:
   ```bash
   python -m pip install -r backend/requirements-ocr.txt
   ```
3. Start the backend as above. The default model is `Qwen/Qwen2.5-VL-3B-Instruct-AWQ`; override `QWEN_VL_MODEL_ID` in `.env` if needed.
4. Click **Teacher** under **Switch Persona**, open **Upload** in the sidebar, upload one or more JPG, PNG, or PDF files, and click **Run OCR**. The optional checkbox waits five seconds before each image/page.

The preview displays extracted text only; it does not grade or publish marks. OCR files are removed from temporary backend storage after each request. If CUDA or model dependencies are unavailable, the endpoint reports an error instead of returning simulated text.

### 8.2 Frontend Setup
```bash
# 1. Install frontend dependencies
npm install

# 2. Start Vite development server
npm run dev
```
Open **`http://localhost:3000`** in your browser.

### 8.3 Run Automated Tests
```bash
python -m pytest backend/tests -v
```
Runs the backend unit and integration tests covering permissions, pacing invariants, OCR extraction, and API endpoints.

### 8.4 PayPal subscriptions

1. In [PayPal Developer Apps & Credentials](https://developer.paypal.com/dashboard/applications/sandbox), select **Sandbox** and open or create a merchant app. In the `apps/lumeneios/.env` file beside `run.bat`, set `PAYPAL_ENV=sandbox` and enter that app's `PAYPAL_CLIENT_ID` and `PAYPAL_CLIENT_SECRET`. Use the PayPal section of `.env.example` if you need to create the file. Keep the secret in the backend environment.
2. From `apps/lumeneios`, run the setup script once to create the sandbox billing plans ($20 USD per school and $5 USD per teacher seat, both monthly).

   ```powershell
   .\.venv\Scripts\python.exe -m backend.scripts.create_paypal_plans
   ```

   If you installed the backend dependencies outside the virtual environment, use `python` instead. Copy the two printed assignments, `PAYPAL_BASE_PLAN_ID` and `PAYPAL_SEAT_PLAN_ID`, into `.env`. Reuse those IDs for this sandbox account.
3. For automatic status updates, add a webhook to the same sandbox app. Use a public HTTPS backend URL ending in `/api/v1/subscriptions/webhook` and copy its webhook ID to `PAYPAL_WEBHOOK_ID`. Subscribe to `BILLING.SUBSCRIPTION.ACTIVATED`, `BILLING.SUBSCRIPTION.SUSPENDED`, `BILLING.SUBSCRIPTION.CANCELLED`, and `BILLING.SUBSCRIPTION.EXPIRED`. Use a public HTTPS tunnel to the local backend if testing webhook delivery from your laptop.
4. Restart the backend from `apps/lumeneios`. If you use Docker Compose, recreate the backend container to pick up the environment changes. Sign in as a principal linked to a school, open **School subscription**, and approve both subscriptions with a sandbox personal buyer account. With the webhook configured, refresh the page and check that both subscriptions show **Active**.

The local checkout redirects use `http://localhost:3000`. Set `PAYPAL_RETURN_URL` and `PAYPAL_CANCEL_URL` to the corresponding frontend URLs when hosting the app. Live payments require a separate live app, live plan IDs, a live webhook, and `PAYPAL_ENV=live`.

---

### 8.5 School document search and Postman

For local development, start Elasticsearch from the app directory:

```powershell
docker compose -f infrastructure/elasticsearch.local.yml up -d
```

Set `ELASTICSEARCH_URL=http://127.0.0.1:9200` in `.env` and restart the backend. This Docker configuration binds to localhost and is for local testing. For hosted deployments use a private, authenticated Elasticsearch endpoint and set `ELASTICSEARCH_API_KEY` to its encoded API key.

Import `postman/lumeneios.postman_collection.json`. Set local values for `email`, `password`, and `role`, then run **Login and save token for role** for a principal, teacher, and student. In **School document search**, attach a searchable policy PDF containing your test topic, upload it as a principal, then publish it and run the teacher's search. The teacher and principal must belong to the same school. Staff can also select **Search school documents** in **Ask LumenEIOS**. The PDF links show the source page. Image-only PDFs need searchable text added first.

The collection checks subscription pricing, role boundaries, and sandbox approval links. Run **Start sandbox checkout for 12 seats** individually on a test school without an open subscription. Approve both links using a PayPal sandbox Personal account. Status changes require a working PayPal webhook. Keep passwords and tokens in local Postman values.

### 8.6 What requires setup on a fresh clone

The source repository does not include machine-specific credentials, model weights, uploaded student work, or a database. After cloning on a new device:

- **Core app and demo accounts:** install Python and Node.js dependencies with `run.bat` (Windows) or the backend/frontend steps above. Demo features use seeded local records.
- **Ask LumenEIOS:** install and start [Ollama](https://ollama.com/download), then run `ollama pull qwen2.5:7b`. Without the model and running Ollama, the assistant returns its unavailable message.
- **AI Question Studio:** the `qwen2.5vl:7b` Ollama model and working internet for first-time model download are required for AI generation and source-page processing.
- **Qwen OCR preview:** install a CUDA-compatible PyTorch build and `backend/requirements-ocr.txt`, provide GPU drivers, and set `HF_TOKEN` when the selected Hugging Face model requires access. This does not work on a CPU-only host.
- **Cited school-document search:** run a private Elasticsearch service, set `ELASTICSEARCH_URL` and (for authenticated hosts) `ELASTICSEARCH_API_KEY`, restart the backend, then have a principal or admin publish searchable PDFs. Until then, staff document search is unavailable.
- **PayPal billing:** provide Sandbox or Live app credentials and matching plan IDs in `.env`. Run the plan setup script once for a new PayPal account. A public HTTPS webhook is needed for automatic subscription status updates. Without these settings, checkout is unavailable.
- **Voice input:** requires a supported browser and microphone permission. Typed chat still works without speech recognition. Browser speech recognition availability and audio handling depend on the browser.
- **Existing school data:** the SQLite database, upload directory, Elasticsearch index, and PayPal configuration live outside Git. Copy or restore them from a secure backup to retain real school data. A new clone starts with its own local database and has no uploaded documents.

Use `docs/vast-ai-deployment.md` and `SET_UP.md` for GPU-hosted setup. Keep `.env`, API secrets, and real student data out of Git.

## 9. Production Docker Compose Deployment

To deploy the entire production stack including PostgreSQL 16 (pgvector), Redis 7, MinIO object storage, and the FastAPI application:

```bash
cd infrastructure
docker-compose up -d --build
```

---

## 10. Technical Documentation Index

Detailed architectural documents are located in the [`docs/`](./docs) directory:
- [System Architecture](./docs/architecture.md)
- [Database Schema & ER Reference](./docs/database-schema.md)
- [Frontend to Backend API Mapping](./docs/frontend-api-mapping.md)
- [Time-Aware Pedagogical Engine & 60/40 Compression](./docs/time-aware-engine.md)
- [Optical Assessment (OCR) & Human Review Pipeline](./docs/ocr-pipeline.md)
- [Model Fine-Tuning & Evaluation Gates](./docs/model-training.md)
- [Security, Permissions & Tenant Isolation](./docs/security.md)
- [Deployment & Operational Guide](./docs/deployment.md)
