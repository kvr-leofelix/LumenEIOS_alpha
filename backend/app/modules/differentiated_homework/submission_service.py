"""Saving and submitting a student's answers. No database I/O here: functions change ORM
objects in memory and the caller commits once, so a request is saved completely or not at all.

No grading. Nothing here reads correct_answer or marking_rubric, or computes marks or scores.

Contract (enforced here; the request shapes are in schemas.py):
- One submission per assignment. The first save creates it with status in_progress.
- A save is partial: listed positions change, others keep their answers. {"clear": true}
  removes an answer.
- Every change must be made against the current version (optimistic locking). With no
  submission yet, expected_version must be omitted.
- The whole request is validated before anything changes. One bad answer rejects it all.
- Final submit locks the submission for good. It may be blank or partial, and is_late is set
  when it is submitted after the assignment's due time. There is no penalty.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Sequence

from sqlalchemy.orm.attributes import flag_modified

from backend.app.models.entities import generate_uuid
from backend.app.modules.differentiated_homework.draft_service import as_utc
from backend.app.modules.differentiated_homework.models import (
    HomeworkAssignmentRecord,
    HomeworkDraftItemRecord,
    HomeworkSubmissionAnswerRecord,
    HomeworkSubmissionRecord,
)
from backend.app.modules.differentiated_homework.schemas import (
    MAX_ANSWER_TEXT_LENGTH,
    AnswerUpdate,
    SubmissionAnswerOut,
    SubmissionAnswersUpdate,
    SubmissionFinalizeRequest,
    HomeworkSubmissionOut,
)

# Question types as stored on frozen items (QuestionBankItem.type).
TEXT_ANSWER_TYPES = frozenset({"short", "descriptive", "practical"})
OPTION_ANSWER_TYPES = frozenset({"mcq"})


class SubmissionError(Exception):
    """Base class. Each subclass maps to one HTTP status in a later phase."""


class NotSubmittable(SubmissionError):
    """The assignment can't take answers (wrong status, or the submission belongs elsewhere)."""


class SubmissionMismatch(NotSubmittable):
    """Stored data is inconsistent: the submission or one of its answers doesn't belong to the
    assignment it was loaded for. A server-side fault, not a client conflict. A subclass of
    NotSubmittable so Phase 1 callers that catch NotSubmittable keep working."""


class SubmissionLocked(SubmissionError):
    """The submission has been submitted; its answers can't change."""


class VersionConflict(SubmissionError):
    """expected_version doesn't match: someone else changed the submission first."""


@dataclass(frozen=True)
class AnswerProblem:
    position: int
    reason: str


class InvalidAnswers(SubmissionError):
    """One or more answers are invalid. Lists every problem, not just the first."""

    def __init__(self, problems: List[AnswerProblem]):
        self.problems = problems
        super().__init__("; ".join(f"position {p.position}: {p.reason}" for p in problems))


@dataclass(frozen=True)
class AnswerChange:
    """A validated change, ready to apply."""

    draft_item_id: str
    position: int
    action: str  # "answer_text", "selected_option_index" or "clear"
    answer_text: Optional[str] = None
    selected_option_index: Optional[int] = None


def items_by_position(assignment: HomeworkAssignmentRecord) -> Dict[int, HomeworkDraftItemRecord]:
    return {item.position: item for item in assignment.draft.items}


def validate_answer_updates(
    updates: Sequence[AnswerUpdate], items: Dict[int, HomeworkDraftItemRecord]
) -> List[AnswerChange]:
    """Check every update against the frozen questions. Raises InvalidAnswers listing all
    problems. The schema already checks shapes; this checks them against the real questions,
    and repeats the shape checks so direct callers get the same guarantees."""
    problems: List[AnswerProblem] = []
    changes: List[AnswerChange] = []
    seen = set()
    for update in updates:
        position = update.position
        if position in seen:
            problems.append(AnswerProblem(position, "this position appears more than once"))
            continue
        seen.add(position)
        item = items.get(position)
        if item is None:
            problems.append(AnswerProblem(position, "there is no question at this position"))
            continue
        action = update.action
        if action == "clear":
            changes.append(AnswerChange(item.id, position, "clear"))
        elif action == "answer_text":
            text = update.answer_text
            if item.type in OPTION_ANSWER_TYPES:
                problems.append(AnswerProblem(position, f"this is a {item.type} question; send selected_option_index"))
            elif item.type not in TEXT_ANSWER_TYPES:
                problems.append(AnswerProblem(position, f"question type '{item.type}' can't be answered"))
            elif text is None or not text.strip():
                problems.append(AnswerProblem(position, "answer_text can't be blank; use clear: true"))
            elif len(text) > MAX_ANSWER_TEXT_LENGTH:
                problems.append(AnswerProblem(position, f"answer_text is longer than {MAX_ANSWER_TEXT_LENGTH} characters"))
            else:
                changes.append(AnswerChange(item.id, position, "answer_text", answer_text=text))
        else:
            index = update.selected_option_index
            options = item.options_json if isinstance(item.options_json, list) else []
            if item.type in TEXT_ANSWER_TYPES:
                problems.append(AnswerProblem(position, f"this is a {item.type} question; send answer_text"))
            elif item.type not in OPTION_ANSWER_TYPES:
                problems.append(AnswerProblem(position, f"question type '{item.type}' can't be answered"))
            elif not options:
                problems.append(AnswerProblem(position, "this question has no options to choose from"))
            elif type(index) is not int or not 0 <= index < len(options):
                problems.append(AnswerProblem(position, f"selected_option_index must be from 0 to {len(options) - 1}"))
            else:
                changes.append(AnswerChange(item.id, position, "selected_option_index", selected_option_index=index))
    if problems:
        raise InvalidAnswers(problems)
    return changes


def _check_assignment_open(assignment: HomeworkAssignmentRecord) -> None:
    if assignment.status != "assigned":
        raise NotSubmittable(f"Assignment {assignment.id} isn't open for answers.")


def _check_can_change(
    assignment: HomeworkAssignmentRecord,
    submission: Optional[HomeworkSubmissionRecord],
    expected_version: Optional[int],
) -> None:
    """Rules shared by save and final submit."""
    _check_assignment_open(assignment)
    if submission is None:
        if expected_version is not None:
            raise VersionConflict("No submission exists yet; omit expected_version.")
        return
    if submission.assignment_id != assignment.id or submission.student_id != assignment.student_id:
        raise SubmissionMismatch("This submission doesn't belong to this assignment.")
    if submission.status == "submitted":
        raise SubmissionLocked("This homework has been submitted and can't be changed.")
    if expected_version is None:
        raise VersionConflict("expected_version is required to change an existing submission.")
    if expected_version != submission.version:
        raise VersionConflict("The submission was changed elsewhere; reload it and try again.")


def _new_submission(assignment: HomeworkAssignmentRecord, now: datetime) -> HomeworkSubmissionRecord:
    """Student and school are copied from the assignment, never taken from a request."""
    return HomeworkSubmissionRecord(
        id=generate_uuid(),  # known before saving, so it can be returned at once
        assignment_id=assignment.id,
        student_id=assignment.student_id,
        school_id=assignment.school_id,
        status="in_progress",
        is_late=False,
        started_at=now,
        updated_at=now,
        answers=[],
    )


def _touch(submission: HomeworkSubmissionRecord, now: datetime) -> None:
    """Force an UPDATE of the submission row, so the version always goes up and a concurrent
    change is always detected. flag_modified is needed because two saves can get the same
    timestamp, and an unchanged value alone wouldn't be written."""
    submission.updated_at = now
    flag_modified(submission, "updated_at")


def save_answers(
    assignment: HomeworkAssignmentRecord,
    submission: Optional[HomeworkSubmissionRecord],
    request: SubmissionAnswersUpdate,
    now: datetime,
) -> HomeworkSubmissionRecord:
    """Apply a partial save. Returns the submission (new when `submission` was None); the
    caller adds a new one to the session and commits. Raises before changing anything."""
    _check_can_change(assignment, submission, request.expected_version)
    changes = validate_answer_updates(request.answers, items_by_position(assignment))

    if submission is None:
        submission = _new_submission(assignment, now)
    existing = {answer.draft_item_id: answer for answer in submission.answers}
    for change in changes:
        answer = existing.get(change.draft_item_id)
        if change.action == "clear":
            if answer is not None:
                submission.answers.remove(answer)  # delete-orphan removes the row
            continue
        if answer is None:
            answer = HomeworkSubmissionAnswerRecord(draft_item_id=change.draft_item_id, created_at=now)
            submission.answers.append(answer)
            existing[change.draft_item_id] = answer
        answer.answer_text = change.answer_text
        answer.selected_option_index = change.selected_option_index
        answer.updated_at = now
    _touch(submission, now)
    return submission


def finalize_submission(
    assignment: HomeworkAssignmentRecord,
    submission: Optional[HomeworkSubmissionRecord],
    request: SubmissionFinalizeRequest,
    now: datetime,
) -> HomeworkSubmissionRecord:
    """Lock the submission. Blank and partial submissions are allowed. is_late is true only
    when there is a due time and `now` is after it (submitting exactly at it is on time)."""
    _check_can_change(assignment, submission, request.expected_version)
    if submission is None:
        submission = _new_submission(assignment, now)
    due_at = as_utc(assignment.due_at)
    submission.status = "submitted"
    submission.submitted_at = now
    submission.is_late = due_at is not None and as_utc(now) > due_at
    _touch(submission, now)
    return submission


def to_submission_out(submission: HomeworkSubmissionRecord, assignment: HomeworkAssignmentRecord) -> HomeworkSubmissionOut:
    """Student-facing view. Built field by field; never reads the answer key or rubric."""
    positions = {item.id: item.position for item in assignment.draft.items}
    answers = []
    for answer in submission.answers:
        if answer.draft_item_id not in positions:
            raise SubmissionMismatch("A stored answer doesn't match this assignment's questions.")
        answers.append(SubmissionAnswerOut(
            position=positions[answer.draft_item_id],
            answer_text=answer.answer_text,
            selected_option_index=answer.selected_option_index,
        ))
    answers.sort(key=lambda a: a.position)
    return HomeworkSubmissionOut(
        id=submission.id,
        assignment_id=submission.assignment_id,
        status=submission.status,
        version=submission.version,
        is_late=bool(submission.is_late),
        started_at=as_utc(submission.started_at),
        updated_at=as_utc(submission.updated_at),
        submitted_at=as_utc(submission.submitted_at),
        answered_count=len(answers),
        question_count=len(positions),
        answers=answers,
    )


def empty_submission_out(assignment: HomeworkAssignmentRecord) -> HomeworkSubmissionOut:
    """The view before any save: nothing is stored, and nothing is created by building it.
    question_count is the assignment's real number of questions, so all three states describe
    the same homework; answered_count is 0."""
    return HomeworkSubmissionOut(
        id=None,
        assignment_id=assignment.id,
        status="not_started",
        version=None,
        is_late=False,
        started_at=None,
        updated_at=None,
        submitted_at=None,
        answered_count=0,
        question_count=len(assignment.draft.items),
        answers=[],
    )
