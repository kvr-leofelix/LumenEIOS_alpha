"""Phase 2 of answer submission: the three student endpoints.

GET/PUT /api/v1/students/me/homework/assignments/{assignment_id}/submission
POST    /api/v1/students/me/homework/assignments/{assignment_id}/submission/submit

Students are identified only through StudentAccountLink. Races are simulated as in the draft
tests: a competing request runs to completion after this request has loaded the submission and
before it writes.
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

import backend.app.modules.differentiated_homework.router as homework_router
from backend.app.core.config import settings
from backend.app.core.security import create_access_token
from backend.app.models.entities import AuditEvent, ClassSection, ParentStudentLink, Student, Subject, User
from backend.app.modules.differentiated_homework.models import (
    HomeworkAssignmentRecord,
    HomeworkDraftItemRecord,
    HomeworkDraftRecord,
    HomeworkSubmissionRecord,
    StudentAccountLink,
)

SUB = "/api/v1/students/me/homework/assignments/{}/submission"
SUBMIT = SUB + "/submit"
DUE = datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)
BEFORE_DUE = DUE - timedelta(days=1)
QUESTIONS = (("mcq", ["A", "B", "C"]), ("short", []), ("descriptive", []), ("practical", []))
OUT_FIELDS = {"id", "assignment_id", "status", "version", "is_late", "started_at", "updated_at", "submitted_at",
              "answered_count", "question_count", "answers"}
HIDDEN = ("SECRET", "correct_answer", "marking_rubric", "rubric", "marks", "score", "grade", "feedback",
          "competency", "bloom", "Apply", "source_question_id", "draft_item_id", "draft_id", "student_id",
          "school_id", "reviewed", "assigned_by", "src-")


def uid(prefix):
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


def bearer(user_id, role="student", school_id="school-1"):
    return {"Authorization": f"Bearer {create_access_token(user_id, school_id=school_id, role=role)}"}


def make_user(role, school_id):
    user_id = uid(f"sap-{role}")
    return User(id=user_id, email=f"{user_id}@test.invalid", name=f"Test {role}", hashed_password="x",
                role=role, school_id=school_id)


def make_student(cls, school_id, name):
    return Student(id=uid("sap-student"), school_id=school_id, class_id=cls.id, class_name=cls.name, name=name,
                   roll_no=1, lu_score=40, cu_score=70, au_score=60, ct_score=50, overall_score=55)


def make_assignment(student, subject_id, due_at):
    """An assigned draft with frozen questions (secret answers included) and its assignment."""
    items = [
        HomeworkDraftItemRecord(
            position=i, source_question_id=uid("src"), text=f"{student.name} question {i}", type=qtype,
            options_json=list(options), marks=3, competency="LU", competency_rank=1, bloom_level="Apply",
            is_ai_generated=False, correct_answer="SECRET-ANSWER", marking_rubric="SECRET-RUBRIC",
        )
        for i, (qtype, options) in enumerate(QUESTIONS, start=1)
    ]
    draft = HomeworkDraftRecord(
        student_id=student.id, school_id=student.school_id, subject_id=subject_id, created_by="user-teacher-1",
        status="assigned", requested_questions=len(items), include_ai_generated=False,
        question_count=len(items), total_marks=3 * len(items), shortfall=0, notes_json=["teacher-only"],
        rationale_json={"targeted_competencies": ["LU"], "weakest": ["LU"],
                        "competency_scores": {"LU": 40, "CU": 70, "AU": 60, "CT": 50},
                        "lowest_score": 40, "highest_score": 70, "score_source": "test", "summary": "SECRET-SUMMARY"},
        reviewed_by="user-teacher-1", review_note="SECRET-REVIEW", items=items,
    )
    return HomeworkAssignmentRecord(
        id=uid("sap-asg"), draft=draft, student_id=student.id, school_id=student.school_id, subject_id=subject_id,
        assigned_by="user-teacher-1", assigned_at=BEFORE_DUE - timedelta(days=2), due_at=due_at, status="assigned",
    )


@pytest_asyncio.fixture
async def world(db_session):
    subj = Subject(id=uid("sap-subj"), name="Submission Maths", code=uid("SAP"), grade=8)
    cls1 = ClassSection(id=uid("sap-c1"), school_id="school-1", grade=8, section="S", name="Sub 1",
                        subject_ids_json=[subj.id])
    cls3 = ClassSection(id=uid("sap-c3"), school_id="school-3", grade=8, section="T", name="Sub 3",
                        subject_ids_json=[subj.id])
    alice, bob = make_student(cls1, "school-1", "Alice"), make_student(cls1, "school-1", "Bob")
    cara = make_student(cls3, "school-3", "Cara")
    u_alice, u_bob, u_cara = make_user("student", "school-1"), make_user("student", "school-1"), make_user("student", "school-3")
    u_unlinked, u_parent = make_user("student", "school-1"), make_user("parent", "school-1")

    a_alice = make_assignment(alice, subj.id, DUE)
    a_alice_nodue = make_assignment(alice, subj.id, None)
    a_bob = make_assignment(bob, subj.id, DUE)
    a_cara = make_assignment(cara, subj.id, DUE)

    ids = {
        "alice": alice.id, "bob": bob.id, "cara": cara.id,
        "u_alice": u_alice.id, "u_bob": u_bob.id, "u_cara": u_cara.id,
        "u_unlinked": u_unlinked.id, "u_parent": u_parent.id,
        "a_alice": a_alice.id, "a_alice_nodue": a_alice_nodue.id, "a_bob": a_bob.id, "a_cara": a_cara.id,
        "classes": [cls1.id, cls3.id], "subject": subj.id,
    }
    db_session.add_all([
        subj, cls1, cls3, alice, bob, cara, u_alice, u_bob, u_cara, u_unlinked, u_parent,
        a_alice, a_alice_nodue, a_bob, a_cara,
        StudentAccountLink(user_id=u_alice.id, student_id=alice.id, created_by="user-admin"),
        StudentAccountLink(user_id=u_bob.id, student_id=bob.id, created_by="user-admin"),
        StudentAccountLink(user_id=u_cara.id, student_id=cara.id, created_by="user-admin"),
        ParentStudentLink(id=uid("sap-plink"), parent_user_id=u_parent.id, student_id=alice.id),
    ])
    await db_session.commit()
    yield ids

    await db_session.rollback()
    for student_id in (ids["alice"], ids["bob"], ids["cara"]):
        p = {"s": student_id}
        for sql in (
            "DELETE FROM homework_submission_answers WHERE submission_id IN "
            "(SELECT id FROM homework_submissions WHERE student_id = :s)",
            "DELETE FROM homework_submissions WHERE student_id = :s",
            "DELETE FROM homework_assignments WHERE student_id = :s",
            "DELETE FROM homework_draft_items WHERE draft_id IN (SELECT id FROM homework_drafts WHERE student_id = :s)",
            "DELETE FROM homework_drafts WHERE student_id = :s",
            "DELETE FROM student_account_links WHERE student_id = :s",
            "DELETE FROM parent_student_links WHERE student_id = :s",
            "DELETE FROM students WHERE id = :s",
        ):
            await db_session.execute(text(sql), p)
    for key in ("u_alice", "u_bob", "u_cara", "u_unlinked", "u_parent"):
        await db_session.execute(text("DELETE FROM audit_events WHERE user_id = :u"), {"u": ids[key]})
        await db_session.execute(text("DELETE FROM student_account_links WHERE user_id = :u"), {"u": ids[key]})
        await db_session.execute(text("DELETE FROM users WHERE id = :u"), {"u": ids[key]})
    for class_id in ids["classes"]:
        await db_session.execute(text("DELETE FROM classes WHERE id = :c"), {"c": class_id})
    await db_session.execute(text("DELETE FROM subjects WHERE id = :j"), {"j": ids["subject"]})
    await db_session.commit()


@pytest.fixture
def frozen_clock(monkeypatch):
    """Set the router's clock. Returns a setter."""
    def set_now(moment):
        monkeypatch.setattr(homework_router, "utc_now", lambda: moment)
    set_now(BEFORE_DUE)
    return set_now


def alice(w):
    return bearer(w["u_alice"])


async def put(client, w, assignment_key, answers, version=None, who="u_alice"):
    body = {"answers": answers}
    if version is not None:
        body["expected_version"] = version
    return await client.put(SUB.format(w[assignment_key]), json=body, headers=bearer(w[who]))


async def submit(client, w, assignment_key, version=None, who="u_alice"):
    body = {} if version is None else {"expected_version": version}
    return await client.post(SUBMIT.format(w[assignment_key]), json=body, headers=bearer(w[who]))


async def count(db_session, model, **filters):
    query = select(func.count()).select_from(model)
    for name, value in filters.items():
        query = query.filter(getattr(model, name) == value)
    return await db_session.scalar(query)


async def audits(db_session, user_id):
    return await db_session.scalar(select(func.count()).select_from(AuditEvent).filter(
        AuditEvent.user_id == user_id, AuditEvent.action == "Homework Submitted"))


def answers_of(res):
    return {a["position"]: (a["answer_text"], a["selected_option_index"]) for a in res.json()["answers"]}


def race_after_load(monkeypatch, competing):
    """The endpoint's submission lookup runs `competing` (a whole other request) right after this
    request has read the submission and before it writes. Only the first lookup does this."""
    real_load = homework_router._load_submission
    state = {"raced": False}

    async def load_then_race(db, assignment_id):
        loaded = await real_load(db, assignment_id)
        if not state["raced"]:
            state["raced"] = True
            await competing()
        return loaded

    monkeypatch.setattr(homework_router, "_load_submission", load_then_race)


# --- Identity and access ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_linked_student_uses_all_three_endpoints(client, world, frozen_clock):
    a = world["a_alice"]
    assert (await client.get(SUB.format(a), headers=alice(world))).status_code == 200
    assert (await put(client, world, "a_alice", [{"position": 2, "answer_text": "x"}])).status_code == 201
    assert (await submit(client, world, "a_alice", version=1)).status_code == 200


async def assert_all_three_refused(client, w, headers, code, detail=None):
    for method, url, body in (("GET", SUB, None), ("PUT", SUB, {"answers": []}), ("POST", SUBMIT, {})):
        res = await client.request(method, url.format(w["a_alice"]), json=body, headers=headers)
        assert res.status_code == code, (method, res.text)
        if detail:
            assert res.json()["detail"] == detail


@pytest.mark.asyncio
async def test_unlinked_student_is_refused(client, db_session, world):
    await assert_all_three_refused(client, world, bearer(world["u_unlinked"]), 403,
                                   "This account isn't linked to a student record.")
    assert await count(db_session, HomeworkSubmissionRecord, assignment_id=world["a_alice"]) == 0


@pytest.mark.asyncio
async def test_same_id_account_without_a_link_is_refused(client, db_session, world):
    """A student account whose ID equals Alice's Student ID, with no link."""
    twin = User(id=world["alice"], email=f"{uid('twin')}@test.invalid", name="Twin", hashed_password="x",
                role="student", school_id="school-1")
    db_session.add(twin)
    await db_session.commit()
    try:
        await assert_all_three_refused(client, world, bearer(world["alice"]), 403)
    finally:
        await db_session.execute(text("DELETE FROM users WHERE id = :u"), {"u": world["alice"]})
        await db_session.commit()


@pytest.mark.asyncio
async def test_wrong_role_is_refused_even_with_a_link(client, db_session, world):
    await db_session.execute(text("UPDATE users SET role = 'Student' WHERE id = :u"), {"u": world["u_alice"]})
    await db_session.commit()
    await assert_all_three_refused(client, world, alice(world), 403, "Access denied.")


@pytest.mark.asyncio
async def test_other_roles_are_refused(client, db_session, world, teacher_token, principal_token, admin_token,
                                       parent_token):
    tokens = [{"Authorization": f"Bearer {t}"} for t in (teacher_token, principal_token, admin_token, parent_token)]
    for headers in tokens + [bearer(world["u_parent"], "parent")]:  # last: the parent linked to Alice
        await assert_all_three_refused(client, world, headers, 403, "Access denied.")
    assert await count(db_session, HomeworkSubmissionRecord, assignment_id=world["a_alice"]) == 0


@pytest.mark.asyncio
async def test_deleted_student_record_fails_closed(client, db_session, world):
    """SQLite foreign keys are off, so the link survives as a stale link."""
    await db_session.execute(text("DELETE FROM students WHERE id = :s"), {"s": world["alice"]})
    await db_session.commit()
    await assert_all_three_refused(client, world, alice(world), 403, "This account isn't linked to a student record.")


@pytest.mark.asyncio
async def test_removed_link_fails_closed(client, db_session, world, frozen_clock):
    assert (await put(client, world, "a_alice", [{"position": 2, "answer_text": "kept"}])).status_code == 201
    await db_session.execute(text("DELETE FROM student_account_links WHERE user_id = :u"), {"u": world["u_alice"]})
    await db_session.commit()
    await assert_all_three_refused(client, world, alice(world), 403)
    assert await count(db_session, HomeworkSubmissionRecord, assignment_id=world["a_alice"]) == 1  # data kept


@pytest.mark.asyncio
@pytest.mark.parametrize("table, key", [("users", "u_alice"), ("students", "alice")])
async def test_school_mismatch_is_refused(client, db_session, world, table, key):
    await db_session.execute(text(f"UPDATE {table} SET school_id = 'school-3' WHERE id = :i"), {"i": world[key]})
    await db_session.commit()
    await assert_all_three_refused(client, world, alice(world), 403)


@pytest.mark.asyncio
async def test_demo_mode_cannot_bypass_the_student_role(client, world):
    assert settings.DEMO_MODE is True  # no token -> treated as admin by shared code -> refused here
    await assert_all_three_refused(client, world, {}, 403, "Access denied.")
    previous = settings.DEMO_MODE
    settings.DEMO_MODE = False
    try:
        await assert_all_three_refused(client, world, {}, 401)
        await assert_all_three_refused(client, world, {"Authorization": "Bearer not-a-jwt"}, 401)
    finally:
        settings.DEMO_MODE = previous


# --- Ownership ----------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_other_students_assignments_are_404_and_untouched(client, db_session, world, frozen_clock):
    bob_saved = await put(client, world, "a_bob", [{"position": 2, "answer_text": "Bob's answer"}], who="u_bob")
    assert bob_saved.status_code == 201

    for key in ("a_bob", "a_cara"):  # same school, other school
        for res in (
            await client.get(SUB.format(world[key]), headers=alice(world)),
            await put(client, world, key, [{"position": 2, "answer_text": "overwrite"}], version=1),
            await put(client, world, key, [{"position": 2, "answer_text": "create"}]),
            await submit(client, world, key, version=1),
            await submit(client, world, key),
        ):
            assert res.status_code == 404 and res.json() == {"detail": "Assignment not found."}
            assert "Bob" not in res.text and "Cara" not in res.text
    for res in (await client.get(SUB.format("no-such-assignment"), headers=alice(world)),
                await client.post(SUBMIT.format("no-such-assignment"), json={}, headers=alice(world))):
        assert res.status_code == 404

    bob_now = await client.get(SUB.format(world["a_bob"]), headers=bearer(world["u_bob"]))
    assert bob_now.json() == bob_saved.json()  # unchanged: same version, answers and status
    assert await count(db_session, HomeworkSubmissionRecord, assignment_id=world["a_cara"]) == 0
    assert await audits(db_session, world["u_alice"]) == 0


# --- GET --------------------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_before_any_save_is_the_empty_state_and_creates_nothing(client, db_session, world):
    for _ in range(2):
        res = await client.get(SUB.format(world["a_alice"]), headers=alice(world))
        assert res.status_code == 200
        assert res.json() == {
            "id": None, "assignment_id": world["a_alice"], "status": "not_started", "version": None,
            "is_late": False, "started_at": None, "updated_at": None, "submitted_at": None,
            "answered_count": 0, "question_count": 4, "answers": [],
        }
    assert await count(db_session, HomeworkSubmissionRecord, assignment_id=world["a_alice"]) == 0


@pytest.mark.asyncio
async def test_get_in_progress_and_submitted_states(client, world, frozen_clock):
    saved = await put(client, world, "a_alice", [{"position": 3, "answer_text": "three"},
                                                 {"position": 1, "selected_option_index": 2}])
    got = await client.get(SUB.format(world["a_alice"]), headers=alice(world))
    assert got.status_code == 200 and got.json() == saved.json()
    body = got.json()
    assert set(body) == OUT_FIELDS and body["status"] == "in_progress" and body["version"] == 1
    assert body["answers"] == [{"position": 1, "answer_text": None, "selected_option_index": 2},
                               {"position": 3, "answer_text": "three", "selected_option_index": None}]
    assert body["submitted_at"] is None and body["started_at"].endswith(("Z", "+00:00"))

    submitted = await submit(client, world, "a_alice", version=1)
    got = await client.get(SUB.format(world["a_alice"]), headers=alice(world))
    assert got.json() == submitted.json()
    assert got.json()["status"] == "submitted" and got.json()["answered_count"] == 2


# --- PUT ----------------------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_first_save_is_201_and_later_saves_are_200_with_rising_versions(client, world, frozen_clock):
    first = await put(client, world, "a_alice", [{"position": 2, "answer_text": "one"}])
    assert first.status_code == 201 and first.json()["version"] == 1 and first.json()["status"] == "in_progress"
    second = await put(client, world, "a_alice", [{"position": 2, "answer_text": "two"}], version=1)
    assert second.status_code == 200 and second.json()["version"] == 2
    third = await put(client, world, "a_alice", [], version=2)  # same frozen time, empty save
    assert third.status_code == 200 and third.json()["version"] == 3
    assert third.json()["id"] == first.json()["id"]


@pytest.mark.asyncio
async def test_partial_updates_and_clearing(client, world, frozen_clock):
    await put(client, world, "a_alice", [{"position": 1, "selected_option_index": 0},
                                         {"position": 2, "answer_text": "keep"},
                                         {"position": 3, "answer_text": "clear me"}])
    res = await put(client, world, "a_alice", [{"position": 1, "selected_option_index": 1},
                                               {"position": 3, "clear": True},
                                               {"position": 4, "clear": True}], version=1)  # 4 was never answered
    assert res.status_code == 200
    assert answers_of(res) == {1: (None, 1), 2: ("keep", None)}
    assert res.json()["answered_count"] == 2


@pytest.mark.asyncio
async def test_answer_validation_is_structured_and_all_or_nothing(client, db_session, world, frozen_clock):
    await put(client, world, "a_alice", [{"position": 2, "answer_text": "original"}])
    res = await put(client, world, "a_alice", [
        {"position": 2, "clear": True},  # valid, but must not be applied
        {"position": 1, "selected_option_index": 3},  # out of range
        {"position": 3, "selected_option_index": 0},  # index on a text question
        {"position": 4, "answer_text": "fine"},  # valid, must not be applied
        {"position": 9, "answer_text": "nowhere"},  # no such question
    ], version=1)
    assert res.status_code == 422
    detail = res.json()["detail"]
    assert [d["position"] for d in detail] == [1, 3, 9]
    assert all(set(d) == {"position", "reason"} for d in detail)
    assert "from 0 to 2" in detail[0]["reason"] and "answer_text" in detail[1]["reason"]
    assert "Traceback" not in res.text and "sqlite" not in res.text.lower()

    after = await client.get(SUB.format(world["a_alice"]), headers=alice(world))
    assert after.json()["version"] == 1 and answers_of(after) == {2: ("original", None)}


@pytest.mark.asyncio
async def test_text_on_an_mcq_is_rejected(client, world, frozen_clock):
    res = await put(client, world, "a_alice", [{"position": 1, "answer_text": "B"}])
    assert res.status_code == 422 and res.json()["detail"][0]["position"] == 1
    assert (await client.get(SUB.format(world["a_alice"]), headers=alice(world))).json()["status"] == "not_started"


@pytest.mark.asyncio
@pytest.mark.parametrize("answer", [
    {"position": 2, "answer_text": "   "},
    {"position": 2, "answer_text": "x" * 10_001},
    {"position": 2, "answer_text": None},
    {"position": 2, "clear": False},
    {"position": 2, "answer_text": "a", "clear": True},
    {"position": 1, "selected_option_index": "0"},
    {"position": 0, "clear": True},
    {"position": 2, "answer_text": "a", "marks": 3},
])
async def test_malformed_bodies_use_fastapis_standard_format(client, db_session, world, answer):
    res = await put(client, world, "a_alice", [answer])
    assert res.status_code == 422
    assert all({"loc", "msg", "type"} <= set(d) for d in res.json()["detail"])
    assert await count(db_session, HomeworkSubmissionRecord, assignment_id=world["a_alice"]) == 0


@pytest.mark.asyncio
async def test_duplicate_positions_and_unknown_top_level_fields_are_malformed(client, world):
    url = SUB.format(world["a_alice"])
    dup = {"answers": [{"position": 2, "answer_text": "a"}, {"position": 2, "clear": True}]}
    assert (await client.put(url, json=dup, headers=alice(world))).status_code == 422
    assert (await client.put(url, json={"answers": [], "status": "submitted"}, headers=alice(world))).status_code == 422
    assert (await client.post(SUBMIT.format(world["a_alice"]), json={"is_late": False},
                              headers=alice(world))).status_code == 422


@pytest.mark.asyncio
async def test_version_errors_are_409(client, world, frozen_clock):
    first_with_version = await put(client, world, "a_alice", [{"position": 2, "answer_text": "a"}], version=1)
    assert first_with_version.status_code == 409 and "omit expected_version" in first_with_version.json()["detail"]
    assert (await put(client, world, "a_alice", [{"position": 2, "answer_text": "a"}])).status_code == 201

    missing = await put(client, world, "a_alice", [{"position": 2, "answer_text": "b"}])
    assert missing.status_code == 409 and "required" in missing.json()["detail"]
    outdated = await put(client, world, "a_alice", [{"position": 2, "answer_text": "b"}], version=5)
    assert outdated.status_code == 409 and "changed elsewhere" in outdated.json()["detail"]
    assert (await submit(client, world, "a_alice")).status_code == 409
    assert (await submit(client, world, "a_alice", version=7)).status_code == 409
    after = await client.get(SUB.format(world["a_alice"]), headers=alice(world))
    assert after.json()["version"] == 1 and answers_of(after) == {2: ("a", None)}


@pytest.mark.asyncio
async def test_saves_after_the_due_time_are_accepted(client, world, frozen_clock):
    frozen_clock(DUE + timedelta(days=3))
    res = await put(client, world, "a_alice", [{"position": 2, "answer_text": "late work"}])
    assert res.status_code == 201 and res.json()["is_late"] is False  # decided only at final submit


# --- Final submit ---------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_blank_submission_without_any_save(client, db_session, world, frozen_clock):
    res = await submit(client, world, "a_alice")
    assert res.status_code == 200
    body = res.json()
    assert (body["status"], body["answered_count"], body["version"], body["answers"]) == ("submitted", 0, 1, [])
    assert body["submitted_at"].startswith("2026-11-19T12:00:00")


@pytest.mark.asyncio
async def test_partial_submission_locks_permanently(client, world, frozen_clock):
    await put(client, world, "a_alice", [{"position": 2, "answer_text": "only this"}])
    done = await submit(client, world, "a_alice", version=1)
    assert done.status_code == 200 and done.json()["answered_count"] == 1 and done.json()["version"] == 2

    edit = await put(client, world, "a_alice", [{"position": 2, "clear": True}], version=2)
    assert edit.status_code == 409 and "submitted" in edit.json()["detail"]
    again = await submit(client, world, "a_alice", version=2)
    assert again.status_code == 409 and "submitted" in again.json()["detail"]
    later = await client.get(SUB.format(world["a_alice"]), headers=alice(world))
    assert later.json() == done.json()


@pytest.mark.asyncio
@pytest.mark.parametrize("now, late", [
    (DUE - timedelta(seconds=1), False),
    (DUE, False),  # exactly at the due time is on time
    (DUE + timedelta(seconds=1), True),
    (DUE + timedelta(days=30), True),
])
async def test_due_time_boundary(client, db_session, world, frozen_clock, now, late):
    frozen_clock(now)
    res = await submit(client, world, "a_alice")
    assert res.status_code == 200 and res.json()["is_late"] is late
    stored = await db_session.scalar(select(HomeworkSubmissionRecord.is_late).filter(
        HomeworkSubmissionRecord.assignment_id == world["a_alice"]))
    assert bool(stored) is late


@pytest.mark.asyncio
async def test_no_due_date_is_never_late(client, world, frozen_clock):
    frozen_clock(DUE + timedelta(days=365))
    res = await submit(client, world, "a_alice_nodue")
    assert res.status_code == 200 and res.json()["is_late"] is False


# --- Concurrency and transactions -------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_two_simultaneous_first_saves(client, db_session, world, frozen_clock, monkeypatch):
    async def competing_first_save():
        res = await put(client, world, "a_alice", [{"position": 2, "answer_text": "winner"}])
        assert res.status_code == 201

    race_after_load(monkeypatch, competing_first_save)
    loser = await put(client, world, "a_alice", [{"position": 2, "answer_text": "loser"},
                                                 {"position": 3, "answer_text": "loser too"}])
    assert loser.status_code == 409
    assert loser.json()["detail"] == "A submission was started by another request. Reload it and try again."
    monkeypatch.undo()
    assert await count(db_session, HomeworkSubmissionRecord, assignment_id=world["a_alice"]) == 1
    final = await client.get(SUB.format(world["a_alice"]), headers=alice(world))
    assert answers_of(final) == {2: ("winner", None)} and final.json()["version"] == 1


@pytest.mark.asyncio
async def test_two_conflicting_updates(client, world, frozen_clock, monkeypatch):
    await put(client, world, "a_alice", [{"position": 2, "answer_text": "start"}])

    async def competing_update():
        assert (await put(client, world, "a_alice", [{"position": 2, "answer_text": "winner"}],
                          version=1)).status_code == 200

    race_after_load(monkeypatch, competing_update)
    loser = await put(client, world, "a_alice", [{"position": 2, "answer_text": "loser"},
                                                 {"position": 4, "answer_text": "loser extra"}], version=1)
    assert loser.status_code == 409
    assert loser.json()["detail"] == "This submission was changed by another request. Reload it and try again."
    monkeypatch.undo()
    final = await client.get(SUB.format(world["a_alice"]), headers=alice(world))
    assert answers_of(final) == {2: ("winner", None)} and final.json()["version"] == 2  # nothing of the loser


@pytest.mark.asyncio
async def test_save_racing_a_final_submit(client, db_session, world, frozen_clock, monkeypatch):
    await put(client, world, "a_alice", [{"position": 2, "answer_text": "submitted text"}])

    async def competing_submit():
        assert (await submit(client, world, "a_alice", version=1)).status_code == 200

    race_after_load(monkeypatch, competing_submit)
    loser = await put(client, world, "a_alice", [{"position": 2, "answer_text": "too late"}], version=1)
    assert loser.status_code == 409
    monkeypatch.undo()
    final = await client.get(SUB.format(world["a_alice"]), headers=alice(world))
    assert final.json()["status"] == "submitted" and answers_of(final) == {2: ("submitted text", None)}
    assert await audits(db_session, world["u_alice"]) == 1


@pytest.mark.asyncio
async def test_final_submit_racing_a_save(client, db_session, world, frozen_clock, monkeypatch):
    await put(client, world, "a_alice", [{"position": 2, "answer_text": "first"}])

    async def competing_save():
        assert (await put(client, world, "a_alice", [{"position": 2, "answer_text": "newer"}],
                          version=1)).status_code == 200

    race_after_load(monkeypatch, competing_save)
    loser = await submit(client, world, "a_alice", version=1)
    assert loser.status_code == 409
    monkeypatch.undo()
    final = await client.get(SUB.format(world["a_alice"]), headers=alice(world))
    assert final.json()["status"] == "in_progress" and answers_of(final) == {2: ("newer", None)}
    assert await audits(db_session, world["u_alice"]) == 0  # the failed submit's audit was rolled back


@pytest.mark.asyncio
async def test_two_simultaneous_final_submits(client, db_session, world, frozen_clock, monkeypatch):
    await put(client, world, "a_alice", [{"position": 2, "answer_text": "x"}])

    async def competing_submit():
        assert (await submit(client, world, "a_alice", version=1)).status_code == 200

    race_after_load(monkeypatch, competing_submit)
    assert (await submit(client, world, "a_alice", version=1)).status_code == 409
    monkeypatch.undo()
    assert await audits(db_session, world["u_alice"]) == 1
    assert await count(db_session, HomeworkSubmissionRecord, assignment_id=world["a_alice"]) == 1


@pytest.mark.asyncio
async def test_two_simultaneous_blank_first_submits(client, db_session, world, frozen_clock, monkeypatch):
    async def competing_submit():
        assert (await submit(client, world, "a_alice")).status_code == 200

    race_after_load(monkeypatch, competing_submit)
    assert (await submit(client, world, "a_alice")).status_code == 409
    monkeypatch.undo()
    assert await audits(db_session, world["u_alice"]) == 1
    assert await count(db_session, HomeworkSubmissionRecord, assignment_id=world["a_alice"]) == 1


# --- Audit -----------------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_exactly_one_audit_event_and_only_for_a_successful_submit(client, db_session, world, frozen_clock):
    await put(client, world, "a_alice", [{"position": 2, "answer_text": "a"}])
    await put(client, world, "a_alice", [{"position": 3, "answer_text": "b"}], version=1)
    await submit(client, world, "a_alice", version=1)  # outdated: fails
    await client.post(SUBMIT.format(world["a_alice"]), json={"expected_version": "2"}, headers=alice(world))
    assert await audits(db_session, world["u_alice"]) == 0  # saves and failures aren't audited

    assert (await submit(client, world, "a_alice", version=2)).status_code == 200
    await submit(client, world, "a_alice", version=3)  # locked: fails
    assert await audits(db_session, world["u_alice"]) == 1
    event = (await db_session.execute(select(AuditEvent).filter(
        AuditEvent.user_id == world["u_alice"], AuditEvent.action == "Homework Submitted"))).scalars().one()
    assert event.category == "curriculum" and world["a_alice"] in event.details
    assert "SECRET" not in event.details and "late" not in event.details


@pytest.mark.asyncio
async def test_late_submit_is_noted_in_the_audit_event(client, db_session, world, frozen_clock):
    frozen_clock(DUE + timedelta(hours=1))
    await submit(client, world, "a_alice")
    details = await db_session.scalar(select(AuditEvent.details).filter(AuditEvent.user_id == world["u_alice"]))
    assert details.endswith("(late).")


@pytest.mark.asyncio
async def test_audit_and_lock_are_atomic(client, db_session, world, frozen_clock, monkeypatch):
    """If the audit event can't be saved, the lock isn't saved either."""
    await put(client, world, "a_alice", [{"position": 2, "answer_text": "a"}])
    real_audit = homework_router._audit

    def broken_audit(user, action, details):
        event = real_audit(user, action, details)
        event.user_name = None  # NOT NULL in the database
        return event

    monkeypatch.setattr(homework_router, "_audit", broken_audit)
    with pytest.raises(IntegrityError):
        await submit(client, world, "a_alice", version=1)
    monkeypatch.undo()
    after = await client.get(SUB.format(world["a_alice"]), headers=alice(world))
    assert after.json()["status"] == "in_progress" and after.json()["version"] == 1
    assert await audits(db_session, world["u_alice"]) == 0


# --- Corrupted data ----------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_inconsistent_stored_data_is_a_500_without_details(client, db_session, world, frozen_clock, caplog):
    await put(client, world, "a_alice", [{"position": 2, "answer_text": "a"}])
    foreign_item = await db_session.scalar(select(HomeworkDraftItemRecord.id).join(
        HomeworkAssignmentRecord, HomeworkAssignmentRecord.draft_id == HomeworkDraftItemRecord.draft_id).filter(
        HomeworkAssignmentRecord.id == world["a_bob"]))
    await db_session.execute(text(
        "UPDATE homework_submission_answers SET draft_item_id = :i WHERE submission_id = "
        "(SELECT id FROM homework_submissions WHERE assignment_id = :a)"), {"i": foreign_item, "a": world["a_alice"]})
    await db_session.commit()

    with caplog.at_level("ERROR"):
        res = await client.get(SUB.format(world["a_alice"]), headers=alice(world))
    assert res.status_code == 500
    assert res.json() == {"detail": "This submission can't be processed because of a server-side data problem."}
    assert foreign_item not in res.text and "Bob" not in res.text
    assert any("Inconsistent homework submission data" in r.getMessage() for r in caplog.records)


# --- Information leakage -------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_hidden_data_in_any_response(client, world, frozen_clock):
    responses = [
        await client.get(SUB.format(world["a_alice"]), headers=alice(world)),
        await put(client, world, "a_alice", [{"position": 1, "selected_option_index": 0},
                                             {"position": 2, "answer_text": "two"}]),
        await client.get(SUB.format(world["a_alice"]), headers=alice(world)),
        await put(client, world, "a_alice", [{"position": 1, "selected_option_index": 9}], version=1),
        await put(client, world, "a_alice", [{"position": 2, "clear": True}], version=4),
        await submit(client, world, "a_alice", version=1),
        await client.get(SUB.format(world["a_alice"]), headers=alice(world)),
    ]
    for res in responses:
        for hidden in HIDDEN + (world["alice"], world["u_alice"]):
            assert hidden not in res.text, (hidden, res.text)
    for res in (responses[0], responses[1], responses[2], responses[5], responses[6]):
        assert set(res.json()) == OUT_FIELDS
        for answer in res.json()["answers"]:
            assert set(answer) == {"position", "answer_text", "selected_option_index"}


@pytest.mark.asyncio
async def test_openapi_response_schemas_have_no_hidden_fields(client):
    spec = (await client.get("/api/v1/openapi.json")).json()
    paths = spec["paths"]
    base = "/api/v1/students/me/homework/assignments/{assignment_id}/submission"
    assert set(paths[base]) == {"get", "put"} and set(paths[base + "/submit"]) == {"post"}
    schemas = spec["components"]["schemas"]
    assert set(schemas["HomeworkSubmissionOut"]["properties"]) == OUT_FIELDS
    assert set(schemas["SubmissionAnswerOut"]["properties"]) == {"position", "answer_text", "selected_option_index"}
    for operation in (paths[base]["get"], paths[base]["put"], paths[base + "/submit"]["post"]):
        ok = operation["responses"].get("200") or operation["responses"].get("201")
        assert ok["content"]["application/json"]["schema"]["$ref"].endswith("/HomeworkSubmissionOut")
    assert set(paths[base]["put"]["responses"]) >= {"200", "201", "422"}
    # Field definitions only: the descriptions deliberately say what is NOT returned.
    fields = str(schemas["HomeworkSubmissionOut"]["properties"]) + str(schemas["SubmissionAnswerOut"]["properties"])
    for hidden in ("correct_answer", "marking_rubric", "marks", "grade", "feedback", "competency", "school_id"):
        assert hidden not in fields
    # The teammate's assessment SubmissionOut keeps its public schema name.
    assert "SubmissionOut" in schemas and "rubric" not in str(schemas["SubmissionOut"]["properties"])


@pytest.mark.asyncio
async def test_existing_student_assignment_endpoints_still_work(client, world, frozen_clock):
    await put(client, world, "a_alice", [{"position": 2, "answer_text": "a"}])
    listing = await client.get("/api/v1/students/me/homework/assignments", headers=alice(world))
    assert listing.status_code == 200 and {a["status"] for a in listing.json()} == {"assigned"}
    detail = await client.get(f"/api/v1/students/me/homework/assignments/{world['a_alice']}", headers=alice(world))
    assert detail.status_code == 200 and len(detail.json()["items"]) == 4 and "SECRET" not in detail.text


# --- Final review: corrupted data writes nothing; only real duplicates become 409 -------------------------


@pytest.mark.asyncio
async def test_writes_on_corrupted_data_are_refused_before_anything_is_saved(client, db_session, world,
                                                                             frozen_clock):
    """Found in the final review: the consistency check used to run only when building the
    response, after the commit. A PUT saved its answers, and a submit saved the lock and the
    audit event, and then both returned 500."""
    await put(client, world, "a_alice", [{"position": 2, "answer_text": "a"}])
    foreign_item = await db_session.scalar(select(HomeworkDraftItemRecord.id).join(
        HomeworkAssignmentRecord, HomeworkAssignmentRecord.draft_id == HomeworkDraftItemRecord.draft_id).filter(
        HomeworkAssignmentRecord.id == world["a_bob"], HomeworkDraftItemRecord.position == 2))
    await db_session.execute(text(
        "UPDATE homework_submission_answers SET draft_item_id = :i WHERE submission_id = "
        "(SELECT id FROM homework_submissions WHERE assignment_id = :a)"), {"i": foreign_item, "a": world["a_alice"]})
    await db_session.commit()

    for res in (await put(client, world, "a_alice", [{"position": 3, "answer_text": "new"}], version=1),
                await submit(client, world, "a_alice", version=1)):
        assert res.status_code == 500
        assert res.json() == {"detail": "This submission can't be processed because of a server-side data problem."}

    row = (await db_session.execute(text(
        "SELECT status, version FROM homework_submissions WHERE assignment_id = :a"), {"a": world["a_alice"]})).one()
    assert tuple(row) == ("in_progress", 1)  # nothing saved, not locked
    answers = await db_session.scalar(text(
        "SELECT COUNT(*) FROM homework_submission_answers WHERE submission_id = "
        "(SELECT id FROM homework_submissions WHERE assignment_id = :a)"), {"a": world["a_alice"]})
    assert answers == 1  # the new answer wasn't added
    assert await audits(db_session, world["u_alice"]) == 0


class _FakeResult:
    def __init__(self, row):
        self.row = row

    def first(self):
        return self.row


class _FakeSession:
    """Just enough of AsyncSession for _commit_submission: commit fails with `error`."""

    def __init__(self, error, winner):
        self.error, self.winner, self.rolled_back = error, winner, False

    async def commit(self):
        raise self.error

    async def rollback(self):
        self.rolled_back = True

    async def execute(self, statement):
        return _FakeResult(("winner-id",) if self.winner else None)


def _integrity(message):
    return IntegrityError("INSERT ...", {}, Exception(message))


SQLITE_DUPLICATE = "UNIQUE constraint failed: homework_submissions.assignment_id"
POSTGRES_DUPLICATE = 'duplicate key value violates unique constraint "uq_homework_submissions_assignment"'
UNRELATED = "NOT NULL constraint failed: audit_events.user_name"


@pytest.mark.asyncio
@pytest.mark.parametrize("message, created, winner, expect_409", [
    (SQLITE_DUPLICATE, True, True, True),
    (POSTGRES_DUPLICATE, True, True, True),
    (SQLITE_DUPLICATE, True, False, False),  # no winner: not a lost race
    (SQLITE_DUPLICATE, False, True, False),  # this request didn't create one
    (UNRELATED, True, True, False),  # an unrelated fault while someone else created one: still re-raised
    (UNRELATED, False, False, False),
])
async def test_only_a_real_duplicate_first_save_becomes_409(message, created, winner, expect_409):
    from fastapi import HTTPException

    session = _FakeSession(_integrity(message), winner)
    if expect_409:
        with pytest.raises(HTTPException) as caught:
            await homework_router._commit_submission(session, "a1", created)
        assert caught.value.status_code == 409
    else:
        with pytest.raises(IntegrityError):
            await homework_router._commit_submission(session, "a1", created)
    assert session.rolled_back
