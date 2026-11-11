"""Tests for student account links and the student-facing homework endpoints.

Students are identified only through an admin-created StudentAccountLink, never by
User.id == Student.id. Each test builds its own users, students, drafts and assignments.
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import func, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine

from backend.app.core.config import settings
from backend.app.core.security import create_access_token
from backend.app.db.session import Base
from backend.app.models.entities import ClassSection, ParentStudentLink, Student, Subject, User
from backend.app.modules.differentiated_homework.models import (
    HomeworkAssignmentRecord,
    HomeworkDraftItemRecord,
    HomeworkDraftRecord,
    StudentAccountLink,
)

MINE = "/api/v1/students/me/homework/assignments"
MINE_ONE = "/api/v1/students/me/homework/assignments/{}"
LINKS = "/api/v1/student-account-links"


def uid(prefix):
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


def bearer(user_id, role, school_id=None):
    return {"Authorization": f"Bearer {create_access_token(user_id, school_id=school_id, role=role)}"}


def make_user(role, school_id):
    user_id = uid(f"sha-{role}")
    return User(id=user_id, email=f"{user_id}@test.invalid", name=f"Test {role}", hashed_password="x",
                role=role, school_id=school_id)


def make_student(cls, school_id, name):
    return Student(id=uid("sha-student"), school_id=school_id, class_id=cls.id, class_name=cls.name, name=name,
                   roll_no=1, lu_score=40, cu_score=70, au_score=60, ct_score=50, overall_score=55)


def assigned_draft(student, subject_id, assigned_at, created_by="user-teacher-1", marks=(3, 2)):
    """An assigned draft with secret answers, plus its assignment, built directly."""
    draft = HomeworkDraftRecord(
        student_id=student.id, school_id=student.school_id, subject_id=subject_id, created_by=created_by,
        status="assigned", requested_questions=len(marks), include_ai_generated=False,
        question_count=len(marks), total_marks=sum(marks), shortfall=0, notes_json=["teacher-only note"],
        rationale_json={"targeted_competencies": ["LU"], "weakest": ["LU"],
                        "competency_scores": {"LU": 40, "CU": 70, "AU": 60, "CT": 50},
                        "lowest_score": 40, "highest_score": 70, "score_source": "test",
                        "summary": "TEACHER-ONLY-RATIONALE"},
        reviewed_by="user-teacher-1", review_note="TEACHER-ONLY-REVIEW",
        items=[
            HomeworkDraftItemRecord(position=i, source_question_id=uid("src"), text=f"{student.name} question {i}",
                                    type="mcq" if i == 1 else "short", options_json=["A", "B"] if i == 1 else [],
                                    marks=m, competency="LU", competency_rank=1, bloom_level="Apply",
                                    is_ai_generated=False, correct_answer="SECRET-ANSWER",
                                    marking_rubric="SECRET-RUBRIC")
            for i, m in enumerate(marks, start=1)
        ],
    )
    assignment = HomeworkAssignmentRecord(
        draft=draft, student_id=student.id, school_id=student.school_id, subject_id=subject_id,
        assigned_by=created_by, assigned_at=assigned_at, due_at=assigned_at + timedelta(days=7), status="assigned",
    )
    return draft, assignment


@pytest_asyncio.fixture
async def world(db_session):
    subj = Subject(id=uid("sha-subj"), name="Student Access Maths", code=uid("SHA"), grade=8)
    cls1 = ClassSection(id=uid("sha-c1"), school_id="school-1", grade=8, section="S", name="Access 1",
                        subject_ids_json=[subj.id])
    cls3 = ClassSection(id=uid("sha-c3"), school_id="school-3", grade=8, section="T", name="Access 3",
                        subject_ids_json=[subj.id])
    alice = make_student(cls1, "school-1", "Alice")
    bob = make_student(cls1, "school-1", "Bob")
    cara = make_student(cls3, "school-3", "Cara")

    u_alice, u_bob, u_cara = make_user("student", "school-1"), make_user("student", "school-1"), make_user("student", "school-3")
    u_unlinked = make_user("student", "school-1")
    u_parent = make_user("parent", "school-1")

    now = datetime(2026, 11, 1, 9, 0, tzinfo=timezone.utc)
    d_a_old, a_alice_old = assigned_draft(alice, subj.id, now)
    d_a_new, a_alice_new = assigned_draft(alice, subj.id, now + timedelta(days=2))
    d_b, a_bob = assigned_draft(bob, subj.id, now + timedelta(days=1))
    d_c, a_cara = assigned_draft(cara, subj.id, now + timedelta(days=1), created_by="user-teacher-3")

    links = [
        StudentAccountLink(user_id=u_alice.id, student_id=alice.id, created_by="user-admin"),
        StudentAccountLink(user_id=u_bob.id, student_id=bob.id, created_by="user-admin"),
        StudentAccountLink(user_id=u_cara.id, student_id=cara.id, created_by="user-admin"),
    ]
    parent_link = ParentStudentLink(id=uid("sha-plink"), parent_user_id=u_parent.id, student_id=alice.id)

    db_session.add_all([subj, cls1, cls3, alice, bob, cara, u_alice, u_bob, u_cara, u_unlinked, u_parent,
                        d_a_old, d_a_new, d_b, d_c, a_alice_old, a_alice_new, a_bob, a_cara, *links, parent_link])
    await db_session.commit()

    ids = {
        "students": [alice.id, bob.id, cara.id],
        "users": [u_alice.id, u_bob.id, u_cara.id, u_unlinked.id, u_parent.id],
        "classes": [cls1.id, cls3.id], "subject": subj.id,
    }
    yield {
        "subj": subj, "alice": alice, "bob": bob, "cara": cara,
        "u_alice": u_alice, "u_bob": u_bob, "u_cara": u_cara, "u_unlinked": u_unlinked, "u_parent": u_parent,
        "a_alice_old": a_alice_old.id, "a_alice_new": a_alice_new.id, "a_bob": a_bob.id, "a_cara": a_cara.id,
    }

    await db_session.rollback()
    for student_id in ids["students"]:
        p = {"s": student_id}
        for sql in (
            "DELETE FROM student_account_links WHERE student_id = :s",
            "DELETE FROM parent_student_links WHERE student_id = :s",
            "DELETE FROM homework_assignments WHERE student_id = :s",
            "DELETE FROM homework_draft_items WHERE draft_id IN (SELECT id FROM homework_drafts WHERE student_id = :s)",
            "DELETE FROM homework_drafts WHERE student_id = :s",
            "DELETE FROM students WHERE id = :s",
        ):
            await db_session.execute(text(sql), p)
    for user_id in ids["users"]:
        await db_session.execute(text("DELETE FROM student_account_links WHERE user_id = :u"), {"u": user_id})
        await db_session.execute(text("DELETE FROM users WHERE id = :u"), {"u": user_id})
    for class_id in ids["classes"]:
        await db_session.execute(text("DELETE FROM classes WHERE id = :c"), {"c": class_id})
    await db_session.execute(text("DELETE FROM subjects WHERE id = :j"), {"j": ids["subject"]})
    await db_session.commit()


def as_student(world, key):
    user = world[key]
    return bearer(user.id, "student", user.school_id)


# --- Own assignments ----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_student_sees_only_their_own_assignments_newest_first(client, world):
    res = await client.get(MINE, headers=as_student(world, "u_alice"))

    assert res.status_code == 200
    body = res.json()
    assert [a["id"] for a in body] == [world["a_alice_new"], world["a_alice_old"]]
    first = body[0]
    assert set(first) == {"id", "subject_id", "subject_name", "status", "assigned_at", "due_at",
                          "question_count", "total_marks"}
    assert first["subject_name"] == "Student Access Maths" and first["status"] == "assigned"
    assert first["question_count"] == 2 and first["total_marks"] == 5
    assert first["assigned_at"].endswith("Z") or first["assigned_at"].endswith("+00:00")


@pytest.mark.asyncio
async def test_student_assignment_detail_has_questions_but_no_hidden_data(client, world):
    res = await client.get(MINE_ONE.format(world["a_alice_new"]), headers=as_student(world, "u_alice"))

    assert res.status_code == 200
    body = res.json()
    assert [i["position"] for i in body["items"]] == [1, 2]
    assert body["items"][0] == {"position": 1, "text": "Alice question 1", "type": "mcq", "options": ["A", "B"],
                                "marks": 3}
    assert set(body["items"][1]) == {"position", "text", "type", "options", "marks"}
    for hidden in ("SECRET", "TEACHER-ONLY", "competency", "rubric", "correct_answer", "source_question_id",
                   "draft_id", "assigned_by", "school_id", "reviewed", "user-teacher-1", "bloom"):
        assert hidden not in res.text, hidden


@pytest.mark.asyncio
async def test_status_filter(client, world):
    headers = as_student(world, "u_alice")
    assert len((await client.get(MINE, params={"status": "assigned"}, headers=headers)).json()) == 2
    assert (await client.get(MINE, params={"status": "submitted"}, headers=headers)).status_code == 422


# --- Isolation ----------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_student_cannot_open_another_students_assignment(client, world):
    headers = as_student(world, "u_alice")
    for other in (world["a_bob"], world["a_cara"], "no-such-assignment"):
        res = await client.get(MINE_ONE.format(other), headers=headers)
        assert res.status_code == 404 and res.json()["detail"] == "Assignment not found."
        assert "Bob" not in res.text and "Cara" not in res.text


@pytest.mark.asyncio
async def test_school_and_student_isolation(client, world):
    def ids(res):
        return [a["id"] for a in res.json()]

    assert ids(await client.get(MINE, headers=as_student(world, "u_bob"))) == [world["a_bob"]]
    assert ids(await client.get(MINE, headers=as_student(world, "u_cara"))) == [world["a_cara"]]


# --- Identity and roles -------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_student_account_without_a_link_is_refused(client, world):
    headers = as_student(world, "u_unlinked")
    for url in (MINE, MINE_ONE.format(world["a_alice_new"])):
        res = await client.get(url, headers=headers)
        assert res.status_code == 403 and res.json()["detail"] == "This account isn't linked to a student record."


@pytest.mark.asyncio
async def test_same_id_shortcut_is_not_used(client, db_session, world):
    """A student account whose ID equals a Student.id, but with no link, gets nothing."""
    twin = User(id=world["bob"].id, email=f"{uid('twin')}@test.invalid", name="Twin", hashed_password="x",
                role="student", school_id="school-1")
    db_session.add(twin)
    await db_session.commit()
    try:
        res = await client.get(MINE, headers=bearer(twin.id, "student", "school-1"))
        assert res.status_code == 403
    finally:
        await db_session.execute(text("DELETE FROM users WHERE id = :u"), {"u": twin.id})
        await db_session.commit()


@pytest.mark.asyncio
async def test_seeded_student_account_is_linked(client, student_token):
    response = await client.get(MINE, headers={"Authorization": f"Bearer {student_token}"})
    assert response.status_code == 200



@pytest.mark.asyncio
async def test_non_student_roles_are_refused(client, world, teacher_token, principal_token, admin_token,
                                             parent_token, other_school_teacher_token):
    linked_parent = bearer(world["u_parent"].id, "parent", "school-1")
    tokens = [teacher_token, principal_token, admin_token, parent_token, other_school_teacher_token]
    for headers in [{"Authorization": f"Bearer {t}"} for t in tokens] + [linked_parent]:
        for url in (MINE, MINE_ONE.format(world["a_alice_new"])):
            assert (await client.get(url, headers=headers)).status_code == 403


@pytest.mark.asyncio
async def test_parent_keeps_existing_access_through_parent_link(client, world):
    """Parents use the existing parent-gated endpoint, unchanged; not the student endpoints."""
    headers = bearer(world["u_parent"].id, "parent", "school-1")
    res = await client.get(f"/api/v1/students/{world['alice'].id}/homework/gap-analysis", headers=headers)
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_role_must_match_exactly(client, db_session, world):
    """An account with a valid link but a role of 'Student' (capitalised) is still refused."""
    class_id = (await db_session.execute(
        select(ClassSection.id).filter(ClassSection.id.like("sha-c1-%")))).scalars().first()
    cls = await db_session.get(ClassSection, class_id)
    odd = make_user("Student", "school-1")
    student = make_student(cls, "school-1", "Eve")
    odd_id, student_id = odd.id, student.id  # captured before any commit or rollback
    db_session.add_all([odd, student])
    await db_session.commit()
    db_session.add(StudentAccountLink(user_id=odd_id, student_id=student_id, created_by="user-admin"))
    await db_session.commit()
    try:
        assert (await client.get(MINE, headers=bearer(odd_id, "student", "school-1"))).status_code == 403
    finally:
        await db_session.execute(text("DELETE FROM student_account_links WHERE user_id = :u"), {"u": odd_id})
        await db_session.execute(text("DELETE FROM students WHERE id = :s"), {"s": student_id})
        await db_session.execute(text("DELETE FROM users WHERE id = :u"), {"u": odd_id})
        await db_session.commit()


@pytest.mark.asyncio
async def test_account_school_must_still_match_the_student(client, db_session, world):
    await db_session.execute(text("UPDATE users SET school_id = 'school-3' WHERE id = :u"), {"u": world["u_alice"].id})
    await db_session.commit()
    res = await client.get(MINE, headers=bearer(world["u_alice"].id, "student", "school-3"))
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_teacher_endpoints_stay_closed_to_linked_students(client, world):
    headers = as_student(world, "u_alice")
    assert (await client.get("/api/v1/homework/assignments", headers=headers)).status_code == 403
    assert (await client.get(f"/api/v1/homework/assignments/{world['a_alice_new']}", headers=headers)).status_code == 403
    assert (await client.get("/api/v1/homework/drafts", headers=headers)).status_code == 403


# --- Authentication ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("header", [None, "Bearer not-a-jwt", "Basic dXNlcjpwYXNz"])
async def test_missing_or_invalid_authentication(client, world, header):
    previous = settings.DEMO_MODE
    settings.DEMO_MODE = False
    try:
        headers = {"Authorization": header} if header else {}
        res = await client.get(MINE, headers=headers)
        assert res.status_code == 401
    finally:
        settings.DEMO_MODE = previous


@pytest.mark.asyncio
async def test_demo_mode_without_token_does_not_act_as_a_student(client, world):
    # Existing shared behaviour: no token in DEMO_MODE means admin, which these endpoints refuse.
    assert settings.DEMO_MODE is True
    assert (await client.get(MINE)).status_code == 403


# --- Admin link management ---------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_links_an_account_and_access_starts(client, db_session, admin_token, world):
    user = make_user("student", "school-1")
    student = make_student(await db_session.get(ClassSection, (await db_session.execute(
        select(ClassSection.id).filter(ClassSection.id.like("sha-c1-%")))).scalars().first()), "school-1", "Dina")
    db_session.add_all([user, student])
    await db_session.commit()
    try:
        headers = bearer(user.id, "student", "school-1")
        assert (await client.get(MINE, headers=headers)).status_code == 403

        res = await client.post(LINKS, json={"user_id": user.id, "student_id": student.id},
                                headers={"Authorization": f"Bearer {admin_token}"})
        assert res.status_code == 201
        assert res.json()["user_id"] == user.id and res.json()["created_by"] == "user-admin"

        assert (await client.get(MINE, headers=headers)).json() == []  # linked, no homework yet
        audit = await db_session.scalar(text(
            "SELECT COUNT(*) FROM audit_events WHERE action = 'Student Account Linked' AND details LIKE :d"),
            {"d": f"%{user.id}%"})
        assert audit == 1

        deleted = await client.delete(f"{LINKS}/{res.json()['id']}", headers={"Authorization": f"Bearer {admin_token}"})
        assert deleted.status_code == 204
        assert (await client.get(MINE, headers=headers)).status_code == 403
    finally:
        await db_session.execute(text("DELETE FROM student_account_links WHERE user_id = :u"), {"u": user.id})
        await db_session.execute(text("DELETE FROM students WHERE id = :s"), {"s": student.id})
        await db_session.execute(text("DELETE FROM users WHERE id = :u"), {"u": user.id})
        await db_session.commit()


@pytest.mark.asyncio
async def test_link_validation(client, admin_token, world):
    admin = {"Authorization": f"Bearer {admin_token}"}

    async def post(payload):
        return await client.post(LINKS, json=payload, headers=admin)

    assert (await post({"user_id": world["u_alice"].id, "student_id": world["bob"].id})).status_code == 409
    assert (await post({"user_id": world["u_unlinked"].id, "student_id": world["alice"].id})).status_code == 409
    assert (await post({"user_id": world["u_parent"].id, "student_id": world["alice"].id})).status_code == 422
    assert (await post({"user_id": world["u_unlinked"].id, "student_id": world["cara"].id})).status_code == 422
    assert (await post({"user_id": "no-such-user", "student_id": world["alice"].id})).status_code == 404
    assert (await post({"user_id": world["u_unlinked"].id, "student_id": "no-such-student"})).status_code == 404
    assert (await post({"user_id": world["u_unlinked"].id, "student_id": world["alice"].id,
                        "school_id": "x"})).status_code == 422
    assert (await post({"user_id": "", "student_id": world["alice"].id})).status_code == 422
    assert (await client.delete(f"{LINKS}/no-such-link", headers=admin)).status_code == 404


@pytest.mark.asyncio
async def test_only_admins_manage_links(client, world, teacher_token, principal_token, parent_token):
    payload = {"user_id": world["u_unlinked"].id, "student_id": world["alice"].id}
    others = [{"Authorization": f"Bearer {t}"} for t in (teacher_token, principal_token, parent_token)]
    for headers in others + [as_student(world, "u_alice")]:
        assert (await client.post(LINKS, json=payload, headers=headers)).status_code == 403
        assert (await client.delete(f"{LINKS}/anything", headers=headers)).status_code == 403


@pytest.mark.asyncio
async def test_database_enforces_one_to_one_links(db_session, world):
    # Captured first: the rollbacks below expire the fixture objects.
    alice_user, unlinked_user = world["u_alice"].id, world["u_unlinked"].id
    alice = world["alice"].id

    # Only the account rule is broken here: the student ID has no link (foreign keys are off,
    # so it needn't exist), but Alice's account already has one.
    db_session.add(StudentAccountLink(user_id=alice_user, student_id=uid("unlinked-student"), created_by="x"))
    with pytest.raises(IntegrityError, match="student_account_links.user_id"):
        await db_session.commit()
    await db_session.rollback()

    db_session.add(StudentAccountLink(user_id=unlinked_user, student_id=alice, created_by="x"))
    with pytest.raises(IntegrityError, match="student_account_links.student_id"):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_student_endpoints_write_nothing(client, db_session, world):
    async def counts():
        return [await db_session.scalar(select(func.count()).select_from(m))
                for m in (HomeworkAssignmentRecord, HomeworkDraftRecord, StudentAccountLink)]

    before = await counts()
    await client.get(MINE, headers=as_student(world, "u_alice"))
    await client.get(MINE_ONE.format(world["a_alice_new"]), headers=as_student(world, "u_alice"))
    await client.get(MINE_ONE.format(world["a_bob"]), headers=as_student(world, "u_alice"))
    assert await counts() == before


# --- Table creation on an existing database --------------------------------------------------------


@pytest.mark.asyncio
async def test_create_all_adds_link_table_without_touching_existing_tables(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{(tmp_path / 'old.db').as_posix()}")
    old_tables = [t for n, t in Base.metadata.tables.items() if n != "student_account_links"]
    try:
        async with engine.begin() as conn:
            await conn.run_sync(lambda c: Base.metadata.create_all(c, tables=old_tables))
            await conn.execute(text(
                "INSERT INTO schools (id, name, location, state, infrastructure_tier, academic_year, student_count, "
                "teacher_count, class_count, pacing_risk, official_working_days, is_archived, created_at) VALUES "
                "('keep', 'Kept School', 'L', 'S', 'standard', '2026', 0, 0, 0, 'low', 220, 0, '2026-01-01')"))
            student_cols = await conn.run_sync(lambda c: [col["name"] for col in inspect(c).get_columns("students")])
        for _ in range(2):
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
        async with engine.connect() as conn:
            tables = await conn.run_sync(lambda c: inspect(c).get_table_names())
            student_cols_after = await conn.run_sync(lambda c: [col["name"] for col in inspect(c).get_columns("students")])
            kept = (await conn.execute(text("SELECT name FROM schools WHERE id = 'keep'"))).scalar()
        assert "student_account_links" in tables and kept == "Kept School"
        assert student_cols_after == student_cols  # the existing students table wasn't altered
    finally:
        await engine.dispose()


# --- Link request schema and lifecycle ----------------------------------------------------------


async def fresh_pair(db_session, name):
    """A new student account and Student record in school-1, not linked. Returns their IDs."""
    class_id = (await db_session.execute(
        select(ClassSection.id).filter(ClassSection.id.like("sha-c1-%")))).scalars().first()
    cls = await db_session.get(ClassSection, class_id)
    user, student = make_user("student", "school-1"), make_student(cls, "school-1", name)
    user_id, student_id = user.id, student.id  # captured before commit expires the objects
    db_session.add_all([user, student])
    await db_session.commit()
    return user_id, student_id


async def remove_pair(db_session, user_ids, student_ids):
    for u in user_ids:
        await db_session.execute(text("DELETE FROM student_account_links WHERE user_id = :u"), {"u": u})
        await db_session.execute(text("DELETE FROM users WHERE id = :u"), {"u": u})
    for s in student_ids:
        await db_session.execute(text("DELETE FROM student_account_links WHERE student_id = :s"), {"s": s})
        await db_session.execute(text("DELETE FROM students WHERE id = :s"), {"s": s})
    await db_session.commit()


@pytest.mark.asyncio
async def test_link_request_schema_and_returned_mapping(client, db_session, admin_token, world):
    schema = (await client.get("/api/v1/openapi.json")).json()["components"]["schemas"]["StudentAccountLinkCreate"]
    assert sorted(schema["required"]) == ["student_id", "user_id"]
    assert schema["additionalProperties"] is False
    assert schema["properties"]["user_id"]["minLength"] == 1 and schema["properties"]["student_id"]["minLength"] == 1

    admin = {"Authorization": f"Bearer {admin_token}"}
    user_id, student_id = await fresh_pair(db_session, "Finn")
    try:
        assert (await client.post(LINKS, json={"user_id": user_id}, headers=admin)).status_code == 422
        assert (await client.post(LINKS, json={"student_id": student_id}, headers=admin)).status_code == 422
        assert (await client.post(LINKS, json={"user_id": user_id, "student_id": 5}, headers=admin)).status_code == 422

        res = await client.post(LINKS, json={"user_id": user_id, "student_id": student_id}, headers=admin)
        assert res.status_code == 201
        body = res.json()
        assert set(body) == {"id", "user_id", "student_id", "created_by", "created_at"}
        assert (body["user_id"], body["student_id"], body["created_by"]) == (user_id, student_id, "user-admin")
        assert body["created_at"].endswith("Z") or body["created_at"].endswith("+00:00")
        row = (await db_session.execute(text(
            "SELECT user_id, student_id FROM student_account_links WHERE id = :i"), {"i": body["id"]})).one()
        assert tuple(row) == (user_id, student_id)
    finally:
        await remove_pair(db_session, [user_id], [student_id])


@pytest.mark.asyncio
async def test_unlink_then_relink(client, db_session, admin_token, world):
    admin = {"Authorization": f"Bearer {admin_token}"}
    user_id, student_id = await fresh_pair(db_session, "Gia")
    headers = bearer(user_id, "student", "school-1")
    payload = {"user_id": user_id, "student_id": student_id}
    try:
        first = (await client.post(LINKS, json=payload, headers=admin)).json()["id"]
        assert (await client.delete(f"{LINKS}/{first}", headers=admin)).status_code == 204
        assert (await client.get(MINE, headers=headers)).status_code == 403
        assert (await client.delete(f"{LINKS}/{first}", headers=admin)).status_code == 404  # already gone

        again = await client.post(LINKS, json=payload, headers=admin)
        assert again.status_code == 201 and again.json()["id"] != first
        assert (await client.get(MINE, headers=headers)).status_code == 200
    finally:
        await remove_pair(db_session, [user_id], [student_id])


@pytest.mark.asyncio
async def test_deleted_student_record_fails_closed_and_leaves_a_stale_link(client, db_session, admin_token, world):
    """SQLite foreign keys are off, so deleting a Student leaves the link behind (stale)."""
    admin = {"Authorization": f"Bearer {admin_token}"}
    user_id, student_id = await fresh_pair(db_session, "Hal")
    _, other_student = await fresh_pair(db_session, "Ivy")
    headers = bearer(user_id, "student", "school-1")
    try:
        link_id = (await client.post(LINKS, json={"user_id": user_id, "student_id": student_id},
                                     headers=admin)).json()["id"]
        await db_session.execute(text("DELETE FROM students WHERE id = :s"), {"s": student_id})
        await db_session.commit()

        assert (await client.get(MINE, headers=headers)).status_code == 403  # fails closed
        # The stale link still holds the account, so relinking is refused until it is removed.
        relink = {"user_id": user_id, "student_id": other_student}
        assert (await client.post(LINKS, json=relink, headers=admin)).status_code == 409
        assert (await client.delete(f"{LINKS}/{link_id}", headers=admin)).status_code == 204
        assert (await client.post(LINKS, json=relink, headers=admin)).status_code == 201
    finally:
        await remove_pair(db_session, [user_id], [student_id, other_student])


@pytest.mark.asyncio
async def test_deleted_user_account_is_refused_and_leaves_a_stale_link(client, db_session, admin_token, world):
    admin = {"Authorization": f"Bearer {admin_token}"}
    user_id, student_id = await fresh_pair(db_session, "Jo")
    new_user, unused_student = await fresh_pair(db_session, "Unused")
    try:
        link_id = (await client.post(LINKS, json={"user_id": user_id, "student_id": student_id},
                                     headers=admin)).json()["id"]
        await db_session.execute(text("DELETE FROM users WHERE id = :u"), {"u": user_id})
        await db_session.commit()

        # Existing shared login code: a token for a deleted user gets 404 "User not found."
        assert (await client.get(MINE, headers=bearer(user_id, "student", "school-1"))).status_code == 404
        relink = {"user_id": new_user, "student_id": student_id}
        assert (await client.post(LINKS, json=relink, headers=admin)).status_code == 409
        assert (await client.delete(f"{LINKS}/{link_id}", headers=admin)).status_code == 204
        assert (await client.post(LINKS, json=relink, headers=admin)).status_code == 201
    finally:
        await remove_pair(db_session, [user_id, new_user], [student_id, unused_student])


@pytest.mark.asyncio
async def test_student_moved_to_another_school_fails_closed(client, db_session, world):
    bob = world["bob"].id
    await db_session.execute(text("UPDATE students SET school_id = 'school-3' WHERE id = :s"), {"s": bob})
    await db_session.commit()
    assert (await client.get(MINE, headers=as_student(world, "u_bob"))).status_code == 403


@pytest.mark.asyncio
async def test_account_role_changed_away_from_student_fails_closed(client, db_session, world):
    """The role is read from the database on each request, not from the token."""
    headers = as_student(world, "u_bob")
    await db_session.execute(text("UPDATE users SET role = 'teacher' WHERE id = :u"), {"u": world["u_bob"].id})
    await db_session.commit()
    assert (await client.get(MINE, headers=headers)).status_code == 403


# --- Listing links (admin only) ------------------------------------------------------------------

LIST_FIELDS = {"id", "user_id", "student_id", "created_by", "created_at", "user_exists", "student_exists", "is_stale"}


@pytest.mark.asyncio
async def test_only_admins_list_links(client, world, teacher_token, principal_token, parent_token,
                                      other_school_teacher_token):
    others = [{"Authorization": f"Bearer {t}"}
              for t in (teacher_token, principal_token, parent_token, other_school_teacher_token)]
    for headers in others + [as_student(world, "u_alice")]:
        res = await client.get(LINKS, headers=headers)
        assert res.status_code == 403 and world["u_alice"].id not in res.text


@pytest.mark.asyncio
async def test_list_requires_authentication(client, world):
    previous = settings.DEMO_MODE
    settings.DEMO_MODE = False
    try:
        assert (await client.get(LINKS)).status_code == 401
    finally:
        settings.DEMO_MODE = previous


@pytest.mark.asyncio
async def test_admin_lists_all_links_without_personal_details(client, admin_token, world):
    res = await client.get(LINKS, headers={"Authorization": f"Bearer {admin_token}"})

    assert res.status_code == 200
    body = res.json()
    by_user = {link["user_id"]: link for link in body}
    for user_key, student_key in (("u_alice", "alice"), ("u_bob", "bob"), ("u_cara", "cara")):
        link = by_user[world[user_key].id]
        assert set(link) == LIST_FIELDS
        assert link["student_id"] == world[student_key].id and link["created_by"] == "user-admin"
        assert (link["user_exists"], link["student_exists"], link["is_stale"]) == (True, True, False)
    assert world["u_unlinked"].id not in by_user
    created = [link["created_at"] for link in body]
    assert created == sorted(created, reverse=True)  # newest first
    for personal in ("Alice", "Bob", "Cara", "@test.invalid", "hashed_password", "Test student"):
        assert personal not in res.text, personal


@pytest.mark.asyncio
async def test_list_filters(client, admin_token, world):
    admin = {"Authorization": f"Bearer {admin_token}"}

    async def listed(**params):
        res = await client.get(LINKS, params=params, headers=admin)
        assert res.status_code == 200
        return [(link["user_id"], link["student_id"]) for link in res.json()]

    alice_pair = (world["u_alice"].id, world["alice"].id)
    assert await listed(user_id=world["u_alice"].id) == [alice_pair]
    assert await listed(student_id=world["alice"].id) == [alice_pair]
    assert await listed(user_id=world["u_alice"].id, student_id=world["alice"].id) == [alice_pair]
    assert await listed(user_id=world["u_alice"].id, student_id=world["bob"].id) == []  # filters combine
    assert await listed(user_id=world["u_unlinked"].id) == []
    assert await listed(student_id="no-such-student") == []
    assert (await client.get(LINKS, params={"user_id": ""}, headers=admin)).status_code == 422
    assert (await client.get(LINKS, params={"student_id": ""}, headers=admin)).status_code == 422


@pytest.mark.asyncio
async def test_list_detects_stale_links_and_replacement_works(client, db_session, admin_token, world):
    """Delete a Student behind one link and a User behind another (SQLite foreign keys are off,
    so both links stay). The list flags both; DELETE removes them; replacements then succeed."""
    admin = {"Authorization": f"Bearer {admin_token}"}
    gone_student_user, gone_student = await fresh_pair(db_session, "Kai")
    gone_user, kept_student = await fresh_pair(db_session, "Lea")
    new_student_for_account = (await fresh_pair(db_session, "Max"))[1]
    new_account_for_student, spare_student = await fresh_pair(db_session, "Spare")
    try:
        for pair in ((gone_student_user, gone_student), (gone_user, kept_student)):
            res = await client.post(LINKS, json={"user_id": pair[0], "student_id": pair[1]}, headers=admin)
            assert res.status_code == 201
        await db_session.execute(text("DELETE FROM students WHERE id = :s"), {"s": gone_student})
        await db_session.execute(text("DELETE FROM users WHERE id = :u"), {"u": gone_user})
        await db_session.commit()

        missing_student = (await client.get(LINKS, params={"student_id": gone_student}, headers=admin)).json()
        assert len(missing_student) == 1
        assert (missing_student[0]["user_exists"], missing_student[0]["student_exists"],
                missing_student[0]["is_stale"]) == (True, False, True)
        missing_user = (await client.get(LINKS, params={"user_id": gone_user}, headers=admin)).json()
        assert len(missing_user) == 1
        assert (missing_user[0]["user_exists"], missing_user[0]["student_exists"],
                missing_user[0]["is_stale"]) == (False, True, True)

        stale_ids = {link["id"] for link in (await client.get(LINKS, headers=admin)).json() if link["is_stale"]}
        assert {missing_student[0]["id"], missing_user[0]["id"]} <= stale_ids

        # While stale, they block replacements.
        replace_account = {"user_id": gone_student_user, "student_id": new_student_for_account}
        replace_student = {"user_id": new_account_for_student, "student_id": kept_student}
        assert (await client.post(LINKS, json=replace_account, headers=admin)).status_code == 409
        assert (await client.post(LINKS, json=replace_student, headers=admin)).status_code == 409

        for link in (missing_student[0], missing_user[0]):
            assert (await client.delete(f"{LINKS}/{link['id']}", headers=admin)).status_code == 204
        assert (await client.get(LINKS, params={"student_id": gone_student}, headers=admin)).json() == []

        assert (await client.post(LINKS, json=replace_account, headers=admin)).status_code == 201
        assert (await client.post(LINKS, json=replace_student, headers=admin)).status_code == 201
        healthy = (await client.get(LINKS, params={"user_id": gone_student_user}, headers=admin)).json()
        assert healthy[0]["student_id"] == new_student_for_account and healthy[0]["is_stale"] is False
        assert (await client.get(MINE, headers=bearer(gone_student_user, "student", "school-1"))).status_code == 200
    finally:
        await remove_pair(db_session, [gone_student_user, gone_user, new_account_for_student],
                          [gone_student, kept_student, new_student_for_account, spare_student])


@pytest.mark.asyncio
async def test_listing_writes_nothing(client, db_session, admin_token, world):
    async def snapshot():
        return [tuple(r) for r in (await db_session.execute(text(
            "SELECT id, user_id, student_id FROM student_account_links ORDER BY id"))).all()]

    before = await snapshot()
    await client.get(LINKS, headers={"Authorization": f"Bearer {admin_token}"})
    assert await snapshot() == before
