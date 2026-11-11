"""Homework Assembler: turns a gap analysis and a question selection into a homework draft.

Pure logic with no database access. Nothing is saved: the draft is for teacher review and
isn't an assignment.

Steps:
1. Check that the three inputs agree with each other and are internally consistent.
   Any problem raises AssemblyError; nothing is silently corrected.
2. Copy the selected questions, in order, into numbered draft items.
3. Recalculate the question count and total marks from the items.
4. Build a rationale from the gap analysis only. The summary sentence states facts from the
   data; it doesn't add teaching advice or explanations.
5. Pass on the notes from the gap analysis and the selection, then add assembly notes.

Deliberately not included: title, due date, teacher, review status. No agreed rules exist for
them, and the existing HomeworkRemediation model can't safely store a draft.

TRUSTED UPSTREAM INVARIANTS (can't be verified here with the current schemas):
- School and subject: SelectionResult and SelectedQuestion don't carry them, so the draft
  copies them from the request. The selector filters by the same request, so they're correct
  when the request passed in is the one used for selection.
- Competency label within a tie: a question relabelled to another competency with the same
  rank can't be detected, because SelectedQuestion is the only source of the label.
"""
from typing import Dict, List

from backend.app.modules.differentiated_homework.schemas import (
    COMPETENCIES,
    DraftItem,
    DraftRationale,
    GapAnalysis,
    HomeworkDraft,
    SelectionRequest,
    SelectionResult,
)


class AssemblyError(ValueError):
    """The inputs are inconsistent, so no draft can be assembled."""


def _check_inputs(analysis: GapAnalysis, selection: SelectionResult, request: SelectionRequest) -> Dict[str, int]:
    ranks = {gap.competency: gap.rank for gap in analysis.ranked}
    if len(analysis.ranked) != len(COMPETENCIES) or set(ranks) != set(COMPETENCIES):
        raise AssemblyError("Gap analysis must rank each of LU, CU, AU and CT exactly once.")

    # The rationale copies these fields, so they must agree with the ranked scores, using the
    # same rules as the Gap Analyzer. GapAnalysis has no validator of its own.
    scores = {gap.competency: gap.score for gap in analysis.ranked}
    lowest, highest = min(scores.values()), max(scores.values())
    expected_weakest = [c for c in COMPETENCIES if scores[c] == lowest] if highest > lowest else []
    expected_ranks = {c: 1 + sum(1 for v in scores.values() if v < scores[c]) for c in COMPETENCIES}
    if (
        analysis.lowest_score != lowest
        or analysis.highest_score != highest
        or analysis.spread != highest - lowest
        or list(analysis.weakest) != expected_weakest
        or analysis.has_single_weakest != (len(expected_weakest) == 1)
        or ranks != expected_ranks
    ):
        raise AssemblyError("Gap analysis is internally inconsistent with its own scores.")

    if selection.student_id != analysis.student_id:
        raise AssemblyError("The selection and the gap analysis are for different students.")

    if selection.requested_questions != request.max_questions:
        raise AssemblyError("The selection doesn't match the request's question count.")
    if selection.max_total_marks != request.max_total_marks:
        raise AssemblyError("The selection doesn't match the request's marks limit.")

    question_ids = [item.question_id for item in selection.selected]
    if len(set(question_ids)) != len(question_ids):
        raise AssemblyError("The selection contains the same question more than once.")
    if len(question_ids) > selection.requested_questions:
        raise AssemblyError("The selection has more questions than were requested.")

    for item in selection.selected:
        if item.is_ai_generated and not request.include_ai_generated:
            raise AssemblyError(
                f"Question {item.question_id} is AI-generated, but the request doesn't allow AI-generated questions."
            )
        if item.marks < 1:
            raise AssemblyError(f"Question {item.question_id} has invalid marks.")
        if item.competency_rank != ranks[item.competency]:
            raise AssemblyError(
                f"Question {item.question_id} has a competency rank that doesn't match the gap analysis."
            )

    if selection.total_marks != sum(item.marks for item in selection.selected):
        raise AssemblyError("The selection's total marks don't match its questions.")
    if selection.shortfall != selection.requested_questions - len(question_ids):
        raise AssemblyError("The selection's shortfall doesn't match its questions.")
    if selection.max_total_marks is not None and selection.total_marks > selection.max_total_marks:
        raise AssemblyError("The selection exceeds its marks limit.")

    return ranks


def rationale_summary(
    targeted: List[str], scores: Dict[str, int], weakest: List[str], lowest: int, highest: int
) -> str:
    """Factual one-line summary. Also used when a saved draft is edited."""
    if not targeted:
        return "No questions were selected."
    parts = ", ".join(f"{c} ({scores[c]})" for c in targeted)
    if weakest:
        lowest_text = f"lowest score: {', '.join(weakest)} ({lowest})"
    else:
        lowest_text = f"all four scores equal ({lowest})"
    return f"Targets {parts}. Student's {lowest_text}; score range {lowest}-{highest}."


def _summary(targeted: List[str], analysis: GapAnalysis) -> str:
    scores = {gap.competency: gap.score for gap in analysis.ranked}
    return rationale_summary(targeted, scores, list(analysis.weakest), analysis.lowest_score, analysis.highest_score)


def assemble_homework_draft(
    analysis: GapAnalysis,
    selection: SelectionResult,
    request: SelectionRequest,
) -> HomeworkDraft:
    _check_inputs(analysis, selection, request)

    items = [
        DraftItem(
            position=index,
            question_id=question.question_id,
            competency=question.competency,
            competency_rank=question.competency_rank,
            marks=question.marks,
            type=question.type,
            bloom_level=question.bloom_level,
            is_ai_generated=question.is_ai_generated,
            text=question.text,
        )
        for index, question in enumerate(selection.selected, start=1)
    ]

    targeted: List[str] = []
    for item in items:
        if item.competency not in targeted:
            targeted.append(item.competency)

    rationale = DraftRationale(
        targeted_competencies=targeted,
        weakest=list(analysis.weakest),
        competency_scores={gap.competency: gap.score for gap in analysis.ranked},
        lowest_score=analysis.lowest_score,
        highest_score=analysis.highest_score,
        score_source=analysis.source,
        summary=_summary(targeted, analysis),
    )

    shortfall = request.max_questions - len(items)
    notes = list(analysis.notes) + list(selection.notes)
    if not items:
        notes.append("The draft has no questions, so there's nothing to review yet.")
    elif shortfall:
        notes.append(f"The draft is incomplete: {shortfall} requested question(s) couldn't be found.")
    if any(item.is_ai_generated for item in items):
        notes.append("The draft includes AI-generated questions, which have no review status.")

    return HomeworkDraft(
        student_id=analysis.student_id,
        school_id=request.school_id,
        subject_id=request.subject_id,
        items=items,
        question_count=len(items),
        total_marks=sum(item.marks for item in items),
        requested_questions=request.max_questions,
        max_total_marks=request.max_total_marks,
        shortfall=shortfall,
        is_complete=shortfall == 0,
        contains_ai_generated=any(item.is_ai_generated for item in items),
        rationale=rationale,
        notes=notes,
    )
