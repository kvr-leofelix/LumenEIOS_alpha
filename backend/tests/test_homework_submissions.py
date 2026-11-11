"""Phase 1 of answer submission: models, request shapes and the submission service. No API yet.

Unit tests build ORM objects in memory (no database). Database tests use the isolated test
database from conftest, plus throwaway SQLite files for foreign keys and create_all.
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from pydantic import ValidationError
from sqlalchemy import event, func, inspect, select, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm.exc import StaleDataError
from sqlalchemy.schema import CreateTable

from backend.app.db.session import AsyncSessionLocal, Base
from backend.app.models.entities import Student
from backend.app.modules.differentiated_homework.models import (
    HomeworkAssignmentRecord,
    HomeworkDraftItemRecord,
    HomeworkDraftRecord,
    HomeworkSubmissionAnswerRecord,
    HomeworkSubmissionRecord,
)
from backend.app.modules.differentiated_homework.schemas import (
    MAX_ANSWER_TEXT_LENGTH,
    MAX_ANSWER_UPDATES,
    AnswerUpdate,
    SubmissionAnswerOut,
    SubmissionAnswersUpdate,
    SubmissionFinalizeRequest,
    HomeworkSubmissionOut,
)
from backend.app.modules.differentiated_homework.submission_service import (
    InvalidAnswers,
    NotSubmittable,
    SubmissionLocked,
    VersionConflict,
    finalize_submission,
    save_answers,
    to_submission_out,
    validate_answer_updates,
    items_by_position,
)

NOW = datetime(2026, 11, 9, 10, 0, tzinfo=timezone.utc)
QUESTIONS = (("mcq", ["A", "B", "C"]), ("short", []), ("descriptive", []), ("practical", []))
NEW_TABLES = ("homework_submissions", "homework_submission_answers")


def uid(prefix):
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


def build_assignment(questions=QUESTIONS, due_at=None, status="assigned"):
    """An assigned draft with frozen items (including secret answers) and its assignment."""
    student_id = uid("sub-student")
    items = [
        HomeworkDraftItemRecord(
            id=uid("sub-item"), position=i, source_question_id=uid("src"), text=f"Question {i}", type=qtype,
            options_json=list(options), marks=2, competency="LU", competency_rank=1, bloom_level="Apply",
            is_ai_generated=False, correct_answer="SECRET-ANSWER", marking_rubric="SECRET-RUBRIC",
        )
        for i, (qtype, options) in enumerate(questions, start=1)
    ]
    draft = HomeworkDraftRecord(
        id=uid("sub-draft"), student_id=student_id, school_id="school-1", subject_id="subj-sub",
        created_by="user-teacher-1", status="assigned", requested_questions=len(items),
        include_ai_generated=False, question_count=len(items), total_marks=2 * len(items), shortfall=0,
        notes_json=[], rationale_json={"targeted_competencies": ["LU"], "weakest": ["LU"],
                                       "competency_scores": {"LU": 40, "CU": 70, "AU": 60, "CT": 50},
                                       "lowest_score": 40, "highest_score": 70, "score_source": "test",
                                       "summary": "test"},
        items=items,
    )
    return HomeworkAssignmentRecord(
        id=uid("sub-asg"), draft=draft, draft_id=draft.id, student_id=student_id, school_id="school-1",
        subject_id="subj-sub", assigned_by="user-teacher-1", assigned_at=NOW - timedelta(days=1),
        due_at=due_at, status=status,
    )


def update(*answers, version=None):
    payload = {"answers": list(answers)}
    if version is not None:
        payload["expected_version"] = version
    return SubmissionAnswersUpdate.model_validate(payload)


def stored(submission, assignment):
    """{position: (answer_text, selected_option_index)} for the submission's current answers."""
    positions = {item.id: item.position for item in assignment.draft.items}
    return {positions[a.draft_item_id]: (a.answer_text, a.selected_option_index) for a in submission.answers}


def as_saved(submission, version):
    """Simulate a flushed submission (the ORM sets the version on flush)."""
    submission.version = version
    return submission


# --- Request shapes ----------------------------------------------------------------------------


@pytest.mark.parametrize("payload, action", [
    ({"position": 1, "selected_option_index": 0}, "selected_option_index"),
    ({"position": 2, "answer_text": "Because it doubles."}, "answer_text"),
    ({"position": 3, "clear": True}, "clear"),
])
def test_answer_update_accepts_exactly_one_action(payload, action):
    assert AnswerUpdate.model_validate(payload).action == action


@pytest.mark.parametrize("payload", [
    {"position": 1},  # no action
    {"position": 1, "answer_text": "x", "selected_option_index": 0},  # two actions
    {"position": 1, "answer_text": "x", "clear": True},
    {"position": 1, "answer_text": None},  # explicit null is not "clear"
    {"position": 1, "selected_option_index": None},
    {"position": 1, "clear": None},
    {"position": 1, "clear": False},  # only true is meaningful
    {"position": 1, "answer_text": "   \n "},  # blank text; use clear instead
    {"position": 1, "answer_text": "x" * (MAX_ANSWER_TEXT_LENGTH + 1)},
    {"position": 1, "selected_option_index": -1},
    {"position": 1, "selected_option_index": True},  # bool is not an index
    {"position": 1, "selected_option_index": "1"},
    {"position": 1, "selected_option_index": 1.0},
    {"position": 0, "clear": True},
    {"position": "1", "clear": True},
    {"position": 1, "clear": True, "marks": 5},  # unknown field
])
def test_answer_update_rejects_bad_shapes(payload):
    with pytest.raises(ValidationError):
        AnswerUpdate.model_validate(payload)


def test_text_at_the_length_limit_is_accepted():
    assert AnswerUpdate.model_validate({"position": 1, "answer_text": "x" * MAX_ANSWER_TEXT_LENGTH})


def test_save_request_rules():
    assert SubmissionAnswersUpdate.model_validate({}).answers == []  # an empty save is allowed
    with pytest.raises(ValidationError, match="repeated: \\[2\\]"):
        update({"position": 2, "answer_text": "a"}, {"position": 2, "clear": True})
    with pytest.raises(ValidationError):
        SubmissionAnswersUpdate.model_validate({"expected_version": 0, "answers": []})
    with pytest.raises(ValidationError):
        SubmissionAnswersUpdate.model_validate({"expected_version": "1", "answers": []})
    too_many = [{"position": i, "clear": True} for i in range(1, MAX_ANSWER_UPDATES + 2)]
    with pytest.raises(ValidationError):
        SubmissionAnswersUpdate.model_validate({"answers": too_many})
    with pytest.raises(ValidationError):
        SubmissionFinalizeRequest.model_validate({"expected_version": 1, "answers": []})


def test_student_facing_shapes_have_no_hidden_fields():
    hidden = {"correct_answer", "marking_rubric", "marks", "marks_obtained", "score", "grade", "feedback",
              "competency", "student_id", "school_id", "draft_item_id", "source_question_id"}
    assert not hidden & set(HomeworkSubmissionOut.model_fields)
    assert not hidden & set(SubmissionAnswerOut.model_fields)
    assert set(SubmissionAnswerOut.model_fields) == {"position", "answer_text", "selected_option_index"}


# --- Validation against the frozen questions ---------------------------------------------------------


def test_validation_against_questions_lists_every_problem():
    items = items_by_position(build_assignment(
        questions=QUESTIONS + (("mcq", []), ("essay", []))))  # 5: mcq with no options, 6: unknown type
    updates = [AnswerUpdate.model_validate(p) for p in (
        {"position": 1, "answer_text": "B"},  # text on an mcq
        {"position": 2, "selected_option_index": 0},  # index on a short question
        {"position": 9, "clear": True},  # no such question
        {"position": 5, "selected_option_index": 0},
        {"position": 6, "answer_text": "x"},
        {"position": 3, "answer_text": "fine"},
    )]
    with pytest.raises(InvalidAnswers) as caught:
        validate_answer_updates(updates, items)
    reasons = {p.position: p.reason for p in caught.value.problems}
    assert set(reasons) == {1, 2, 9, 5, 6}
    assert "send selected_option_index" in reasons[1] and "send answer_text" in reasons[2]
    assert "no question" in reasons[9] and "no options" in reasons[5] and "'essay'" in reasons[6]


@pytest.mark.parametrize("index, ok", [(0, True), (2, True), (3, False), (99, False)])
def test_option_index_is_checked_against_frozen_options(index, ok):
    items = items_by_position(build_assignment())
    updates = [AnswerUpdate.model_validate({"position": 1, "selected_option_index": index})]
    if ok:
        assert validate_answer_updates(updates, items)[0].selected_option_index == index
    else:
        with pytest.raises(InvalidAnswers, match="from 0 to 2"):
            validate_answer_updates(updates, items)


def test_service_repeats_shape_checks_for_direct_callers():
    """model_construct skips validation, as a careless internal caller might."""
    items = items_by_position(build_assignment())
    sneaky = [
        AnswerUpdate.model_construct(position=2, answer_text="  ", _fields_set={"position", "answer_text"}),
        AnswerUpdate.model_construct(position=3, answer_text="x" * (MAX_ANSWER_TEXT_LENGTH + 1),
                                     _fields_set={"position", "answer_text"}),
        AnswerUpdate.model_construct(position=4, answer_text="dup", _fields_set={"position", "answer_text"}),
        AnswerUpdate.model_construct(position=4, answer_text="dup", _fields_set={"position", "answer_text"}),
    ]
    with pytest.raises(InvalidAnswers) as caught:
        validate_answer_updates(sneaky, items)
    assert [p.position for p in caught.value.problems] == [2, 3, 4]


# --- Saving (in memory) ------------------------------------------------------------------------


def test_first_save_creates_an_in_progress_submission_from_the_assignment():
    assignment = build_assignment()
    sub = save_answers(assignment, None, update({"position": 1, "selected_option_index": 2},
                                                {"position": 2, "answer_text": "Ten"}), NOW)
    assert (sub.assignment_id, sub.student_id, sub.school_id) == (assignment.id, assignment.student_id, "school-1")
    assert sub.status == "in_progress" and sub.is_late is False and sub.submitted_at is None
    assert stored(sub, assignment) == {1: (None, 2), 2: ("Ten", None)}


def test_first_save_must_not_claim_a_version():
    with pytest.raises(VersionConflict, match="omit expected_version"):
        save_answers(build_assignment(), None, update(version=1), NOW)


def test_partial_save_changes_only_listed_answers_and_clear_removes_one():
    assignment = build_assignment()
    sub = as_saved(save_answers(assignment, None, update(
        {"position": 1, "selected_option_index": 0},
        {"position": 2, "answer_text": "first"},
        {"position": 3, "answer_text": "keep me"}), NOW), 1)

    save_answers(assignment, sub, update(
        {"position": 1, "selected_option_index": 1},  # change
        {"position": 2, "clear": True},  # clear
        {"position": 4, "clear": True},  # clearing an unanswered question does nothing
        version=1), NOW)

    assert stored(sub, assignment) == {1: (None, 1), 3: ("keep me", None)}


def test_an_invalid_request_changes_nothing():
    assignment = build_assignment()
    sub = as_saved(save_answers(assignment, None, update({"position": 2, "answer_text": "original"}), NOW), 1)
    before = (stored(sub, assignment), sub.updated_at)

    with pytest.raises(InvalidAnswers):
        save_answers(assignment, sub, update({"position": 2, "clear": True},
                                             {"position": 3, "answer_text": "new"},
                                             {"position": 1, "answer_text": "wrong form"},
                                             version=1), NOW + timedelta(minutes=5))
    assert (stored(sub, assignment), sub.updated_at) == before


@pytest.mark.parametrize("expected, message", [(None, "required"), (2, "changed elsewhere")])
def test_existing_submission_needs_the_current_version(expected, message):
    assignment = build_assignment()
    sub = as_saved(save_answers(assignment, None, update(), NOW), 1)
    with pytest.raises(VersionConflict, match=message):
        save_answers(assignment, sub, update({"position": 2, "answer_text": "x"}, version=expected), NOW)
    with pytest.raises(VersionConflict, match=message):
        finalize_submission(assignment, sub, SubmissionFinalizeRequest(expected_version=expected), NOW)


def test_only_open_assignments_take_answers():
    closed = build_assignment(status="cancelled")
    with pytest.raises(NotSubmittable):
        save_answers(closed, None, update(), NOW)
    with pytest.raises(NotSubmittable):
        finalize_submission(closed, None, SubmissionFinalizeRequest(), NOW)


def test_submission_must_belong_to_the_assignment():
    mine, other = build_assignment(), build_assignment()
    theirs = as_saved(save_answers(other, None, update(), NOW), 1)
    with pytest.raises(NotSubmittable):
        save_answers(mine, theirs, update(version=1), NOW)


# --- Final submit (in memory) ---------------------------------------------------------------------


def test_final_submit_locks_the_submission():
    assignment = build_assignment()
    sub = as_saved(save_answers(assignment, None, update({"position": 2, "answer_text": "done"}), NOW), 1)
    finalize_submission(assignment, sub, SubmissionFinalizeRequest(expected_version=1), NOW)
    as_saved(sub, 2)
    assert sub.status == "submitted" and sub.submitted_at == NOW

    with pytest.raises(SubmissionLocked):
        save_answers(assignment, sub, update({"position": 2, "clear": True}, version=2), NOW)
    with pytest.raises(SubmissionLocked):
        finalize_submission(assignment, sub, SubmissionFinalizeRequest(expected_version=2), NOW)
    assert stored(sub, assignment) == {2: ("done", None)}


def test_blank_submission_can_be_submitted_without_saving_first():
    sub = finalize_submission(build_assignment(), None, SubmissionFinalizeRequest(), NOW)
    assert sub.status == "submitted" and sub.answers == []


@pytest.mark.parametrize("due_at, late", [
    (None, False),  # no due time: never late
    (NOW + timedelta(seconds=1), False),
    (NOW, False),  # exactly at the due time is on time
    (NOW - timedelta(seconds=1), True),
    ((NOW - timedelta(hours=1)).replace(tzinfo=None), True),  # naive, as SQLite returns it
    (NOW.astimezone(timezone(timedelta(hours=5, minutes=30))) + timedelta(minutes=1), False),  # other zone
])
def test_late_flag(due_at, late):
    sub = finalize_submission(build_assignment(due_at=due_at), None, SubmissionFinalizeRequest(), NOW)
    assert sub.is_late is late


# --- Student-facing output -----------------------------------------------------------------------


def test_output_lists_answers_by_position_with_no_hidden_data():
    assignment = build_assignment()
    sub = as_saved(save_answers(assignment, None, update({"position": 3, "answer_text": "third"},
                                                         {"position": 1, "selected_option_index": 0}), NOW), 1)
    out = to_submission_out(sub, assignment)
    assert [a.position for a in out.answers] == [1, 3]
    assert (out.answered_count, out.question_count, out.version, out.status) == (2, 4, 1, "in_progress")
    assert out.started_at.tzinfo is not None
    dumped = out.model_dump_json()
    for secret in ("SECRET", "draft_item_id", "student_id", "school_id", assignment.draft.items[0].id):
        assert secret not in dumped


def test_output_refuses_answers_from_other_questions():
    assignment, other = build_assignment(), build_assignment()
    sub = as_saved(save_answers(assignment, None, update({"position": 2, "answer_text": "x"}), NOW), 1)
    sub.answers[0].draft_item_id = other.draft.items[1].id
    with pytest.raises(NotSubmittable):
        to_submission_out(sub, assignment)


# --- Database ----------------------------------------------------------------------------------------


@pytest_asyncio.fixture
async def saved_assignment(db_session):
    assignment = build_assignment(due_at=NOW + timedelta(days=1))
    ids = {"assignment": assignment.id, "draft": assignment.draft_id}
    db_session.add(assignment)
    await db_session.commit()
    yield ids
    await db_session.rollback()
    for sql in (
        "DELETE FROM homework_submission_answers WHERE submission_id IN "
        "(SELECT id FROM homework_submissions WHERE assignment_id = :a)",
        "DELETE FROM homework_submissions WHERE assignment_id = :a",
        "DELETE FROM homework_assignments WHERE id = :a",
        "DELETE FROM homework_draft_items WHERE draft_id = :d",
        "DELETE FROM homework_drafts WHERE id = :d",
    ):
        await db_session.execute(text(sql), {"a": ids["assignment"], "d": ids["draft"]})
    await db_session.commit()


async def load(session, assignment_id):
    assignment = await session.get(HomeworkAssignmentRecord, assignment_id)
    submission = (await session.execute(
        select(HomeworkSubmissionRecord).filter(HomeworkSubmissionRecord.assignment_id == assignment_id)
    )).scalars().first()
    return assignment, submission


@pytest.mark.asyncio
async def test_saves_persist_and_every_save_raises_the_version(saved_assignment):
    a_id = saved_assignment["assignment"]
    async with AsyncSessionLocal() as s:
        assignment, _ = await load(s, a_id)
        s.add(save_answers(assignment, None, update({"position": 1, "selected_option_index": 1}), NOW))
        await s.commit()
    async with AsyncSessionLocal() as s:
        assignment, sub = await load(s, a_id)
        assert sub.version == 1 and stored(sub, assignment) == {1: (None, 1)}
        # The same timestamp again (a frozen clock) must still raise the version.
        save_answers(assignment, sub, update({"position": 2, "answer_text": "two"}, version=1), NOW)
        await s.commit()
        save_answers(assignment, sub, update({"position": 1, "clear": True}, version=2), NOW)
        await s.commit()
    async with AsyncSessionLocal() as s:
        assignment, sub = await load(s, a_id)
        assert sub.version == 3 and stored(sub, assignment) == {2: ("two", None)}
        rows = await s.scalar(select(func.count()).select_from(HomeworkSubmissionAnswerRecord)
                              .filter(HomeworkSubmissionAnswerRecord.submission_id == sub.id))
        assert rows == 1  # the cleared answer's row is gone


@pytest.mark.asyncio
async def test_concurrent_saves_one_wins_and_nothing_is_half_written(saved_assignment):
    a_id = saved_assignment["assignment"]
    async with AsyncSessionLocal() as s:
        assignment, _ = await load(s, a_id)
        s.add(save_answers(assignment, None, update({"position": 2, "answer_text": "start"}), NOW))
        await s.commit()

    async with AsyncSessionLocal() as first, AsyncSessionLocal() as second:
        a1, sub1 = await load(first, a_id)
        a2, sub2 = await load(second, a_id)  # both read version 1
        save_answers(a1, sub1, update({"position": 2, "answer_text": "first wins"}, version=1), NOW)
        save_answers(a2, sub2, update({"position": 2, "answer_text": "second"},
                                      {"position": 3, "answer_text": "also second"}, version=1), NOW)
        await first.commit()
        with pytest.raises(StaleDataError):
            await second.commit()
        await second.rollback()

    async with AsyncSessionLocal() as s:
        assignment, sub = await load(s, a_id)
        assert sub.version == 2 and stored(sub, assignment) == {2: ("first wins", None)}


@pytest.mark.asyncio
async def test_concurrent_first_saves_create_only_one_submission(saved_assignment):
    a_id = saved_assignment["assignment"]
    async with AsyncSessionLocal() as first, AsyncSessionLocal() as second:
        a1, _ = await load(first, a_id)
        a2, _ = await load(second, a_id)
        first.add(save_answers(a1, None, update({"position": 2, "answer_text": "one"}), NOW))
        second.add(save_answers(a2, None, update({"position": 2, "answer_text": "two"}), NOW))
        await first.commit()
        with pytest.raises(IntegrityError, match="homework_submissions.assignment_id"):
            await second.commit()
        await second.rollback()
    async with AsyncSessionLocal() as s:
        count = await s.scalar(select(func.count()).select_from(HomeworkSubmissionRecord)
                               .filter(HomeworkSubmissionRecord.assignment_id == a_id))
        assert count == 1


@pytest.mark.asyncio
async def test_final_submit_persists_and_locks(saved_assignment):
    a_id = saved_assignment["assignment"]
    async with AsyncSessionLocal() as s:
        assignment, _ = await load(s, a_id)
        s.add(finalize_submission(assignment, None, SubmissionFinalizeRequest(), NOW))
        await s.commit()
    async with AsyncSessionLocal() as s:
        assignment, sub = await load(s, a_id)
        out = to_submission_out(sub, assignment)
        assert (out.status, out.is_late, out.answered_count, out.version) == ("submitted", False, 0, 1)
        assert out.submitted_at == NOW
        with pytest.raises(SubmissionLocked):
            save_answers(assignment, sub, update({"position": 2, "answer_text": "late edit"}, version=1), NOW)


@pytest.mark.asyncio
async def test_one_answer_per_question_per_submission(db_session, saved_assignment):
    a_id = saved_assignment["assignment"]
    assignment, _ = await load(db_session, a_id)
    item_id = assignment.draft.items[1].id
    sub = HomeworkSubmissionRecord(assignment_id=a_id, student_id=assignment.student_id, school_id="school-1",
                                   status="in_progress", started_at=NOW, updated_at=NOW)
    sub.answers = [HomeworkSubmissionAnswerRecord(draft_item_id=item_id, answer_text="a"),
                   HomeworkSubmissionAnswerRecord(draft_item_id=item_id, answer_text="b")]
    db_session.add(sub)
    with pytest.raises(IntegrityError, match="homework_submission_answers.submission_id"):
        await db_session.commit()
    await db_session.rollback()


SUBMISSION_INSERT = (
    "INSERT INTO homework_submissions (id, assignment_id, student_id, school_id, status, is_late, "
    "started_at, updated_at, submitted_at, version) VALUES (:id, :a, 's', 'school-1', :status, :late, "
    "'2026-11-09', '2026-11-09', :submitted_at, 1)"
)
ANSWER_INSERT = (
    "INSERT INTO homework_submission_answers (id, submission_id, draft_item_id, answer_text, "
    "selected_option_index, created_at, updated_at) VALUES (:id, :s, :item, :t, :i, '2026-11-09', '2026-11-09')"
)


@pytest.mark.asyncio
@pytest.mark.parametrize("status, late, submitted_at, constraint", [
    ("graded", 0, None, "ck_homework_submissions_status"),
    ("submitted", 0, None, "ck_homework_submissions_submitted_at"),  # submitted without a time
    ("in_progress", 0, "2026-11-09", "ck_homework_submissions_submitted_at"),  # a time without submitting
    ("in_progress", 1, None, "ck_homework_submissions_late"),  # late before submitting
])
async def test_submission_check_constraints(db_session, saved_assignment, status, late, submitted_at, constraint):
    with pytest.raises(IntegrityError, match=constraint):
        await db_session.execute(text(SUBMISSION_INSERT), {
            "id": uid("raw"), "a": uid("raw-asg"), "status": status, "late": late, "submitted_at": submitted_at})
    await db_session.rollback()


@pytest.mark.asyncio
@pytest.mark.parametrize("answer_text, index, constraint", [
    (None, None, "ck_homework_submission_answers_one_form"),  # no answer at all
    ("text", 1, "ck_homework_submission_answers_one_form"),  # both forms
    (None, -1, "ck_homework_submission_answers_index"),
])
async def test_answer_check_constraints(db_session, saved_assignment, answer_text, index, constraint):
    with pytest.raises(IntegrityError, match=constraint):
        await db_session.execute(text(ANSWER_INSERT), {
            "id": uid("raw"), "s": uid("raw-sub"), "item": uid("raw-item"), "t": answer_text, "i": index})
    await db_session.rollback()


@pytest.mark.asyncio
async def test_deleting_a_submission_removes_its_answers(saved_assignment):
    a_id = saved_assignment["assignment"]
    async with AsyncSessionLocal() as s:
        assignment, _ = await load(s, a_id)
        s.add(save_answers(assignment, None, update({"position": 2, "answer_text": "x"},
                                                    {"position": 3, "answer_text": "y"}), NOW))
        await s.commit()
    async with AsyncSessionLocal() as s:
        _, sub = await load(s, a_id)
        sub_id = sub.id
        await s.delete(sub)
        await s.commit()
        left = await s.scalar(text("SELECT COUNT(*) FROM homework_submission_answers WHERE submission_id = :s"),
                              {"s": sub_id})
        assert left == 0


# --- Schema creation, foreign keys and PostgreSQL ---------------------------------------------------------


@pytest.mark.asyncio
async def test_create_all_adds_only_the_new_tables(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{(tmp_path / 'old.db').as_posix()}")
    old = [t for name, t in Base.metadata.tables.items() if name not in NEW_TABLES]

    def describe(conn):
        insp = inspect(conn)
        return {name: [c["name"] for c in insp.get_columns(name)] for name in insp.get_table_names()}

    try:
        async with engine.begin() as conn:
            await conn.run_sync(lambda c: Base.metadata.create_all(c, tables=old))
            before = await conn.run_sync(describe)
        for _ in range(2):  # running it again is harmless
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
        async with engine.connect() as conn:
            after = await conn.run_sync(describe)
        assert set(after) - set(before) == set(NEW_TABLES)
        assert {name: after[name] for name in before} == before  # no existing table changed
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_foreign_keys_hold_when_the_database_enforces_them(tmp_path):
    """The app's SQLite engine has foreign keys off; PostgreSQL enforces them. This runs the
    same tables with SQLite foreign keys on, to check the relationships themselves."""
    engine = create_async_engine(f"sqlite+aiosqlite:///{(tmp_path / 'fk.db').as_posix()}")

    @event.listens_for(engine.sync_engine, "connect")
    def _foreign_keys_on(dbapi_connection, _):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with engine.begin() as conn:
            with pytest.raises(IntegrityError, match="FOREIGN KEY"):
                await conn.execute(text(SUBMISSION_INSERT), {
                    "id": "s1", "a": "no-such-assignment", "status": "in_progress", "late": 0, "submitted_at": None})
        async with engine.begin() as conn:
            with pytest.raises(IntegrityError, match="FOREIGN KEY"):
                await conn.execute(text(ANSWER_INSERT), {"id": "x1", "s": "no-such-submission",
                                                         "item": "no-such-item", "t": "a", "i": None})
        # Parent rows (student, draft, item, assignment) are set up through a second connection
        # with foreign keys off, using the ORM so teammate tables get their defaults. The checks
        # below run with foreign keys on; inserting a row only checks its direct parents.
        setup_engine = create_async_engine(f"sqlite+aiosqlite:///{(tmp_path / 'fk.db').as_posix()}")
        assignment = build_assignment()
        a_id, student_id, item_id = assignment.id, assignment.student_id, assignment.draft.items[1].id
        try:
            async with async_sessionmaker(setup_engine, expire_on_commit=False)() as setup:
                setup.add_all([
                    Student(id=student_id, school_id="sch", class_id="cls", class_name="A", name="N", roll_no=1,
                            lu_score=1, cu_score=1, au_score=1, ct_score=1, overall_score=1),
                    assignment,
                ])
                await setup.commit()
        finally:
            await setup_engine.dispose()

        async with engine.begin() as conn:
            await conn.execute(text(SUBMISSION_INSERT.replace("'s', 'school-1'", f"'{student_id}', 'school-1'")), {
                "id": "sub", "a": a_id, "status": "in_progress", "late": 0, "submitted_at": None})
            await conn.execute(text(ANSWER_INSERT), {"id": "ans", "s": "sub", "item": item_id, "t": "x", "i": None})
        async with engine.begin() as conn:
            # The database refuses to delete a question that has an answer.
            with pytest.raises(IntegrityError, match="FOREIGN KEY"):
                await conn.execute(text("DELETE FROM homework_draft_items WHERE id = :i"), {"i": item_id})
        async with engine.begin() as conn:
            await conn.execute(text("DELETE FROM homework_submissions WHERE id = 'sub'"))
            left = (await conn.execute(text("SELECT COUNT(*) FROM homework_submission_answers"))).scalar()
        assert left == 0  # ON DELETE CASCADE removed the answer
    finally:
        await engine.dispose()


def test_new_tables_compile_for_postgresql():
    dialect = postgresql.dialect()
    submissions = str(CreateTable(Base.metadata.tables["homework_submissions"]).compile(dialect=dialect))
    answers = str(CreateTable(Base.metadata.tables["homework_submission_answers"]).compile(dialect=dialect))
    assert "UNIQUE (assignment_id)" in submissions
    assert "(status = 'submitted') = (submitted_at IS NOT NULL)" in submissions
    assert "NOT is_late OR status = 'submitted'" in submissions and "BOOLEAN" in submissions
    assert "UNIQUE (submission_id, draft_item_id)" in answers
    assert "(answer_text IS NULL) <> (selected_option_index IS NULL)" in answers
    assert "ON DELETE CASCADE" in answers
