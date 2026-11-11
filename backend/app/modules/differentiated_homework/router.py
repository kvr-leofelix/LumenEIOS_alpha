from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from backend.app.api.dependencies import get_current_user, require_roles
from backend.app.db.session import get_db
from backend.app.models.entities import HomeworkRemediation, Student, User, AuditEvent, utc_now
from backend.app.schemas.competencies import HomeworkOut
from backend.app.services.competency_service import generate_differentiated_recommendation
import logging

from pydantic import ValidationError

from backend.app.modules.differentiated_homework.access import can_view_student, role_may_view_students
from backend.app.modules.differentiated_homework.competency_adapter import load_competency_profile
from backend.app.modules.differentiated_homework.gap_analyzer import analyze_gaps
from backend.app.modules.differentiated_homework.schemas import GapAnalysis
from backend.app.models.entities import ClassSection, Subject
from backend.app.modules.differentiated_homework.access import role_may_generate_homework
from backend.app.modules.differentiated_homework.homework_assembler import AssemblyError, assemble_homework_draft
from backend.app.modules.differentiated_homework.question_bank_adapter import load_candidate_questions
from backend.app.modules.differentiated_homework.question_selector import select_questions
from backend.app.modules.differentiated_homework.schemas import (
    HomeworkDraft,
    HomeworkPreviewRequest,
    SelectionRequest,
)
from fastapi import Query
from backend.app.models.entities import SchoolMembership
from backend.app.modules.differentiated_homework.access import can_access_draft
from backend.app.modules.differentiated_homework.draft_service import (
    InvalidEdit,
    InvalidTransition,
    StaleQuestion,
    apply_review,
    build_draft_record,
    remove_item,
    renumber_and_recount,
    stage_renumber,
    to_out,
    to_summary,
)
from sqlalchemy.orm.exc import StaleDataError
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from backend.app.modules.differentiated_homework.access import can_access_assignment
from backend.app.modules.differentiated_homework.draft_service import (
    build_assignment,
    to_assignment_out,
    to_assignment_summary,
)
from backend.app.modules.differentiated_homework.models import HomeworkAssignmentRecord, StudentAccountLink
from fastapi import Response
from backend.app.modules.differentiated_homework.draft_service import as_utc
from backend.app.modules.differentiated_homework.schemas import (
    StudentAccountLinkCreate,
    StudentAccountLinkListItemOut,
    StudentAccountLinkOut,
    StudentAssignmentOut,
    StudentAssignmentSummaryOut,
)
from backend.app.modules.differentiated_homework.student_access import (
    resolve_linked_student,
    subject_names,
    to_student_detail,
    to_student_summary,
)
from backend.app.modules.differentiated_homework.models import HomeworkSubmissionRecord
from backend.app.modules.differentiated_homework.schemas import (
    AnswerProblemOut,
    SubmissionAnswersUpdate,
    SubmissionFinalizeRequest,
    HomeworkSubmissionOut,
)
from backend.app.modules.differentiated_homework.submission_service import (
    InvalidAnswers,
    NotSubmittable,
    SubmissionLocked,
    SubmissionMismatch,
    VersionConflict,
    empty_submission_out,
    finalize_submission,
    save_answers,
    to_submission_out,
)
from backend.app.modules.differentiated_homework.schemas import (
    AssignmentOut,
    AssignmentStatus,
    AssignmentSummaryOut,
    AssignRequest,
)
from backend.app.modules.differentiated_homework.models import HomeworkDraftRecord
from backend.app.modules.differentiated_homework.question_bank_adapter import load_question_snapshots
from backend.app.modules.differentiated_homework.schemas import (
    DraftReviewRequest,
    DraftStatus,
    HomeworkDraftSaveRequest,
    SavedDraftOut,
    SavedDraftSummaryOut,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Homework & Remediation"])


class HomeworkCreate(BaseModel):
    student_id: str
    class_id: str
    subject_id: str = "sub-math"
    title: str
    competency_target: str
    reason: Optional[str] = None
    description: str
    due_date: str


@router.get("/classes/{class_id}/homework", response_model=List[HomeworkOut])
async def list_class_homework(class_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    res = await db.execute(select(HomeworkRemediation).filter(HomeworkRemediation.class_id == class_id))
    return res.scalars().all()


@router.post("/classes/{class_id}/homework", response_model=HomeworkOut, status_code=status.HTTP_201_CREATED)
async def assign_homework(
    class_id: str,
    req: HomeworkCreate,
    db: AsyncSession = Depends(get_db),
    educator: User = Depends(require_roles("admin", "principal", "teacher"))
):
    st_res = await db.execute(select(Student).filter(Student.id == req.student_id))
    st = st_res.scalars().first()
    student_name = st.name if st else "Student"

    hw = HomeworkRemediation(
        student_id=req.student_id,
        student_name=student_name,
        class_id=class_id,
        subject_id=req.subject_id,
        title=req.title,
        competency_target=req.competency_target,
        reason=req.reason,
        description=req.description,
        due_date=req.due_date,
        status="assigned"
    )
    db.add(hw)

    audit = AuditEvent(
        timestamp=utc_now().strftime("%Y-%m-%d %H:%M"),
        user_id=educator.id,
        user_name=educator.name,
        action="Assigned Differentiated Remediation",
        details=f"Assigned {req.competency_target} task '{req.title}' to {student_name}",
        category="curriculum"
    )
    db.add(audit)
    await db.commit()
    await db.refresh(hw)
    return hw


@router.get("/students/{student_id}/homework", response_model=List[HomeworkOut])
async def list_student_homework(student_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role == "student" and current_user.id != student_id:
        raise HTTPException(status_code=403, detail="Access denied.")

    res = await db.execute(select(HomeworkRemediation).filter(HomeworkRemediation.student_id == student_id))
    return res.scalars().all()


@router.post("/homework/{homework_id}/submissions")
async def submit_homework(homework_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    res = await db.execute(select(HomeworkRemediation).filter(HomeworkRemediation.id == homework_id))
    hw = res.scalars().first()
    if not hw:
        raise HTTPException(status_code=404, detail="Homework not found.")

    hw.status = "submitted"
    hw.score = 92
    await db.commit()
    return {"message": "Homework submitted successfully.", "score": 92}


@router.get("/students/{student_id}/remediation/recommendation")
async def get_student_remediation_recommendation(
    student_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    st_res = await db.execute(select(Student).filter(Student.id == student_id))
    st = st_res.scalars().first()
    if not st:
        raise HTTPException(status_code=404, detail="Student not found.")
    return generate_differentiated_recommendation(st)


@router.get("/students/{student_id}/homework/gap-analysis", response_model=GapAnalysis)
async def get_student_gap_analysis(
    student_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Read-only: rank the student's LU, CU, AU and CT scores and report the weakest.

    Access rules are in access.py. Scores come from the temporary competency adapter and
    are unverified, so the result is a relative comparison, not a diagnosis.
    """
    # Roles that can never view student analysis are refused before any lookup, so they
    # can't use this endpoint to find out which student IDs exist.
    if not role_may_view_students(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    result = await db.execute(select(Student).filter(Student.id == student_id))
    student = result.scalars().first()
    if student is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found.")

    if not await can_view_student(db, current_user, student):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    try:
        profile = await load_competency_profile(db, student_id)
    except ValidationError:
        # Stored data is out of range or malformed. Don't return or log the values.
        logger.warning("Invalid stored competency scores for a student; gap analysis refused.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="This student's competency data is invalid. Contact an administrator.",
        )
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found.")

    return analyze_gaps(profile)


INVALID_DATA = "This student's data is invalid. Contact an administrator."


@router.post("/students/{student_id}/homework/preview", response_model=HomeworkDraft)
async def preview_student_homework(
    student_id: str,
    body: HomeworkPreviewRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Build an unsaved homework draft for one student. Nothing is written to the database.

    Runs the existing pipeline: competency adapter, Gap Analyzer, question bank adapter,
    Question Selector, Homework Assembler. The school comes from the student's record.
    """
    return await _generate_draft(db, current_user, student_id, body)


async def _generate_draft(
    db: AsyncSession, current_user: User, student_id: str, body: HomeworkPreviewRequest
) -> HomeworkDraft:
    """Shared by preview and save: checks access and inputs, then runs the pipeline. No writes."""
    if not role_may_generate_homework(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    student = (await db.execute(select(Student).filter(Student.id == student_id))).scalars().first()
    if student is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found.")
    if not await can_view_student(db, current_user, student):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    # The subject must exist and be offered by the student's own class (agreed rule).
    subject = (await db.execute(select(Subject.id).filter(Subject.id == body.subject_id))).first()
    if subject is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found.")
    student_class = (
        await db.execute(select(ClassSection).filter(ClassSection.id == student.class_id))
    ).scalars().first()
    if (
        student_class is None
        or student_class.school_id != student.school_id
        or not isinstance(student_class.subject_ids_json, list)
    ):
        logger.warning("Student class record missing or inconsistent; homework preview refused.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=INVALID_DATA)
    if body.subject_id not in student_class.subject_ids_json:
        raise HTTPException(
            status_code=422,  # plain number: the named constant differs between Starlette versions
            detail="This subject isn't offered in the student's class.",
        )

    try:
        profile = await load_competency_profile(db, student_id)
    except ValidationError:
        logger.warning("Invalid stored competency scores for a student; homework preview refused.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="This student's competency data is invalid. Contact an administrator.",
        )
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found.")

    analysis = analyze_gaps(profile)
    selection_request = SelectionRequest(
        school_id=student.school_id,
        subject_id=body.subject_id,
        max_questions=body.max_questions,
        max_total_marks=body.max_total_marks,
        include_ai_generated=body.include_ai_generated,
    )
    loaded = await load_candidate_questions(db, student.school_id, body.subject_id)
    selection = select_questions(analysis, loaded.candidates, selection_request)

    try:
        draft = assemble_homework_draft(analysis, selection, selection_request)
    except AssemblyError:
        # The pipeline produced inconsistent data; this is a server fault, not a client error.
        logger.exception("Homework assembly failed on pipeline output.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Homework preview failed.")

    if loaded.malformed_question_ids:
        note = f"{len(loaded.malformed_question_ids)} question bank row(s) couldn't be read and were skipped."
        draft = draft.model_copy(update={"notes": [*draft.notes, note]})
    return draft


# --- Saved homework drafts ------------------------------------------------------------


def _audit(user: User, action: str, details: str) -> AuditEvent:
    return AuditEvent(
        timestamp=utc_now().strftime("%Y-%m-%d %H:%M"),
        user_id=user.id,
        user_name=user.name,
        action=action,
        details=details,
        category="curriculum",
    )


async def _accessible_school_ids(db: AsyncSession, user: User) -> set:
    ids = {user.school_id} if user.school_id else set()
    rows = await db.execute(
        select(SchoolMembership.school_id).filter(
            SchoolMembership.user_id == user.id,
            SchoolMembership.is_active == True,  # noqa: E712 (SQL comparison)
        )
    )
    ids.update(r.school_id for r in rows.all())
    return ids


async def _load_draft_for(db: AsyncSession, user: User, draft_id: str) -> HomeworkDraftRecord:
    if not role_may_generate_homework(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")
    record = (
        await db.execute(select(HomeworkDraftRecord).filter(HomeworkDraftRecord.id == draft_id))
    ).scalars().first()
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found.")
    if not await can_access_draft(db, user, record):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")
    return record


@router.post("/students/{student_id}/homework/drafts", response_model=SavedDraftOut, status_code=201)
async def save_homework_draft(
    student_id: str,
    body: HomeworkDraftSaveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Explicitly save a homework draft. The server regenerates it with the same pipeline as
    the preview, so a client can't post altered questions. Saved with status 'draft'."""
    draft = await _generate_draft(db, current_user, student_id, body)

    question_ids = [item.question_id for item in draft.items]
    if body.expected_question_ids is not None and body.expected_question_ids != question_ids:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The selected questions have changed since the preview. Preview again before saving.",
        )
    if not question_ids:
        raise HTTPException(status_code=422, detail="There are no questions to save.")

    snapshots = await load_question_snapshots(db, question_ids, draft.school_id, draft.subject_id)
    try:
        record = build_draft_record(draft, snapshots, body, created_by=current_user.id)
    except StaleQuestion:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A selected question changed while saving. Preview again before saving.",
        )

    db.add(record)
    db.add(_audit(current_user, "Saved Homework Draft",
                  f"Saved homework draft for student {draft.student_id} ({draft.question_count} questions)."))
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return to_out(record)


@router.get("/homework/drafts", response_model=List[SavedDraftSummaryOut])
async def list_homework_drafts(
    draft_status: Optional[DraftStatus] = Query(default=None, alias="status"),
    student_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Drafts the user may see: admin all, principal their schools, teacher their own."""
    if not role_may_generate_homework(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    query = select(HomeworkDraftRecord)
    if current_user.role != "admin":
        schools = await _accessible_school_ids(db, current_user)
        query = query.filter(HomeworkDraftRecord.school_id.in_(schools))
        if current_user.role == "teacher":
            query = query.filter(HomeworkDraftRecord.created_by == current_user.id)
    if draft_status:
        query = query.filter(HomeworkDraftRecord.status == draft_status)
    if student_id:
        query = query.filter(HomeworkDraftRecord.student_id == student_id)

    rows = await db.execute(query.order_by(HomeworkDraftRecord.created_at.desc(), HomeworkDraftRecord.id))
    return [to_summary(r) for r in rows.scalars().all()]


@router.get("/homework/drafts/{draft_id}", response_model=SavedDraftOut)
async def get_homework_draft(
    draft_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return to_out(await _load_draft_for(db, current_user, draft_id))


CHANGED_ELSEWHERE = "This draft was changed by another request. Reload it and try again."


async def _commit_or_conflict(db: AsyncSession) -> None:
    """Commit; if another request changed the draft first (version mismatch), roll back and 409."""
    try:
        await db.commit()
    except StaleDataError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=CHANGED_ELSEWHERE)


async def _review(db: AsyncSession, user: User, draft_id: str, action: str, note) -> SavedDraftOut:
    record = await _load_draft_for(db, user, draft_id)
    try:
        apply_review(record, action, user.id, note)
    except InvalidTransition as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    db.add(_audit(user, f"Homework Draft {action.capitalize()}", f"{action} draft {record.id}."))
    await _commit_or_conflict(db)
    return to_out(record)


@router.post("/homework/drafts/{draft_id}/approve", response_model=SavedDraftOut)
async def approve_homework_draft(
    draft_id: str,
    body: Optional[DraftReviewRequest] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await _review(db, current_user, draft_id, "approve", body.note if body else None)


@router.post("/homework/drafts/{draft_id}/reject", response_model=SavedDraftOut)
async def reject_homework_draft(
    draft_id: str,
    body: Optional[DraftReviewRequest] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await _review(db, current_user, draft_id, "reject", body.note if body else None)


@router.post("/homework/drafts/{draft_id}/reopen", response_model=SavedDraftOut)
async def reopen_homework_draft(
    draft_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Move a rejected draft back to 'draft' so it can be edited."""
    return await _review(db, current_user, draft_id, "reopen", None)


@router.delete("/homework/drafts/{draft_id}/items/{position}", response_model=SavedDraftOut)
async def remove_homework_draft_item(
    draft_id: str,
    position: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove one question from a draft in 'draft' status; positions and totals are updated."""
    record = await _load_draft_for(db, current_user, draft_id)
    try:
        removed = remove_item(record, position)
    except LookupError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No question at that position.")
    except InvalidEdit as exc:
        code = status.HTTP_409_CONFLICT if record.status != "draft" else 422
        raise HTTPException(status_code=code, detail=str(exc))

    try:
        await db.flush()  # delete the removed item first
        stage_renumber(record)
        await db.flush()  # temporary positions, so final numbering can't collide
    except StaleDataError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=CHANGED_ELSEWHERE)
    renumber_and_recount(record, removed)
    db.add(_audit(current_user, "Homework Draft Edited",
                  f"Removed question {removed.source_question_id} from draft {record.id}."))
    await _commit_or_conflict(db)
    return to_out(record)


# --- Homework assignments ---------------------------------------------------------------


@router.post("/homework/drafts/{draft_id}/assign", response_model=AssignmentOut, status_code=201)
async def assign_homework_draft(
    draft_id: str,
    body: Optional[AssignRequest] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Issue an approved draft to its student. Creates the assignment and marks the draft
    'assigned' in one transaction. Student, school and teacher come from the server."""
    record = await _load_draft_for(db, current_user, draft_id)

    existing = (await db.execute(
        select(HomeworkAssignmentRecord.id).filter(HomeworkAssignmentRecord.draft_id == record.id)
    )).first()
    if existing is not None or record.status == "assigned":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This draft has already been assigned.")

    due_at = body.due_at if body else None
    if due_at is not None and due_at <= datetime.now(timezone.utc):
        raise HTTPException(status_code=422, detail="The due date must be in the future.")

    try:
        apply_review(record, "assign", current_user.id, None)
    except InvalidTransition:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Only approved drafts can be assigned; this one is {record.status}.",
        )

    assignment = build_assignment(record, current_user.id, due_at)
    db.add(assignment)
    db.add(_audit(current_user, "Homework Assigned",
                  f"Assigned draft {record.id} to student {record.student_id}."))
    try:
        await db.commit()
    except StaleDataError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=CHANGED_ELSEWHERE)
    except IntegrityError:
        await db.rollback()
        # Only a duplicate (another request assigned this draft first, hitting the unique
        # draft_id) is a 409. Any other integrity failure is a server fault: re-raise it.
        duplicate = (await db.execute(
            select(HomeworkAssignmentRecord.id).filter(HomeworkAssignmentRecord.draft_id == draft_id)
        )).first()
        if duplicate is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This draft has already been assigned.")
        raise
    return to_assignment_out(assignment)


@router.get("/homework/assignments", response_model=List[AssignmentSummaryOut])
async def list_homework_assignments(
    student_id: Optional[str] = None,
    subject_id: Optional[str] = None,
    assignment_status: Optional[AssignmentStatus] = Query(default=None, alias="status"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Assignments the user may see, filtered in the database query."""
    if not role_may_generate_homework(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    query = (
        select(HomeworkAssignmentRecord)
        .join(HomeworkDraftRecord, HomeworkAssignmentRecord.draft_id == HomeworkDraftRecord.id)
        # Summaries need draft totals but not the questions: skip loading items (and fail loudly
        # if anything tries to read them).
        .options(selectinload(HomeworkAssignmentRecord.draft).raiseload(HomeworkDraftRecord.items))
    )
    if current_user.role != "admin":
        schools = await _accessible_school_ids(db, current_user)
        query = query.filter(HomeworkAssignmentRecord.school_id.in_(schools))
        if current_user.role == "teacher":
            query = query.filter(HomeworkDraftRecord.created_by == current_user.id)
    if student_id:
        query = query.filter(HomeworkAssignmentRecord.student_id == student_id)
    if subject_id:
        query = query.filter(HomeworkAssignmentRecord.subject_id == subject_id)
    if assignment_status:
        query = query.filter(HomeworkAssignmentRecord.status == assignment_status)

    rows = await db.execute(
        query.order_by(HomeworkAssignmentRecord.assigned_at.desc(), HomeworkAssignmentRecord.id)
    )
    return [to_assignment_summary(a) for a in rows.scalars().all()]


@router.get("/homework/assignments/{assignment_id}", response_model=AssignmentOut)
async def get_homework_assignment(
    assignment_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not role_may_generate_homework(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")
    assignment = (await db.execute(
        select(HomeworkAssignmentRecord).filter(HomeworkAssignmentRecord.id == assignment_id)
    )).scalars().first()
    if assignment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found.")
    if not await can_access_assignment(db, current_user, assignment):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")
    return to_assignment_out(assignment)


# --- Student account links (admin only) ---------------------------------------------------


def _require_admin(user: User) -> None:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")


@router.post("/student-account-links", response_model=StudentAccountLinkOut, status_code=201)
async def create_student_account_link(
    body: StudentAccountLinkCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Link a student login to a Student record, one to one. Admin only; nothing is inferred."""
    _require_admin(current_user)

    account = (await db.execute(select(User).filter(User.id == body.user_id))).scalars().first()
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    if account.role != "student":
        raise HTTPException(status_code=422, detail="Only accounts with the 'student' role can be linked.")
    student = (await db.execute(select(Student).filter(Student.id == body.student_id))).scalars().first()
    if student is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found.")
    if not account.school_id or account.school_id != student.school_id:
        raise HTTPException(status_code=422, detail="The account and the student belong to different schools.")

    existing = (await db.execute(
        select(StudentAccountLink.id).filter(
            (StudentAccountLink.user_id == body.user_id) | (StudentAccountLink.student_id == body.student_id)
        )
    )).first()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="This account or this student is already linked.")

    link = StudentAccountLink(user_id=account.id, student_id=student.id, created_by=current_user.id)
    db.add(link)
    db.add(_audit(current_user, "Student Account Linked", f"Linked account {account.id} to student {student.id}."))
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        clash = (await db.execute(
            select(StudentAccountLink.id).filter(
                (StudentAccountLink.user_id == body.user_id) | (StudentAccountLink.student_id == body.student_id)
            )
        )).first()
        if clash is not None:  # another request linked one of them first
            raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                detail="This account or this student is already linked.")
        raise
    return StudentAccountLinkOut(id=link.id, user_id=link.user_id, student_id=link.student_id,
                                 created_by=link.created_by, created_at=as_utc(link.created_at))


@router.get("/student-account-links", response_model=List[StudentAccountLinkListItemOut])
async def list_student_account_links(
    user_id: Optional[str] = Query(default=None, min_length=1),
    student_id: Optional[str] = Query(default=None, min_length=1),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List links, newest first, optionally filtered. Admin only. Each link says whether its
    User and Student still exist, so stale links can be found and removed with DELETE."""
    _require_admin(current_user)
    query = (
        select(StudentAccountLink, User.id.is_not(None), Student.id.is_not(None))
        .outerjoin(User, User.id == StudentAccountLink.user_id)
        .outerjoin(Student, Student.id == StudentAccountLink.student_id)
    )
    if user_id is not None:
        query = query.filter(StudentAccountLink.user_id == user_id)
    if student_id is not None:
        query = query.filter(StudentAccountLink.student_id == student_id)
    rows = (await db.execute(
        query.order_by(StudentAccountLink.created_at.desc(), StudentAccountLink.id)
    )).all()
    return [
        StudentAccountLinkListItemOut(
            id=link.id, user_id=link.user_id, student_id=link.student_id, created_by=link.created_by,
            created_at=as_utc(link.created_at), user_exists=bool(user_ok), student_exists=bool(student_ok),
            is_stale=not (user_ok and student_ok),
        )
        for link, user_ok, student_ok in rows
    ]


@router.delete("/student-account-links/{link_id}", status_code=204)
async def delete_student_account_link(
    link_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove a link, for example after a mistake. The student account loses homework access."""
    _require_admin(current_user)
    link = (await db.execute(select(StudentAccountLink).filter(StudentAccountLink.id == link_id))).scalars().first()
    if link is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link not found.")
    await db.delete(link)
    db.add(_audit(current_user, "Student Account Unlinked",
                  f"Unlinked account {link.user_id} from student {link.student_id}."))
    await db.commit()
    return Response(status_code=204)


# --- Student-facing homework ----------------------------------------------------------------

NOT_LINKED = "This account isn't linked to a student record."


async def _current_student(db: AsyncSession, user: User) -> Student:
    """The Student linked to this login. Fails closed: wrong role, no link, or a school
    mismatch all give 403. The student is never taken from the request."""
    if user.role != "student":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")
    student = await resolve_linked_student(db, user)
    if student is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=NOT_LINKED)
    return student


@router.get("/students/me/homework/assignments", response_model=List[StudentAssignmentSummaryOut])
async def list_my_homework_assignments(
    assignment_status: Optional[AssignmentStatus] = Query(default=None, alias="status"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """The logged-in student's own assignments, newest first."""
    student = await _current_student(db, current_user)
    query = (
        select(HomeworkAssignmentRecord)
        .filter(HomeworkAssignmentRecord.student_id == student.id)
        .options(selectinload(HomeworkAssignmentRecord.draft).raiseload(HomeworkDraftRecord.items))
    )
    if assignment_status:
        query = query.filter(HomeworkAssignmentRecord.status == assignment_status)
    rows = (await db.execute(
        query.order_by(HomeworkAssignmentRecord.assigned_at.desc(), HomeworkAssignmentRecord.id)
    )).scalars().all()
    names = await subject_names(db, (a.subject_id for a in rows))
    return [to_student_summary(a, names) for a in rows]


@router.get("/students/me/homework/assignments/{assignment_id}", response_model=StudentAssignmentOut)
async def get_my_homework_assignment(
    assignment_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """One of the student's own assignments, with questions. Anyone else's assignment returns
    404, the same as a missing one, so a student can't tell whether another assignment exists."""
    student = await _current_student(db, current_user)
    assignment = (await db.execute(
        select(HomeworkAssignmentRecord).filter(
            HomeworkAssignmentRecord.id == assignment_id,
            HomeworkAssignmentRecord.student_id == student.id,
        )
    )).scalars().first()
    if assignment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found.")
    names = await subject_names(db, [assignment.subject_id])
    return to_student_detail(assignment, names)


# --- Student answer submissions -----------------------------------------------------------------

SUBMISSION_PATH = "/students/me/homework/assignments/{assignment_id}/submission"
SUBMISSION_CHANGED = "This submission was changed by another request. Reload it and try again."
SUBMISSION_STARTED = "A submission was started by another request. Reload it and try again."
SUBMISSION_FAULT = "This submission can't be processed because of a server-side data problem."


async def _my_assignment(db: AsyncSession, user: User, assignment_id: str) -> HomeworkAssignmentRecord:
    """The logged-in student's own assignment. Loaded by its ID and the linked student's ID,
    so another student's assignment gives 404, the same as a missing one."""
    student = await _current_student(db, user)
    assignment = (await db.execute(
        select(HomeworkAssignmentRecord).filter(
            HomeworkAssignmentRecord.id == assignment_id,
            HomeworkAssignmentRecord.student_id == student.id,
        )
    )).scalars().first()
    if assignment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found.")
    return assignment


async def _load_submission(db: AsyncSession, assignment_id: str) -> Optional[HomeworkSubmissionRecord]:
    """The assignment's submission, if any. Only ever called with an assignment already
    checked to belong to the student."""
    return (await db.execute(
        select(HomeworkSubmissionRecord).filter(HomeworkSubmissionRecord.assignment_id == assignment_id)
    )).scalars().first()


def _submission_error(exc: Exception) -> HTTPException:
    """Map a submission-service error to HTTP. Order matters: SubmissionMismatch is a
    NotSubmittable, but it's a server-side fault (500), not a client conflict."""
    if isinstance(exc, SubmissionMismatch):
        logger.error("Inconsistent homework submission data: %s", exc)
        return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=SUBMISSION_FAULT)
    if isinstance(exc, InvalidAnswers):
        return HTTPException(status_code=422, detail=[
            AnswerProblemOut(position=p.position, reason=p.reason).model_dump() for p in exc.problems
        ])
    if isinstance(exc, (SubmissionLocked, VersionConflict, NotSubmittable)):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    raise exc


# How the "one submission per assignment" violation appears in the driver's message: the
# constraint name on PostgreSQL, the column on SQLite (which doesn't report constraint names).
DUPLICATE_SUBMISSION_MARKERS = ("uq_homework_submissions_assignment", "homework_submissions.assignment_id")


def _is_duplicate_submission(exc: IntegrityError) -> bool:
    message = str(getattr(exc, "orig", exc))
    return any(marker in message for marker in DUPLICATE_SUBMISSION_MARKERS)


async def _commit_submission(db: AsyncSession, assignment_id: str, created: bool) -> None:
    """One commit for the whole request (answers, lock and audit together). On failure the
    transaction is rolled back, so nothing is half-written.
    - StaleDataError: another request changed the submission since it was read -> 409.
    - IntegrityError: 409 only when this request created the submission, the error is the
      unique assignment_id rule, and another request's submission now exists. Any other
      integrity error is a real fault and is re-raised (500)."""
    try:
        await db.commit()
    except StaleDataError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=SUBMISSION_CHANGED)
    except IntegrityError as exc:
        await db.rollback()
        if created and _is_duplicate_submission(exc):
            winner = (await db.execute(
                select(HomeworkSubmissionRecord.id).filter(HomeworkSubmissionRecord.assignment_id == assignment_id)
            )).first()
            if winner is not None:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=SUBMISSION_STARTED)
        raise


def _render(submission: HomeworkSubmissionRecord, assignment: HomeworkAssignmentRecord) -> HomeworkSubmissionOut:
    try:
        return to_submission_out(submission, assignment)
    except SubmissionMismatch as exc:
        raise _submission_error(exc)


def _check_stored_submission(submission: Optional[HomeworkSubmissionRecord],
                             assignment: HomeworkAssignmentRecord) -> None:
    """Before changing anything: refuse (500) if the stored submission is inconsistent, so a
    request on corrupted data writes nothing instead of committing and then failing."""
    if submission is not None:
        _render(submission, assignment)


@router.get(SUBMISSION_PATH, response_model=HomeworkSubmissionOut)
async def get_my_submission(
    assignment_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """The student's answers to their own assignment. Before the first save this returns the
    not_started state and creates nothing."""
    assignment = await _my_assignment(db, current_user, assignment_id)
    submission = await _load_submission(db, assignment.id)
    if submission is None:
        return empty_submission_out(assignment)
    return _render(submission, assignment)


@router.put(SUBMISSION_PATH, response_model=HomeworkSubmissionOut,
            responses={201: {"model": HomeworkSubmissionOut, "description": "First save: submission created"}})
async def save_my_answers(
    assignment_id: str,
    body: SubmissionAnswersUpdate,
    response: Response,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Save some answers (a partial update). 201 when this creates the submission, 200 after.
    Allowed after the due time; lateness is decided only at final submit."""
    assignment = await _my_assignment(db, current_user, assignment_id)
    existing = await _load_submission(db, assignment.id)
    _check_stored_submission(existing, assignment)
    try:
        submission = save_answers(assignment, existing, body, utc_now())
    except Exception as exc:
        raise _submission_error(exc)
    created = existing is None
    if created:
        db.add(submission)
    await _commit_submission(db, assignment.id, created)
    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    return _render(submission, assignment)


@router.post(f"{SUBMISSION_PATH}/submit", response_model=HomeworkSubmissionOut)
async def submit_my_answers(
    assignment_id: str,
    body: SubmissionFinalizeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Final submit: locks the answers for good. Blank and partial submissions are allowed.
    Late only when strictly after the due time. The audit event is saved in the same
    transaction as the lock."""
    assignment = await _my_assignment(db, current_user, assignment_id)
    existing = await _load_submission(db, assignment.id)
    _check_stored_submission(existing, assignment)
    try:
        submission = finalize_submission(assignment, existing, body, utc_now())
    except Exception as exc:
        raise _submission_error(exc)
    created = existing is None
    if created:
        db.add(submission)
    db.add(_audit(current_user, "Homework Submitted",
                  f"Submitted assignment {assignment.id}{' (late)' if submission.is_late else ''}."))
    await _commit_submission(db, assignment.id, created)
    return _render(submission, assignment)

