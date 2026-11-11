"""Tests for homework assignment: assigning approved drafts, access, immutability, listing."""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from backend.app.core.security import create_access_token
from backend.app.models.entities import ClassSection, QuestionBankItem, Student, Subject
from backend.app.modules.differentiated_homework import router as homework_router
from backend.app.modules.differentiated_homework.draft_service import apply_review
from backend.app.modules.differentiated_homework.models import HomeworkAssignmentRecord, HomeworkDraftRecord

SAVE = "/api/v1/students/{}/homework/drafts"
DRAFT = "/api/v1/homework/drafts/{}"
ASSIGN = "/api/v1/homework/drafts/{}/assign"
LIST = "/api/v1/homework/assignments"
ONE = "/api/v1/homework/assignments/{}"


def uid(prefix):
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def future(days=7):
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


@pytest.fixture
def teacher2_token():
    return create_access_token("user-teacher-2", school_id="school-1", role="teacher")


@pytest_asyncio.fixture
async def world(db_session):
    subj = Subject(id=uid("asg-subj"), name="Assign Subject", code=uid("ASG"), grade=8)
    cls = ClassSection(id=uid("asg-class"), school_id="school-1", grade=8, section="A", name="Assign Class",
                       subject_ids_json=[subj.id])
    student = Student(id=uid("asg-student"), school_id="school-1", class_id=cls.id, class_name=cls.name,
                      name="Private Assign Name", roll_no=903, lu_score=40, cu_score=70, au_score=60, ct_score=50,
                      overall_score=55)
    p = uid("asgq")
    questions = [
        QuestionBankItem(id=f"{p}-l1", school_id="school-1", subject_id=subj.id, text="Assigned LU one",
                         type="mcq", options_json=["W", "X"], marks=3, competency="LU", bloom_level="Apply",
                         correct_answer="SECRET-A1", marking_rubric="SECRET-R1"),
        QuestionBankItem(id=f"{p}-t1", school_id="school-1", subject_id=subj.id, text="Assigned CT one",
                         type="short", marks=2, competency="CT", bloom_level="Analyze",
                         correct_answer="SECRET-A2", marking_rubric="SECRET-R2"),
    ]
    ids = {"s": student.id, "c": cls.id, "j": subj.id, "p": f"{p}-%"}  # captured before any test runs
    db_session.add_all([subj, cls, student, *questions])
    await db_session.commit()

    yield {"subj": subj, "student": student, "p": p}

    # Plain SQL by captured IDs: a test may have rolled back this session and expired the objects.
    await db_session.rollback()
    for sql in (
        "DELETE FROM homework_assignments WHERE student_id = :s",
        "DELETE FROM homework_draft_items WHERE draft_id IN (SELECT id FROM homework_drafts WHERE student_id = :s)",
        "DELETE FROM homework_drafts WHERE student_id = :s",
        "DELETE FROM question_bank_items WHERE id LIKE :p",
        "DELETE FROM students WHERE id = :s",
        "DELETE FROM classes WHERE id = :c",
        "DELETE FROM subjects WHERE id = :j",
    ):
        await db_session.execute(text(sql), ids)
    await db_session.commit()


async def make_draft(client, token, world, approve=True):
    body = {"subject_id": world["subj"].id, "max_questions": 2, "include_ai_generated": False}
    draft = (await client.post(SAVE.format(world["student"].id), json=body, headers=auth(token))).json()
    if approve:
        await client.post(f"{DRAFT.format(draft['id'])}/approve", headers=auth(token))
    return draft


async def assignment_count(db, draft_id):
    return await db.scalar(select(func.count()).select_from(HomeworkAssignmentRecord)
                           .filter(HomeworkAssignmentRecord.draft_id == draft_id))


# --- Assigning ------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_assign_approved_draft(client, db_session, teacher_token, world):
    draft = await make_draft(client, teacher_token, world)
    due = future()

    res = await client.post(ASSIGN.format(draft["id"]), json={"due_at": due}, headers=auth(teacher_token))

    assert res.status_code == 201
    out = res.json()
    assert out["draft_id"] == draft["id"] and out["status"] == "assigned"
    assert out["student_id"] == world["student"].id and out["school_id"] == "school-1"
    assert out["subject_id"] == world["subj"].id and out["assigned_by"] == "user-teacher-1"
    assert datetime.fromisoformat(out["due_at"]) == datetime.fromisoformat(due)
    assert out["question_count"] == 2 and out["total_marks"] == 5
    assert out["items"] == draft["items"]
    assert "SECRET" not in res.text and "Private Assign Name" not in res.text

    after = (await client.get(DRAFT.format(draft["id"]), headers=auth(teacher_token))).json()
    assert after["status"] == "assigned"
    assert after["reviewed_by"] == "user-teacher-1"  # assigning keeps the approval record

    fetched = await client.get(ONE.format(out["id"]), headers=auth(teacher_token))
    assert fetched.status_code == 200 and fetched.json() == out


@pytest.mark.asyncio
async def test_assign_without_due_date(client, teacher_token, world):
    draft = await make_draft(client, teacher_token, world)
    res = await client.post(ASSIGN.format(draft["id"]), headers=auth(teacher_token))
    assert res.status_code == 201 and res.json()["due_at"] is None


@pytest.mark.asyncio
async def test_unapproved_and_rejected_drafts_cannot_be_assigned(client, db_session, teacher_token, world):
    pending = await make_draft(client, teacher_token, world, approve=False)
    res = await client.post(ASSIGN.format(pending["id"]), headers=auth(teacher_token))
    assert res.status_code == 409 and "approved" in res.json()["detail"]

    rejected = await make_draft(client, teacher_token, world, approve=False)
    await client.post(f"{DRAFT.format(rejected['id'])}/reject", headers=auth(teacher_token))
    assert (await client.post(ASSIGN.format(rejected["id"]), headers=auth(teacher_token))).status_code == 409

    for draft in (pending, rejected):
        assert await assignment_count(db_session, draft["id"]) == 0


@pytest.mark.asyncio
async def test_draft_cannot_be_assigned_twice(client, db_session, teacher_token, world):
    draft = await make_draft(client, teacher_token, world)
    assert (await client.post(ASSIGN.format(draft["id"]), headers=auth(teacher_token))).status_code == 201

    again = await client.post(ASSIGN.format(draft["id"]), headers=auth(teacher_token))
    assert again.status_code == 409 and "already" in again.json()["detail"]
    assert await assignment_count(db_session, draft["id"]) == 1


@pytest.mark.asyncio
async def test_database_rejects_a_second_assignment_for_the_same_draft(client, db_session, teacher_token, world):
    draft = await make_draft(client, teacher_token, world)
    await client.post(ASSIGN.format(draft["id"]), headers=auth(teacher_token))

    db_session.add(HomeworkAssignmentRecord(draft_id=draft["id"], student_id=world["student"].id,
                                            school_id="school-1", subject_id=world["subj"].id,
                                            assigned_by="user-teacher-1"))
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_assign_access_rules(client, db_session, teacher_token, teacher2_token, other_school_teacher_token,
                                   parent_token, student_token, world):
    draft = await make_draft(client, teacher_token, world)
    for token in (teacher2_token, other_school_teacher_token, parent_token, student_token):
        assert (await client.post(ASSIGN.format(draft["id"]), headers=auth(token))).status_code == 403
    assert await assignment_count(db_session, draft["id"]) == 0
    assert (await client.post(ASSIGN.format("no-such-draft"), headers=auth(teacher_token))).status_code == 404


@pytest.mark.asyncio
async def test_principal_and_admin_can_assign(client, teacher_token, principal_token, admin_token, world):
    for token, expected_by in ((principal_token, "user-principal-1"), (admin_token, "user-admin")):
        draft = await make_draft(client, teacher_token, world)
        res = await client.post(ASSIGN.format(draft["id"]), headers=auth(token))
        assert res.status_code == 201 and res.json()["assigned_by"] == expected_by
        # The teacher who made the draft can still see the assignment.
        assert (await client.get(ONE.format(res.json()["id"]), headers=auth(teacher_token))).status_code == 200


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {"due_at": "2099-01-01T10:00:00"},  # no time zone
        {"due_at": "tomorrow"},
        {"due_at": "2020-01-01T10:00:00+00:00"},  # in the past
        {"due_at": future(), "student_id": "someone-else"},
        {"school_id": "school-3"},
        {"assigned_by": "user-admin"},
    ],
)
async def test_invalid_assign_requests(client, db_session, teacher_token, world, payload):
    draft = await make_draft(client, teacher_token, world)
    res = await client.post(ASSIGN.format(draft["id"]), json=payload, headers=auth(teacher_token))
    assert res.status_code == 422
    assert await assignment_count(db_session, draft["id"]) == 0
    assert (await client.get(DRAFT.format(draft["id"]), headers=auth(teacher_token))).json()["status"] == "approved"


@pytest.mark.asyncio
async def test_failed_assignment_rolls_back_both_changes(client, db_session, teacher_token, world, monkeypatch):
    draft = await make_draft(client, teacher_token, world)

    def failing_audit(*args, **kwargs):
        raise RuntimeError("simulated failure after the assignment was added")

    monkeypatch.setattr(homework_router, "_audit", failing_audit)
    with pytest.raises(RuntimeError):
        await client.post(ASSIGN.format(draft["id"]), headers=auth(teacher_token))
    monkeypatch.undo()

    assert await assignment_count(db_session, draft["id"]) == 0
    assert (await client.get(DRAFT.format(draft["id"]), headers=auth(teacher_token))).json()["status"] == "approved"


@pytest.mark.asyncio
async def test_concurrent_change_during_assignment_is_refused(client, db_session, teacher_token, world, monkeypatch):
    from backend.app.db.session import AsyncSessionLocal

    draft = await make_draft(client, teacher_token, world)
    real_load = homework_router._load_draft_for

    async def load_then_race(db, user, draft_id):
        record = await real_load(db, user, draft_id)
        async with AsyncSessionLocal() as other:  # another request changes the draft meanwhile
            row = (await other.execute(select(HomeworkDraftRecord).filter(HomeworkDraftRecord.id == draft_id))).scalars().one()
            row.review_note = "changed elsewhere"
            await other.commit()
        return record

    monkeypatch.setattr(homework_router, "_load_draft_for", load_then_race)
    res = await client.post(ASSIGN.format(draft["id"]), headers=auth(teacher_token))
    monkeypatch.undo()

    assert res.status_code == 409
    assert await assignment_count(db_session, draft["id"]) == 0


# --- Immutability -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_assigned_draft_cannot_be_reviewed_reopened_or_edited(client, teacher_token, principal_token, world):
    draft = await make_draft(client, teacher_token, world)
    await client.post(ASSIGN.format(draft["id"]), headers=auth(teacher_token))
    url = DRAFT.format(draft["id"])

    for token in (teacher_token, principal_token):
        for action in ("approve", "reject", "reopen"):
            assert (await client.post(f"{url}/{action}", headers=auth(token))).status_code == 409
        assert (await client.delete(f"{url}/items/1", headers=auth(token))).status_code == 409


def test_assign_transition_does_not_touch_review_fields():
    record = HomeworkDraftRecord(status="approved", reviewed_by="reviewer", review_note="fine")
    apply_review(record, "assign", "assigner", None)
    assert (record.status, record.reviewed_by, record.review_note) == ("assigned", "reviewer", "fine")


@pytest.mark.asyncio
async def test_assigned_questions_survive_question_bank_changes(client, db_session, teacher_token, world):
    draft = await make_draft(client, teacher_token, world)
    assignment = (await client.post(ASSIGN.format(draft["id"]), headers=auth(teacher_token))).json()
    p = world["p"]

    await db_session.execute(text("UPDATE question_bank_items SET text = 'CHANGED', marks = 9 WHERE id = :id"),
                             {"id": f"{p}-l1"})
    await db_session.execute(text("DELETE FROM question_bank_items WHERE id = :id"), {"id": f"{p}-t1"})
    await db_session.commit()

    again = (await client.get(ONE.format(assignment["id"]), headers=auth(teacher_token))).json()
    assert again["items"] == assignment["items"] and again["total_marks"] == 5


# --- Listing and viewing ------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_follows_access_rules(client, teacher_token, teacher2_token, principal_token, admin_token,
                                         other_school_teacher_token, world):
    draft = await make_draft(client, teacher_token, world)
    assignment_id = (await client.post(ASSIGN.format(draft["id"]), headers=auth(teacher_token))).json()["id"]

    def ids(res):
        return [a["id"] for a in res.json()]

    assert assignment_id in ids(await client.get(LIST, headers=auth(teacher_token)))
    assert assignment_id in ids(await client.get(LIST, headers=auth(principal_token)))
    assert assignment_id in ids(await client.get(LIST, headers=auth(admin_token)))
    assert assignment_id not in ids(await client.get(LIST, headers=auth(teacher2_token)))
    assert assignment_id not in ids(await client.get(LIST, headers=auth(other_school_teacher_token)))


@pytest.mark.asyncio
async def test_list_filters(client, teacher_token, world):
    draft = await make_draft(client, teacher_token, world)
    assignment_id = (await client.post(ASSIGN.format(draft["id"]), headers=auth(teacher_token))).json()["id"]
    sid, subj = world["student"].id, world["subj"].id

    def ids(res):
        return [a["id"] for a in res.json()]

    assert ids(await client.get(LIST, params={"student_id": sid}, headers=auth(teacher_token))) == [assignment_id]
    assert ids(await client.get(LIST, params={"subject_id": subj, "status": "assigned"},
                                headers=auth(teacher_token))) == [assignment_id]
    assert ids(await client.get(LIST, params={"student_id": "nobody"}, headers=auth(teacher_token))) == []
    assert (await client.get(LIST, params={"status": "submitted"}, headers=auth(teacher_token))).status_code == 422
    listed = (await client.get(LIST, params={"student_id": sid}, headers=auth(teacher_token))).json()[0]
    assert "items" not in listed and listed["total_marks"] == 5


@pytest.mark.asyncio
async def test_detail_access_rules(client, teacher_token, teacher2_token, other_school_teacher_token,
                                   parent_token, student_token, world):
    draft = await make_draft(client, teacher_token, world)
    assignment_id = (await client.post(ASSIGN.format(draft["id"]), headers=auth(teacher_token))).json()["id"]

    for token in (teacher2_token, other_school_teacher_token, parent_token, student_token):
        assert (await client.get(ONE.format(assignment_id), headers=auth(token))).status_code == 403
    for token in (parent_token, student_token):
        assert (await client.get(LIST, headers=auth(token))).status_code == 403
    assert (await client.get(ONE.format("no-such-assignment"), headers=auth(teacher_token))).status_code == 404


# --- Final review: audit events and deletion protection ------------------------------------------


async def assign_audit_count(db, draft_id):
    return await db.scalar(text(
        "SELECT COUNT(*) FROM audit_events WHERE action = 'Homework Assigned' AND details LIKE :d"),
        {"d": f"%{draft_id}%"})


@pytest.mark.asyncio
async def test_assignment_writes_exactly_one_audit_event(client, db_session, teacher_token, world):
    draft = await make_draft(client, teacher_token, world)
    await client.post(ASSIGN.format(draft["id"]), headers=auth(teacher_token))
    await client.post(ASSIGN.format(draft["id"]), headers=auth(teacher_token))  # refused duplicate
    assert await assign_audit_count(db_session, draft["id"]) == 1


@pytest.mark.asyncio
async def test_failed_assignment_leaves_no_audit_event(client, db_session, teacher_token, world, monkeypatch):
    draft = await make_draft(client, teacher_token, world)
    real_build = homework_router.build_assignment

    def broken_build(record, assigned_by, due_at):
        assignment = real_build(record, assigned_by, due_at)
        assignment.student_id = None  # NOT NULL: the commit fails after the audit event was added
        return assignment

    monkeypatch.setattr(homework_router, "build_assignment", broken_build)
    with pytest.raises(IntegrityError):  # not a duplicate, so it's a server fault, not a 409
        await client.post(ASSIGN.format(draft["id"]), headers=auth(teacher_token))
    monkeypatch.undo()

    assert await assignment_count(db_session, draft["id"]) == 0
    assert await assign_audit_count(db_session, draft["id"]) == 0
    assert (await client.get(DRAFT.format(draft["id"]), headers=auth(teacher_token))).json()["status"] == "approved"


@pytest.mark.asyncio
async def test_simultaneous_assignment_of_the_same_draft(client, db_session, teacher_token, world, monkeypatch):
    """Another request assigns the draft after this request's 'already assigned' check but
    before its commit. The unique draft_id stops a second row; this request gets 409, and the
    winning assignment is kept.

    Simulated by committing the competing assignment first, then hiding it from this request's
    single existence check, exactly as if it had been committed just after that check.
    """
    from backend.app.db.session import AsyncSessionLocal

    draft = await make_draft(client, teacher_token, world)
    winner_id = uid("winner")
    async with AsyncSessionLocal() as other:
        other.add(HomeworkAssignmentRecord(id=winner_id, draft_id=draft["id"], student_id=world["student"].id,
                                           school_id="school-1", subject_id=world["subj"].id,
                                           assigned_by="user-principal-1"))
        await other.commit()

    class NothingFound:
        def first(self):
            return None

    real_load = homework_router._load_draft_for

    async def load_then_hide_next_query(db, user, draft_id):
        record = await real_load(db, user, draft_id)
        real_execute = db.execute

        async def hide_once(statement, *args, **kwargs):
            db.execute = real_execute  # only the existence check is affected
            return NothingFound()

        db.execute = hide_once
        return record

    monkeypatch.setattr(homework_router, "_load_draft_for", load_then_hide_next_query)
    res = await client.post(ASSIGN.format(draft["id"]), headers=auth(teacher_token))
    monkeypatch.undo()

    assert res.status_code == 409 and "already" in res.json()["detail"]
    rows = (await db_session.execute(
        select(HomeworkAssignmentRecord.id).filter(HomeworkAssignmentRecord.draft_id == draft["id"]))).all()
    assert [r.id for r in rows] == [winner_id]
    assert await assign_audit_count(db_session, draft["id"]) == 0  # the loser's audit event was rolled back


@pytest.mark.asyncio
async def test_assigned_draft_cannot_be_deleted(client, db_session, teacher_token, world):
    """Deleting the draft would cascade to the question snapshots the assignment depends on."""
    from backend.app.modules.differentiated_homework.models import AssignedDraftDeletionError

    draft = await make_draft(client, teacher_token, world)
    assignment_id = (await client.post(ASSIGN.format(draft["id"]), headers=auth(teacher_token))).json()["id"]

    record = (await db_session.execute(
        select(HomeworkDraftRecord).filter(HomeworkDraftRecord.id == draft["id"]))).scalars().one()
    await db_session.delete(record)
    with pytest.raises(AssignedDraftDeletionError):
        await db_session.flush()
    await db_session.rollback()

    detail = await client.get(ONE.format(assignment_id), headers=auth(teacher_token))
    assert detail.status_code == 200 and len(detail.json()["items"]) == 2


@pytest.mark.asyncio
async def test_unassigned_draft_can_still_be_deleted(client, db_session, teacher_token, world):
    draft = await make_draft(client, teacher_token, world, approve=False)
    record = (await db_session.execute(
        select(HomeworkDraftRecord).filter(HomeworkDraftRecord.id == draft["id"]))).scalars().one()
    await db_session.delete(record)
    await db_session.commit()
    assert (await client.get(DRAFT.format(draft["id"]), headers=auth(teacher_token))).status_code == 404
