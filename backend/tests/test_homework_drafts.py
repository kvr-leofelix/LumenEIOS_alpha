"""Tests for saved homework drafts: save, list, get, review actions, edits, snapshots,
rollback, and creating the new tables on an existing database."""
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import func, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine

from backend.app.core.security import create_access_token
from backend.app.db.session import Base
from backend.app.models.entities import ClassSection, QuestionBankItem, Student, Subject
from backend.app.modules.differentiated_homework import router as homework_router
from backend.app.modules.differentiated_homework.draft_service import (
    TRANSITIONS,
    InvalidTransition,
    next_status,
)
from backend.app.modules.differentiated_homework.models import HomeworkDraftItemRecord, HomeworkDraftRecord

SAVE = "/api/v1/students/{}/homework/drafts"
PREVIEW = "/api/v1/students/{}/homework/preview"
LIST = "/api/v1/homework/drafts"
ONE = "/api/v1/homework/drafts/{}"


def uid(prefix):
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def body(subject_id, max_questions=3, **extra):
    return {"subject_id": subject_id, "max_questions": max_questions, "include_ai_generated": False, **extra}


@pytest.fixture
def teacher2_token():
    return create_access_token("user-teacher-2", school_id="school-1", role="teacher")


@pytest_asyncio.fixture
async def world(db_session):
    subj = Subject(id=uid("drf-subj"), name="Draft Subject", code=uid("DRF"), grade=8)
    empty = Subject(id=uid("drf-empty"), name="Empty", code=uid("DRFE"), grade=8)
    cls = ClassSection(id=uid("drf-class"), school_id="school-1", grade=8, section="D", name="Draft Class",
                       subject_ids_json=[subj.id, empty.id])
    student = Student(id=uid("drf-student"), school_id="school-1", class_id=cls.id, class_name=cls.name,
                      name="Private Draft Name", roll_no=902, lu_score=40, cu_score=70, au_score=60, ct_score=50,
                      overall_score=55)
    p = uid("drfq")
    questions = [
        QuestionBankItem(id=f"{p}-l1", school_id="school-1", subject_id=subj.id, text="LU question one",
                         type="mcq", options_json=["A", "B", "C"], marks=3, competency="LU", bloom_level="Apply",
                         correct_answer="SECRET-ANSWER-1", marking_rubric="SECRET-RUBRIC-1"),
        QuestionBankItem(id=f"{p}-l2", school_id="school-1", subject_id=subj.id, text="LU question two",
                         type="short", marks=4, competency="LU", bloom_level="Analyze",
                         correct_answer="SECRET-ANSWER-2", marking_rubric="SECRET-RUBRIC-2"),
        QuestionBankItem(id=f"{p}-t1", school_id="school-1", subject_id=subj.id, text="CT question one",
                         type="short", marks=2, competency="CT", bloom_level="Evaluate",
                         correct_answer="SECRET-ANSWER-3", marking_rubric="SECRET-RUBRIC-3"),
    ]
    rows = [subj, empty, cls, student, *questions]
    # IDs captured before any test runs: a test may expire or roll back these objects.
    ids = {"s": student.id, "c": cls.id, "j": subj.id, "e": empty.id, "p": f"{p}-%"}
    db_session.add_all(rows)
    await db_session.commit()

    yield {"subj": subj, "empty": empty, "student": student, "p": p, "questions": questions}

    # Plain SQL by captured IDs. Some tests change or delete questions, so those go by ID pattern.
    await db_session.rollback()
    for sql in (
        "DELETE FROM homework_assignments WHERE student_id = :s",
        "DELETE FROM homework_draft_items WHERE draft_id IN (SELECT id FROM homework_drafts WHERE student_id = :s)",
        "DELETE FROM homework_drafts WHERE student_id = :s",
        "DELETE FROM question_bank_items WHERE id LIKE :p",
        "DELETE FROM students WHERE id = :s",
        "DELETE FROM classes WHERE id = :c",
        "DELETE FROM subjects WHERE id IN (:j, :e)",
    ):
        await db_session.execute(text(sql), ids)
    await db_session.commit()


async def draft_count(db, student_id):
    return await db.scalar(select(func.count()).select_from(HomeworkDraftRecord)
                           .filter(HomeworkDraftRecord.student_id == student_id))


async def save(client, token, world, **extra):
    return await client.post(SAVE.format(world["student"].id), json=body(world["subj"].id, **extra),
                             headers=auth(token))


# --- Saving ------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_save_creates_draft_with_snapshots_and_hides_answers(client, db_session, teacher_token, world):
    res = await save(client, teacher_token, world)

    assert res.status_code == 201
    out = res.json()
    p = world["p"]
    assert out["status"] == "draft" and out["created_by"] == "user-teacher-1"
    assert out["school_id"] == "school-1" and out["subject_id"] == world["subj"].id
    assert [i["source_question_id"] for i in out["items"]] == [f"{p}-l1", f"{p}-l2", f"{p}-t1"]
    assert out["items"][0]["options"] == ["A", "B", "C"] and out["items"][0]["type"] == "mcq"
    assert out["total_marks"] == 9 and out["question_count"] == 3 and out["is_complete"]
    assert out["reviewed_by"] is None
    assert "SECRET" not in res.text and "Private Draft Name" not in res.text

    # The answer key is stored for later grading, just never returned.
    stored = (await db_session.execute(
        select(HomeworkDraftItemRecord).filter(HomeworkDraftItemRecord.draft_id == out["id"])
        .order_by(HomeworkDraftItemRecord.position))).scalars().all()
    assert [i.correct_answer for i in stored] == ["SECRET-ANSWER-1", "SECRET-ANSWER-2", "SECRET-ANSWER-3"]

    fetched = await client.get(ONE.format(out["id"]), headers=auth(teacher_token))
    assert fetched.status_code == 200 and "SECRET" not in fetched.text


@pytest.mark.asyncio
async def test_preview_still_saves_nothing(client, db_session, teacher_token, world):
    res = await client.post(PREVIEW.format(world["student"].id), json=body(world["subj"].id), headers=auth(teacher_token))
    assert res.status_code == 200
    assert await draft_count(db_session, world["student"].id) == 0


@pytest.mark.asyncio
async def test_expected_question_ids_must_match(client, db_session, teacher_token, world):
    p = world["p"]
    good = await save(client, teacher_token, world, expected_question_ids=[f"{p}-l1", f"{p}-l2", f"{p}-t1"])
    assert good.status_code == 201

    bad = await save(client, teacher_token, world, expected_question_ids=[f"{p}-l2", f"{p}-l1", f"{p}-t1"])
    assert bad.status_code == 409
    assert await draft_count(db_session, world["student"].id) == 1


@pytest.mark.asyncio
async def test_empty_selection_cannot_be_saved(client, db_session, teacher_token, world):
    res = await client.post(SAVE.format(world["student"].id), json=body(world["empty"].id), headers=auth(teacher_token))
    assert res.status_code == 422
    assert await draft_count(db_session, world["student"].id) == 0


@pytest.mark.asyncio
async def test_save_access_rules(client, db_session, parent_token, student_token, other_school_teacher_token, world):
    for token in (parent_token, student_token, other_school_teacher_token):
        assert (await save(client, token, world)).status_code == 403
    assert await draft_count(db_session, world["student"].id) == 0


@pytest.mark.asyncio
async def test_question_changed_while_saving_is_refused(client, db_session, teacher_token, world, monkeypatch):
    real = homework_router.load_question_snapshots

    async def changed(db, ids, school_id, subject_id):
        snaps = await real(db, ids, school_id, subject_id)
        first = ids[0]
        snaps[first] = snaps[first].model_copy(update={"marks": 99})
        return snaps

    monkeypatch.setattr(homework_router, "load_question_snapshots", changed)
    res = await save(client, teacher_token, world)
    assert res.status_code == 409
    assert await draft_count(db_session, world["student"].id) == 0


@pytest.mark.asyncio
async def test_partial_failure_rolls_back_everything(client, db_session, teacher_token, world, monkeypatch):
    real = homework_router.build_draft_record

    def broken(draft, snapshots, request, created_by):
        record = real(draft, snapshots, request, created_by)
        record.items[1].position = record.items[0].position  # violates unique (draft, position)
        return record

    monkeypatch.setattr(homework_router, "build_draft_record", broken)
    with pytest.raises(IntegrityError):
        await save(client, teacher_token, world)

    assert await draft_count(db_session, world["student"].id) == 0
    orphans = await db_session.scalar(text(
        "SELECT COUNT(*) FROM homework_draft_items WHERE draft_id NOT IN (SELECT id FROM homework_drafts)"))
    assert orphans == 0


@pytest.mark.asyncio
async def test_snapshots_survive_question_bank_changes(client, db_session, teacher_token, world):
    out = (await save(client, teacher_token, world)).json()
    p = world["p"]

    await db_session.execute(text("UPDATE question_bank_items SET text = 'CHANGED', marks = 1, options_json = '[]' "
                                  "WHERE id = :id"), {"id": f"{p}-l1"})
    await db_session.execute(text("DELETE FROM question_bank_items WHERE id = :id"), {"id": f"{p}-t1"})
    await db_session.commit()

    again = (await client.get(ONE.format(out["id"]), headers=auth(teacher_token))).json()
    assert again["items"] == out["items"]
    assert again["items"][0]["text"] == "LU question one" and again["items"][0]["marks"] == 3


# --- Listing and viewing -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_and_get_follow_ownership_and_school(client, teacher_token, teacher2_token, principal_token,
                                                        admin_token, other_school_teacher_token, world):
    draft_id = (await save(client, teacher_token, world)).json()["id"]

    def ids(res):
        return [d["id"] for d in res.json()]

    assert draft_id in ids(await client.get(LIST, headers=auth(teacher_token)))
    assert draft_id not in ids(await client.get(LIST, headers=auth(teacher2_token)))
    assert draft_id in ids(await client.get(LIST, headers=auth(principal_token)))
    assert draft_id in ids(await client.get(LIST, headers=auth(admin_token)))
    assert draft_id not in ids(await client.get(LIST, headers=auth(other_school_teacher_token)))

    assert (await client.get(ONE.format(draft_id), headers=auth(teacher_token))).status_code == 200
    assert (await client.get(ONE.format(draft_id), headers=auth(principal_token))).status_code == 200
    assert (await client.get(ONE.format(draft_id), headers=auth(teacher2_token))).status_code == 403
    assert (await client.get(ONE.format(draft_id), headers=auth(other_school_teacher_token))).status_code == 403
    assert (await client.get(ONE.format("no-such-draft"), headers=auth(teacher_token))).status_code == 404


@pytest.mark.asyncio
async def test_parents_and_students_cannot_list_or_view(client, teacher_token, parent_token, student_token, world):
    draft_id = (await save(client, teacher_token, world)).json()["id"]
    for token in (parent_token, student_token):
        assert (await client.get(LIST, headers=auth(token))).status_code == 403
        assert (await client.get(ONE.format(draft_id), headers=auth(token))).status_code == 403


@pytest.mark.asyncio
async def test_list_filters(client, teacher_token, world):
    draft_id = (await save(client, teacher_token, world)).json()["id"]

    by_student = await client.get(LIST, params={"student_id": world["student"].id}, headers=auth(teacher_token))
    assert [d["id"] for d in by_student.json()] == [draft_id]
    approved = await client.get(LIST, params={"status": "approved", "student_id": world["student"].id},
                                headers=auth(teacher_token))
    assert approved.json() == []
    assert (await client.get(LIST, params={"status": "bogus"}, headers=auth(teacher_token))).status_code == 422


# --- Status changes -------------------------------------------------------------------------


def test_transition_table_allows_only_listed_moves():
    statuses = ["draft", "approved", "rejected", "assigned"]
    for action, (source, target) in TRANSITIONS.items():
        assert next_status(source, action) == target
        for other in statuses:
            if other != source:
                with pytest.raises(InvalidTransition):
                    next_status(other, action)
    with pytest.raises(InvalidTransition):
        next_status("draft", "publish")


@pytest.mark.asyncio
async def test_approve_reject_reopen_flow(client, teacher_token, world):
    draft_id = (await save(client, teacher_token, world)).json()["id"]
    url = ONE.format(draft_id)

    rejected = await client.post(f"{url}/reject", json={"note": "Too easy"}, headers=auth(teacher_token))
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected" and rejected.json()["review_note"] == "Too easy"
    assert rejected.json()["reviewed_by"] == "user-teacher-1"

    assert (await client.post(f"{url}/approve", headers=auth(teacher_token))).status_code == 409

    reopened = await client.post(f"{url}/reopen", headers=auth(teacher_token))
    assert reopened.json()["status"] == "draft" and reopened.json()["reviewed_by"] is None

    approved = await client.post(f"{url}/approve", headers=auth(teacher_token))
    assert approved.json()["status"] == "approved" and approved.json()["reviewed_at"] is not None

    for action in ("approve", "reject", "reopen"):
        assert (await client.post(f"{url}/{action}", headers=auth(teacher_token))).status_code == 409


@pytest.mark.asyncio
async def test_other_teacher_cannot_review_but_principal_can(client, teacher_token, teacher2_token,
                                                            principal_token, world):
    draft_id = (await save(client, teacher_token, world)).json()["id"]

    assert (await client.post(f"{ONE.format(draft_id)}/approve", headers=auth(teacher2_token))).status_code == 403
    res = await client.post(f"{ONE.format(draft_id)}/approve", headers=auth(principal_token))
    assert res.status_code == 200 and res.json()["reviewed_by"] == "user-principal-1"


@pytest.mark.asyncio
async def test_review_note_validation(client, teacher_token, world):
    draft_id = (await save(client, teacher_token, world)).json()["id"]
    url = f"{ONE.format(draft_id)}/reject"
    assert (await client.post(url, json={"note": "x" * 2001}, headers=auth(teacher_token))).status_code == 422
    assert (await client.post(url, json={"note": "ok", "extra": 1}, headers=auth(teacher_token))).status_code == 422


# --- Editing ------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_remove_item_renumbers_and_recounts(client, teacher_token, world):
    out = (await save(client, teacher_token, world)).json()
    p = world["p"]

    res = await client.delete(f"{ONE.format(out['id'])}/items/3", headers=auth(teacher_token))
    assert res.status_code == 200
    edited = res.json()
    assert [(i["position"], i["source_question_id"]) for i in edited["items"]] == [(1, f"{p}-l1"), (2, f"{p}-l2")]
    assert edited["question_count"] == 2 and edited["total_marks"] == 7 and edited["shortfall"] == 1
    assert edited["rationale"]["targeted_competencies"] == ["LU"]
    assert edited["rationale"]["summary"].startswith("Targets LU (40).")
    assert any("removed" in n for n in edited["notes"])

    middle = await client.delete(f"{ONE.format(out['id'])}/items/1", headers=auth(teacher_token))
    assert [(i["position"], i["source_question_id"]) for i in middle.json()["items"]] == [(1, f"{p}-l2")]


@pytest.mark.asyncio
async def test_remove_item_rules(client, teacher_token, teacher2_token, world):
    draft_id = (await save(client, teacher_token, world, max_questions=1)).json()["id"]
    url = ONE.format(draft_id)

    assert (await client.delete(f"{url}/items/1", headers=auth(teacher_token))).status_code == 422  # last item
    assert (await client.delete(f"{url}/items/9", headers=auth(teacher_token))).status_code == 404
    assert (await client.delete(f"{url}/items/1", headers=auth(teacher2_token))).status_code == 403

    await client.post(f"{url}/approve", headers=auth(teacher_token))
    assert (await client.delete(f"{url}/items/1", headers=auth(teacher_token))).status_code == 409


@pytest.mark.asyncio
async def test_rejected_draft_is_edited_through_reopen(client, teacher_token, world):
    draft_id = (await save(client, teacher_token, world)).json()["id"]
    url = ONE.format(draft_id)
    await client.post(f"{url}/reject", headers=auth(teacher_token))

    assert (await client.delete(f"{url}/items/1", headers=auth(teacher_token))).status_code == 409
    await client.post(f"{url}/reopen", headers=auth(teacher_token))
    assert (await client.delete(f"{url}/items/1", headers=auth(teacher_token))).status_code == 200


# --- Creating the new tables on an existing database ---------------------------------------------


@pytest.mark.asyncio
async def test_create_all_adds_draft_tables_without_touching_existing_data(tmp_path):
    """Simulates an existing database that predates these tables, using a disposable file."""
    engine = create_async_engine(f"sqlite+aiosqlite:///{(tmp_path / 'old.db').as_posix()}")
    new_tables = {"homework_drafts", "homework_draft_items", "homework_assignments"}
    old_tables = [t for name, t in Base.metadata.tables.items() if name not in new_tables]
    try:
        async with engine.begin() as conn:
            await conn.run_sync(lambda c: Base.metadata.create_all(c, tables=old_tables))
            await conn.execute(text(
                "INSERT INTO schools (id, name, location, state, infrastructure_tier, academic_year, "
                "student_count, teacher_count, class_count, pacing_risk, official_working_days, is_archived, "
                "created_at) VALUES ('keep-me', 'Existing School', 'X', 'Y', 'standard', '2026-2027', 1, 1, 1, "
                "'low', 220, 0, '2026-01-01 00:00:00')"))
        async with engine.connect() as conn:
            before = set(await conn.run_sync(lambda c: inspect(c).get_table_names()))
        assert not before & new_tables

        for _ in range(2):  # what init_db does on startup; running twice must be safe
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

        async with engine.connect() as conn:
            after = set(await conn.run_sync(lambda c: inspect(c).get_table_names()))
            kept = (await conn.execute(text("SELECT name FROM schools WHERE id = 'keep-me'"))).scalar()
        assert new_tables <= after and before <= after
        assert kept == "Existing School"

        async with engine.begin() as conn:
            with pytest.raises(IntegrityError, match="ck_homework_drafts_status"):  # status rule enforced
                await conn.execute(text(
                    "INSERT INTO homework_drafts (id, student_id, school_id, subject_id, created_by, status, "
                    "requested_questions, include_ai_generated, question_count, total_marks, shortfall, "
                    "rationale_json, notes_json, created_at, updated_at, version) VALUES ('d', 's', 'x', 'y', 'u', "
                    "'bogus', 1, 0, 1, 1, 0, '{}', '[]', '2026-01-01', '2026-01-01', 1)"))
    finally:
        await engine.dispose()


# --- Phase 1 audit: regression tests ------------------------------------------------------


@pytest.mark.asyncio
async def test_timestamps_are_reported_the_same_way_before_and_after_reload(client, teacher_token, world):
    saved = (await save(client, teacher_token, world)).json()
    fetched = (await client.get(ONE.format(saved["id"]), headers=auth(teacher_token))).json()
    assert saved["created_at"] == fetched["created_at"]

    approved = (await client.post(f"{ONE.format(saved['id'])}/approve", headers=auth(teacher_token))).json()
    fetched = (await client.get(ONE.format(saved["id"]), headers=auth(teacher_token))).json()
    assert approved["reviewed_at"] == fetched["reviewed_at"]
    assert approved["updated_at"] == fetched["updated_at"]
    assert fetched["reviewed_at"].endswith("Z") or fetched["reviewed_at"].endswith("+00:00")


def race_after_load(monkeypatch, draft_id, competing_change):
    """Make the endpoint's draft lookup also run a competing write on a separate connection,
    after this request has read the draft but before it writes. That's the race window."""
    from backend.app.db.session import AsyncSessionLocal

    real_load = homework_router._load_draft_for

    async def load_then_race(db, user, draft_id_):
        record = await real_load(db, user, draft_id_)
        async with AsyncSessionLocal() as other:
            row = (await other.execute(
                select(HomeworkDraftRecord).filter(HomeworkDraftRecord.id == draft_id))).scalars().one()
            competing_change(row)
            await other.commit()
        return record

    monkeypatch.setattr(homework_router, "_load_draft_for", load_then_race)


@pytest.mark.asyncio
async def test_concurrent_status_change_is_refused(client, teacher_token, world, monkeypatch):
    from backend.app.modules.differentiated_homework.draft_service import apply_review

    draft_id = (await save(client, teacher_token, world)).json()["id"]
    race_after_load(monkeypatch, draft_id, lambda row: apply_review(row, "reject", "someone-else", None))

    res = await client.post(f"{ONE.format(draft_id)}/approve", headers=auth(teacher_token))
    assert res.status_code == 409

    monkeypatch.undo()
    final = (await client.get(ONE.format(draft_id), headers=auth(teacher_token))).json()
    assert final["status"] == "rejected" and final["reviewed_by"] == "someone-else"


@pytest.mark.asyncio
async def test_conflict_is_detected_even_when_the_clock_does_not_move(client, teacher_token, world, monkeypatch):
    """Rapid updates can share a timestamp (on Windows most consecutive clock readings are
    identical). Conflict detection must not depend on the clock, so freeze it."""
    from datetime import datetime, timezone

    from backend.app.modules.differentiated_homework import models as homework_models
    from backend.app.modules.differentiated_homework.draft_service import apply_review

    draft_id = (await save(client, teacher_token, world)).json()["id"]
    frozen = datetime(2026, 1, 1, tzinfo=timezone.utc)
    monkeypatch.setattr(homework_models, "utc_now", lambda: frozen)
    # One update under the frozen clock, so a timestamp-based version would now equal `frozen`.
    assert (await client.delete(f"{ONE.format(draft_id)}/items/3", headers=auth(teacher_token))).status_code == 200

    race_after_load(monkeypatch, draft_id, lambda row: apply_review(row, "reject", "someone-else", None))
    res = await client.post(f"{ONE.format(draft_id)}/approve", headers=auth(teacher_token))
    monkeypatch.undo()

    assert res.status_code == 409
    final = (await client.get(ONE.format(draft_id), headers=auth(teacher_token))).json()
    assert final["status"] == "rejected" and final["reviewed_by"] == "someone-else"


@pytest.mark.asyncio
async def test_version_increases_by_one_on_every_change(client, db_session, teacher_token, world):
    async def version_of(draft_id):
        # Selecting a single column always reads the database, not cached objects.
        return await db_session.scalar(select(HomeworkDraftRecord.version).filter(HomeworkDraftRecord.id == draft_id))

    draft_id = (await save(client, teacher_token, world)).json()["id"]
    url = ONE.format(draft_id)
    seen = [await version_of(draft_id)]
    for method, path in (("delete", f"{url}/items/3"), ("post", f"{url}/reject"), ("post", f"{url}/reopen"),
                         ("post", f"{url}/approve")):
        res = await getattr(client, method)(path, headers=auth(teacher_token))
        assert res.status_code == 200
        seen.append(await version_of(draft_id))
    assert seen == [1, 2, 3, 4, 5]

    # A refused change doesn't bump the version.
    assert (await client.post(f"{url}/approve", headers=auth(teacher_token))).status_code == 409
    assert await version_of(draft_id) == 5


@pytest.mark.asyncio
async def test_concurrent_edit_is_refused(client, teacher_token, world, monkeypatch):
    from backend.app.modules.differentiated_homework.draft_service import apply_review

    draft_id = (await save(client, teacher_token, world)).json()["id"]
    race_after_load(monkeypatch, draft_id, lambda row: apply_review(row, "approve", "someone-else", None))

    res = await client.delete(f"{ONE.format(draft_id)}/items/1", headers=auth(teacher_token))
    assert res.status_code == 409

    monkeypatch.undo()
    final = (await client.get(ONE.format(draft_id), headers=auth(teacher_token))).json()
    assert final["status"] == "approved" and final["question_count"] == 3


@pytest.mark.asyncio
async def test_removing_any_position_never_breaks_unique_positions(client, teacher_token, world):
    """Repeated many times because the bug depended on random primary-key order."""
    for _ in range(8):
        draft_id = (await save(client, teacher_token, world)).json()["id"]
        res = await client.delete(f"{ONE.format(draft_id)}/items/1", headers=auth(teacher_token))
        assert res.status_code == 200
        assert [i["position"] for i in res.json()["items"]] == [1, 2]


@pytest.mark.asyncio
async def test_deleting_a_draft_deletes_its_items(client, db_session, teacher_token, world):
    draft_id = (await save(client, teacher_token, world)).json()["id"]
    record = (await db_session.execute(select(HomeworkDraftRecord).filter(HomeworkDraftRecord.id == draft_id))).scalars().one()
    await db_session.delete(record)
    await db_session.commit()

    remaining = await db_session.scalar(select(func.count()).select_from(HomeworkDraftItemRecord)
                                        .filter(HomeworkDraftItemRecord.draft_id == draft_id))
    assert remaining == 0


@pytest.mark.asyncio
async def test_unknown_role_is_refused_everywhere(client, world):
    token = auth(create_access_token("user-teacher-1", school_id="school-1", role="teacher"))
    draft_id = (await save(client, token["Authorization"].split()[1], world)).json()["id"]

    from backend.app.db.session import AsyncSessionLocal
    from backend.app.models.entities import User

    async with AsyncSessionLocal() as db:
        db.add(User(id="drf-odd-role", email=f"{uid('odd')}@test.invalid", name="Odd", hashed_password="x",
                    role="staff", school_id="school-1"))
        await db.commit()
    try:
        odd = auth(create_access_token("drf-odd-role", school_id="school-1", role="staff"))
        assert (await client.get(LIST, headers=odd)).status_code == 403
        assert (await client.get(ONE.format(draft_id), headers=odd)).status_code == 403
        assert (await client.post(f"{ONE.format(draft_id)}/approve", headers=odd)).status_code == 403
        assert (await save(client, odd["Authorization"].split()[1], world)).status_code == 403
    finally:
        async with AsyncSessionLocal() as db:
            await db.execute(text("DELETE FROM users WHERE id = 'drf-odd-role'"))
            await db.commit()


# --- Phase 1 completion: deterministic reproductions and fail-closed checks -------------------


async def draft_with_controlled_item_ids(db, world, ids_by_position):
    """Build a draft directly, choosing item primary keys, so the database update order is known.

    SQLAlchemy sends UPDATEs for existing rows in primary-key order. Giving later positions
    smaller keys makes a naive renumbering collide every time, not by chance.
    """
    p = world["p"]
    draft = HomeworkDraftRecord(
        student_id=world["student"].id, school_id="school-1", subject_id=world["subj"].id,
        created_by="user-teacher-1", status="draft", requested_questions=len(ids_by_position),
        include_ai_generated=False, question_count=len(ids_by_position), total_marks=2 * len(ids_by_position),
        shortfall=0,
        rationale_json={"targeted_competencies": ["LU"], "weakest": ["LU"],
                        "competency_scores": {"LU": 40, "CU": 70, "AU": 60, "CT": 50},
                        "lowest_score": 40, "highest_score": 70, "score_source": "test", "summary": "x"},
        notes_json=[],
        items=[
            HomeworkDraftItemRecord(id=item_id, position=position, source_question_id=f"{p}-src-{position}",
                                    text=f"Q{position}", type="short", options_json=[], marks=2, competency="LU",
                                    competency_rank=1, bloom_level="Apply", is_ai_generated=False)
            for position, item_id in ids_by_position.items()
        ],
    )
    db.add(draft)
    await db.commit()
    return draft.id


@pytest.mark.asyncio
async def test_renumbering_is_safe_when_update_order_would_collide(client, db_session, teacher_token, world):
    """Deterministic: position 3 has the smallest key, so it is updated first (3 to 2) while
    position 2 still holds 2. Without temporary positions this always breaks the unique rule."""
    base = uid("ord")
    draft_id = await draft_with_controlled_item_ids(
        db_session, world, {1: f"{base}-c", 2: f"{base}-b", 3: f"{base}-a"})

    res = await client.delete(f"{ONE.format(draft_id)}/items/1", headers=auth(teacher_token))

    assert res.status_code == 200
    assert [(i["position"], i["text"]) for i in res.json()["items"]] == [(1, "Q2"), (2, "Q3")]


@pytest.mark.asyncio
async def test_concurrent_removals_cannot_break_positions(client, teacher_token, world, monkeypatch):
    """Two requests remove different questions at the same moment. The second is refused,
    and the stored draft keeps unique, gap-free positions."""
    from backend.app.db.session import AsyncSessionLocal
    from backend.app.modules.differentiated_homework.draft_service import (
        remove_item, renumber_and_recount, stage_renumber,
    )

    draft_id = (await save(client, teacher_token, world)).json()["id"]
    real_load = homework_router._load_draft_for

    async def load_then_race(db, user, draft_id_):
        record = await real_load(db, user, draft_id_)
        async with AsyncSessionLocal() as other:  # the competing request removes position 3 first
            row = (await other.execute(
                select(HomeworkDraftRecord).filter(HomeworkDraftRecord.id == draft_id))).scalars().one()
            removed = remove_item(row, 3)
            await other.flush()
            stage_renumber(row)
            await other.flush()
            renumber_and_recount(row, removed)
            await other.commit()
        return record

    monkeypatch.setattr(homework_router, "_load_draft_for", load_then_race)
    res = await client.delete(f"{ONE.format(draft_id)}/items/1", headers=auth(teacher_token))
    monkeypatch.undo()

    assert res.status_code == 409
    final = (await client.get(ONE.format(draft_id), headers=auth(teacher_token))).json()
    assert [i["position"] for i in final["items"]] == [1, 2]
    assert final["question_count"] == 2 and final["total_marks"] == 7


@pytest.mark.asyncio
async def test_sqlite_foreign_key_behaviour_for_draft_tables(tmp_path):
    """What SQLite actually does with these tables, on a disposable database.

    - Foreign keys OFF (the SQLite default, and this app's engine setting): deleting a draft with
      raw SQL leaves its items behind. Only ORM deletes cascade (see the ORM test above).
    - Foreign keys ON: the ON DELETE CASCADE in the table definition removes the items.
    """
    # With foreign keys ON, SQLite needs every referenced table to exist, even if empty.
    tables = [Base.metadata.tables[n] for n in ("schools", "users", "classes", "students",
                                                "homework_drafts", "homework_draft_items")]

    async def items_left_after_raw_delete(foreign_keys_on):
        path = (tmp_path / f"fk{int(foreign_keys_on)}.db").as_posix()
        engine = create_async_engine(f"sqlite+aiosqlite:///{path}")
        try:
            async with engine.begin() as conn:
                # The referenced tables exist but stay empty, so the draft's student and user
                # references point nowhere. Rows are inserted with checking off, then the delete
                # runs with the setting under test.
                await conn.run_sync(lambda c: Base.metadata.create_all(c, tables=tables))
                await conn.execute(text("PRAGMA foreign_keys = OFF"))
                await conn.execute(text(
                    "INSERT INTO homework_drafts (id, student_id, school_id, subject_id, created_by, status, "
                    "requested_questions, include_ai_generated, question_count, total_marks, shortfall, "
                    "rationale_json, notes_json, created_at, updated_at, version) VALUES ('d1', 'st1', 's1', 'sub', "
                    "'u1', 'draft', 1, 0, 1, 2, 0, '{}', '[]', '2026-01-01', '2026-01-01', 1)"))
                await conn.execute(text(
                    "INSERT INTO homework_draft_items (id, draft_id, position, source_question_id, text, type, "
                    "options_json, marks, competency, competency_rank, bloom_level, is_ai_generated, created_at) "
                    "VALUES ('i1', 'd1', 1, 'q', 't', 'short', '[]', 2, 'LU', 1, 'Apply', 0, '2026-01-01')"))
            async with engine.begin() as conn:
                await conn.execute(text(f"PRAGMA foreign_keys = {'ON' if foreign_keys_on else 'OFF'}"))
                assert (await conn.execute(text("PRAGMA foreign_keys"))).scalar() == int(foreign_keys_on)
                await conn.execute(text("DELETE FROM homework_drafts WHERE id = 'd1'"))
                return (await conn.execute(text("SELECT COUNT(*) FROM homework_draft_items"))).scalar()
        finally:
            await engine.dispose()

    assert await items_left_after_raw_delete(foreign_keys_on=False) == 1  # orphan: documented limitation
    assert await items_left_after_raw_delete(foreign_keys_on=True) == 0   # schema cascade is correct


@pytest_asyncio.fixture
async def odd_users(db_session):
    """Users with malformed or edge-case authorization data."""
    from backend.app.models.entities import User

    def make(key, role, school_id):
        return User(id=uid(f"odd-{key}"), email=f"{uid(key)}@test.invalid", name=key, hashed_password="x",
                    role=role, school_id=school_id)

    users = {
        "blank_role": make("blank", "", "school-1"),
        "capital_role": make("cap", "Teacher", "school-1"),
        "padded_role": make("pad", "admin ", "school-1"),
        "schoolless_principal": make("prin", "principal", None),
    }
    db_session.add_all(users.values())
    await db_session.commit()
    ids = [u.id for u in users.values()]
    yield users
    for user_id in ids:
        await db_session.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})
    await db_session.commit()


@pytest.mark.asyncio
async def test_malformed_roles_fail_closed(client, teacher_token, world, odd_users):
    draft_id = (await save(client, teacher_token, world)).json()["id"]
    for key in ("blank_role", "capital_role", "padded_role"):
        user = odd_users[key]
        # The token claims "teacher", but the role stored on the user is what counts.
        headers = auth(create_access_token(user.id, school_id=user.school_id, role="teacher"))
        assert (await client.get(LIST, headers=headers)).status_code == 403, key
        assert (await client.get(ONE.format(draft_id), headers=headers)).status_code == 403, key
        assert (await client.post(f"{ONE.format(draft_id)}/approve", headers=headers)).status_code == 403, key
        assert (await client.delete(f"{ONE.format(draft_id)}/items/1", headers=headers)).status_code == 403, key
        save_res = await client.post(SAVE.format(world["student"].id), json=body(world["subj"].id), headers=headers)
        assert save_res.status_code == 403, key


@pytest.mark.asyncio
async def test_principal_without_any_school_sees_nothing(client, teacher_token, world, odd_users):
    draft_id = (await save(client, teacher_token, world)).json()["id"]
    user = odd_users["schoolless_principal"]
    headers = auth(create_access_token(user.id, role="principal"))

    assert draft_id not in [d["id"] for d in (await client.get(LIST, headers=headers)).json()]
    assert (await client.get(ONE.format(draft_id), headers=headers)).status_code == 403


@pytest.mark.asyncio
async def test_teacher_who_lost_school_access_loses_their_drafts(client, db_session, world):
    from backend.app.models.entities import User

    teacher_id = uid("moved-teacher")
    db_session.add(User(id=teacher_id, email=f"{uid('m')}@test.invalid", name="Moved", hashed_password="x",
                        role="teacher", school_id="school-1"))
    await db_session.commit()
    try:
        headers = auth(create_access_token(teacher_id, school_id="school-1", role="teacher"))
        draft_id = (await client.post(SAVE.format(world["student"].id), json=body(world["subj"].id),
                                      headers=headers)).json()["id"]

        await db_session.execute(text("UPDATE users SET school_id = 'school-3' WHERE id = :id"), {"id": teacher_id})
        await db_session.commit()

        assert (await client.get(ONE.format(draft_id), headers=headers)).status_code == 403
        assert draft_id not in [d["id"] for d in (await client.get(LIST, headers=headers)).json()]
        assert (await client.post(f"{ONE.format(draft_id)}/approve", headers=headers)).status_code == 403
    finally:
        await db_session.execute(text("DELETE FROM users WHERE id = :id"), {"id": teacher_id})
        await db_session.commit()


def _broken_signature_token():
    token = create_access_token("user-teacher-1", role="teacher")
    return token[:-4] + ("AAAA" if not token.endswith("AAAA") else "BBBB")


@pytest.mark.asyncio
@pytest.mark.parametrize("header", ["Bearer not-a-jwt", "Bearer " + _broken_signature_token(), "Basic dXNlcjpwYXNz"])
async def test_malformed_tokens_never_reveal_drafts(client, teacher_token, world, header):
    from backend.app.core.config import settings

    draft_id = (await save(client, teacher_token, world)).json()["id"]
    previous = settings.DEMO_MODE
    settings.DEMO_MODE = False  # otherwise existing shared code treats a missing token as admin
    try:
        for res in (await client.get(LIST, headers={"Authorization": header}),
                    await client.get(ONE.format(draft_id), headers={"Authorization": header})):
            assert res.status_code == 401
            assert draft_id not in res.text
    finally:
        settings.DEMO_MODE = previous


@pytest.mark.asyncio
async def test_token_for_unknown_user_is_refused(client, teacher_token, world):
    draft_id = (await save(client, teacher_token, world)).json()["id"]
    ghost = auth(create_access_token("no-such-user", school_id="school-1", role="admin"))
    res = await client.get(ONE.format(draft_id), headers=ghost)
    assert res.status_code in (401, 404) and draft_id not in res.text
