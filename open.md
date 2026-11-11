# Open and run LumenEIOS

## Open the project

Open the project folder in VS Code: **File → Open Folder** → select this repository. Or, from PowerShell in the project folder, run:

```powershell
code .
```

## Start the app

Install Node.js 18+ and Python 3.12+. For Qwen OCR, use the CUDA-capable laptop and install an NVIDIA driver supported by the installed CUDA-enabled PyTorch build. Open a VS Code terminal in the project folder.

Start the frontend:

```powershell
npm install
npm run dev
```

Open the URL printed in the terminal (usually `http://localhost:3000`).

To run the API as well, open a second terminal in the project folder:

```powershell
python -m pip install -r backend\requirements.txt
```

### Optional: enable Qwen OCR on the GPU laptop

Install the CUDA-enabled PyTorch build that matches the laptop's NVIDIA driver using the [PyTorch install selector](https://pytorch.org/get-started/locally/), then run:

```powershell
python -m pip install -r backend\requirements-ocr.txt
python -c "import torch; print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CUDA GPU not detected')"
```

Proceed only if the check reports `True` and prints the NVIDIA GPU name. Start the backend from the project root:

```powershell
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

In a separate terminal, start the frontend with `npm run dev`, open the printed URL, click **Teacher** under **Switch Persona**, and open **Scan Review** in the sidebar. Upload one or more JPG, PNG, or PDF files and select **Run OCR**. The first run downloads the Qwen model and may take a while. Extracted text appears below the upload area. OCR preview does not grade or publish marks.

If CUDA is not detected, or model loading fails, check the displayed backend error and install the matching CUDA PyTorch build; do not install CPU-only PyTorch for this test. More details: [README.md](README.md#optional-qwen-ocr-developer-mode-cuda).

API docs: `http://localhost:8000/api/v1/docs`

For the demo login accounts, see [README.md](README.md#3-demo-credentials--personas).
