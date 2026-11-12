import abc
import asyncio
import io
import logging
import os
import threading
import time
from typing import Dict, List, Any, Optional
from backend.app.core.config import settings
from backend.app.services.progress import report_progress

logger = logging.getLogger(__name__)

class BaseOCRProvider(abc.ABC):
    @abc.abstractmethod
    async def extract_document(self, document_path: str, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Return normalized page and answer-region extraction results."""
        raise NotImplementedError


class SimulatedOCRProvider(BaseOCRProvider):
    """
    Deterministic simulated OCR provider for local demos and testing.
    Provides realistic bounding boxes, extracted handwriting, confidence scores, and suggested marks.
    """
    async def extract_document(self, document_path: str, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return {
            "provider": "simulated",
            "model_version": "v1.2-synthetic-trocr",
            "confidence_score": 0.984,
            "regions": [
                {
                    "item_index": 1,
                    "bounding_box": [0.12, 0.08, 0.28, 0.92],
                    "extracted_text": "Length = 4m, Breadth = 3m, Height = 2m. Volume = L * B * H = 4 * 3 * 2 = 24 m3. Since 1m3 = 1000 Liters, Total capacity = 24,000 Liters. Time taken at 60 L/min = 24000 / 60 = 400 minutes = 6 hrs 40 mins.",
                    "confidence": 0.984,
                    "suggested_marks": 4,
                    "max_marks": 4,
                    "target_competency": "AU"
                },
                {
                    "item_index": 2,
                    "bounding_box": [0.32, 0.08, 0.44, 0.92],
                    "extracted_text": "The reciprocal is -19/13. Because (-13/19) * (-19/13) = +247/247 = 1.",
                    "confidence": 0.991,
                    "suggested_marks": 2,
                    "max_marks": 2,
                    "target_competency": "CU"
                },
                {
                    "item_index": 3,
                    "bounding_box": [0.48, 0.08, 0.62, 0.92],
                    "extracted_text": "Every square has all right angles and opposite sides equal, so it meets rectangle criteria. But rectangles do not have all 4 equal sides.",
                    "confidence": 0.962,
                    "suggested_marks": 3,
                    "max_marks": 3,
                    "target_competency": "LU"
                },
                {
                    "item_index": 4,
                    "bounding_box": [0.66, 0.08, 0.84, 0.92],
                    "extracted_text": "False. If sides are scaled uniformly by factor 2, perimeter doubles (2P), but area scales quadratically by factor of 4 (4A).",
                    "confidence": 0.975,
                    "suggested_marks": 4,
                    "max_marks": 5,
                    "target_competency": "CT"
                }
            ]
        }


class TrOCRHuggingFaceProvider(BaseOCRProvider):
    """
    Adapter for Hugging Face TrOCR or Transformer endpoints.
    Falls back to simulated provider if models or weights are not loaded locally.
    """
    def __init__(self, model_id: str = "microsoft/trocr-base-handwritten"):
        self.model_id = model_id

    async def extract_document(self, document_path: str, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        # Graceful fallback if PyTorch / TrOCR weights are not downloaded
        simulated = SimulatedOCRProvider()
        res = await simulated.extract_document(document_path, options)
        res["provider"] = "trocr-huggingface"
        res["model_version"] = self.model_id
        return res


class PaddleOCRProvider(BaseOCRProvider):
    """
    Adapter for PaddleOCR document analysis.
    """
    async def extract_document(self, document_path: str, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        simulated = SimulatedOCRProvider()
        res = await simulated.extract_document(document_path, options)
        res["provider"] = "paddleocr"
        res["model_version"] = "pp-ocrv4"
        return res


class QwenOCRUnavailableError(RuntimeError):
    pass


class QwenOCRInputError(ValueError):
    pass


class QwenOCRInferenceError(RuntimeError):
    pass


class QwenVisionOCRProvider(BaseOCRProvider):
    """Server-side Qwen2.5-VL OCR; model and optional GPU dependencies load on first use."""

    _prompt = (
        "You are an expert OCR model. Extract only the text and formulas visible in the image. "
        "Transcribe the original language directly without translating it. If text is unclear, "
        "write [unclear] instead of guessing. Format mathematical expressions in LaTeX. "
        "Do not add an introduction, headings, summaries, or explanations."
    )
    _max_pdf_pages = 25

    def __init__(self) -> None:
        self._model = None
        self._processor = None
        self._torch = None
        self._process_vision_info = None
        self._inference_lock = threading.Lock()

    async def extract_document(
        self, document_path: str, options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        buffer = options or {}
        return await asyncio.to_thread(self._extract_sync, document_path, buffer)

    def _load_model(self) -> None:
        if self._model is not None:
            return

        report_progress("model", "Loading the shared Qwen model", 0, 1)

        try:
            import torch
            from qwen_vl_utils import process_vision_info
            from transformers import AutoConfig, AutoProcessor, Qwen2_5_VLForConditionalGeneration
        except ImportError as exc:
            raise QwenOCRUnavailableError(
                "Qwen OCR dependencies are missing. Install backend/requirements-ocr.txt "
                "with a CUDA-enabled PyTorch build."
            ) from exc

        if not torch.cuda.is_available():
            raise QwenOCRUnavailableError(
                "Qwen OCR requires an available NVIDIA CUDA GPU in the backend environment."
            )

        model_id = settings.QWEN_VL_MODEL_ID
        try:
            processor = AutoProcessor.from_pretrained(
                model_id,
                min_pixels=512 * 28 * 28,
                max_pixels=2048 * 28 * 28,
            )
            config = AutoConfig.from_pretrained(model_id)
            # lm_head has no quantized weights in these AWQ checkpoints (it is tied to
            # embed_tokens or stored as plain float16). Converting it would replace it
            # with randomly initialized AWQ weights and break inference.
            quantization_config = getattr(config, "quantization_config", None)
            if quantization_config:
                excluded = quantization_config.get("modules_to_not_convert") or []
                quantization_config["modules_to_not_convert"] = [*excluded, "lm_head"]
            model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
                model_id,
                config=config,
                torch_dtype=torch.float16,
                device_map="auto",
            )
        except Exception as exc:
            logger.exception("Could not load Qwen OCR model %s", model_id)
            raise QwenOCRUnavailableError(
                f"Could not load Qwen OCR model '{model_id}'. Check backend logs and GPU compatibility."
            ) from exc

        self._torch = torch
        self._processor = processor
        self._model = model
        self._process_vision_info = process_vision_info
        report_progress("model", "Loaded the shared Qwen model", 1, 1)

    def generate(self, messages: list[dict[str, Any]], max_new_tokens: int) -> str:
        """Generate with the same model and GPU lock used by worksheet OCR."""
        with self._inference_lock:
            self._load_model()
            return self._generate_locked(messages, max_new_tokens)

    def _infer_image(self, image: Any) -> str:
        return self._generate_locked([{
            "role": "user",
            "content": [
                {"type": "image", "image": image},
                {"type": "text", "text": self._prompt},
            ],
        }], max_new_tokens=2048)

    def _generate_locked(self, messages: list[dict[str, Any]], max_new_tokens: int) -> str:
        try:
            text = self._processor.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
            image_inputs, video_inputs = self._process_vision_info(messages)
            inputs = self._processor(
                text=[text],
                images=image_inputs,
                videos=video_inputs,
                padding=True,
                return_tensors="pt",
            ).to(self._model.device)

            with self._torch.inference_mode():
                generated_ids = self._model.generate(
                    **inputs,
                    max_new_tokens=max_new_tokens,
                    do_sample=False,
                )

            trimmed_ids = [
                output_ids[len(input_ids) :]
                for input_ids, output_ids in zip(inputs.input_ids, generated_ids)
            ]
            return self._processor.batch_decode(
                trimmed_ids,
                skip_special_tokens=True,
                clean_up_tokenization_spaces=False,
            )[0].strip()
        except Exception as exc:
            logger.exception("Qwen inference failed")
            raise QwenOCRInferenceError(
                "Qwen inference failed; check backend logs for the model error."
            ) from exc

    def _extract_sync(self, document_path: str, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        from PIL import Image

        options = options or {}
        buffer_seconds = int(options.get("buffer_seconds") or 0)
        file_name = str(options.get("file_name") or os.path.basename(document_path))
        page_texts: List[str] = []
        is_pdf = os.path.splitext(document_path)[1].lower() == ".pdf"

        if is_pdf:
            try:
                import pymupdf
            except ImportError as exc:
                raise QwenOCRUnavailableError(
                    "PDF OCR requires PyMuPDF. Install backend/requirements-ocr.txt."
                ) from exc

            # Open from bytes: a failed open by path can leave the file locked on Windows,
            # which then blocks deleting the temporary upload.
            try:
                with open(document_path, "rb") as handle:
                    pdf_document = pymupdf.open(stream=handle.read(), filetype="pdf")
            except Exception as exc:
                raise QwenOCRInputError("The uploaded PDF could not be opened.") from exc

            with pdf_document as pdf:
                if pdf.needs_pass:
                    raise QwenOCRInputError("Password-protected PDFs are not supported.")
                if pdf.page_count == 0:
                    raise QwenOCRInputError("The uploaded PDF contains no pages.")
                if pdf.page_count > self._max_pdf_pages:
                    raise QwenOCRInputError(
                        f"PDF exceeds the {self._max_pdf_pages}-page OCR limit."
                    )
                total_pages = pdf.page_count
                for index, page in enumerate(pdf, start=1):
                    report_progress(
                        "extract",
                        f"{file_name}: extracting page {index} of {total_pages}",
                        index - 1,
                        total_pages,
                    )
                    page_image = Image.open(
                        io.BytesIO(
                            page.get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False).tobytes("png")
                        )
                    )
                    with page_image:
                        # ponytail: serialize inference on the shared GPU; add per-device workers if throughput matters
                        with self._inference_lock:
                            self._load_model()
                            if buffer_seconds:
                                time.sleep(buffer_seconds)
                            page_texts.append(self._infer_image(page_image.convert("RGB")))
                    report_progress(
                        "extract",
                        f"{file_name}: extracted page {index} of {total_pages}",
                        index,
                        total_pages,
                    )
        else:
            try:
                image = Image.open(document_path)
            except (OSError, ValueError) as exc:
                raise QwenOCRInputError("The uploaded image could not be opened.") from exc
            with image:
                try:
                    rgb_image = image.convert("RGB")
                except (OSError, ValueError) as exc:
                    raise QwenOCRInputError("The uploaded image could not be decoded.") from exc
                report_progress("extract", f"{file_name}: extracting page 1 of 1", 0, 1)
                with self._inference_lock:
                    self._load_model()
                    if buffer_seconds:
                        time.sleep(buffer_seconds)
                    page_texts.append(self._infer_image(rgb_image))
                report_progress("extract", f"{file_name}: extracted page 1 of 1", 1, 1)

        return {
            "provider": "qwen2.5-vl",
            "model_version": settings.QWEN_VL_MODEL_ID,
            "extracted_text": "\n\n".join(text for text in page_texts if text),
            "pages_processed": len(page_texts),
        }


qwen_model = QwenVisionOCRProvider()


def get_ocr_provider(provider_name: str = "simulated") -> BaseOCRProvider:
    if provider_name == "trocr":
        return TrOCRHuggingFaceProvider()
    elif provider_name == "paddleocr":
        return PaddleOCRProvider()
    elif provider_name == "qwen":
        return qwen_model
    return SimulatedOCRProvider()
