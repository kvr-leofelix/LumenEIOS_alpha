import pytest
from pathlib import Path
import backend.app.api.v1.ocr as ocr_api
from backend.app.services.ocr_service import QwenOCRUnavailableError


@pytest.mark.asyncio
async def test_health_and_readiness(client):
    res_health = await client.get("/health")
    assert res_health.status_code == 200
    data = res_health.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"

    res_ready = await client.get("/ready")
    assert res_ready.status_code == 200
    assert res_ready.json()["ready"] is True


@pytest.mark.asyncio
async def test_auth_login_success(client):
    # Test logging in as admin with JSON credentials
    res = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@lumeneios.demo", "password": "demo123"},
    )
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["user"]["role"] == "admin"
    assert data["user"]["email"] == "admin@lumeneios.demo"

    # Test logging in as teacher
    res_t = await client.post(
        "/api/v1/auth/login",
        json={"email": "teacher@lumeneios.demo", "password": "demo123"},
    )
    assert res_t.status_code == 200
    data_t = res_t.json()
    assert data_t["user"]["role"] == "teacher"


@pytest.mark.asyncio
async def test_auth_login_invalid_password(client):
    # Temporarily check rejection with invalid password
    from backend.app.core.config import settings
    prev_demo = settings.DEMO_MODE
    settings.DEMO_MODE = False
    try:
        res = await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@lumeneios.demo", "password": "wrong_password"},
        )
        assert res.status_code == 401
    finally:
        settings.DEMO_MODE = prev_demo


@pytest.mark.asyncio
async def test_schools_endpoints(client, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    res = await client.get("/api/v1/schools", headers=headers)
    assert res.status_code == 200
    schools = res.json()
    assert len(schools) >= 5

    res_single = await client.get("/api/v1/schools/school-1", headers=headers)
    assert res_single.status_code == 200
    assert res_single.json()["name"] == "Sunrise Public School"


@pytest.mark.asyncio
async def test_time_aware_pacing(client, teacher_token):
    headers = {"Authorization": f"Bearer {teacher_token}"}
    res = await client.post(
        "/api/v1/classes/class-8a/time-aware/calculate",
        headers=headers,
        json={"total_official_days": 220, "current_day": 104},
    )
    assert res.status_code == 200
    pacing = res.json()
    assert "pacing_buffer" in pacing
    assert "risk_status" in pacing
    assert pacing["total_official_days"] == 220


@pytest.mark.asyncio
async def test_compression_proposal_lifecycle(client, teacher_token, principal_token):
    # 1. Teacher previews/generates compression proposal
    t_headers = {"Authorization": f"Bearer {teacher_token}"}
    res_gen = await client.post(
        "/api/v1/classes/class-8a/time-aware/compression-preview",
        headers=t_headers,
        json={"total_official_days": 220, "current_day": 104},
    )
    assert res_gen.status_code == 200
    proposal = res_gen.json()
    assert proposal["days_saved"] > 0
    prop_id = proposal["proposal_id"]

    # 2. Principal approves proposal
    p_headers = {"Authorization": f"Bearer {principal_token}"}
    res_app = await client.post(
        f"/api/v1/curriculum-proposals/{prop_id}/approve",
        headers=p_headers,
        json={"action": "approve"},
    )
    assert res_app.status_code == 200
    assert res_app.json()["status"] == "approved"


@pytest.mark.asyncio
async def test_assessments_and_submissions(client, teacher_token):
    headers = {"Authorization": f"Bearer {teacher_token}"}
    res = await client.get("/api/v1/assessments", headers=headers)
    assert res.status_code == 200
    assessments = res.json()
    assert len(assessments) >= 4

    # Submissions for asm-2
    res_subs = await client.get("/api/v1/assessments/asm-2/submissions", headers=headers)
    assert res_subs.status_code == 200
    subs = res_subs.json()
    assert len(subs) >= 5
    assert any(s["student_name"] == "Aarav Patel" for s in subs)


@pytest.mark.asyncio
async def test_simulated_ocr_and_human_review(client, teacher_token):
    headers = {"Authorization": f"Bearer {teacher_token}"}
    # 1. Trigger OCR extraction for doc-demo-1
    res_ocr = await client.post(
        "/api/v1/ocr/process",
        headers=headers,
        json={"document_id": "doc-demo-1", "provider": "simulated"},
    )
    assert res_ocr.status_code == 200
    ocr_data = res_ocr.json()
    assert ocr_data["provider"] == "simulated"
    assert ocr_data["confidence_score"] > 0.95
    assert len(ocr_data["regions"]) == 4

    # 2. Human Review verification by teacher
    review_payload = {
        "document_id": "doc-demo-1",
        "student_id": "user-student-1",
        "assessment_id": "asm-2",
        "verified_items": [
            {"item_index": 1, "marks": 4, "text": "Volume = 24 m3"},
            {"item_index": 2, "marks": 2, "text": "The reciprocal is -19/13"},
            {"item_index": 3, "marks": 3, "text": "Valid statement"},
            {"item_index": 4, "marks": 4, "text": "False. Quadratic scaling"},
        ],
        "teacher_notes": "Verified offline optical sheet handwriting transcription.",
    }
    res_review = await client.post(
        "/api/v1/ocr/review/verify",
        headers=headers,
        json=review_payload,
    )
    assert res_review.status_code == 200
    review_res = res_review.json()
    assert review_res["status"] == "approved"
    assert review_res["verified_marks"] == 13


@pytest.mark.asyncio
async def test_qwen_ocr_preview_accepts_multiple_files_and_passes_buffer(client, teacher_token, monkeypatch):
    paths = []
    options_seen = []

    class PreviewProvider:
        async def extract_document(self, document_path, options=None):
            paths.append(Path(document_path))
            options_seen.append(options)
            assert Path(document_path).exists()
            return {"extracted_text": "Recognized answer", "pages_processed": 1}

    monkeypatch.setattr(ocr_api, "get_ocr_provider", lambda _name: PreviewProvider())
    response = await client.post(
        "/api/v1/ocr/extract-preview",
        headers={"Authorization": f"Bearer {teacher_token}"},
        data={"wait_before_each_image": "true"},
        files=[
            ("files", ("first.png", b"first image", "image/png")),
            ("files", ("second.jpg", b"second image", "image/jpeg")),
        ],
    )

    assert response.status_code == 200
    result = response.json()
    assert [item["file_name"] for item in result["results"]] == ["first.png", "second.jpg"]
    assert all(item["extracted_text"] == "Recognized answer" for item in result["results"])
    assert [options["buffer_seconds"] for options in options_seen] == [5, 5]
    assert [options["file_name"] for options in options_seen] == ["first.png", "second.jpg"]
    assert all(not path.exists() for path in paths)


@pytest.mark.asyncio
async def test_qwen_ocr_preview_reports_unavailable_gpu_and_cleans_upload(
    client, teacher_token, monkeypatch
):
    paths = []

    class UnavailableProvider:
        async def extract_document(self, document_path, _options=None):
            paths.append(Path(document_path))
            raise QwenOCRUnavailableError("CUDA GPU is unavailable.")

    monkeypatch.setattr(ocr_api, "get_ocr_provider", lambda _name: UnavailableProvider())
    response = await client.post(
        "/api/v1/ocr/extract-preview",
        headers={"Authorization": f"Bearer {teacher_token}"},
        files=[("files", ("answer.png", b"image bytes", "image/png"))],
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "CUDA GPU is unavailable."
    assert len(paths) == 1
    assert not paths[0].exists()


@pytest.mark.asyncio
async def test_notifications_and_audit(client, admin_token, teacher_token):
    headers = {"Authorization": f"Bearer {teacher_token}"}
    res_notif = await client.get("/api/v1/notifications", headers=headers)
    assert res_notif.status_code == 200
    notifs = res_notif.json()
    assert len(notifs) >= 1

    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    res_audit = await client.get("/api/v1/audit/events", headers=admin_headers)
    assert res_audit.status_code == 200
    logs = res_audit.json()
    assert len(logs) >= 1
