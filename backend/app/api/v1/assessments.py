import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.dependencies import get_current_user, require_roles
from backend.app.core.config import settings
from backend.app.db.session import get_db
from backend.app.models.entities import (
    Assessment,
    AssessmentSubmission,
    AssignmentOcrUpload,
    ClassSection,
    QuestionBankItem,
    Document,
    Student,
    StudentOcrHistory,
    StudentCompetencySnapshot,
    Subject,
    User,
    AuditEvent,
    Notification,
    utc_now,
)
from backend.app.schemas.assessments import (
    AssessmentCreate,
    AssessmentOut,
    AssignmentTarget,
    UploadAssignment,
    SubmissionCreate,
    SubmissionOut,
    GenerateQuestionsRequest,
    QuestionUpdateRequest,
)
from backend.app.services.llm_service import (
    QwenQuestionStudioInferenceError,
    QwenQuestionStudioInputError,
    QwenQuestionStudioUnavailable,
    qwen_question_studio,
)
from backend.app.services.progress import report_progress, stream_job
from backend.app.services.web_source import WebSourceError, fetch_web_source, normalize_urls
from backend.app.services.assessment_audience import upload_assignments, validate_assignment_target
from backend.app.services.storage_service import storage_service

router = APIRouter(tags=["Assessments"])
logger = logging.getLogger(__name__)


@router.get("/assessments", response_model=List[AssessmentOut])
async def list_all_assessments(
    class_id: Optional[str] = None,
    school_id: Optional[str] = None,
    subject_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "principal", "teacher", authenticated=True)),
):
    query = select(Assessment)
    if current_user.role != "admin":
        query = query.where(Assessment.school_id == current_user.school_id)
    if class_id:
        query = query.filter(Assessment.class_id == class_id)
    if school_id:
        query = query.filter(Assessment.school_id == school_id)
    if subject_id:
        query = query.filter(Assessment.subject_id == subject_id)
    res = await db.execute(query.order_by(Assessment.cycle_number))
    return res.scalars().all()


@router.get("/classes/{class_id}/assessments", response_model=List[AssessmentOut])
async def list_class_assessments(
    class_id: str,
    subject_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "principal", "teacher", authenticated=True)),
):
    query = select(Assessment).filter(Assessment.class_id == class_id)
    if current_user.role != "admin":
        query = query.where(Assessment.school_id == current_user.school_id)
    if subject_id:
        query = query.filter(Assessment.subject_id == subject_id)
    res = await db.execute(query.order_by(Assessment.cycle_number))
    return res.scalars().all()


@router.get("/assessments/targets", response_model=List[AssignmentTarget])
async def get_assignment_targets(
    db: AsyncSession = Depends(get_db),
    educator: User = Depends(require_roles("admin", "principal", "teacher", authenticated=True)),
):
    sections = (await db.scalars(
        select(ClassSection).where(ClassSection.school_id == educator.school_id).order_by(ClassSection.name)
    )).all()
    subject_ids = {subject_id for section in sections for subject_id in section.subject_ids_json}
    subjects = {subject.id: subject.name for subject in (await db.scalars(
        select(Subject).where(Subject.id.in_(subject_ids))
    )).all()}
    return [
        {"id": section.id, "name": section.name, "subjects": [
            {"id": subject_id, "name": subjects[subject_id]}
            for subject_id in section.subject_ids_json if subject_id in subjects
        ]}
        for section in sections
    ]


@router.get("/assessments/upload-assignments", response_model=List[UploadAssignment])
async def list_upload_assignments(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("teacher", "student", authenticated=True)),
):
    student, rows = await upload_assignments(db, current_user)
    uploaded = set()
    if student and rows:
        uploaded = set((await db.scalars(
            select(AssignmentOcrUpload.assessment_id)
            .join(StudentOcrHistory, StudentOcrHistory.id == AssignmentOcrUpload.history_id)
            .where(
                StudentOcrHistory.student_id == student.id,
                AssignmentOcrUpload.assessment_id.in_([assessment.id for assessment, _, _ in rows]),
            )
            .distinct()
        )).all())
    return [
        UploadAssignment(
            id=assessment.id, title=assessment.title, date=assessment.date,
            class_name=section.name, subject_name=subject.name, total_marks=assessment.total_marks,
            uploaded=assessment.id in uploaded, questions=assessment.questions_json,
        )
        for assessment, section, subject in rows
    ]


@router.post("/classes/{class_id}/assessments", response_model=AssessmentOut, status_code=status.HTTP_201_CREATED)
async def create_assessment(
    class_id: str,
    req: AssessmentCreate,
    db: AsyncSession = Depends(get_db),
    educator: User = Depends(require_roles("admin", "principal", "teacher", authenticated=True)),
):
    if req.class_id is not None and req.class_id != class_id:
        raise HTTPException(status_code=422, detail="The requested class does not match the target class.")
    section = await validate_assignment_target(db, educator.school_id, class_id, req.subject_id)
    asm = Assessment(
        school_id=section.school_id,
        class_id=class_id,
        subject_id=req.subject_id,
        title=req.title,
        cycle_number=req.cycle_number,
        date=req.date,
        duration_minutes=req.duration_minutes,
        total_marks=req.total_marks,
        status="scheduled",
        competency_focus_json=req.competency_focus,
        questions_json=[q.model_dump() for q in req.questions]
    )
    db.add(asm)

    audit = AuditEvent(
        timestamp=utc_now().strftime("%Y-%m-%d %H:%M"),
        user_id=educator.id,
        user_name=educator.name,
        action="Created Assessment Cycle",
        details=f"Created assessment: '{asm.title}' (Cycle {asm.cycle_number})",
        category="assessment"
    )
    db.add(audit)
    await db.commit()
    await db.refresh(asm)
    return asm


def _serialize_qb_item(item: QuestionBankItem) -> Dict[str, Any]:
    return {
        "id": item.id,
        "subject_id": item.subject_id,
        "text": item.text,
        "type": item.type,
        "options": item.options_json or [],
        "correct_answer": item.correct_answer,
        "marking_rubric": item.marking_rubric or item.correct_answer,
        "marks": item.marks,
        "competency": item.competency,
        "bloom_level": item.bloom_level,
        "source_document_ids": item.source_document_ids_json or [],
        "source_document_names": item.source_document_names_json or [],
        "is_ai_generated": item.is_ai_generated,
    }


@router.get("/assessments/question-bank")
async def get_question_bank(
    subject_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    educator: User = Depends(require_roles("admin", "principal", "teacher", authenticated=True)),
):
    query = select(QuestionBankItem)
    if educator.role != "admin":
        query = query.where(QuestionBankItem.school_id == educator.school_id)
    if subject_id:
        query = query.filter(QuestionBankItem.subject_id == subject_id)
    res = await db.execute(query.order_by(QuestionBankItem.created_at.desc()))
    items = list(res.scalars().all())
    if items:
        return [_serialize_qb_item(it) for it in items]

    # Fallback default items if table is empty
    return [
        {
            "id": "q-1",
            "subject_id": "sub-math",
            "text": "A water tank is in the shape of a cuboid with length 4m, breadth 3m, and depth 2m. If water is poured at the rate of 60 liters per minute, how many hours will it take to fill the tank completely? (1 m3 = 1000 liters)",
            "type": "practical",
            "options": [],
            "marks": 4,
            "competency": "AU",
            "bloom_level": "Apply",
            "correct_answer": "Volume = 24 m3 = 24,000 Liters. Time = 24000/60 = 400 mins = 6 hours and 40 minutes.",
            "marking_rubric": "1m for cuboid volume; 1m for Liter conversion; 1m for division; 1m for hours/mins.",
            "source_document_ids": ["doc-src-math-1"],
            "source_document_names": ["NCERT_Grade8_Maths_Ch11_Mensuration_&_Volumes.pdf"],
            "is_ai_generated": False,
        }
    ]


@router.post("/assessments/generate-questions-beta")
async def generate_questions_beta(
    req: GenerateQuestionsRequest,
    db: AsyncSession = Depends(get_db),
    educator: User = Depends(require_roles("admin", "principal", "teacher")),
):
    if (
        not 0 <= req.mcq_count <= 15
        or not 0 <= req.theory_count <= 10
        or req.mcq_count + req.theory_count == 0
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Request 1–15 MCQs and 0–10 theory questions, with at least one question.",
        )
    if req.bloom_level not in {"Remember", "Understand", "Apply", "Analyze", "Evaluate", "Create"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid Bloom's Taxonomy level.")

    document_ids = list(dict.fromkeys(req.source_document_ids))
    if len(document_ids) > 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Use one chapter PDF per generation.")
    try:
        source_urls = normalize_urls(req.source_urls)
    except WebSourceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if not document_ids and not source_urls:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Upload a chapter PDF or paste a learning-resource link to generate questions.",
        )

    document = None
    if document_ids:
        doc_result = await db.execute(
            select(Document).filter(
                Document.id == document_ids[0],
                Document.school_id == (educator.school_id or "school-1"),
            )
        )
        document = doc_result.scalars().first()
        if not document:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Uploaded PDF not found.")
        if document.mime_type != "application/pdf" or not document.file_name.lower().endswith(".pdf"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only PDF source documents are supported.")

    web_sources = []
    for index, url in enumerate(source_urls, start=1):
        report_progress("links", f"Reading link {index} of {len(source_urls)}", index - 1, len(source_urls))
        try:
            web_sources.append(await fetch_web_source(url))
        except WebSourceError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
        report_progress("links", f"Read link {index} of {len(source_urls)}", index, len(source_urls))
    source_names = ([document.file_name] if document else []) + [source.url for source in web_sources]

    try:
        pdf_path = storage_service.get_file_path(document.storage_path) if document else None
        generated_items = await qwen_question_studio.generate_questions(
            pdf_path=pdf_path,
            subject_id=req.subject_id,
            subject_name=req.subject_name or req.subject_id,
            source_document_id=document.id if document else None,
            source_document_name=document.file_name if document else None,
            mcq_count=req.mcq_count,
            theory_count=req.theory_count,
            bloom_level=req.bloom_level,
            focus_topic=req.focus_topic,
            web_sources=web_sources,
        )
    except QwenQuestionStudioInputError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except QwenQuestionStudioUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except (QwenQuestionStudioInferenceError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc) or "Qwen returned invalid question data.",
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("AI Question Studio Beta generation failed.")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Question generation failed. Check backend logs.",
        ) from exc

    saved_out = []
    for item in generated_items:
        qb_item = QuestionBankItem(
            id=item["id"],
            school_id=educator.school_id or "school-1",
            subject_id=req.subject_id,
            text=item["text"],
            type=item["type"],
            options_json=item["options"],
            correct_answer=item["correct_answer"],
            marking_rubric=item["marking_rubric"],
            marks=item["marks"],
            competency=item["competency"],
            bloom_level=req.bloom_level,
            source_document_ids_json=[document.id] if document else [],
            source_document_names_json=source_names,
            is_ai_generated=True,
            created_by=educator.id,
        )
        if req.save_to_bank:
            db.add(qb_item)
        saved_out.append(_serialize_qb_item(qb_item))

    db.add(
        AuditEvent(
            timestamp=utc_now().strftime("%Y-%m-%d %H:%M"),
            user_id=educator.id,
            user_name=educator.name,
            action="AI Question Studio Beta Generated Questions",
            details=(
                f"Generated {req.mcq_count} MCQs and {req.theory_count} Theory items "
                f"(Bloom: {req.bloom_level}) from {', '.join(source_names)} using "
                f"{settings.QWEN_VL_MODEL_ID}."
            ),
            category="assessment",
        )
    )
    await db.commit()
    report_progress("save", f"Saved {len(saved_out)} questions", len(saved_out), len(saved_out))
    return {
        "generated_count": len(saved_out),
        "subject_id": req.subject_id,
        "bloom_level": req.bloom_level,
        "source_documents_used": source_names,
        "model": settings.QWEN_VL_MODEL_ID,
        "questions": saved_out,
    }


@router.post("/assessments/generate-questions-beta/stream")
async def stream_generate_questions_beta(
    req: GenerateQuestionsRequest,
    db: AsyncSession = Depends(get_db),
    educator: User = Depends(require_roles("admin", "principal", "teacher")),
):
    return stream_job(lambda: generate_questions_beta(req, db, educator))


@router.put("/assessments/questions/{question_id}")
async def update_question_endpoint(
    question_id: str,
    req: QuestionUpdateRequest,
    db: AsyncSession = Depends(get_db),
    educator: User = Depends(require_roles("admin", "principal", "teacher")),
):
    res = await db.execute(select(QuestionBankItem).filter(QuestionBankItem.id == question_id))
    item = res.scalars().first()
    if not item:
        raise HTTPException(status_code=404, detail="Question not found in bank.")

    if req.text is not None:
        item.text = req.text
    if req.type is not None:
        item.type = req.type
    if req.options is not None:
        item.options_json = req.options
    if req.correct_answer is not None:
        item.correct_answer = req.correct_answer
    if req.marking_rubric is not None:
        item.marking_rubric = req.marking_rubric
    if req.marks is not None:
        item.marks = req.marks
    if req.competency is not None:
        item.competency = req.competency
    if req.bloom_level is not None:
        item.bloom_level = req.bloom_level

    await db.commit()
    await db.refresh(item)
    return _serialize_qb_item(item)


@router.delete("/assessments/questions/{question_id}")
async def delete_question_endpoint(
    question_id: str,
    db: AsyncSession = Depends(get_db),
    educator: User = Depends(require_roles("admin", "principal", "teacher")),
):
    res = await db.execute(select(QuestionBankItem).filter(QuestionBankItem.id == question_id))
    item = res.scalars().first()
    if item:
        await db.delete(item)
        await db.commit()
    return {"status": "deleted", "id": question_id}



@router.post("/assessments/{assessment_id}/submissions", response_model=SubmissionOut)
async def submit_assessment_grade(
    assessment_id: str,
    req: SubmissionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    asm_res = await db.execute(select(Assessment).filter(Assessment.id == assessment_id))
    asm = asm_res.scalars().first()
    if not asm:
        raise HTTPException(status_code=404, detail="Assessment not found.")

    st_res = await db.execute(select(Student).filter(Student.id == req.student_id))
    student = st_res.scalars().first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found.")

    # Authorization guard: students can only submit for themselves
    if current_user.role == "student" and current_user.id != req.student_id:
        raise HTTPException(status_code=403, detail="Students cannot submit grades for other students.")

    percentage = round((req.marks_obtained / max(1, req.total_marks)) * 100)
    overall_comp = round((req.lu_score + req.cu_score + req.au_score + req.ct_score) / 4)

    sub = AssessmentSubmission(
        assessment_id=assessment_id,
        student_id=student.id,
        student_name=student.name,
        marks_obtained=req.marks_obtained,
        total_marks=req.total_marks,
        percentage=percentage,
        lu_score=req.lu_score,
        cu_score=req.cu_score,
        au_score=req.au_score,
        ct_score=req.ct_score,
        overall_score=overall_comp,
        feedback=req.feedback,
        submission_date=utc_now().strftime("%Y-%m-%d"),
        is_scanned=req.is_scanned
    )
    db.add(sub)

    # Recalibrate student's live competencies
    student.lu_score = req.lu_score
    student.cu_score = req.cu_score
    student.au_score = req.au_score
    student.ct_score = req.ct_score
    student.overall_score = overall_comp
    student.needs_support = percentage < 65

    # Record historical snapshot
    snapshot = StudentCompetencySnapshot(
        student_id=student.id,
        cycle_number=asm.cycle_number,
        lu_score=req.lu_score,
        cu_score=req.cu_score,
        au_score=req.au_score,
        ct_score=req.ct_score,
        overall_score=overall_comp,
        notes=f"Graded submission for assessment: {asm.title}"
    )
    db.add(snapshot)

    audit = AuditEvent(
        timestamp=utc_now().strftime("%Y-%m-%d %H:%M"),
        user_id=current_user.id,
        user_name=current_user.name,
        action="Graded Assessment Submission",
        details=f"Recorded {percentage}% for {student.name} in '{asm.title}'. Recalibrated baseline.",
        category="assessment"
    )
    db.add(audit)
    await db.commit()
    await db.refresh(sub)

    return SubmissionOut(
        id=sub.id,
        assessment_id=sub.assessment_id,
        student_id=sub.student_id,
        student_name=sub.student_name,
        marks_obtained=sub.marks_obtained,
        total_marks=sub.total_marks,
        percentage=sub.percentage,
        scores={
            "LU": sub.lu_score,
            "CU": sub.cu_score,
            "AU": sub.au_score,
            "CT": sub.ct_score,
            "overall": sub.overall_score
        },
        feedback=sub.feedback,
        submission_date=sub.submission_date,
        is_scanned=sub.is_scanned
    )


@router.get("/assessments/{assessment_id}/submissions", response_model=List[SubmissionOut])
async def list_assessment_submissions(
    assessment_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = select(AssessmentSubmission).filter(AssessmentSubmission.assessment_id == assessment_id)
    if current_user.role == "student":
        query = query.filter(AssessmentSubmission.student_id == current_user.id)

    res = await db.execute(query)
    subs = res.scalars().all()
    return [
        SubmissionOut(
            id=s.id,
            assessment_id=s.assessment_id,
            student_id=s.student_id,
            student_name=s.student_name,
            marks_obtained=s.marks_obtained,
            total_marks=s.total_marks,
            percentage=s.percentage,
            scores={"LU": s.lu_score, "CU": s.cu_score, "AU": s.au_score, "CT": s.ct_score, "overall": s.overall_score},
            feedback=s.feedback,
            submission_date=s.submission_date,
            is_scanned=s.is_scanned
        ) for s in subs
    ]
