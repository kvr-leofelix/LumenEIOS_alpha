# Vast.ai deployment

Use the repository-root [`SET_UP.md`](../SET_UP.md) as the one-run setup for a Vast.ai **Jupyter** instance. It clones the repository and installs the application, CUDA OCR dependencies, Ollama, and both Ollama models. You do not need to run separate `pip install`, `ollama pull`, build, or service-start commands.

## Choose an instance

| Setting | Recommended |
|---|---|
| Image | Vast.ai Jupyter image with Ubuntu, Python, Conda, and Jupyter Server |
| GPU | NVIDIA GPU with at least 16 GB VRAM |
| Driver | NVIDIA driver 570 or newer for the CUDA 12.8 PyTorch wheel |
| Disk | At least 100 GB for dependencies, models, and local application data |

The setup script expects the Vast Jupyter paths `/workspace`, `/opt/sys-venv/bin/jupyter`, and `supervisor`. It is not the setup for a plain Ubuntu instance without Jupyter.

## Install and start

1. Open the instance's Jupyter terminal.
2. Open [`SET_UP.md`](../SET_UP.md), copy its full `bash` code block, and paste it into the terminal.
3. Wait for setup to finish. The first run downloads Python packages and three model weights (two Ollama models and the Hugging Face OCR model), so it can take a while.
4. Open the printed Jupyter proxy path: `/proxy/absolute/3001/`.

The script clones the `main` branch into `/workspace/LumenEIOS_alpha`, installs CUDA PyTorch when the venv does not already have a working CUDA build, installs `backend/requirements-ocr.txt`, installs Ollama when missing, and pulls `qwen2.5vl:7b` and `qwen2.5:7b`. It creates `.env` on first run and supervises the API and frontend.

## Optional services and credentials

School-library search stays disabled if `ELASTICSEARCH_URL` and `ELASTICSEARCH_API_KEY` are empty. For PayPal subscriptions, add the sandbox or live `PAYPAL_*` settings to `/workspace/LumenEIOS_alpha/.env`. For webhook updates, also set `PAYPAL_WEBHOOK_ID` and register the public HTTPS route `/api/v1/subscriptions/webhook` in the matching PayPal app. After editing `.env`, restart the API with:

```bash
supervisorctl restart lumeneios-api
```

Keep secrets private and do not expose Ollama's port `11434` or Elasticsearch's port `9200` publicly.

## Storage and limitations

The database, uploads, model downloads, and Elasticsearch data live on the instance disk. They are lost when the instance is destroyed unless you use persistent storage or back them up. The initializer has not been run on a real Vast instance; confirm GPU model loading and persistent storage before using real student data. Put the public app behind HTTPS before handling student data.
