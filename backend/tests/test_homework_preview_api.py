"""Tests for POST /api/v1/students/{student_id}/homework/preview.

Each test builds its own school data (subjects, classes, students, questions), so results
don't depend on seed data or on other tests.
"""
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import func, select, text

from backend.app.core.config import settings
from backend.app.core.security import create_access_token
from backend.app.models.entities import (
    AuditEvent,
    ClassSection,
    HomeworkRemediation,
    Notification,
    ParentStudentLink,
    QuestionBankItem,
    SchoolMembership,
    Student,
    StudentCompetencySnapshot,
    Subject,
    User,
)

URL = "/api/v1/students/{}/homework/preview"


def uid(prefix):
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


def body(subject_id, max_questions=3, **extra):
    return {"subject_id": subject_id, "max_questions": max_questions, "include_ai_generated": False, **extra}


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def bearer(user, role):
    return auth(create_access_token(user.id, school_id=user.school_id, role=role))


@pytest_asyncio.fixture
async def world(db_session):
    subj = Subject(id=uid("prev-subj"), name="Preview Subject", code=uid("PREV"), grade=8)
    empty_subj = Subject(id=uid("prev-empty"), name="Empty Subject", code=uid("EMPTY"), grade=8)
    other_subj = Subject(id=uid("prev-other"), name="Not Offered", code=uid("OTHER"), grade=8)

    cls = ClassSection(id=uid("prev-class"), school_id="school-1", grade=8, section="P", name="Preview Class",
                       subject_ids_json=[subj.id, empty_subj.id])
    cls3 = ClassSection(id=uid("prev-class3"), school_id="school-3", grade=8, section="Q", name="Other School",
                        subject_ids_json=[subj.id])

    def student(class_row, school, lu=40, cu=70, au=60, ct=50):
        return Student(id=uid("prev-student"), school_id=school, class_id=class_row.id, class_name=class_row.name,
                       name="Private Preview Name", roll_no=901, lu_score=lu, cu_score=cu, au_score=au,
                       ct_score=ct, overall_score=55)

    s1 = student(cls, "school-1")
    s3 = student(cls3, "school-3")
    bad = student(cls, "school-1", lu=150)

    def question(qid, competency, marks=2, ai=False, school="school-1", subject=None):
        return QuestionBankItem(id=qid, school_id=school, subject_id=subject or subj.id, text=f"Text of {qid}",
                                type="short", marks=marks, competency=competency, bloom_level="Apply",
                                correct_answer=f"SECRET-{qid}", marking_rubric="SECRET-RUBRIC", is_ai_generated=ai)

    p = uid("prevq")
    questions = [
        question(f"{p}-l1", "LU", 3), question(f"{p}-l2", "LU", 4), question(f"{p}-t1", "CT", 2),
        question(f"{p}-ai", "LU", 1, ai=True),
        question(f"{p}-x3", "LU", 2, school="school-3"),  # other school's bank, same subject
    ]

    parent = User(id=uid("prev-parent"), email=f"{uid('p')}@test.invalid", name="Parent", hashed_password="x",
                  role="parent", school_id="school-1")
    member = User(id=uid("prev-member"), email=f"{uid('m')}@test.invalid", name="Member", hashed_password="x",
                  role="teacher", school_id="school-3")
    link = ParentStudentLink(id=uid("prev-link"), parent_user_id=parent.id, student_id=s1.id)
    membership = SchoolMembership(id=uid("prev-mem"), user_id=member.id, school_id="school-1", role="teacher",
                                  is_active=True)

    rows = [subj, empty_subj, other_subj, cls, cls3, s1, s3, bad, *questions, parent, member, link, membership]
    db_session.add_all(rows)
    await db_session.commit()

    yield {"subj": subj, "empty": empty_subj, "other": other_subj, "cls": cls, "s1": s1, "s3": s3, "bad": bad,
           "p": p, "parent": parent, "member": member}

    for row in reversed(rows):
        await db_session.delete(row)
    await db_session.commit()


# --- Success -------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_teacher_gets_draft_for_student_in_school(client, teacher_token, world):
    res = await client.post(URL.format(world["s1"].id), json=body(world["subj"].id), headers=auth(teacher_token))

    assert res.status_code == 200
    draft = res.json()
    p = world["p"]
    assert draft["student_id"] == world["s1"].id
    assert draft["school_id"] == "school-1"  # from the student record, not the client
    assert draft["subject_id"] == world["subj"].id
    assert [i["question_id"] for i in draft["items"]] == [f"{p}-l1", f"{p}-l2", f"{p}-t1"]
    assert [i["position"] for i in draft["items"]] == [1, 2, 3]
    assert draft["total_marks"] == 9 and draft["question_count"] == 3 and draft["is_complete"]
    assert draft["rationale"]["targeted_competencies"] == ["LU", "CT"]
    assert "SECRET" not in res.text and "Private Preview Name" not in res.text


@pytest.mark.asyncio
async def test_principal_and_admin_can_preview(client, principal_token, admin_token, world):
    for token in (principal_token, admin_token):
        res = await client.post(URL.format(world["s1"].id), json=body(world["subj"].id), headers=auth(token))
        assert res.status_code == 200


@pytest.mark.asyncio
async def test_teacher_with_active_membership_can_preview(client, world):
    res = await client.post(URL.format(world["s1"].id), json=body(world["subj"].id),
                            headers=bearer(world["member"], "teacher"))
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_questions_come_only_from_the_students_school(client, admin_token, world):
    res = await client.post(URL.format(world["s3"].id), json=body(world["subj"].id, 5), headers=auth(admin_token))

    assert res.status_code == 200
    assert [i["question_id"] for i in res.json()["items"]] == [f"{world['p']}-x3"]


# --- Request validation ------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {"max_questions": 3, "include_ai_generated": False},  # no subject_id
        {"subject_id": "", "max_questions": 3, "include_ai_generated": False},
        {"subject_id": "s", "include_ai_generated": False},  # no max_questions
        {"subject_id": "s", "max_questions": 0, "include_ai_generated": False},
        {"subject_id": "s", "max_questions": "3", "include_ai_generated": False},
        {"subject_id": "s", "max_questions": 2.5, "include_ai_generated": False},
        {"subject_id": "s", "max_questions": 3, "max_total_marks": 0, "include_ai_generated": False},
        {"subject_id": "s", "max_questions": 3},  # no include_ai_generated
        {"subject_id": "s", "max_questions": 3, "include_ai_generated": "true"},
        {"subject_id": "s", "max_questions": 3, "include_ai_generated": 1},
        {"subject_id": "s", "max_questions": 3, "include_ai_generated": False, "school_id": "school-3"},
    ],
)
async def test_invalid_request_bodies_are_rejected(client, teacher_token, world, payload):
    res = await client.post(URL.format(world["s1"].id), json=payload, headers=auth(teacher_token))
    assert res.status_code == 422


# --- Authorization -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_other_school_teacher_is_denied(client, other_school_teacher_token, world):
    res = await client.post(URL.format(world["s1"].id), json=body(world["subj"].id),
                            headers=auth(other_school_teacher_token))
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_linked_parent_cannot_generate(client, world):
    res = await client.post(URL.format(world["s1"].id), json=body(world["subj"].id),
                            headers=bearer(world["parent"], "parent"))
    assert res.status_code == 403


@pytest.mark.asyncio
@pytest.mark.parametrize("target", ["user-student-1", "s1", "no-such-student"])
async def test_students_are_denied(client, student_token, world, target):
    student_id = world["s1"].id if target == "s1" else target
    res = await client.post(URL.format(student_id), json=body(world["subj"].id), headers=auth(student_token))
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_missing_token_rejected_when_demo_mode_off(client, world):
    previous = settings.DEMO_MODE
    settings.DEMO_MODE = False
    try:
        res = await client.post(URL.format(world["s1"].id), json=body(world["subj"].id))
        assert res.status_code == 401
    finally:
        settings.DEMO_MODE = previous


# --- Invalid student and subject -------------------------------------------------------------


@pytest.mark.asyncio
async def test_unknown_student_returns_404(client, teacher_token, world):
    res = await client.post(URL.format("no-such-student"), json=body(world["subj"].id), headers=auth(teacher_token))
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_unknown_subject_returns_404(client, teacher_token, world):
    res = await client.post(URL.format(world["s1"].id), json=body("no-such-subject"), headers=auth(teacher_token))
    assert res.status_code == 404
    assert res.json()["detail"] == "Subject not found."


@pytest.mark.asyncio
async def test_subject_not_offered_in_students_class_returns_422(client, teacher_token, world):
    res = await client.post(URL.format(world["s1"].id), json=body(world["other"].id), headers=auth(teacher_token))
    assert res.status_code == 422
    assert res.json()["detail"] == "This subject isn't offered in the student's class."


@pytest.mark.asyncio
async def test_invalid_stored_scores_return_safe_error(client, teacher_token, world):
    res = await client.post(URL.format(world["bad"].id), json=body(world["subj"].id), headers=auth(teacher_token))
    assert res.status_code == 500
    assert "150" not in res.text


# --- Selection outcomes ------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_empty_question_bank_gives_empty_draft(client, teacher_token, world):
    res = await client.post(URL.format(world["s1"].id), json=body(world["empty"].id, 3), headers=auth(teacher_token))

    assert res.status_code == 200
    draft = res.json()
    assert draft["items"] == [] and draft["shortfall"] == 3 and not draft["is_complete"]


@pytest.mark.asyncio
async def test_shortfall_is_reported(client, teacher_token, world):
    res = await client.post(URL.format(world["s1"].id), json=body(world["subj"].id, 10), headers=auth(teacher_token))

    draft = res.json()
    assert draft["question_count"] == 3 and draft["shortfall"] == 7 and not draft["is_complete"]


@pytest.mark.asyncio
async def test_ai_questions_only_when_requested(client, teacher_token, world):
    p = world["p"]
    url = URL.format(world["s1"].id)

    without = (await client.post(url, json=body(world["subj"].id, 4), headers=auth(teacher_token))).json()
    assert f"{p}-ai" not in [i["question_id"] for i in without["items"]]
    assert not without["contains_ai_generated"]

    with_ai = await client.post(url, json=body(world["subj"].id, 4, include_ai_generated=True),
                                headers=auth(teacher_token))
    ids = [i["question_id"] for i in with_ai.json()["items"]]
    assert f"{p}-ai" in ids and with_ai.json()["contains_ai_generated"]


@pytest.mark.asyncio
async def test_marks_limit_is_applied(client, teacher_token, world):
    res = await client.post(URL.format(world["s1"].id), json=body(world["subj"].id, 3, max_total_marks=5),
                            headers=auth(teacher_token))

    draft = res.json()
    assert draft["max_total_marks"] == 5 and draft["total_marks"] <= 5
    assert [i["question_id"] for i in draft["items"]] == [f"{world['p']}-l1", f"{world['p']}-t1"]


@pytest.mark.asyncio
async def test_malformed_question_row_is_skipped_and_noted(client, db_session, teacher_token, world):
    bad_id = f"{world['p']}-malformed"
    await db_session.execute(
        text(
            "INSERT INTO question_bank_items (id, school_id, subject_id, text, type, options_json, marks, "
            "competency, bloom_level, source_document_ids_json, source_document_names_json, is_ai_generated, "
            "created_at) VALUES (:id, 'school-1', :subject, 'Bad row', 'short', '[]', 'two', 'LU', 'Apply', "
            "'[]', '[]', 0, '2026-01-01 00:00:00')"
        ),
        {"id": bad_id, "subject": world["subj"].id},
    )
    await db_session.commit()
    try:
        res = await client.post(URL.format(world["s1"].id), json=body(world["subj"].id), headers=auth(teacher_token))
        assert res.status_code == 200
        assert bad_id not in res.text
        assert any("couldn't be read" in note for note in res.json()["notes"])
    finally:
        await db_session.execute(text("DELETE FROM question_bank_items WHERE id = :id"), {"id": bad_id})
        await db_session.commit()


# --- Read-only ------------------------------------------------------------------------------------


async def table_counts(db):
    models = (Student, StudentCompetencySnapshot, AuditEvent, HomeworkRemediation, Notification,
              QuestionBankItem, ClassSection, Subject)
    return {m.__tablename__: await db.scalar(select(func.count()).select_from(m)) for m in models}


@pytest.mark.asyncio
async def test_preview_writes_nothing(client, db_session, teacher_token, other_school_teacher_token, world):
    s1 = world["s1"]
    before = await table_counts(db_session)

    responses = [
        await client.post(URL.format(s1.id), json=body(world["subj"].id), headers=auth(teacher_token)),
        await client.post(URL.format(s1.id), json=body(world["other"].id), headers=auth(teacher_token)),
        await client.post(URL.format(s1.id), json=body(world["subj"].id), headers=auth(other_school_teacher_token)),
        await client.post(URL.format(world["bad"].id), json=body(world["subj"].id), headers=auth(teacher_token)),
    ]
    assert [r.status_code for r in responses] == [200, 422, 403, 500]

    assert await table_counts(db_session) == before
    await db_session.refresh(s1)
    assert (s1.lu_score, s1.cu_score, s1.au_score, s1.ct_score) == (40, 70, 60, 50)
