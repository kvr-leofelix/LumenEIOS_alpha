# Vast.ai one-run setup

Paste the Bash block below into a Vast.ai Jupyter terminal. It clones the app, installs the GPU dependencies and downloads the shared Qwen model, and starts the web app.

```bash
set -euo pipefail

repo=/workspace/LumenEIOS_alpha
app=$repo
node_env=/workspace/.lumeneios-node
jupyter=/opt/sys-venv/bin/jupyter
repo_url=https://github.com/kvr-leofelix/LumenEIOS_alpha.git
branch=main  # Always deploy the main branch.

if [ ! -d "$repo/.git" ]; then
  git clone --branch "$branch" --single-branch "$repo_url" "$repo"
else
  # Re-run on an existing instance: move to the latest main, even if it was cloned from another branch.
  # Undo this script's own basename edit (reapplied below); .env, the database and uploads are untracked and kept.
  git -C "$repo" checkout -- src/main.tsx
  git -C "$repo" remote set-url origin "$repo_url"
  git -C "$repo" remote set-branches origin "$branch"
  git -C "$repo" fetch origin "$branch"
  git -C "$repo" checkout -B "$branch" "origin/$branch"
fi
git -C "$repo" log -1 --format='Deploying %h (%s) from '"$branch"
cd "$app"

if [ ! -x "$node_env/bin/node" ]; then
  (
    tmp=$(mktemp -d)
    trap 'rm -rf -- "$tmp"' EXIT
    cd "$tmp"
    release=https://nodejs.org/dist/latest-v22.x
    curl -fsSL "$release/SHASUMS256.txt" | awk '$2 ~ /-linux-x64\.tar\.gz$/ { print }' > node.sha256
    read -r checksum archive < node.sha256
    curl -fsSL "$release/$archive" -o "$archive"
    sha256sum -c node.sha256
    mkdir -p "$node_env"
    tar -xzf "$archive" --strip-components=1 -C "$node_env"
  )
fi
export PATH="$node_env/bin:$PATH"

if [ ! -x .venv/bin/pip ]; then
  if ! python3 -m venv .venv; then
    python_minor=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    apt-get update
    apt-get install -y "python${python_minor}-venv"
    python3 -m venv .venv
  fi
fi
.venv/bin/python -m pip install -r backend/requirements.txt

# Install the pinned CUDA build only when this environment does not already have GPU PyTorch.
nvidia-smi >/dev/null
if ! .venv/bin/python -c 'import torch,sys; sys.exit(0 if torch.cuda.is_available() else 1)' 2>/dev/null; then
  .venv/bin/python -m pip install torch==2.11.0 --index-url https://download.pytorch.org/whl/cu128
fi
.venv/bin/python -m pip install -r backend/requirements-ocr.txt
.venv/bin/python -c 'import torch; assert torch.cuda.is_available(), "CUDA PyTorch is required"; print("GPU ready:", torch.cuda.get_device_name(0))'
.venv/bin/python -c 'from huggingface_hub import snapshot_download; snapshot_download("Qwen/Qwen2.5-VL-3B-Instruct-AWQ")'

if [ ! -e .env ]; then
  secret=$(.venv/bin/python -c 'import secrets; print(secrets.token_urlsafe(48))')
  (umask 077; cat > .env <<EOF
APP_ENV=production
DEBUG=false
DEMO_MODE=false
DEMO_ROOT_PASSWORD=
SECRET_KEY=$secret
QWEN_VL_MODEL_ID=Qwen/Qwen2.5-VL-3B-Instruct-AWQ
PAYPAL_ENV=${PAYPAL_ENV:-sandbox}
PAYPAL_CLIENT_ID=${PAYPAL_CLIENT_ID:-}
PAYPAL_CLIENT_SECRET=${PAYPAL_CLIENT_SECRET:-}
PAYPAL_WEBHOOK_ID=${PAYPAL_WEBHOOK_ID:-}
PAYPAL_BASE_PLAN_ID=${PAYPAL_BASE_PLAN_ID:-}
PAYPAL_SEAT_PLAN_ID=${PAYPAL_SEAT_PLAN_ID:-}
PAYPAL_RETURN_URL=${PAYPAL_RETURN_URL:-}
PAYPAL_CANCEL_URL=${PAYPAL_CANCEL_URL:-}
EOF
  )
  unset secret
fi

# Set the PAYPAL_* environment variables before running for sandbox checkout.

sed -i 's|<BrowserRouter>|<BrowserRouter basename="/proxy/absolute/3001">|' src/main.tsx
npm ci
VITE_API_URL=/proxy/8000/api/v1 VITE_DEMO_MODE=false \
  npm run build -- --base=/proxy/absolute/3001/

# Supervisor brings the app back after a Vast reboot.
cat > /etc/supervisor/conf.d/lumeneios.conf <<EOF
[program:lumeneios-api]
directory=$app
command=$app/.venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=$app/backend.log

[program:lumeneios-web]
directory=$app
command=$node_env/bin/node $app/node_modules/vite/bin/vite.js preview --host 127.0.0.1 --port 3001 --strictPort --base=/proxy/absolute/3001/
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=$app/frontend.log
EOF

supervisorctl reread
supervisorctl update
supervisorctl restart lumeneios-api lumeneios-web

jupyter_python=$(sed -n '1s/^#!//p' "$jupyter")
test -x "$jupyter_python"
.venv/bin/python -m pip --python "$jupyter_python" install jupyter-server-proxy
"$jupyter" server extension enable --sys-prefix jupyter_server_proxy

curl -fsS --retry 10 --retry-connrefused --retry-delay 1 http://127.0.0.1:8000/health
printf '\n'
curl -fsS -o /dev/null -w 'Frontend HTTP %{http_code}\n' \
  http://127.0.0.1:3001/proxy/absolute/3001/
printf '\nSetup complete. Open /proxy/absolute/3001/ on your Jupyter address.\n'
```
