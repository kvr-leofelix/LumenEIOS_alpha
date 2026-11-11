import io
import json

import pytest
from PIL import Image

from backend.app.core.security import create_access_token
from backend.app.models.entities import Assessment, Subject
from backend.app.services import ocr_service


@pytest.mark.asyncio
async def test_assignment_audience_and_ocr_upload(client, db_session, monkeypatch, teacher_token, other_school_teacher_token):
    teacher = {"Authorization": f"Bearer {teacher_token}"}
    other_teacher = {"Authorization": f"Bearer {other_school_teacher_token}"}
    base = "/api/v1"
    cards_url = f"{base}/assessments/upload-assignments"

    enrolled = await client.post(f"{base}/onboarding/students", headers=teacher, json={
        "name": "Assignment upload student", "email": "assignment-upload@example.com",
        "password": "sample-upload-test", "class_id": "class-8a", "roll_no": 4568,
    })
    assert enrolled.status_code == 201
    token = create_access_token(enrolled.json()["id"], school_id="school-1", role="student")
    student = {"Authorization": f"Bearer {token}"}

    question = {
        "type": "mcq", "text": "Which value is twice 6?", "options": ["6", "12"],
        "marks": 2, "competency": "AU", "bloom_level": "Apply",
        "correct_answer": "12", "marking_rubric": "Multiply by two.",
    }
    body = {
        "title": "Multiplication practice", "subject_id": "sub-math",
        "date": "2026-11-11", "total_marks": 2, "questions": [question], "competency_focus": ["AU"],
    }

    async def create(class_id, **updates):
        return await client.post(f"{base}/classes/{class_id}/assessments", headers=teacher, json=body | updates)

    targets = (await client.get(f"{base}/assessments/targets", headers=teacher)).json()
    assert {item["id"] for item in targets} >= {"class-8a", "class-9b"}
    assert "class-pragati-8" not in {item["id"] for item in targets}
    assert "sub-eng" not in {item["id"] for item in next(row for row in targets if row["id"] == "class-9b")["subjects"]}
    assert (await create("class-9b", subject_id="sub-eng")).status_code == 422
    assert (await create("class-pragati-8")).status_code == 404
    eligible = await create("class-8a")
    different_class = await create("class-8b")
    assert eligible.status_code == different_class.status_code == 201
    eligible_id = eligible.json()["id"]

    # An older or imported paper can have the right class but the wrong subject.
    db_session.add(Subject(id="sub-unassigned-art", name="Art", code="OCR-ART-8", grade=8))
    db_session.add(Assessment(
        id="asm-unassigned-art", school_id="school-1", class_id="class-8a",
        subject_id="sub-unassigned-art", title="Art practice", date="2026-11-11",
        questions_json=[question],
    ))
    await db_session.commit()
    wrong_ids = {different_class.json()["id"], "asm-unassigned-art"}

    cards = await client.get(cards_url, headers=student)
    assert cards.status_code == 200
    by_id = {item["id"]: item for item in cards.json()}
    assert wrong_ids.isdisjoint(by_id)
    assert not by_id[eligible_id]["uploaded"]
    visible = by_id[eligible_id]["questions"][0]
    assert visible["text"] == question["text"]
    assert {"correct_answer", "marking_rubric"}.isdisjoint(visible)
    assert eligible_id not in {item["id"] for item in (await client.get(cards_url, headers=other_teacher)).json()}
    assert eligible_id in {item["id"] for item in (await client.get(cards_url, headers=teacher)).json()}
    for path in ("/assessments", "/classes/class-8a/assessments", "/assessments/question-bank"):
        assert (await client.get(f"{base}{path}", headers=student)).status_code == 403

    calls = []

    def infer(image):
        calls.append(image.size)
        return "Twelve"

    monkeypatch.setattr(ocr_service._qwen_provider, "_load_model", lambda: None)
    monkeypatch.setattr(ocr_service._qwen_provider, "_infer_image", infer)
    image = io.BytesIO()
    Image.new("RGB", (64, 64), "white").save(image, "PNG")
    files = {"files": ("answer.png", image.getvalue(), "image/png")}
    ocr_url = f"{base}/ocr/extract-preview"
    for wrong_id in wrong_ids:
        denied = await client.post(ocr_url, headers=student, files=files, data={"assessment_id": wrong_id})
        assert denied.status_code == 404
    assert calls == []

    streamed = await client.post(
        f"{ocr_url}/stream", headers=student, files=files, data={"assessment_id": eligible_id},
    )
    events = [json.loads(line[6:]) for line in streamed.text.splitlines() if line.startswith("data: ")]
    assert events[-1]["kind"] == "complete"
    assert len(calls) == 1
    history = (await client.get(f"{base}/ocr/history", headers=student)).json()
    assert history[0]["extracted_text"] == "Twelve"
    assert history[0]["assignment_title"] == body["title"]
    cards = (await client.get(cards_url, headers=student)).json()
    assert next(item for item in cards if item["id"] == eligible_id)["uploaded"] is True
