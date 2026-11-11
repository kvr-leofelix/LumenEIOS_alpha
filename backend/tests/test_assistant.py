import json

import httpx
import pytest

from backend.app.api.v1 import assistant

URL = "/api/v1/assistant/chat"


@pytest.mark.asyncio
async def test_assistant_scopes_parent_records_and_navigation(client, parent_token, monkeypatch):
    captured = {}

    async def answer(self, url, *, json):
        captured.update(json)
        return httpx.Response(200, request=httpx.Request("POST", url), json={
            "message": {"content": '{"answer":"Progress overview","page":"School subscription"}'},
        })

    monkeypatch.setattr(httpx.AsyncClient, "post", answer)
    response = await client.request(
        "POST", URL, json={"message": "How is my child doing?"},
        headers={"Authorization": f"Bearer {parent_token}"},
    )
    assert response.status_code == 200
    assert response.json()["links"] == []
    payload = json.loads(captured["messages"][0]["content"].split("\n", 1)[1])
    assert payload["pages"] == ["Child progress"]
    assert payload["records"]["student_count"] == 2
    assert payload["records"]["classes"] == []


@pytest.mark.asyncio
async def test_assistant_denies_unauthenticated_requests_and_unassigned_schools(client, teacher_token):
    assert (await client.post(URL, json={"message": "Show scores"})).status_code == 401
    assert (await client.post(URL, json={"message": "Show scores"}, headers={
        "Authorization": f"Bearer {teacher_token}", "X-School-Id": "unassigned-school",
    })).status_code == 403


@pytest.mark.asyncio
async def test_teacher_context_excludes_other_teachers_classes(db_session):
    from backend.app.models.entities import User

    teacher = await db_session.get(User, "user-teacher-1")
    context = await assistant.assistant_context(db_session, teacher, "school-1")
    assert context["classes"]
    other_teacher = await db_session.get(User, "user-teacher-2")
    other = await assistant.assistant_context(db_session, other_teacher, "school-1")
    assert other["classes"]
    assert {item["name"] for item in context["classes"]}.isdisjoint(
        item["name"] for item in other["classes"]
    )


@pytest.mark.asyncio
async def test_principal_quote_links_to_review_with_teacher_count(client, principal_token):
    response = await client.post(
        URL, json={"message": "What does a PayPal subscription for 12 teachers cost?"},
        headers={"Authorization": f"Bearer {principal_token}"},
    )
    assert response.status_code == 200
    assert "USD 80.00" in response.json()["answer"]
    assert response.json()["links"] == [{
        "label": "School subscription",
        "path": "/principal/subscription?teacherSeats=12",
    }]


@pytest.mark.asyncio
async def test_student_and_admin_receive_scoped_context(db_session):
    from backend.app.models.entities import User
    from backend.app.modules.differentiated_homework.student_access import resolve_linked_student

    user = await db_session.get(User, "user-student-1")
    student = await resolve_linked_student(db_session, user)
    assert student is not None
    context = await assistant.assistant_context(db_session, user, "unassigned-school")
    assert [record["name"] for record in context["students"]] == [student.name]
    assert context["classes"] == []

    admin = await db_session.get(User, "user-admin")
    context = await assistant.assistant_context(db_session, admin, None)
    assert context["schools"]
    assert all(set(school) == {"name", "student_count", "average_overall"} for school in context["schools"])


@pytest.mark.asyncio
async def test_school_search_returns_only_retrieved_citations(client, teacher_token, student_token, monkeypatch):
    monkeypatch.setattr(assistant.settings, "ELASTICSEARCH_URL", "http://elastic.test")

    async def search(db, school_id, message):
        assert school_id == "school-1"
        return [{"document_id": "policy-1", "name": "Policy.pdf", "page": 3, "text": "One retake is allowed."}]

    async def generate(self, url, *, json):
        assert "One retake is allowed." in json["messages"][0]["content"]
        return httpx.Response(200, request=httpx.Request("POST", url), json={
            "message": {"content": '{"answer":"One retake is allowed.","citations":[1,2]}'},
        })

    monkeypatch.setattr(assistant, "search_documents", search)
    monkeypatch.setattr(httpx.AsyncClient, "post", generate)
    body = {"message": "Can I retake?", "search_library": True}
    for token, code in ((teacher_token, 200), (student_token, 403)):
        response = await client.request("POST", URL, json=body, headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == code
        if code == 200:
            assert response.json()["citations"] == [{"document_id": "policy-1", "name": "Policy.pdf", "page": 3}]


def test_pdf_passages_keep_original_page_number(tmp_path):
    import pymupdf
    from backend.app.services.document_search import pdf_passages

    path = tmp_path / "policy.pdf"
    with pymupdf.open() as pdf:
        pdf.new_page()
        pdf.new_page().insert_text((72, 72), "One retake is allowed.")
        pdf.save(path)
    assert pdf_passages(path) == [(2, 0, "One retake is allowed.")]
