# Qwen OCR Webpage Integration Instructions

This guide explains how to enable and use the Qwen OCR model from the LumenEIOS
web application. Qwen runs in the FastAPI backend, not in the browser. The
webpage uploads images or PDFs, the backend performs OCR on its CUDA GPU, and
the webpage displays the returned transcription.

## 1. Understand the integration

The integration uses these components:

- **Frontend page:** **Scan Review** in the sidebar, route `/teacher/scan-review`
  (the page is titled "OCR Extraction Preview")
- **Frontend client:** `src/lib/apiClient.ts`
- **Backend endpoint:** `POST /api/v1/ocr/extract-preview`
- **Backend provider:** `QwenVisionOCRProvider` in
  `backend/app/services/ocr_service.py`
- **Default model:** `Qwen/Qwen2.5-VL-3B-Instruct-AWQ`
- **Supported files:** JPG, JPEG, PNG, and PDF
- **Per-file limit:** 15 MB
- **Batch limit:** 50 files
- **PDF limit:** 25 pages

The preview endpoint extracts text only. It does not grade work, save marks,
update student competencies, or publish assessment results. OCR files are
deleted from temporary backend storage after each request. Teacher verification
must remain a separate, explicit step.

Only this preview uses the real model. Batch grading still uses simulated OCR,
and the `trocr` and `paddleocr` providers also return simulated data. See
`NOTES.md`.

## 2. Prepare the runtime

Use a machine with:

1. Python 3.12 or newer.
2. An NVIDIA GPU with a working CUDA-enabled PyTorch installation.
3. An NVIDIA driver compatible with the selected PyTorch CUDA build.
4. Node.js 18 or newer and npm.
5. Enough disk space for the Python packages and the downloaded model weights.
6. About 5 GB of free GPU memory while the model is loaded (measured on an
   RTX 5060 with 8 GB).

Run the backend directly on the host for OCR. The Docker image in
`infrastructure/` does not install `backend/requirements-ocr.txt` or set up GPU
access, so OCR requests in that image return 503.

Qwen will not run on a CPU in this integration. The backend returns an explicit
503 error when CUDA or the required Qwen dependencies are unavailable; it does
not silently fall back to simulated OCR.

### 2.1 Additional requirements for RTX 5060 on WSL2

The RTX 5060 is a Blackwell GPU. Use a recent NVIDIA Windows driver and a
PyTorch release that includes Blackwell (`sm_120`) support. PyTorch 2.7 or
newer with a CUDA 12.8 wheel is the practical minimum for this GPU.

Install the NVIDIA driver on **Windows**, not inside WSL. WSL2 exposes the
Windows driver to Linux; installing a separate Linux NVIDIA driver in WSL can
break the CUDA integration. In PowerShell, update WSL if necessary:

```powershell
wsl --update
wsl --shutdown
```

In the WSL terminal, verify that the GPU is visible before installing Python
packages:

```bash
nvidia-smi
```

The command should show the RTX 5060 and a driver version. If it fails, fix
the Windows driver/WSL setup first; installing more Python packages will not
resolve that issue.

## 3. Install the project dependencies

Open a terminal at the repository root.

### 3.1 Install backend dependencies

Create and activate a virtual environment if one is not already active. On
some WSL distributions the executable is named `python3` rather than
`python`:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install the base backend packages:

```bash
python -m pip install -r backend/requirements.txt
```

Install a CUDA-enabled PyTorch build that matches the host GPU and driver.
For a current PyTorch CUDA 12.8 wheel, the command is typically:

```bash
python -m pip install --upgrade torch torchvision \
  --index-url https://download.pytorch.org/whl/cu128
```

If the official PyTorch selector recommends a newer command, use that command
instead. Do this before installing the Qwen-specific packages.

Verify PyTorch from inside WSL:

```bash
python - <<'PY'
import torch

print("PyTorch:", torch.__version__)
print("CUDA wheel:", torch.version.cuda)
print("CUDA available:", torch.cuda.is_available())
if torch.cuda.is_available():
    print("GPU:", torch.cuda.get_device_name(0))
    print("Compute capability:", torch.cuda.get_device_capability(0))
PY
```

For an RTX 5060, `CUDA available` must be `True` and the compute capability
should be `(12, 0)`. Do not continue to Qwen setup until this check succeeds.

Then install the Qwen OCR dependencies:

```bash
python -m pip install -r backend/requirements-ocr.txt
```

The OCR requirements install pinned versions of Transformers, Accelerate,
AutoAWQ, Triton, Qwen vision utilities, and PyMuPDF. They are pinned because
AutoAWQ is deprecated and was last tested with Transformers 4.51.3. `Pillow` is
already included in the base backend requirements and is used to decode images.

Do not install `gptqmodel`. This model runs through AutoAWQ, and `gptqmodel`
requires a newer PyTorch than the verified setup uses.

### 3.2 Install frontend dependencies

In a terminal at the repository root:

```bash
npm install
```

## 4. Configure the backend

Create a root `.env` file from `.env.example`:

```bash
cp .env.example .env
```

Set the Qwen model value:

```dotenv
QWEN_VL_MODEL_ID=Qwen/Qwen2.5-VL-3B-Instruct-AWQ
```

The preview endpoint always uses the Qwen provider, so no other OCR setting is
needed.

`QWEN_VL_MODEL_ID` may be changed to another Qwen2.5-VL model available to the
Transformers loader, but only the default model has been verified. The model is
loaded lazily on the first OCR request and is cached in the running FastAPI
process.

For local browser access, keep the frontend origin in
`BACKEND_CORS_ORIGINS`:

```dotenv
BACKEND_CORS_ORIGINS=["http://localhost:3000","http://127.0.0.1:3000"]
```

The frontend API client defaults to:

```text
http://localhost:8000/api/v1
```

To use another backend address, set `VITE_API_URL` before starting Vite:

```bash
VITE_API_URL=http://localhost:8000/api/v1 npm run dev
```

Use a strong, private `SECRET_KEY` outside demo development. Do not commit
`.env`, model credentials, or access tokens.

## 5. Start the backend

From the repository root, with the virtual environment active:

```bash
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

Confirm that the service is reachable:

```bash
curl http://localhost:8000/health
```

The first OCR request downloads the configured model if it is not already
cached, which can take several minutes and requires network access to the model
repository. With the weights cached, the first request takes about 30 seconds.
Later requests reuse the loaded model and take about 4 seconds per image.

`--reload` restarts the server when a backend Python file changes, which unloads
the model. The next OCR request then loads it again.

Useful backend URLs:

- Health: `http://localhost:8000/health`
- Swagger: `http://localhost:8000/api/v1/docs`
- ReDoc: `http://localhost:8000/api/v1/redoc`

## 6. Start the webpage

In a second terminal at the repository root:

```bash
npm run dev
```

The Vite configuration serves the webpage at:

```text
http://localhost:3000
```

Keep both the FastAPI and Vite processes running while using OCR.

## 7. Use Qwen OCR from the webpage

1. Open `http://localhost:3000`.
2. Choose an account with the `admin`, `principal`, or `teacher` role. A new
   browser opens as Admin without showing a login page, which can already use
   OCR. To test as a teacher, click **Teacher** under **Switch Persona** in the
   top bar.
3. Click **Scan Review** in the sidebar, or navigate directly to
   `/teacher/scan-review`.
4. Drop answer sheets into the upload area or click it to browse.
5. Select one or more `.pdf`, `.jpg`, `.jpeg`, or `.png` files.
6. Confirm that every file is no larger than 15 MB and that no more than 50
   files are selected.
7. Optionally select **Wait 5 seconds before processing each image/page**.
   This passes a five-second buffer to the backend before each Qwen inference.
8. Click **Run OCR**.
9. Wait for the backend to load Qwen (on the first request) and process the
   files.
10. Review the extracted text in the **Extracted text** panels. PDF results
    include the number of pages processed.

The model prompt asks Qwen to transcribe visible text and formulas in the
original language, use LaTeX for mathematical expressions, and write
`[unclear]` rather than guessing. Always compare the transcription with the
original scan before using it.

## 8. API request and response

The frontend creates a `FormData` request with:

- `files`: one or more uploaded files
- `wait_before_each_image`: `true` or `false`

The request is sent to:

```text
POST /api/v1/ocr/extract-preview
```

Access rules:

- A token, if sent, must be valid and belong to an `admin`, `principal`, or
  `teacher`.
- With `DEMO_MODE=true`, the default, a request with no token runs as admin. Set
  `DEMO_MODE=false` to require a token.
- The webpage sends `X-School-Id`, but this endpoint does not use it.

The successful response has this shape:

```json
{
  "provider": "qwen2.5-vl",
  "model_version": "Qwen/Qwen2.5-VL-3B-Instruct-AWQ",
  "results": [
    {
      "file_name": "answer-sheet.png",
      "extracted_text": "Transcribed text...",
      "pages_processed": 1
    }
  ]
}
```

For manual API testing, first obtain a token through the login endpoint, then
send the token with the upload:

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"teacher@lumeneios.demo","password":"demo123"}'

curl -X POST http://localhost:8000/api/v1/ocr/extract-preview \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -F "wait_before_each_image=false" \
  -F "files=@/absolute/path/to/answer-sheet.png"
```

## 9. Error handling

The webpage displays backend errors in its alert area. Common responses are:

| Status | Meaning | Action |
| --- | --- | --- |
| 400 | Unreadable image or PDF, password-protected or empty PDF, PDF over 25 pages, empty file, or file over 15 MB | Correct the upload and retry |
| 401 | Invalid or expired token (tokens last 120 minutes) | Log out and back in, or click your persona again |
| 403 | Role is not allowed, such as a student | Use an `admin`, `principal`, or `teacher` account |
| 415 | File type is not JPG, PNG, or PDF | Convert the file to a supported format |
| 422 | API request with no `files` field | Send at least one file |
| 500 | OCR failed unexpectedly | Check the FastAPI logs and GPU memory |
| 503 | Qwen dependencies, CUDA, or model loading unavailable | Verify the CUDA PyTorch install and `backend/requirements-ocr.txt` |

If the browser reports a network error, verify that FastAPI is running on port
8000 and that `VITE_API_URL` points to the correct `/api/v1` URL. If the
browser reports a CORS error, add the exact webpage origin to
`BACKEND_CORS_ORIGINS` and restart FastAPI.

One bad file fails the whole request, and results for the other files in that
request are not returned. Remove the file named in the error and run the
request again.

If the endpoint returns 500 and the backend log contains
`triton.compiler.errors.CompilationError` with `invalid operands of type
triton.language.float16`, the model's `lm_head` layer was converted to AWQ. The
checkpoint has no AWQ weights for that layer, so it was filled with random
values. Make sure `_load_model` in `backend/app/services/ocr_service.py` still
adds `lm_head` to `modules_to_not_convert`. Changing Triton versions does not
fix this.

## 10. Verify the integration

Run the backend tests. They use a temporary database and upload folder, and they
replace the model with a stub:

```bash
python -m pytest backend/tests -v
```

Run the real model on the GPU. Stop FastAPI first if the GPU does not have enough
free memory for a second copy of the model:

```bash
RUN_QWEN_GPU_TEST=1 python -m pytest backend/tests/test_qwen_gpu_smoke.py -v
```

Build the frontend into a temporary folder, because `dist/` is tracked in Git:

```bash
npx tsc && npx vite build --outDir /tmp/lumeneios-dist --emptyOutDir
```

Then perform one manual smoke test with a small, readable image:

1. Click **Teacher** under **Switch Persona**.
2. Upload one PNG from **Scan Review**.
3. Click **Run OCR**.
4. Confirm the line under **Extracted text** starts with `qwen2.5-vl`.
5. Confirm extracted text appears in the result panel.
6. Confirm no marks or competency values are changed by the preview.

Also test a real handwritten answer sheet, because printed text is much easier
for the model to read.

## 11. Production considerations

1. Run Qwen on the backend host with a supported NVIDIA GPU; never expose
   model credentials or GPU services directly to the browser.
2. Restrict `BACKEND_CORS_ORIGINS` to the deployed webpage origins.
3. Set `DEMO_MODE=false`, and replace demo credentials and the default secret
   key. The webpage's demo login and persona switcher must also be replaced; see
   `NOTES.md`.
4. Put FastAPI behind HTTPS and an authenticated reverse proxy.
5. Monitor GPU memory, request duration, model-load time, and inference errors.
6. Keep the 15 MB, 50-file, and 25-page limits unless the backend has been
   capacity-tested with different values.
7. Treat OCR output as provisional. An authorized educator must verify content
   before any separate grading or competency workflow is used.
