import io
import json
import uuid
import pytest


@pytest.mark.asyncio
async def test_bulk_source_document_upload_mixed_files(client, teacher_token):
    headers = {"Authorization": f"Bearer {teacher_token}"}
    nonce = uuid.uuid4().hex
    pdf_bytes = f"%PDF-1.4 Algebra and Identities curriculum content {nonce} /Page /Page".encode("utf-8")
    txt_bytes = f"Quadrilaterals, Rhombus, and Parallelogram properties for Grade 8 ({nonce}).".encode("utf-8")

    files = [
        ("files", ("ncert_ch12_algebra.pdf", io.BytesIO(pdf_bytes), "application/pdf")),
        ("files", ("geometry_notes.txt", io.BytesIO(txt_bytes), "text/plain")),
        ("files", ("invalid_script.exe", io.BytesIO(b"MZ_executable_binary"), "application/x-msdownload")),
        ("files", ("ncert_ch12_algebra_dup.pdf", io.BytesIO(pdf_bytes), "application/pdf")),
    ]

    res = await client.post(
        "/api/v1/documents/bulk-upload",
        headers=headers,
        data={"subject_id": "sub-math", "doc_type": "source_material"},
        files=files,
    )
    assert res.status_code == 200
    body = res.json()
    assert body["total_selected"] == 4
    assert body["uploaded_count"] == 2
    assert body["failed_count"] == 1
    assert body["duplicate_count"] == 1

    statuses = {item["file_name"]: item["status"] for item in body["items"]}
    assert statuses["ncert_ch12_algebra.pdf"] == "uploaded"
    assert statuses["geometry_notes.txt"] == "uploaded"
    assert statuses["invalid_script.exe"] == "failed"
    assert statuses["ncert_ch12_algebra_dup.pdf"] == "duplicate"


@pytest.mark.asyncio
async def test_beta_question_generation_edit_and_delete(client, teacher_token, monkeypatch):
    from backend.app.services.llm_service import qwen_question_studio

    pymupdf = pytest.importorskip("pymupdf")
    with pymupdf.open() as pdf:
        page = pdf.new_page()
        page.insert_text((50, 50), "Area of a square equals the side multiplied by itself.")
        chapter = pdf.tobytes()

    headers = {"Authorization": f"Bearer {teacher_token}"}
    upload = await client.post(
        "/api/v1/documents/studio-pdf-upload", headers=headers,
        data={"subject_id": "sub-math"}, files={"file": ("square.pdf", chapter, "application/pdf")},
    )
    assert upload.status_code == 201
    document_id = upload.json()["id"]

    def generate(prompt, **kwargs):
        assert "Area of a square" in prompt
        return json.dumps({
            "mcqs": [{
                "type": "mcq", "text": "What is the area of a square of side 3?",
                "options": ["3", "6", "9", "12"], "correct_answer": "9",
                "marking_rubric": "Multiply 3 by itself.", "competency": "AU",
            }],
            "theory": [{
                "type": "short", "text": "Explain how to find the area of a square.",
                "correct_answer": "Multiply its side by itself.",
                "marking_rubric": "Explain the formula.", "competency": "CU",
            }],
        })

    monkeypatch.setattr(qwen_question_studio, "_generate_text", generate)
    body = {
        "subject_id": "sub-math", "source_document_ids": [document_id],
        "mcq_count": 1, "theory_count": 1, "bloom_level": "Apply", "save_to_bank": True,
    }
    assert (await client.post("/api/v1/assessments/generate-questions", headers=headers, json=body)).status_code == 404
    gen_res = await client.post("/api/v1/assessments/generate-questions-beta", headers=headers, json=body)
    assert gen_res.status_code == 200
    questions = gen_res.json()["questions"]
    assert [q["type"] for q in questions] == ["mcq", "short"]
    assert all(q["source_document_ids"] == [document_id] and q["correct_answer"] for q in questions)

    target_q = questions[0]
    q_id = target_q["id"]

    # 3. Edit question
    edit_res = await client.put(
        f"/api/v1/assessments/questions/{q_id}",
        headers=headers,
        json={
            "text": "Updated Question Text: Calculate the volume of a cylinder with radius 7m and height 10m.",
            "marks": 3,
            "bloom_level": "Evaluate",
        },
    )
    assert edit_res.status_code == 200
    edited = edit_res.json()
    assert "Updated Question Text" in edited["text"]
    assert edited["marks"] == 3
    assert edited["bloom_level"] == "Evaluate"

    # Delete the saved question.
    del_res = await client.delete(f"/api/v1/assessments/questions/{q_id}", headers=headers)
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "deleted"


@pytest.mark.asyncio
async def test_auto_grade_batch_lifecycle_recovery_and_approval(client, teacher_token, student_token):
    t_headers = {"Authorization": f"Bearer {teacher_token}"}
    s_headers = {"Authorization": f"Bearer {student_token}"}

    # Verify Student cannot create a grading batch (403 Forbidden)
    forbidden_res = await client.post(
        "/api/v1/ocr/batches",
        headers=s_headers,
        data={"class_id": "class-8a", "subject_id": "sub-math", "assessment_id": "asm-2"},
        files=[("files", ("sheet1.jpg", io.BytesIO(b"fake_image_bytes"), "image/jpeg"))],
    )
    assert forbidden_res.status_code == 403

    # 1. Teacher creates a bulk grading batch with:
    #    - Valid identified student paper (aarav_patel_math.jpg)
    #    - Valid identified student paper (ananya_patel_math.pdf)
    #    - Uncertain student paper (scan_unmapped_01.png)
    #    - Corrupted scan paper (corrupt_scan_rohan.jpg)
    #    - Duplicate file (aarav_patel_math_dup.jpg with identical content)
    #    - Invalid format file (malware.bat)
    aarav_bytes = b"\xff\xd8\xff\xe0Aarav Patel Roll 14 answer script content"
    files = [
        ("files", ("aarav_patel_math.jpg", io.BytesIO(aarav_bytes), "image/jpeg")),
        ("files", ("ananya_patel_math.pdf", io.BytesIO(b"%PDF-1.4 Ananya Patel Roll 15 answer script"), "application/pdf")),
        ("files", ("scan_unmapped_01.png", io.BytesIO(b"\x89PNG\r\n\x1a\nUnidentified student script"), "image/png")),
        ("files", ("corrupt_scan_rohan.jpg", io.BytesIO(b"\xff\xd8\xff\xe0Corrupted scan stream"), "image/jpeg")),
        ("files", ("aarav_dup.jpg", io.BytesIO(aarav_bytes), "image/jpeg")),
        ("files", ("notes.bat", io.BytesIO(b"echo invalid"), "application/x-bat")),
    ]

    create_res = await client.post(
        "/api/v1/ocr/batches",
        headers=t_headers,
        data={
            "class_id": "class-8a",
            "subject_id": "sub-math",
            "assessment_id": "asm-2",
            "concurrency_limit": "3",
        },
        files=files,
    )
    assert create_res.status_code == 201
    batch = create_res.json()
    batch_id = batch["id"]

    assert batch["status"] == "configuring"
    assert batch["total_files"] == 6
    assert batch["valid_files"] == 4
    assert batch["invalid_or_duplicate_files"] == 2

    # 2. Start batch processing and wait for completion
    start_res = await client.post(
        f"/api/v1/ocr/batches/{batch_id}/start?wait_for_completion=true",
        headers=t_headers,
    )
    assert start_res.status_code == 200
    processed_batch = start_res.json()
    assert processed_batch["status"] == "completed_with_warnings"
    assert processed_batch["completed_files"] == 2  # Aarav and Ananya
    assert processed_batch["review_required_files"] == 1  # scan_unmapped_01.png
    assert processed_batch["failed_files"] == 1  # corrupt_scan_rohan.jpg

    items_by_name = {it["file_name"]: it for it in processed_batch["items"]}

    # Verify corrupt file failed without stopping the batch
    corrupt_item = items_by_name["corrupt_scan_rohan.jpg"]
    assert corrupt_item["status"] == "failed"
    assert "Corrupted" in corrupt_item["error_message"]

    # 3. Retry the failed item — it should recover on retry!
    retry_res = await client.post(
        f"/api/v1/ocr/batches/{batch_id}/items/{corrupt_item['id']}/retry?wait_for_completion=true",
        headers=t_headers,
    )
    assert retry_res.status_code == 200
    retried_batch = retry_res.json()
    assert retried_batch["failed_files"] == 0
    recovered_item = next(i for i in retried_batch["items"] if i["id"] == corrupt_item["id"])
    assert recovered_item["status"] in ("completed", "requires_review")
    assert recovered_item["retry_count"] == 1

    # 4. Verify unmapped student paper is blocked from approval until student is assigned
    unmapped_item = items_by_name["scan_unmapped_01.png"]
    assert unmapped_item["requires_review"] is True
    block_res = await client.post(
        f"/api/v1/ocr/batches/{batch_id}/items/{unmapped_item['id']}/approve",
        headers=t_headers,
    )
    assert block_res.status_code == 400

    # 5. Teacher manually assigns student ("student-4" Priya Nair) and adjusts marks
    update_res = await client.put(
        f"/api/v1/ocr/batches/{batch_id}/items/{unmapped_item['id']}",
        headers=t_headers,
        json={
            "student_id": "student-4",
            "marks_obtained": 25,
            "clear_review_flag": True,
        },
    )
    assert update_res.status_code == 200
    updated_item = update_res.json()
    assert updated_item["student_id"] == "student-4"
    assert updated_item["student_name"] == "Priya Nair"
    assert updated_item["requires_review"] is False
    assert updated_item["marks_obtained"] == 25

    # 6. Approve all verified items in the batch
    approve_all_res = await client.post(
        f"/api/v1/ocr/batches/{batch_id}/approve-all",
        headers=t_headers,
    )
    assert approve_all_res.status_code == 200
    final_batch = approve_all_res.json()
    approved_items = [i for i in final_batch["items"] if i["is_approved"]]
    assert len(approved_items) >= 3
    for ai in approved_items:
        assert ai["submission_id"] is not None


@pytest.mark.asyncio
async def test_multi_student_pdf_splitting(client, teacher_token):
    headers = {"Authorization": f"Bearer {teacher_token}"}
    pdf_bytes = b"%PDF-1.4 /Page 1 /Page 2 /Page 3 /Page 4 /Page 5 /Page 6 combined student bundle"

    res = await client.post(
        "/api/v1/ocr/batches",
        headers=headers,
        data={
            "class_id": "class-8a",
            "subject_id": "sub-math",
            "assessment_id": "asm-2",
            "split_multi_pdf": "true",
        },
        files=[("files", ("class8a_combined_bundle.pdf", io.BytesIO(pdf_bytes), "application/pdf"))],
    )
    assert res.status_code == 201
    batch = res.json()
    # 6 pages split into 2-page student scripts -> 3 separate student submissions
    assert batch["valid_files"] == 3
    assert all(it["page_range"] is not None for it in batch["items"])
