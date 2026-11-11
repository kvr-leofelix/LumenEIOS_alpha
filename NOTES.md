# OCR Integration Notes

Last updated: 2026-11-03. None of these changes are committed.

## Current status

OCR works from the website with the default model, `Qwen/Qwen2.5-VL-3B-Instruct-AWQ`,
on the RTX 5060. Only the Scan Review preview uses the real model. It has only been
tested on typed text, **not on handwriting**.

## What was changed

### Bugs fixed

| Problem | Before | Now | File |
|---|---|---|---|
| The model's final layer (`lm_head`) was converted to AWQ with random weights | Every OCR request returned 500 with a Triton `CompilationError` | OCR works | `backend/app/services/ocr_service.py` |
| PDF over 25 pages | 500 (`NameError`); site showed "Failed to fetch" | 400 with a clear message | `backend/app/services/ocr_service.py` |
| Corrupt PDF | 500; site showed "Failed to fetch" | 400 with a clear message | `backend/app/services/ocr_service.py` |
| Password-protected PDF | Not handled | 400 with a clear message (covered by code only, not tested) | `backend/app/services/ocr_service.py` |
| Truncated image | 500 (found by reading the code) | 400 with a clear message | `backend/app/services/ocr_service.py` |
| `.gif` and similar file types | 400 | 415, the same as other unsupported types | `backend/app/api/v1/ocr.py` |
| Files sent as `image/jpg` | 415 (found by reading the code) | Accepted | `backend/app/api/v1/ocr.py` |
| Unexpected OCR errors | Plain 500 with no CORS header; site showed "Failed to fetch" | JSON 500 naming the file | `backend/app/api/v1/ocr.py` |
| `POST /ocr/process` with `provider=qwen` | 500 | 400 pointing to `/ocr/extract-preview` | `backend/app/api/v1/ocr.py` |

The `lm_head` bug: this checkpoint stores no weights for that layer because it is tied to
`embed_tokens`. Transformers still converted it and filled it with random values. Changing
Triton versions would not have helped.

### Dependencies

- `backend/requirements-ocr.txt` now pins the verified versions, because AutoAWQ is
  deprecated and unpinned upgrades could break it.
- Removed `gptqmodel` from the requirements and uninstalled it from `.venv`. It required
  `torch>=2.14.1`, nothing in this path uses it, and `pip check` is now clean. The real
  model test passed with it blocked.
- Replaced the deprecated `fitz` import with `pymupdf`.
- Removed the unused `ACTIVE_OCR_PROVIDER` setting from `config.py`, `.env.example`, and
  `docs/deployment.md`. The line is still in your local `.env`, where it is ignored.

### Website

- Renamed the sidebar item from "Auto-Grade & OCR" (badge "Batch") to "Scan Review" (badge
  "OCR"), because the page does not grade anything.
- Results now show the provider, for example `qwen2.5-vl · Qwen/... · 1 file(s) processed`.

### Tests

- **New:** `backend/tests/test_qwen_ocr_preview.py` has 13 tests covering the fixes above.
  The `lm_head` test fails when that fix is removed.
- **New:** `backend/tests/test_qwen_gpu_smoke.py` runs the real model. It only runs with
  `RUN_QWEN_GPU_TEST=1`.
- **Changed:** `backend/tests/conftest.py` now uses a temporary database and upload folder.
  Tests used to write to the tracked `lumeneios.db` and `storage_uploads/`.

### Docs and repository

- Corrected `INSTRUCTIONS.md`: navigation, login, access rules, error table, the Triton
  advice, `gptqmodel`, timings, Docker, and verification steps.
- Updated the navigation text in `README.md` and `open.md`.
- `.gitignore` now covers `.env`, `.venv/`, `__pycache__/`, `*.pyc`, `.pytest_cache/`, and
  new files in `storage_uploads/`.

## Verification results

| Check | Result |
|---|---|
| Backend tests | 46 passed, 1 skipped (the GPU test) |
| Real model test on the GPU | Passed |
| TypeScript check and frontend build | Passed (built to a temporary folder) |
| Headless Chromium: Teacher, Scan Review, PNG, and JPG + 2-page PDF together | Correct text shown |
| Headless Chromium: PDF over 25 pages, corrupt PDF, corrupt PNG | Clear error messages |
| Headless Chromium: student account | Blocked with 403 |
| Database after OCR | Only `audit_events` changed, from test logins |
| Temporary upload cleanup | No files left behind |
| Clean virtual environment, `pip install --dry-run` | Requirements resolve |
| `DEMO_MODE=false` | Requests with no token get 401 |

Measured on the RTX 5060: about 30 seconds for the first request, about 4 seconds per image
after that, and about 5 GB of GPU memory in use.

### Not tested

- **Handwriting**, which is the main use case. All test files were typed text.
- **A browser on Windows.** Everything ran inside WSL.
- **A full install from scratch.** The clean environment was a dry run only.
- **Any model other than the default.** The cached 7B AWQ copy is also missing its first
  weights file, so using it would need a download.

## Remaining problems

### Need your decision

1. **Batch grading still uses fake OCR.** `backend/app/services/batch_grading_service.py:316`
   is hard-coded to the simulated provider. Qwen returns plain text with no answer regions,
   confidence scores, or suggested marks, so connecting it needs new design work, not a small
   fix.
2. **Demo login is not secure, and this appears to be intentional.** Changing it would remove
   the prototype's instant access, so it was left as is. It must be replaced before real use:
   - A new browser opens as Admin with no login page (`src/context/AuthContext.tsx`).
   - The login form checks only the email, not the password.
   - Anyone can switch persona from the top bar.
   - `DEMO_MODE` defaults to `true`, which treats requests with no token as admin and accepts
     `demo123` for every account.
   - `verify_password` in `backend/app/core/security.py` also accepts the stored password hash
     as a password.
3. **Runtime files are tracked in Git:** `lumeneios.db`, `dist/`, 33 files in
   `storage_uploads/`, and 53 `__pycache__` files. `lumeneios.db` shows as modified whenever
   the app runs. These should probably be removed from tracking, which would be a separate
   commit.
4. **18 uploads are now hidden from `git status`.** These untracked files in
   `storage_uploads/` probably came from earlier test runs. They were not opened or deleted,
   and they could contain student work, so please check them and delete them if unneeded.
5. **AutoAWQ is deprecated.** It was last tested with Torch 2.6 and this setup uses 2.11. It
   works today, but a future upgrade may force a move to llm-compressor or a non-AWQ model.

### OCR limitations

- One bad file fails the whole request, and results for the other files are lost. Files are
  also not validated before OCR starts, so a bad last file wastes the earlier work.
- There is no progress display, cancel button, or job queue. Requests run one at a time, and
  the largest allowed upload (50 files of 25 pages) could run for more than an hour.
- Very long pages may be cut off silently, because output stops at 2048 tokens.
- OCR quality has no confidence score, so a teacher must compare each result with the scan.

### Other issues (found by reading the code, not tested)

- `trocr` and `paddleocr` return simulated data under real-sounding names, and an unknown
  provider name silently falls back to simulated data.
- Tokens expire after 120 minutes with no refresh or redirect. The page shows an error until
  you log out or click a persona again.
- Login runs in the background and failures are ignored. If the backend is down during a
  persona switch, the old token stays in use, so requests can run as the previous user.
- Students can open the Scan Review page, although the backend blocks their requests.
- Two selected files with the same name produce a duplicate React key.
- Some `documents` rows in `lumeneios.db` have Windows-style paths, such as
  `./storage_uploads\doc-....jpg`, which will not resolve on Linux.
- `README.md` around line 88 and `docs/frontend-api-mapping.md` section 6 may still describe
  the older scan workflow. They were not reviewed.

### Minor

- The committed `dist/` was not rebuilt, so it lacks the website changes above. The dev server
  is not affected; rebuild it before deploying from `dist/`.
- The Docker image cannot run OCR. It has no OCR packages or GPU setup.
- Harmless warnings remain: `pytest-asyncio` loop scope, `passlib` and `bcrypt` version,
  `torch.jit` on Python 3.14, Vite chunk size, and unused sampling settings at inference.
