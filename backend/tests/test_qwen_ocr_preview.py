import io
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image
from sqlalchemy import select

from backend.app.core.security import create_access_token
from backend.app.models.entities import StudentOcrHistory
import backend.app.services.ocr_service as ocr_service
from backend.app.services.storage_service import storage_service

URL = "/api/v1/ocr/extract-preview"


def png_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (64, 64), "white").save(buffer, "PNG")
    return buffer.getvalue()


@pytest.fixture
def fake_model(monkeypatch):
    """Skip the GPU while keeping the provider's file handling real."""
    monkeypatch.setattr(ocr_service.qwen_model, "_load_model", lambda: None)
    monkeypatch.setattr(ocr_service.qwen_model, "_infer_image", lambda _image: "recognized text")


async def post(client, token, name, content, content_type="application/octet-stream"):
    return await client.post(
        URL,
        headers={"Authorization": f"Bearer {token}"},
        files={"files": (name, content, content_type)},
    )


def stub_model_stack(monkeypatch, config):
    captured = {}

    def from_pretrained(model_id, **kwargs):
        captured.update(kwargs)
        return object()

    fake_model_class = SimpleNamespace(from_pretrained=from_pretrained)
    monkeypatch.setitem(
        sys.modules,
        "torch",
        SimpleNamespace(cuda=SimpleNamespace(is_available=lambda: True), float16="float16"),
    )
    monkeypatch.setitem(sys.modules, "qwen_vl_utils", SimpleNamespace(process_vision_info=None))
    monkeypatch.setitem(
        sys.modules,
        "transformers",
        SimpleNamespace(
            AutoConfig=SimpleNamespace(from_pretrained=lambda _id: config),
            AutoProcessor=SimpleNamespace(from_pretrained=lambda _id, **_kwargs: object()),
            Qwen2_5_VLForConditionalGeneration=fake_model_class,
        ),
    )
    return captured


def test_load_model_excludes_lm_head_from_awq_conversion(monkeypatch):
    # Regression: converting lm_head gave it random float16 weights and crashed the Triton kernel.
    config = SimpleNamespace(quantization_config={"modules_to_not_convert": ["visual"]})
    captured = stub_model_stack(monkeypatch, config)

    ocr_service.QwenVisionOCRProvider()._load_model()

    assert captured["config"].quantization_config["modules_to_not_convert"] == ["visual", "lm_head"]


def test_load_model_accepts_unquantized_checkpoints(monkeypatch):
    config = SimpleNamespace()
    captured = stub_model_stack(monkeypatch, config)

    ocr_service.QwenVisionOCRProvider()._load_model()

    assert captured["config"] is config


@pytest.mark.asyncio
async def test_preview_returns_text_and_removes_temporary_upload(client, teacher_token, fake_model):
    before = set(Path(storage_service.upload_dir).iterdir())

    response = await post(client, teacher_token, "sheet.png", png_bytes(), "image/png")

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "qwen2.5-vl"
    assert body["results"][0]["extracted_text"] == "recognized text"
    assert set(Path(storage_service.upload_dir).iterdir()) == before


@pytest.mark.asyncio
async def test_preview_rejects_pdf_over_page_limit(client, teacher_token, fake_model):
    pymupdf = pytest.importorskip("pymupdf")
    document = pymupdf.open()
    for _ in range(26):
        document.new_page()

    response = await post(client, teacher_token, "long.pdf", document.tobytes(), "application/pdf")

    assert response.status_code == 400
    assert "25-page" in response.json()["detail"]


@pytest.mark.asyncio
async def test_preview_rejects_corrupt_pdf(client, teacher_token, fake_model):
    pytest.importorskip("pymupdf")

    response = await post(client, teacher_token, "bad.pdf", b"%PDF-1.4 not a pdf", "application/pdf")

    assert response.status_code == 400
    assert "could not be opened" in response.json()["detail"]


@pytest.mark.asyncio
async def test_preview_rejects_unreadable_and_truncated_images(client, teacher_token, fake_model):
    unreadable = await post(client, teacher_token, "bad.png", b"not a png", "image/png")
    truncated = await post(client, teacher_token, "cut.png", png_bytes()[:40], "image/png")

    assert unreadable.status_code == 400
    assert truncated.status_code == 400


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "name,content_type",
    [("notes.txt", "text/plain"), ("picture.gif", "image/gif"), ("archive.zip", "application/zip")],
)
async def test_preview_rejects_unsupported_types_with_415(client, teacher_token, name, content_type):
    response = await post(client, teacher_token, name, b"content", content_type)

    assert response.status_code == 415


@pytest.mark.asyncio
async def test_preview_rejects_files_over_size_limit(client, teacher_token):
    response = await post(client, teacher_token, "big.png", b"0" * (15 * 1024 * 1024 + 1), "image/png")

    assert response.status_code == 400
    assert "15 MB" in response.json()["detail"]


@pytest.mark.asyncio
async def test_student_uploads_save_extracts_to_the_linked_student_only(
    client, teacher_token, student_token, fake_model, db_session,
):
    enrolled = await client.post(
        "/api/v1/onboarding/students",
        headers={"Authorization": f"Bearer {teacher_token}"},
        json={
            "name": "OCR test student", "email": "ocr-student@example.com", "password": "sample-ocr-test",
            "class_id": "class-8a", "roll_no": 4567,
        },
    )
    assert enrolled.status_code == 201
    user_id = enrolled.json()["id"]
    token = create_access_token(user_id, school_id="school-1", role="student")
    student_headers = {"Authorization": f"Bearer {token}"}
    profile = await client.get("/api/v1/classes/students/me", headers=student_headers)
    assert profile.status_code == 200
    student_id = profile.json()["id"]
    assert student_id != user_id
    assert profile.json()["class_name"] == "Class 8-A"
    assert "Mathematics" in profile.json()["subject_names"]
    demo_profile = await client.get(
        "/api/v1/classes/students/me", headers={"Authorization": f"Bearer {student_token}"},
    )
    assert demo_profile.json()["parent_names"] == ["Meera Patel"]

    response = await post(client, token, "direct.png", png_bytes(), "image/png")
    assert response.status_code == 200
    streamed = await client.post(
        f"{URL}/stream", headers=student_headers, files={"files": ("streamed.png", png_bytes(), "image/png")},
    )
    events = [json.loads(line[6:]) for line in streamed.text.splitlines() if line.startswith("data: ")]
    assert events[-1]["kind"] == "complete"

    history_url = "/api/v1/ocr/history"
    history = await client.get(history_url, headers=student_headers)
    assert history.status_code == 200
    assert [row["file_name"] for row in history.json()] == ["streamed.png", "direct.png"]
    assert all(row["extracted_text"] == "recognized text" for row in history.json())
    rows = (await db_session.scalars(select(StudentOcrHistory).where(StudentOcrHistory.student_id == student_id))).all()
    assert len(rows) == 2

    other = await client.get(history_url, headers={"Authorization": f"Bearer {student_token}"})
    assert other.json() == []
    assert (await client.get(history_url, headers={"Authorization": f"Bearer {teacher_token}"})).status_code == 403


@pytest.mark.asyncio
async def test_preview_returns_json_for_unexpected_errors(client, teacher_token, monkeypatch):
    # A JSON response keeps its CORS headers, so the page can show a real message.
    def fail(*_args):
        raise KeyError("unexpected")

    monkeypatch.setattr(ocr_service.qwen_model, "_extract_sync", fail)

    response = await post(client, teacher_token, "sheet.png", png_bytes(), "image/png")

    assert response.status_code == 500
    assert "sheet.png" in response.json()["detail"]


@pytest.mark.asyncio
async def test_process_endpoint_directs_qwen_to_preview(client, teacher_token):
    response = await client.post(
        "/api/v1/ocr/process",
        headers={"Authorization": f"Bearer {teacher_token}"},
        json={"document_id": "any", "provider": "qwen"},
    )

    assert response.status_code == 400
    assert "extract-preview" in response.json()["detail"]
