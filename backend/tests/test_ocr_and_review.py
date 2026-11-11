import pytest
from PIL import Image
import backend.app.services.ocr_service as ocr_service
from backend.app.services.ocr_service import QwenVisionOCRProvider, SimulatedOCRProvider
from backend.app.services.model_training_service import (
    calculate_cer_wer,
    partition_dataset_by_student,
    check_model_promotion_criteria,
)


@pytest.mark.asyncio
async def test_simulated_ocr_extraction():
    provider = SimulatedOCRProvider()
    result = await provider.extract_document("dummy_path.png")

    assert result["provider"] == "simulated"
    assert result["confidence_score"] > 0.95
    assert len(result["regions"]) == 4

    # Verify each extracted region has bounding box, suggested marks, and target competency
    for region in result["regions"]:
        assert len(region["bounding_box"]) == 4
        assert region["suggested_marks"] > 0
        assert region["target_competency"] in ["LU", "CU", "AU", "CT"]


@pytest.mark.asyncio
async def test_qwen_ocr_image_preview_and_optional_buffer(tmp_path, monkeypatch):
    image_path = tmp_path / "answer.png"
    Image.new("RGB", (4, 4), "white").save(image_path)

    provider = QwenVisionOCRProvider()
    waits = []
    monkeypatch.setattr(provider, "_load_model", lambda: None)
    monkeypatch.setattr(provider, "_infer_image", lambda _image: "उत्तर = 2")
    monkeypatch.setattr(ocr_service.time, "sleep", waits.append)

    result = await provider.extract_document(str(image_path), {"buffer_seconds": 5})
    no_buffer_result = await provider.extract_document(str(image_path))

    assert result["extracted_text"] == "उत्तर = 2"
    assert result["pages_processed"] == 1
    assert no_buffer_result["extracted_text"] == "उत्तर = 2"
    assert waits == [5]


def test_calculate_cer_wer_exact_match():
    ref = "Volume = 24 m3"
    hyp = "Volume = 24 m3"
    cer, wer = calculate_cer_wer(ref, hyp)
    assert cer == 0.0
    assert wer == 0.0


def test_calculate_cer_wer_with_errors():
    ref = "The reciprocal is -19/13"
    hyp = "The reciprocal is -18/13"  # 1 char diff, 1 word diff
    cer, wer = calculate_cer_wer(ref, hyp)
    assert cer > 0.0
    assert wer > 0.0
    assert cer < 0.15  # Small character error


def test_partition_dataset_prevents_student_leakage():
    examples = [
        {"id": f"ex-{i}", "student_id": f"student-{i % 5}", "text": "sample"}
        for i in range(25)
    ]
    splits = partition_dataset_by_student(examples, train_ratio=0.6, val_ratio=0.2)

    train_students = set(e["student_id"] for e in splits["train"])
    val_students = set(e["student_id"] for e in splits["val"])
    test_students = set(e["student_id"] for e in splits["test"])

    # Disjoint student sets across train, val, and test
    assert train_students.isdisjoint(test_students)
    assert train_students.isdisjoint(val_students)
    assert val_students.isdisjoint(test_students)


def test_check_model_promotion_criteria():
    # Passing model
    passed, msg = check_model_promotion_criteria(cer=0.035, wer=0.08, field_accuracy=0.96)
    assert passed is True
    assert "passed all benchmark gates" in msg

    # Failing CER
    passed_cer_fail, msg_cer = check_model_promotion_criteria(cer=0.07, wer=0.08, field_accuracy=0.96)
    assert passed_cer_fail is False
    assert "Character Error Rate" in msg_cer

    # Failing WER
    passed_wer_fail, msg_wer = check_model_promotion_criteria(cer=0.03, wer=0.15, field_accuracy=0.96)
    assert passed_wer_fail is False
    assert "Word Error Rate" in msg_wer

    # Failing Field Accuracy
    passed_acc_fail, msg_acc = check_model_promotion_criteria(cer=0.03, wer=0.08, field_accuracy=0.85)
    assert passed_acc_fail is False
    assert "Field accuracy" in msg_acc
