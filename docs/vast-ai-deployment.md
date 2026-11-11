# Deploying LumenEIOS on a Vast.ai GPU instance

This runs the whole app on one rented GPU machine:
- the FastAPI backend, port 8000
- Qwen2.5-VL-3B OCR, loaded inside the backend
- Ollama with `qwen2.5vl:7b` for AI Question Studio Beta and `qwen2.5:7b` for Ask LumenEIOS
- Elasticsearch for optional cited school-library search
- the built frontend, port 3000

Commands run from the cloned `LumenEIOS_alpha` repository root unless noted.

> **Status:**
> - **Checked locally:** requirement files resolve for Linux x86_64 (Python 3.11 and 3.12), the backend test suite passes on a clean install, and the frontend builds.
> - **Not yet run on a real Vast.ai machine:** verify the instance template, storage persistence, and GPU model load before putting student data on it.

## 1. Rent the instance

| Setting | Choose |
|---|---|
| Template | A PyTorch / CUDA 12.8 image, e.g. `pytorch/pytorch:2.11.0-cuda12.8-cudnn9-runtime`, or any Ubuntu + CUDA 12.8 image |
| GPU | 16 GB VRAM or more (RTX 4080/4090, A4000, L4). OCR 3B uses about 5 GB; Ollama 7B needs about 6–8 GB more |
| Driver | NVIDIA driver 570 or newer (shown on the offer; needed for CUDA 12.8) |
| Disk | 100 GB or more (PyTorch, OCR weights, both Ollama models, Elasticsearch index and persistent student data) |
| Ports | Add `-p 8000:8000 -p 3000:3000` to the Docker options |

After it starts, open the instance's **IP & ports** panel. Vast maps 8000 and 3000 to random public ports, for example `203.0.113.7:41234 -> 8000`. Below, `PUBLIC_IP`, `API_PORT` and `WEB_PORT` mean those public values.

## 2. Get the code

Use a GitHub token or deploy key with access to this repository:

```bash
git clone --branch main https://github.com/kvr-leofelix/LumenEIOS_alpha.git
cd LumenEIOS_alpha
nvidia-smi            # must list the GPU and a driver >= 570
```

## 3. Install the backend

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install --upgrade pip
pip install -r backend/requirements.txt
pip install torch==2.11.0 --index-url https://download.pytorch.org/whl/cu128
pip install -r backend/requirements-ocr.txt
python -c "import torch; print(torch.__version__, torch.cuda.is_available())"   # expect 2.11.0+cu128 True
```

Install the OCR requirements **after** torch. The `triton==3.6.0` pin matches torch 2.11.0.

## 4. Install Ollama (for Question Studio and Ask LumenEIOS)

```bash
curl -fsSL https://ollama.com/install.sh | sh
nohup ollama serve > ollama.log 2>&1 &
ollama pull qwen2.5vl:7b
ollama pull qwen2.5:7b
```

Ollama stays on `127.0.0.1:11434`. Don't expose that port publicly.

## 5. Create `.env` — required before going public

Create `.env` in the repository root. The backend reads it from the folder you start it in.

```bash
APP_ENV=production
DEBUG=false
DEMO_MODE=false
SECRET_KEY=<paste output of: python -c "import secrets; print(secrets.token_urlsafe(48))">
BACKEND_CORS_ORIGINS=["http://PUBLIC_IP:WEB_PORT"]
QWEN_VL_MODEL_ID=Qwen/Qwen2.5-VL-3B-Instruct-AWQ
QWEN_QUESTION_STUDIO_MODEL_ID=qwen2.5vl:7b
OLLAMA_BASE_URL=http://127.0.0.1:11434
ASSISTANT_MODEL=qwen2.5:7b
ELASTICSEARCH_URL=http://127.0.0.1:9200
ELASTICSEARCH_API_KEY=
HF_TOKEN=
```

The backend needs an Elasticsearch service on localhost for school-document search. On a Vast template with Docker Compose installed, start the included single-node service:

```bash
docker compose -f infrastructure/elasticsearch.local.yml up -d
curl http://127.0.0.1:9200/_cluster/health
```

The included Elasticsearch service binds to localhost and disables authentication for local development. For a public deployment, keep Elasticsearch private, enable authentication and TLS, and set its private URL and encoded API key in `.env`. Never expose port 9200 in Vast's public port list.

PayPal sandbox subscriptions also need these backend settings in `.env`: `PAYPAL_ENV`, `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET`, `PAYPAL_BASE_PLAN_ID`, and `PAYPAL_SEAT_PLAN_ID`. Optional webhook status updates require `PAYPAL_WEBHOOK_ID` and a public HTTPS webhook URL ending in `/api/v1/subscriptions/webhook`. Register the URL with the same PayPal app used for the credentials. Update `PAYPAL_RETURN_URL` and `PAYPAL_CANCEL_URL` with the public HTTPS frontend routes.

Why each line matters:

| Setting | If left at the code default |
|---|---|
| `APP_ENV=production` | Disables the team root login even when a development password is configured |
| `SECRET_KEY` | The default key is in the public code, so anyone could forge login tokens |
| `DEMO_MODE=false` | `true` lets requests with no login act as admin |
| `DEBUG=false` | Debug output can leak internals |
| `BACKEND_CORS_ORIGINS` | Default allows only localhost, so the browser blocks the deployed frontend. It must be a JSON list |
| `ELASTICSEARCH_URL` and `ELASTICSEARCH_API_KEY` | Enables protected school-document retrieval. Use a private HTTPS endpoint and encoded API key for deployment |

Also, `infrastructure/docker-compose.yml` sets `DEMO_MODE=true` and the public default secrets. Don't use it as-is on a public machine.

## 6. Start the backend

```bash
source .venv/bin/activate
nohup uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 > backend.log 2>&1 &
curl http://127.0.0.1:8000/health
```

The database defaults to SQLite (`lumeneios.db` in this folder) and uploads to `storage_uploads/`. The Elasticsearch index is also stored on the instance disk. All three are lost when the instance is destroyed unless the instance uses persistent storage. Back them up, or set `DATABASE_URL` to an external PostgreSQL and use durable private storage for uploads and Elasticsearch.

## 7. Build and serve the frontend

```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && apt-get install -y nodejs
npm ci
VITE_API_URL=http://PUBLIC_IP:API_PORT/api/v1 VITE_DEMO_MODE=false npm run build
nohup npx vite preview --host 0.0.0.0 --port 3000 > frontend.log 2>&1 &
```

`VITE_API_URL` is baked in at build time. Rebuild if the public IP or port changes, for example after a restart.

Open `http://PUBLIC_IP:WEB_PORT`.

## 8. Check the GPU pipeline

```bash
RUN_QWEN_GPU_TEST=1 python -m pytest backend/tests/test_qwen_gpu_smoke.py -q   # loads the real 3B model
tail -f backend.log
```

The first OCR request downloads about 3 GB of Qwen weights from Hugging Face. Expect a long wait, then roughly 4 s per page.

## Known limits

- **HTTP only, no TLS.** Put it behind a reverse proxy with HTTPS before real student data goes on it.
- **One page at a time.** OCR runs one page at a time on the GPU, so large batches are slow (see `ocr-gpu-deployment.md`).
- **Students can call OCR preview.** `/ocr/extract-preview` now allows the `student` role, so any student account can use GPU time.
