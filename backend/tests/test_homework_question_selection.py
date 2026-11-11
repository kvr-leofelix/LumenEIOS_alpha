import itertools
import uuid

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select

from backend.app.models.entities import QuestionBankItem
from backend.app.modules.differentiated_homework.gap_analyzer import analyze_gaps
from backend.app.modules.differentiated_homework.question_bank_adapter import load_candidate_questions
from backend.app.modules.differentiated_homework.question_selector import (
    normalize_competency,
    select_questions,
)
from backend.app.modules.differentiated_homework.schemas import (
    CandidateQuestion,
    CompetencyGap,
    CompetencyProfile,
    GapAnalysis,
    SelectedQuestion,
    SelectionRequest,
)

SCHOOL, SUBJECT = "school-1", "sub-math"


def analysis(lu, cu, au, ct):
    return analyze_gaps(
        CompetencyProfile(student_id="student-x", scores={"LU": lu, "CU": cu, "AU": au, "CT": ct}, source="test")
    )


def q(qid, competency, marks=2, school=SCHOOL, subject=SUBJECT, ai=False, text=None):
    return CandidateQuestion(
        id=qid, school_id=school, subject_id=subject, text=text or f"Question {qid}", type="short",
        marks=marks, competency=competency, bloom_level="Apply", is_ai_generated=ai,
    )


def request(max_questions, max_total_marks=None, include_ai_generated=False, school=SCHOOL, subject=SUBJECT):
    return SelectionRequest(
        school_id=school, subject_id=subject, max_questions=max_questions,
        max_total_marks=max_total_marks, include_ai_generated=include_ai_generated,
    )


def ids(result):
    return [s.question_id for s in result.selected]


# --- Priority ----------------------------------------------------------------------


def test_selects_questions_for_the_weakest_competency_first():
    bank = [q("a1", "AU"), q("l1", "LU"), q("l2", "LU"), q("c1", "CU")]
    result = select_questions(analysis(40, 70, 60, 80), bank, request(2))

    assert ids(result) == ["l1", "l2"]
    assert all(s.competency == "LU" and s.competency_rank == 1 for s in result.selected)
    assert result.shortfall == 0


def test_follows_gap_ranking_across_competencies():
    bank = [q("u1", "CU"), q("a1", "AU"), q("t1", "CT"), q("l1", "LU")]
    result = select_questions(analysis(40, 70, 60, 50), bank, request(4))

    assert ids(result) == ["l1", "t1", "a1", "u1"]
    assert [s.competency_rank for s in result.selected] == [1, 2, 3, 4]
    assert result.priority == [["LU"], ["CT"], ["AU"], ["CU"]]


def test_moves_to_next_weakest_when_weakest_runs_out():
    bank = [q("l1", "LU"), q("t1", "CT"), q("t2", "CT"), q("a1", "AU")]
    result = select_questions(analysis(40, 70, 60, 50), bank, request(3))

    assert ids(result) == ["l1", "t1", "t2"]


def test_tied_competencies_take_turns():
    bank = [q(f"l{i}", "LU") for i in range(3)] + [q(f"t{i}", "CT") for i in range(3)]
    result = select_questions(analysis(50, 70, 80, 50), bank, request(4))

    assert result.priority[0] == ["LU", "CT"]
    assert ids(result) == ["l0", "t0", "l1", "t1"]


def test_equal_scores_share_one_priority_group():
    bank = [q("a1", "AU"), q("c1", "CU"), q("l1", "LU"), q("t1", "CT")]
    result = select_questions(analysis(70, 70, 70, 70), bank, request(4))

    assert result.priority == [["LU", "CU", "AU", "CT"]]
    assert ids(result) == ["l1", "c1", "a1", "t1"]
    assert any("equal" in note for note in result.notes)


# --- Filtering ---------------------------------------------------------------------


def test_competency_values_are_normalized_or_rejected():
    assert normalize_competency(" lu ") == "LU"
    assert normalize_competency("ct") == "CT"
    for bad in ["Language Understanding", "", "XX", "L U", "LU1"]:
        assert normalize_competency(bad) is None


def test_unsupported_competency_strings_are_excluded_and_counted():
    bank = [q("ok", " lu "), q("x1", "Language Understanding"), q("x2", ""), q("x3", "XX")]
    result = select_questions(analysis(40, 70, 60, 50), bank, request(4))

    assert ids(result) == ["ok"]
    assert result.selected[0].competency == "LU"
    assert result.excluded == {"unsupported_competency": 3}


def test_only_requested_school_and_subject_are_used():
    bank = [
        q("keep", "LU"),
        q("other-school", "LU", school="school-3"),
        q("other-subject", "LU", subject="sub-sci"),
    ]
    result = select_questions(analysis(40, 70, 60, 50), bank, request(3))

    assert ids(result) == ["keep"]
    assert result.excluded == {"wrong_school": 1, "wrong_subject": 1}


def test_duplicate_ids_and_duplicate_text_are_not_selected_twice():
    bank = [
        q("l1", "LU", text="What is 2 + 2?"),
        q("l1", "LU", text="What is 2 + 2?"),
        q("l2", "LU", text="  what IS 2 +   2? "),
        q("l3", "LU", text="A different question"),
    ]
    result = select_questions(analysis(40, 70, 60, 50), bank, request(4))

    assert ids(result) == ["l1", "l3"]
    assert len(set(ids(result))) == len(ids(result))
    assert result.excluded == {"duplicate_id": 1, "duplicate_text": 1}


def test_invalid_marks_are_excluded():
    bank = [q("zero", "LU", marks=0), q("neg", "LU", marks=-2), q("ok", "LU", marks=1)]
    result = select_questions(analysis(40, 70, 60, 50), bank, request(3))

    assert ids(result) == ["ok"]
    assert result.excluded == {"invalid_marks": 2}


def test_ai_generated_questions_only_when_requested():
    bank = [q("ai", "LU", ai=True), q("human", "LU")]

    without = select_questions(analysis(40, 70, 60, 50), bank, request(2, include_ai_generated=False))
    assert ids(without) == ["human"]
    assert without.excluded == {"ai_generated_not_requested": 1}

    with_ai = select_questions(analysis(40, 70, 60, 50), bank, request(2, include_ai_generated=True))
    assert ids(with_ai) == ["ai", "human"]


# --- Shortfalls and limits -----------------------------------------------------------


def test_empty_question_bank():
    result = select_questions(analysis(40, 70, 60, 50), [], request(3))

    assert result.selected == []
    assert result.shortfall == 3
    assert result.total_marks == 0
    assert result.eligible_by_competency == {"LU": 0, "CU": 0, "AU": 0, "CT": 0}
    assert any("LU" in note for note in result.notes)


def test_insufficient_questions_reports_shortfall():
    bank = [q("a1", "AU"), q("c1", "CU")]
    result = select_questions(analysis(40, 70, 60, 50), bank, request(5))

    assert ids(result) == ["a1", "c1"]
    assert result.shortfall == 3
    assert result.eligible_by_competency["LU"] == 0
    assert any("weakest competency group: LU" in note for note in result.notes)


def test_max_questions_is_respected():
    bank = [q(f"l{i}", "LU") for i in range(10)]
    result = select_questions(analysis(40, 70, 60, 50), bank, request(3))

    assert len(result.selected) == 3
    assert result.shortfall == 0


def test_marks_limit_skips_questions_that_do_not_fit():
    bank = [q("l1", "LU", marks=4), q("l2", "LU", marks=5), q("l3", "LU", marks=2), q("l4", "LU", marks=1)]
    result = select_questions(analysis(40, 70, 60, 50), bank, request(4, max_total_marks=7))

    assert ids(result) == ["l1", "l3", "l4"]
    assert result.total_marks == 7
    assert result.shortfall == 1
    assert any("marks limit" in note for note in result.notes)


def test_marks_limit_smaller_than_every_question():
    bank = [q("l1", "LU", marks=4), q("a1", "AU", marks=3)]
    result = select_questions(analysis(40, 70, 60, 50), bank, request(2, max_total_marks=2))

    assert result.selected == []
    assert result.total_marks == 0


# --- Determinism -------------------------------------------------------------------


def test_same_result_whatever_the_input_order():
    bank = [
        q("l2", "LU"), q("l1", "LU"), q("t1", "CT"), q("a1", "AU", marks=3),
        q("dup", "LU", text="Question l1"), q("x", "nonsense"), q("t2", "CT", school="school-3"),
    ]
    gap = analysis(50, 70, 60, 50)
    req = request(4, max_total_marks=9)

    results = {select_questions(gap, list(order), req).model_dump_json() for order in itertools.permutations(bank)}
    assert len(results) == 1


def test_repeated_runs_give_identical_results():
    bank = [q("l1", "LU"), q("t1", "CT"), q("a1", "AU")]
    gap = analysis(40, 70, 60, 50)
    first = select_questions(gap, bank, request(3))

    for _ in range(5):
        assert select_questions(gap, bank, request(3)) == first


# --- Invalid input -------------------------------------------------------------------


@pytest.mark.parametrize(
    "fields",
    [
        {"max_questions": 0},
        {"max_questions": -1},
        {"max_questions": 2.5},
        {"max_questions": 2, "max_total_marks": 0},
        {"max_questions": 2, "include_ai_generated": None},
        {"max_questions": 2, "school_id": ""},
        {"max_questions": 2, "unexpected": True},
    ],
)
def test_invalid_selection_requests_are_rejected(fields):
    data = {"school_id": SCHOOL, "subject_id": SUBJECT, "include_ai_generated": False, **fields}
    with pytest.raises(ValidationError):
        SelectionRequest(**data)


def test_include_ai_generated_must_be_chosen_explicitly():
    with pytest.raises(ValidationError):
        SelectionRequest(school_id=SCHOOL, subject_id=SUBJECT, max_questions=2)


def test_incomplete_gap_analysis_is_rejected():
    broken = GapAnalysis(
        student_id="s", ranked=[CompetencyGap(competency="LU", score=40, rank=1)], weakest=["LU"],
        has_single_weakest=True, lowest_score=40, highest_score=40, spread=0, source="test", notes=[],
    )
    with pytest.raises(ValueError):
        select_questions(broken, [q("l1", "LU")], request(1))


def test_selected_questions_never_contain_answers():
    fields = set(SelectedQuestion.model_fields) | set(CandidateQuestion.model_fields)
    assert not fields & {"correct_answer", "marking_rubric", "options", "options_json"}


# --- Adapter (temporary database) ----------------------------------------------------


@pytest.mark.asyncio
async def test_adapter_loads_scope_without_answers_or_writes(db_session):
    school, subject = f"school-qs-{uuid.uuid4().hex[:8]}", "sub-qs-test"
    rows = [
        QuestionBankItem(id=f"{school}-b", school_id=school, subject_id=subject, text="B", type="short",
                         marks=2, competency="LU", bloom_level="Apply", correct_answer="SECRET-B"),
        QuestionBankItem(id=f"{school}-a", school_id=school, subject_id=subject, text="A", type="mcq",
                         marks=1, competency="cu", bloom_level="Remember", correct_answer="SECRET-A",
                         is_ai_generated=True),
        QuestionBankItem(id=f"{school}-c", school_id=school, subject_id="sub-other", text="C", type="short",
                         marks=2, competency="LU", bloom_level="Apply"),
        QuestionBankItem(id=f"{school}-d", school_id="school-3", subject_id=subject, text="D", type="short",
                         marks=2, competency="LU", bloom_level="Apply"),
    ]
    db_session.add_all(rows)
    await db_session.commit()
    count_before = await db_session.scalar(select(func.count()).select_from(QuestionBankItem))

    try:
        loaded = await load_candidate_questions(db_session, school, subject)

        assert [c.id for c in loaded.candidates] == [f"{school}-a", f"{school}-b"]
        assert loaded.malformed_question_ids == []
        assert loaded.candidates[0].competency == "cu"  # raw value, normalised later by the selector
        assert "SECRET" not in str([c.model_dump() for c in loaded.candidates])

        result = select_questions(
            analysis(40, 70, 60, 50), loaded.candidates,
            SelectionRequest(school_id=school, subject_id=subject, max_questions=5, include_ai_generated=False),
        )
        assert ids(result) == [f"{school}-b"]

        assert not db_session.new and not db_session.dirty
        assert await db_session.scalar(select(func.count()).select_from(QuestionBankItem)) == count_before
    finally:
        for row in rows:
            await db_session.delete(row)
        await db_session.commit()


@pytest.mark.asyncio
async def test_adapter_returns_empty_list_for_unknown_scope(db_session):
    empty = await load_candidate_questions(db_session, "no-such-school", "no-such-subject")
    assert empty.candidates == [] and empty.malformed_question_ids == []


# --- Final review: regression and verification tests ---------------------------------


def test_same_id_with_different_content_is_order_independent():
    # The database prevents duplicate IDs, but callers can pass any list.
    variants = [
        [q("x", "LU", marks=2, text="Version A"), q("x", "CT", marks=3, text="Version B"), q("y", "AU")],
        [q("x", "LU", marks=0, text="Version A"), q("x", "LU", marks=2, text="Version B"), q("y", "AU")],
    ]
    gap = analysis(40, 70, 60, 50)
    for bank in variants:
        results = {select_questions(gap, list(order), request(3)).model_dump_json() for order in itertools.permutations(bank)}
        assert len(results) == 1


def test_same_question_text_under_different_ids_is_selected_once_by_lowest_id():
    bank = [q("b", "CT", text="Same question"), q("a", "LU", text="Same question"), q("c", "LU")]
    result = select_questions(analysis(40, 70, 60, 50), bank, request(3))

    assert ids(result) == ["a", "c"]
    assert result.excluded == {"duplicate_text": 1}


def test_every_candidate_is_either_eligible_or_excluded_exactly_once():
    bank = [
        q("l1", "LU"), q("l2", "LU", marks=9), q("t1", "CT"), q("dup", "LU", text="Question l1"),
        q("l1", "LU"), q("bad", "??"), q("zero", "AU", marks=0), q("ai", "CU", ai=True),
        q("far", "LU", school="school-3"), q("sci", "LU", subject="sub-sci"),
    ]
    result = select_questions(analysis(40, 70, 60, 50), bank, request(2, max_total_marks=4))

    assert sum(result.eligible_by_competency.values()) + sum(result.excluded.values()) == len(bank)
    assert result.eligible_by_competency == {"LU": 2, "CU": 0, "AU": 0, "CT": 1}
    assert len(result.selected) + result.shortfall == result.requested_questions
    assert result.total_marks == sum(s.marks for s in result.selected)


@pytest.mark.asyncio
async def test_adapter_filters_in_sql_and_never_selects_answer_columns(db_session):
    from sqlalchemy import event

    from backend.app.db.session import engine

    statements = []

    def capture(conn, cursor, statement, parameters, context, executemany):
        statements.append((statement, parameters))

    event.listen(engine.sync_engine, "before_cursor_execute", capture)
    try:
        await load_candidate_questions(db_session, "school-x", "sub-x")
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", capture)

    selects = [(s, p) for s, p in statements if "question_bank_items" in s]
    assert len(selects) == 1
    sql, params = selects[0]
    where = sql.split("WHERE", 1)[1]
    assert "school_id" in where and "subject_id" in where
    assert "school-x" in params and "sub-x" in params
    for column in ("correct_answer", "marking_rubric", "options_json"):
        assert column not in sql


@pytest.mark.asyncio
async def test_adapter_skips_and_reports_malformed_rows(db_session):
    from sqlalchemy import text

    school = f"school-qs-{uuid.uuid4().hex[:8]}"
    insert = text(
        "INSERT INTO question_bank_items (id, school_id, subject_id, text, type, options_json, marks, "
        "competency, bloom_level, source_document_ids_json, source_document_names_json, is_ai_generated, "
        "created_at) VALUES (:id, :school, 'sub-qs', :text, 'short', '[]', :marks, :competency, 'Apply', "
        "'[]', '[]', 0, '2026-01-01 00:00:00')"
    )
    rows = [
        {"id": f"{school}-good", "text": "Good", "marks": 2, "competency": "LU"},
        {"id": f"{school}-bad-marks", "text": "Bad marks", "marks": "two", "competency": "LU"},
        {"id": f"{school}-bad-competency", "text": "Bad competency", "marks": 2, "competency": 7},
    ]
    for row in rows:
        await db_session.execute(insert, {**row, "school": school})
    await db_session.commit()

    try:
        loaded = await load_candidate_questions(db_session, school, "sub-qs")

        # Text in the integer marks column can't be read as a number: skipped and reported.
        assert loaded.malformed_question_ids == [f"{school}-bad-marks"]
        # SQLite stores competency 7 as the text "7" (text column), so it loads and the
        # selector reports it as an unsupported competency.
        assert [c.id for c in loaded.candidates] == [f"{school}-bad-competency", f"{school}-good"]

        result = select_questions(
            analysis(40, 70, 60, 50), loaded.candidates,
            SelectionRequest(school_id=school, subject_id="sub-qs", max_questions=5, include_ai_generated=False),
        )
        assert ids(result) == [f"{school}-good"]
        assert result.excluded == {"unsupported_competency": 1}
    finally:
        await db_session.execute(text("DELETE FROM question_bank_items WHERE school_id = :s"), {"s": school})
        await db_session.commit()
