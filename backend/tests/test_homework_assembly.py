import copy

import pytest
from pydantic import ValidationError

from backend.app.modules.differentiated_homework.gap_analyzer import analyze_gaps
from backend.app.modules.differentiated_homework.homework_assembler import AssemblyError, assemble_homework_draft
from backend.app.modules.differentiated_homework.question_selector import select_questions
from backend.app.modules.differentiated_homework.schemas import (
    CandidateQuestion,
    CompetencyProfile,
    DraftItem,
    HomeworkDraft,
    SelectedQuestion,
    SelectionRequest,
)

SCHOOL, SUBJECT = "school-1", "sub-math"


def analysis(lu=40, cu=70, au=60, ct=50, student_id="student-x"):
    return analyze_gaps(
        CompetencyProfile(student_id=student_id, scores={"LU": lu, "CU": cu, "AU": au, "CT": ct}, source="test")
    )


def q(qid, competency, marks=2, ai=False):
    return CandidateQuestion(
        id=qid, school_id=SCHOOL, subject_id=SUBJECT, text=f"Question {qid}", type="short",
        marks=marks, competency=competency, bloom_level="Apply", is_ai_generated=ai,
    )


def request(max_questions, max_total_marks=None, include_ai_generated=False):
    return SelectionRequest(
        school_id=SCHOOL, subject_id=SUBJECT, max_questions=max_questions,
        max_total_marks=max_total_marks, include_ai_generated=include_ai_generated,
    )


def pipeline(bank, req, gap=None):
    gap = gap or analysis()
    return gap, select_questions(gap, bank, req), req


def tamper(selection, **changes):
    """Copy a selection with some fields replaced, bypassing validation, to test the assembler's checks."""
    return selection.model_copy(update=changes)


# --- Successful assembly -------------------------------------------------------------


def test_assembles_draft_from_analysis_and_selection():
    gap, sel, req = pipeline([q("l1", "LU", 3), q("t1", "CT", 2)], request(2))
    draft = assemble_homework_draft(gap, sel, req)

    assert isinstance(draft, HomeworkDraft)
    assert (draft.student_id, draft.school_id, draft.subject_id) == ("student-x", SCHOOL, SUBJECT)
    assert [i.question_id for i in draft.items] == ["l1", "t1"]
    assert draft.question_count == 2 and draft.total_marks == 5
    assert draft.is_complete and draft.shortfall == 0
    assert draft.rationale.targeted_competencies == ["LU", "CT"]
    assert draft.rationale.summary == "Targets LU (40), CT (50). Student's lowest score: LU (40); score range 40-70."
    assert draft.rationale.score_source == "test"


def test_preserves_order_positions_and_display_fields():
    bank = [q("u1", "CU"), q("a1", "AU", marks=4), q("t1", "CT", marks=1), q("l1", "LU", ai=True)]
    gap, sel, req = pipeline(bank, request(4, include_ai_generated=True))
    draft = assemble_homework_draft(gap, sel, req)

    assert [i.question_id for i in draft.items] == [s.question_id for s in sel.selected] == ["l1", "t1", "a1", "u1"]
    assert [i.position for i in draft.items] == [1, 2, 3, 4]
    for item, chosen in zip(draft.items, sel.selected):
        assert item.model_dump(exclude={"position"}) == chosen.model_dump()
    assert draft.total_marks == 2 + 1 + 4 + 2
    assert draft.contains_ai_generated
    assert any("AI-generated" in note for note in draft.notes)


def test_equal_scores_summary():
    gap, sel, req = pipeline([q("l1", "LU"), q("c1", "CU")], request(2), gap=analysis(70, 70, 70, 70))
    draft = assemble_homework_draft(gap, sel, req)

    assert draft.rationale.weakest == []
    assert "all four scores equal (70)" in draft.rationale.summary


def test_notes_are_passed_on_in_order():
    gap, sel, req = pipeline([q("a1", "AU")], request(3), gap=analysis(70, 70, 70, 70))
    draft = assemble_homework_draft(gap, sel, req)

    assert draft.notes[: len(gap.notes)] == gap.notes
    assert draft.notes[len(gap.notes): len(gap.notes) + len(sel.notes)] == sel.notes


# --- Empty and shortfall -----------------------------------------------------------------


def test_empty_selection_gives_empty_draft():
    gap, sel, req = pipeline([], request(3))
    draft = assemble_homework_draft(gap, sel, req)

    assert draft.items == [] and draft.question_count == 0 and draft.total_marks == 0
    assert draft.shortfall == 3 and not draft.is_complete
    assert draft.rationale.targeted_competencies == []
    assert draft.rationale.summary == "No questions were selected."
    assert any("nothing to review" in note for note in draft.notes)


def test_shortfall_is_reported():
    gap, sel, req = pipeline([q("a1", "AU"), q("c1", "CU")], request(5))
    draft = assemble_homework_draft(gap, sel, req)

    assert draft.question_count == 2 and draft.shortfall == 3 and not draft.is_complete
    assert any("incomplete: 3" in note for note in draft.notes)


def test_marks_limit_is_carried_through():
    gap, sel, req = pipeline([q("l1", "LU", 4), q("l2", "LU", 5), q("l3", "LU", 2)], request(3, max_total_marks=6))
    draft = assemble_homework_draft(gap, sel, req)

    assert draft.max_total_marks == 6 and draft.total_marks == 6


# --- Consistency checks --------------------------------------------------------------------


def test_student_id_mismatch_is_rejected():
    _, sel, req = pipeline([q("l1", "LU")], request(1))
    with pytest.raises(AssemblyError, match="different students"):
        assemble_homework_draft(analysis(student_id="someone-else"), sel, req)


def test_request_must_match_selection():
    gap, sel, _ = pipeline([q("l1", "LU")], request(2))
    with pytest.raises(AssemblyError, match="question count"):
        assemble_homework_draft(gap, sel, request(3))
    with pytest.raises(AssemblyError, match="marks limit"):
        assemble_homework_draft(gap, sel, request(2, max_total_marks=10))


def test_rank_that_disagrees_with_analysis_is_rejected():
    gap, sel, req = pipeline([q("l1", "LU")], request(1))
    wrong = sel.selected[0].model_copy(update={"competency_rank": 4})
    with pytest.raises(AssemblyError, match="rank"):
        assemble_homework_draft(gap, tamper(sel, selected=[wrong]), req)


def test_competency_relabelled_without_rank_change_is_rejected():
    gap, sel, req = pipeline([q("l1", "LU")], request(1))
    wrong = sel.selected[0].model_copy(update={"competency": "CU"})  # CU is rank 4, item says rank 1
    with pytest.raises(AssemblyError, match="rank"):
        assemble_homework_draft(gap, tamper(sel, selected=[wrong]), req)


def test_duplicate_question_in_selection_is_rejected():
    gap, sel, req = pipeline([q("l1", "LU"), q("l2", "LU")], request(2))
    dup = [sel.selected[0], sel.selected[0]]
    with pytest.raises(AssemblyError, match="more than once"):
        assemble_homework_draft(gap, tamper(sel, selected=dup, total_marks=4), req)


@pytest.mark.parametrize(
    "changes, message",
    [
        ({"total_marks": 99}, "total marks"),
        ({"shortfall": 5}, "shortfall"),
        ({"requested_questions": 1, "shortfall": -1}, "question count"),
    ],
)
def test_inconsistent_selection_totals_are_rejected(changes, message):
    gap, sel, req = pipeline([q("l1", "LU"), q("l2", "LU")], request(2))
    with pytest.raises(AssemblyError, match=message):
        assemble_homework_draft(gap, tamper(sel, **changes), req)


def test_more_questions_than_requested_is_rejected():
    gap, sel, _ = pipeline([q("l1", "LU"), q("l2", "LU")], request(2))
    req = request(1)
    with pytest.raises(AssemblyError, match="more questions than"):
        assemble_homework_draft(gap, tamper(sel, requested_questions=1, shortfall=-1), req)


def test_selection_over_its_marks_limit_is_rejected():
    gap, sel, _ = pipeline([q("l1", "LU", 4)], request(1))
    req = request(1, max_total_marks=3)
    with pytest.raises(AssemblyError, match="exceeds its marks limit"):
        assemble_homework_draft(gap, tamper(sel, max_total_marks=3), req)


def test_invalid_marks_in_selection_is_rejected():
    gap, sel, req = pipeline([q("l1", "LU")], request(1))
    bad = sel.selected[0].model_copy(update={"marks": 0})
    with pytest.raises(AssemblyError, match="invalid marks"):
        assemble_homework_draft(gap, tamper(sel, selected=[bad], total_marks=0), req)


def test_incomplete_gap_analysis_is_rejected():
    gap, sel, req = pipeline([q("l1", "LU")], request(1))
    broken = gap.model_copy(update={"ranked": gap.ranked[:3]})
    with pytest.raises(AssemblyError, match="exactly once"):
        assemble_homework_draft(broken, sel, req)


def test_assembly_error_is_a_value_error():
    assert issubclass(AssemblyError, ValueError)


# --- Invalid inputs and immutability -----------------------------------------------------------


def test_selected_question_with_unknown_competency_cannot_be_built():
    with pytest.raises(ValidationError):
        SelectedQuestion(question_id="x", competency="XX", competency_rank=1, marks=1, type="short",
                         bloom_level="Apply", is_ai_generated=False, text="t")


def test_draft_has_no_answer_fields():
    fields = set(DraftItem.model_fields) | set(HomeworkDraft.model_fields)
    assert not fields & {"correct_answer", "marking_rubric", "options", "options_json"}


def test_inputs_are_not_modified():
    gap, sel, req = pipeline([q("l1", "LU"), q("t1", "CT")], request(3))
    before = (copy.deepcopy(gap.model_dump()), copy.deepcopy(sel.model_dump()), copy.deepcopy(req.model_dump()))

    draft = assemble_homework_draft(gap, sel, req)

    assert (gap.model_dump(), sel.model_dump(), req.model_dump()) == before
    assert draft.items is not sel.selected
    assert draft.notes is not gap.notes and draft.notes is not sel.notes


def test_draft_cannot_be_modified():
    gap, sel, req = pipeline([q("l1", "LU")], request(1))
    draft = assemble_homework_draft(gap, sel, req)
    with pytest.raises(ValidationError):
        draft.total_marks = 100


def test_same_inputs_give_identical_drafts():
    gap, sel, req = pipeline([q("l1", "LU"), q("t1", "CT"), q("a1", "AU")], request(3))
    first = assemble_homework_draft(gap, sel, req)
    assert all(assemble_homework_draft(gap, sel, req) == first for _ in range(5))


# --- Final review: regression tests ---------------------------------------------------


def test_ai_question_is_rejected_when_request_excludes_ai():
    gap, sel, _ = pipeline([q("l1", "LU", ai=True)], request(1, include_ai_generated=True))
    with pytest.raises(AssemblyError, match="AI-generated"):
        assemble_homework_draft(gap, sel, request(1, include_ai_generated=False))


def test_ai_question_is_accepted_when_request_allows_ai():
    gap, sel, req = pipeline([q("l1", "LU", ai=True)], request(1, include_ai_generated=True))
    assert assemble_homework_draft(gap, sel, req).contains_ai_generated


@pytest.mark.parametrize(
    "changes",
    [
        {"lowest_score": 10},
        {"highest_score": 99},
        {"weakest": ["CT"]},
        {"weakest": []},
        {"has_single_weakest": False},
        {"spread": 1},
    ],
)
def test_internally_inconsistent_gap_analysis_is_rejected(changes):
    gap, sel, req = pipeline([q("l1", "LU")], request(1))
    with pytest.raises(AssemblyError, match="inconsistent"):
        assemble_homework_draft(gap.model_copy(update=changes), sel, req)


def test_gap_analysis_ranks_must_follow_scores():
    gap, sel, req = pipeline([q("l1", "LU")], request(1))
    # Swap the ranks of LU (score 40) and CU (score 70) without changing scores.
    swapped = [
        g.model_copy(update={"rank": {"LU": 4, "CU": 1}.get(g.competency, g.rank)}) for g in gap.ranked
    ]
    with pytest.raises(AssemblyError, match="inconsistent"):
        assemble_homework_draft(gap.model_copy(update={"ranked": swapped}), sel, req)
