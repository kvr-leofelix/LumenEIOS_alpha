# Optical Assessment (OCR) Pipeline & Human Review

## 1. Overview & Non-Negotiable Invariants

The LumenEIOS Optical Assessment Pipeline transcribes handwritten and printed student test sheets. The Qwen preview workflow returns extracted text for inspection and does not grade or publish marks.

### Non-Negotiable Pedagogical Invariant
> **Human-in-the-Loop Verification**: An AI or OCR model is NEVER permitted to independently publish marks, modify competency records, or alter student masteries. Every machine transcription produces a provisional preview that requires affirmative verification by an authorized educator.

```mermaid
flowchart TD
    Scan["Physical Student Answer Sheet"] --> Upload["Document Ingestion<br/>(MIME checks & file decoding)"]
    Upload --> SecureStorage["Validated temporary backend storage"]
    SecureStorage --> ProviderDispatcher{"Active OCR Provider"}
    ProviderDispatcher -->|Simulated| SimProvider["Simulated Deterministic Provider<br/>(BBox, Confidence & Suggestions)"]
    ProviderDispatcher -->|TrOCR| TrOCRProvider["HuggingFace Vision TrOCR<br/>(microsoft/trocr-base-handwritten)"]
    ProviderDispatcher -->|PaddleOCR| PaddleProvider["PaddleOCR Indic Engine<br/>(Devanagari & Multilingual)"]
    ProviderDispatcher -->|Qwen2.5-VL| QwenProvider["Qwen2.5-VL-3B<br/>(backend CUDA GPU)"]
    
    SimProvider --> ProvisionalRun["Provisional OCR Run<br/>(ocr_runs table)"]
    TrOCRProvider --> ProvisionalRun
    PaddleProvider --> ProvisionalRun
    QwenProvider --> Preview["OCR text preview<br/>(temporary upload removed after request)"]
    
    ProvisionalRun --> TeacherReview["Teacher Scan Review Interface<br/>(Side-by-Side Visual Verification)"]
    TeacherReview -->|Affirmative Teacher Sign-Off| GradeEntry["Official Assessment Submission &<br/>Competency Baseline Recalibration"]
    TeacherReview -->|Annotations Saved| GroundTruth["Dataset Split<br/>(Student-Partitioned Train/Val/Test)"]
```

---

## 2. Ingestion & Security Validation

The OCR preview accepts JPG, PNG, and PDF uploads and applies the existing 15 MB per-file limit. `StorageService` assigns UUID-based filenames under its configured backend storage directory. Image and PDF decoding validates that the content can be opened; temporary preview uploads are deleted after processing.

---

## 3. Pluggable Provider Architecture

The pipeline implements the `BaseOCRProvider` interface, allowing hot-swapping between models via configuration:

```python
class BaseOCRProvider(abc.ABC):
    @abc.abstractmethod
    async def extract_document(self, document_path: str, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Returns normalized page regions, bounding boxes, and transcription."""
        raise NotImplementedError
```

### Supported Providers
1. **`SimulatedOCRProvider` (Default Local Mode)**:
   - 100% deterministic, zero external API keys, zero GPUs required.
   - Extracts 4 standard question regions with bounding boxes (`[ymin, xmin, ymax, xmax]`), suggested marks, and target competencies (AU, CU, LU, CT).
   - Designed for instant local stakeholder demos and unit testing.
2. **`TrOCRHuggingFaceProvider`**:
   - Integrates Hugging Face's `microsoft/trocr-base-handwritten` for deep Transformer-based handwriting recognition.
3. **`PaddleOCRProvider`**:
   - Optimized for lightweight on-premise execution with support for regional Indic scripts and mixed vernacular handwriting.
4. **`QwenVisionOCRProvider`**:
   - Uses `QWEN_VL_MODEL_ID` (defaults to `Qwen/Qwen2.5-VL-3B-Instruct`; Vast.ai setup selects the AWQ checkpoint).
   - Loads lazily in the FastAPI process and requires CUDA. Missing GPU/dependencies or inference errors are reported; it does not silently substitute simulated OCR.
   - Converts PDF pages to images with PyMuPDF, up to 25 pages per PDF. The optional UI buffer waits five seconds before each image/page.

### Qwen OCR developer preview

On Windows, `run.bat` installs CUDA-enabled PyTorch and `backend/requirements-ocr.txt`; on Vast.ai, use the one-run `SET_UP.md` script. Run FastAPI on the GPU host so inference uses its local GPU. The browser uploads files to `POST /api/v1/ocr/extract-preview`, and the backend returns each file's transcription to the **OCR Extraction Preview** panel. This endpoint is OCR-only: it does not persist grades, call the grading pipeline, or publish marks.

---

## 4. OCR Preview and Existing Human Review

The current **Upload** screen (`/upload`) uploads files to `POST /api/v1/ocr/extract-preview` and displays each Qwen transcription in a separate preview panel. It does not award marks or publish results. The separate `POST /api/v1/ocr/review/verify` endpoint remains available for workflows that collect teacher-verified marks; the Qwen preview does not call it.
