"""Runs the real model. Opt in with: RUN_QWEN_GPU_TEST=1 python -m pytest backend/tests/test_qwen_gpu_smoke.py

Stop the backend first if the GPU has too little free memory for a second copy of the model.
"""
import os

import pytest
from PIL import Image, ImageDraw, ImageFont

from backend.app.services.ocr_service import QwenVisionOCRProvider

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_QWEN_GPU_TEST") != "1",
    reason="Set RUN_QWEN_GPU_TEST=1 to run the real Qwen model on the GPU.",
)


@pytest.mark.asyncio
async def test_real_model_reads_printed_text(tmp_path):
    image_path = tmp_path / "printed.png"
    image = Image.new("RGB", (1000, 200), "white")
    ImageDraw.Draw(image).text(
        (40, 60), "The capital of France is Paris.", fill="black", font=ImageFont.load_default(size=48)
    )
    image.save(image_path)

    result = await QwenVisionOCRProvider().extract_document(str(image_path))

    assert "Paris" in result["extracted_text"]
