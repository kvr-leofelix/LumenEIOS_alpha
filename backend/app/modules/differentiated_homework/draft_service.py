"""Saved homework drafts: status rules, building records, edits, and response shapes.

Status rules (anything else is refused):
- approve: draft -> approved
- reject:  draft -> rejected
- reopen:  rejected -> draft   (the explicit way to edit a rejected draft)
- assign:  approved -> assigned (defined for the next milestone; no endpoint yet)

Only questions in "draft" status can be edited. The only edit for now is removing a question.
"""
from datetime import datetime, timezone
from typing import Dict, List

from backend.app.modules.differentiated_homework.homework_assembler import rationale_summary
from backend.app.modules.differentiated_homework.models import (
    HomeworkAssignmentRecord,
    HomeworkDraftItemRecord,
    HomeworkDraftRecord,
)
from backend.app.modules.differentiated_homework.question_selector import normalize_competency
from backend.app.modules.differentiated_homework.schemas import (
    AssignmentOut,
    AssignmentSummaryOut,
    DraftRationale,
    HomeworkDraft,
    HomeworkDraftSaveRequest,
    QuestionSnapshot,
    SavedDraftItemOut,
    SavedDraftOut,
    SavedDraftSummaryOut,
)

TRANSITIONS: Dict[str, tuple] = {
    "approve": ("draft", "approved"),
    "reject": ("draft", "rejected"),
    "reopen": ("rejected", "draft"),
    "assign": ("approved", "assigned"),
}


class InvalidTransition(ValueError):
    pass


class StaleQuestion(ValueError):
    """A question changed or disappeared between selection and saving."""


class InvalidEdit(ValueError):
    pass


def next_status(current: str, action: str) -> str:
    if action not in TRANSITIONS:
        raise InvalidTransition(f"Unknown action: {action}")
    required, target = TRANSITIONS[action]
    if current != required:
        raise InvalidTransition(f"Can't {action} a draft that is {current}.")
    return target


def build_draft_record(
    draft: HomeworkDraft,
    snapshots: Dict[str, QuestionSnapshot],
    request: HomeworkDraftSaveRequest,
    created_by: str,
) -> HomeworkDraftRecord:
    """Turn an assembled draft plus fresh question snapshots into unsaved database rows.

    Each snapshot must still match what was selected (text, marks, competency, type, Bloom
    level, AI flag). If anything changed since selection, StaleQuestion is raised and nothing
    should be saved.
    """
    items = []
    for item in draft.items:
        snap = snapshots.get(item.question_id)
        if snap is None:
            raise StaleQuestion(f"Question {item.question_id} is no longer available.")
        if (
            snap.text != item.text
            or snap.marks != item.marks
            or normalize_competency(snap.competency) != item.competency
            or snap.type != item.type
            or snap.bloom_level != item.bloom_level
            or snap.is_ai_generated != item.is_ai_generated
        ):
            raise StaleQuestion(f"Question {item.question_id} changed after it was selected.")
        items.append(
            HomeworkDraftItemRecord(
                position=item.position,
                source_question_id=item.question_id,
                text=snap.text,
                type=snap.type,
                options_json=list(snap.options_json),
                marks=snap.marks,
                competency=item.competency,
                competency_rank=item.competency_rank,
                bloom_level=snap.bloom_level,
                is_ai_generated=snap.is_ai_generated,
                correct_answer=snap.correct_answer,
                marking_rubric=snap.marking_rubric,
            )
        )

    return HomeworkDraftRecord(
        student_id=draft.student_id,
        school_id=draft.school_id,
        subject_id=draft.subject_id,
        created_by=created_by,
        status="draft",
        requested_questions=draft.requested_questions,
        max_total_marks=draft.max_total_marks,
        include_ai_generated=request.include_ai_generated,
        question_count=draft.question_count,
        total_marks=draft.total_marks,
        shortfall=draft.shortfall,
        rationale_json=draft.rationale.model_dump(),
        notes_json=list(draft.notes),
        items=items,
    )


def apply_review(record: HomeworkDraftRecord, action: str, reviewer_id: str, note) -> None:
    """Change status. approve/reject record the reviewer; reopen clears the review fields;
    assign leaves the review fields as they were."""
    record.status = next_status(record.status, action)
    if action == "reopen":
        record.reviewed_by = None
        record.reviewed_at = None
        record.review_note = None
    elif action in ("approve", "reject"):
        record.reviewed_by = reviewer_id
        record.reviewed_at = datetime.now(timezone.utc)
        record.review_note = note


def as_utc(value):
    """SQLite drops time zones, so values read back are naive. All stored values are UTC, so
    attach UTC to naive values; responses then look the same before and after a reload."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


TEMPORARY_POSITION_OFFSET = 100_000


def remove_item(record: HomeworkDraftRecord, position: int) -> HomeworkDraftItemRecord:
    """Remove one question from a draft-status draft. Returns the removed item.

    Then the caller must: flush; stage_renumber; flush; renumber_and_recount. The database
    applies position updates in primary-key order, which is random, so renumbering straight
    to 1..n could briefly give two items the same position. Moving every item to a temporary
    high position first means no update can collide, whatever the order.
    """
    if record.status != "draft":
        raise InvalidEdit(f"Only drafts in 'draft' status can be edited; this one is {record.status}.")
    item = next((i for i in record.items if i.position == position), None)
    if item is None:
        raise LookupError(f"No question at position {position}.")
    if len(record.items) == 1:
        raise InvalidEdit("A draft needs at least one question.")
    record.items.remove(item)
    return item


def stage_renumber(record: HomeworkDraftRecord) -> None:
    """Move every item to a temporary position above any real one, keeping their order."""
    for item in record.items:
        item.position = item.position + TEMPORARY_POSITION_OFFSET


def renumber_and_recount(record: HomeworkDraftRecord, removed: HomeworkDraftItemRecord) -> None:
    items = sorted(record.items, key=lambda i: i.position)
    for index, item in enumerate(items, start=1):
        item.position = index
    record.question_count = len(items)
    record.total_marks = sum(i.marks for i in items)
    record.shortfall = record.requested_questions - len(items)

    rationale = dict(record.rationale_json)
    targeted: List[str] = []
    for item in items:
        if item.competency not in targeted:
            targeted.append(item.competency)
    rationale["targeted_competencies"] = targeted
    rationale["summary"] = rationale_summary(
        targeted, rationale["competency_scores"], rationale["weakest"],
        rationale["lowest_score"], rationale["highest_score"],
    )
    record.rationale_json = rationale
    record.notes_json = [
        *record.notes_json,
        f"Edited: question {removed.source_question_id} (position {removed.position}) removed.",
    ]


def to_summary(record: HomeworkDraftRecord) -> SavedDraftSummaryOut:
    return SavedDraftSummaryOut(
        id=record.id,
        student_id=record.student_id,
        school_id=record.school_id,
        subject_id=record.subject_id,
        status=record.status,
        created_by=record.created_by,
        question_count=record.question_count,
        total_marks=record.total_marks,
        created_at=as_utc(record.created_at),
        updated_at=as_utc(record.updated_at),
    )


def to_out(record: HomeworkDraftRecord) -> SavedDraftOut:
    """Teacher-facing view. The answer key and rubric are deliberately left out."""
    return SavedDraftOut(
        **to_summary(record).model_dump(),
        requested_questions=record.requested_questions,
        max_total_marks=record.max_total_marks,
        include_ai_generated=record.include_ai_generated,
        shortfall=record.shortfall,
        is_complete=record.shortfall == 0,
        rationale=DraftRationale(**record.rationale_json),
        notes=list(record.notes_json),
        reviewed_by=record.reviewed_by,
        reviewed_at=as_utc(record.reviewed_at),
        review_note=record.review_note,
        items=items_out(record),
    )


def items_out(record: HomeworkDraftRecord) -> List[SavedDraftItemOut]:
    """Snapshot items as shown to teachers, in order. The answer key and rubric are left out."""
    return [
        SavedDraftItemOut(
            position=i.position,
            source_question_id=i.source_question_id,
            text=i.text,
            type=i.type,
            options=list(i.options_json or []),
            marks=i.marks,
            competency=i.competency,
            competency_rank=i.competency_rank,
            bloom_level=i.bloom_level,
            is_ai_generated=i.is_ai_generated,
        )
        for i in sorted(record.items, key=lambda i: i.position)
    ]


# --- Assignments -----------------------------------------------------------------------


def build_assignment(draft: HomeworkDraftRecord, assigned_by: str, due_at) -> HomeworkAssignmentRecord:
    """Unsaved assignment row for an approved draft. The caller also changes the draft's status
    to 'assigned' (apply_review 'assign') in the same transaction."""
    return HomeworkAssignmentRecord(
        draft_id=draft.id,
        student_id=draft.student_id,
        school_id=draft.school_id,
        subject_id=draft.subject_id,
        assigned_by=assigned_by,
        due_at=as_utc(due_at),
        status="assigned",
    )


def to_assignment_summary(assignment: HomeworkAssignmentRecord) -> AssignmentSummaryOut:
    return AssignmentSummaryOut(
        id=assignment.id,
        draft_id=assignment.draft_id,
        student_id=assignment.student_id,
        school_id=assignment.school_id,
        subject_id=assignment.subject_id,
        status=assignment.status,
        assigned_by=assignment.assigned_by,
        assigned_at=as_utc(assignment.assigned_at),
        due_at=as_utc(assignment.due_at),
        question_count=assignment.draft.question_count,
        total_marks=assignment.draft.total_marks,
    )


def to_assignment_out(assignment: HomeworkAssignmentRecord) -> AssignmentOut:
    return AssignmentOut(**to_assignment_summary(assignment).model_dump(), items=items_out(assignment.draft))
