import asyncio
import logging
import os
from pathlib import Path
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from backend.app.api.dependencies import get_current_user, require_roles
from backend.app.core.config import settings
from backend.app.db.session import get_db
from backend.app.models.entities import (
    Document,
    OCRRun,
    HumanReview,
    GradingBatch,
    GradingBatchItem,
    Assessment,
    AssignmentOcrUpload,
    AssessmentSubmission,
    Student,
    StudentOcrHistory,
    StudentCompetencySnapshot,
    DatasetExample,
    User,
    AuditEvent,
    utc_now,
)
from backend.app.schemas.ocr import (
    OCRRunOut,
    OCRPreviewOut,
    StudentOcrHistoryOut,
    OCRAnswerRegion,
    HumanReviewRequest,
    HumanReviewOut,
    BatchItemOut,
    GradingBatchOut,
    BatchItemUpdateRequest,
)
from backend.app.services.ocr_service import (
    QwenOCRInferenceError,
    QwenOCRInputError,
    QwenOCRUnavailableError,
    get_ocr_provider,
)
from backend.app.services.progress import report_progress, stream_job
from backend.app.services.assessment_audience import upload_assignments
from backend.app.modules.differentiated_homework.student_access import require_linked_student
from backend.app.services.storage_service import storage_service
from backend.app.services.batch_grading_service import (
    match_student_from_filename_or_text,
    run_grading_batch_job,
    process_single_batch_item,
    recalculate_batch_counters,
    cancel_batch_job,
    compute_letter_grade,
)

router = APIRouter(prefix="/ocr", tags=["OCR & Human Review"])
logger = logging.getLogger(__name__)

OCR_PREVIEW_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf"}
OCR_PREVIEW_MIME_TYPES = {"image/jpeg", "image/jpg", "image/png", "application/pdf"}


class ProcessOCRRequest(BaseModel):
    document_id: str
    provider: str = "simulated"


@router.get("/history", response_model=List[StudentOcrHistoryOut])
async def get_student_ocr_history(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("student", authenticated=True)),
):
    student = await require_linked_student(db, current_user)
    result = await db.execute(
        select(StudentOcrHistory, Assessment.title)
        .outerjoin(AssignmentOcrUpload, AssignmentOcrUpload.history_id == StudentOcrHistory.id)
        .outerjoin(Assessment, Assessment.id == AssignmentOcrUpload.assessment_id)
        .where(StudentOcrHistory.student_id == student.id)
        .order_by(StudentOcrHistory.created_at.desc(), StudentOcrHistory.id.desc())
    )
    return [
        StudentOcrHistoryOut.model_validate(entry).model_copy(update={"assignment_title": title})
        for entry, title in result
    ]


@router.post("/extract-preview", response_model=OCRPreviewOut)
async def extract_ocr_preview(
    files: List[UploadFile] = File(...),
    wait_before_each_image: bool = Form(False),
    current_user: User = Depends(require_roles("admin", "principal", "teacher", "student")),
    db: AsyncSession = Depends(get_db),
    assessment_id: str | None = Form(None),
):
    if not files:
        raise HTTPException(status_code=400, detail="Please select at least one image or PDF.")
    if len(files) > 50:
        raise HTTPException(status_code=400, detail="Maximum upload size is 50 files at a time.")

    student_id = None
    if assessment_id is not None:
        student, _ = await upload_assignments(db, current_user, assessment_id)
        student_id = student.id if student else None
        await db.rollback()
    elif current_user.role == "student":
        student_id = (await require_linked_student(db, current_user)).id
        # Release the read transaction while the model processes the upload.
        await db.rollback()

    provider = get_ocr_provider("qwen")
    results = []
    total_files = len(files)
    for index, file in enumerate(files, start=1):
        report_progress(
            "file",
            f"Opening {file.filename or 'file'} ({index} of {total_files})",
            index - 1,
            total_files,
        )
        extension = os.path.splitext((file.filename or "").lower())[1]
        if (
            extension not in OCR_PREVIEW_EXTENSIONS
            and (file.content_type or "").lower() not in OCR_PREVIEW_MIME_TYPES
        ):
            raise HTTPException(
                status_code=415,
                detail=f"Unsupported OCR file '{file.filename}'. Upload JPG, PNG, or PDF.",
            )

        detail = await storage_service.save_upload_detailed(file)
        if not detail["valid"]:
            raise HTTPException(status_code=400, detail=detail["error"])

        try:
            if detail["mime_type"] not in OCR_PREVIEW_MIME_TYPES:
                raise HTTPException(
                    status_code=415,
                    detail=f"Unsupported OCR file '{detail['file_name']}'. Upload JPG, PNG, or PDF.",
                )

            extraction = await provider.extract_document(
                detail["storage_path"],
                {
                    "buffer_seconds": 5 if wait_before_each_image else 0,
                    "file_name": detail["file_name"],
                },
            )
            results.append(
                {
                    "file_name": detail["file_name"],
                    "extracted_text": extraction["extracted_text"],
                    "pages_processed": extraction["pages_processed"],
                }
            )
            report_progress(
                "file",
                f"Finished {detail['file_name']} ({index} of {total_files})",
                index,
                total_files,
            )
        except QwenOCRUnavailableError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except QwenOCRInputError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except QwenOCRInferenceError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        except HTTPException:
            raise
        except Exception as exc:
            # An unhandled error would bypass CORS and reach the browser as "Failed to fetch".
            logger.exception("OCR preview failed for %s", detail["file_name"])
            raise HTTPException(
                status_code=500,
                detail=f"OCR failed for '{detail['file_name']}'; check backend logs.",
            ) from exc
        finally:
            Path(detail["storage_path"]).unlink(missing_ok=True)

    if student_id:
        history = [StudentOcrHistory(student_id=student_id, **item) for item in results]
        db.add_all(history)
        if assessment_id is not None:
            await db.flush()
            db.add_all(
                AssignmentOcrUpload(history_id=entry.id, assessment_id=assessment_id) for entry in history
            )
        await db.commit()

    return {
        "provider": "qwen2.5-vl",
        "model_version": settings.QWEN_VL_MODEL_ID,
        "results": results,
    }


@router.post("/extract-preview/stream")
async def stream_extract_ocr_preview(
    files: List[UploadFile] = File(...),
    wait_before_each_image: bool = Form(False),
    current_user: User = Depends(require_roles("admin", "principal", "teacher", "student")),
    db: AsyncSession = Depends(get_db),
    assessment_id: str | None = Form(None),
):
    return stream_job(lambda: extract_ocr_preview(files, wait_before_each_image, current_user, db, assessment_id))


@router.post("/process", response_model=OCRRunOut)
async def process_ocr(
    req: ProcessOCRRequest,
    db: AsyncSession = Depends(get_db),
    educator: User = Depends(require_roles("admin", "principal", "teacher")),
):
    if req.provider == "qwen":
        raise HTTPException(
            status_code=400,
            detail="Qwen returns text only, without answer regions. Use POST /ocr/extract-preview.",
        )

    doc_res = await db.execute(select(Document).filter(Document.id == req.document_id))
    doc = doc_res.scalars().first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    provider = get_ocr_provider(req.provider)
    extraction = await provider.extract_document(doc.storage_path)

    ocr_run = OCRRun(
        document_id=doc.id,
        provider=extraction["provider"],
        model_version=extraction["model_version"],
        confidence_score=extraction["confidence_score"],
        extraction_json=extraction["regions"],
        status="completed",
    )
    db.add(ocr_run)
    await db.commit()
    await db.refresh(ocr_run)

    return OCRRunOut(
        id=ocr_run.id,
        document_id=ocr_run.document_id,
        provider=ocr_run.provider,
        model_version=ocr_run.model_version,
        confidence_score=ocr_run.confidence_score,
        status=ocr_run.status,
        regions=[OCRAnswerRegion(**r) for r in extraction["regions"]],
        created_at=ocr_run.created_at,
    )


@router.post("/review/verify", response_model=HumanReviewOut)
async def verify_human_review(
    req: HumanReviewRequest,
    db: AsyncSession = Depends(get_db),
    educator: User = Depends(require_roles("admin", "principal", "teacher")),
):
    st_res = await db.execute(select(Student).filter(Student.id == req.student_id))
    student = st_res.scalars().first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found.")

    ocr_res = await db.execute(
        select(OCRRun).filter(OCRRun.document_id == req.document_id).order_by(OCRRun.created_at.desc())
    )
    ocr_run = ocr_res.scalars().first()
    ocr_run_id = ocr_run.id if ocr_run else "ocr-fallback"

    total_marks_obtained = sum(item.marks for item in req.verified_items)
    max_marks = 14  # total benchmark for worksheet
    percentage = round((total_marks_obtained / max_marks) * 100)

    # Calculate dimension shifts
    new_lu = min(100, student.lu_score + 4)
    new_cu = min(100, student.cu_score + 5)
    new_au = min(100, student.au_score + 6)
    new_ct = min(100, student.ct_score + 3)
    new_overall = round((new_lu + new_cu + new_au + new_ct) / 4)

    review = HumanReview(
        ocr_run_id=ocr_run_id,
        reviewer_id=educator.id,
        student_id=student.id,
        assessment_id=req.assessment_id,
        verified_marks=total_marks_obtained,
        total_marks=max_marks,
        verified_data_json=[item.model_dump() for item in req.verified_items],
        teacher_notes=req.teacher_notes,
        status="approved",
    )
    db.add(review)

    # Save to assessment submission
    sub = AssessmentSubmission(
        assessment_id=req.assessment_id,
        student_id=student.id,
        student_name=student.name,
        marks_obtained=total_marks_obtained,
        total_marks=max_marks,
        percentage=percentage,
        lu_score=new_lu,
        cu_score=new_cu,
        au_score=new_au,
        ct_score=new_ct,
        overall_score=new_overall,
        feedback=f"Teacher verified optical worksheet. Final: {percentage}%.",
        submission_date=utc_now().strftime("%Y-%m-%d"),
        is_scanned=True,
    )
    db.add(sub)

    # Update student baseline
    student.lu_score = new_lu
    student.cu_score = new_cu
    student.au_score = new_au
    student.ct_score = new_ct
    student.overall_score = new_overall

    # Add verified sample to eligible training dataset
    for item in req.verified_items:
        dataset_ex = DatasetExample(
            dataset_version="v1.2",
            document_id=req.document_id,
            split_type="train",
            ground_truth_text=item.text,
            verified_by=educator.name,
            is_approved=True,
        )
        db.add(dataset_ex)

    audit = AuditEvent(
        timestamp=utc_now().strftime("%Y-%m-%d %H:%M"),
        user_id=educator.id,
        user_name=educator.name,
        action="Graded Offline Optical Scan Sheets",
        details=f"Verified transcription for {student.name}. Recalibrated baseline to {new_overall}%.",
        category="assessment",
    )
    db.add(audit)

    await db.commit()
    await db.refresh(review)

    return HumanReviewOut(
        id=review.id,
        ocr_run_id=review.ocr_run_id,
        reviewer_id=review.reviewer_id,
        student_id=review.student_id,
        assessment_id=review.assessment_id,
        verified_marks=review.verified_marks,
        total_marks=review.total_marks,
        status=review.status,
        reviewed_at=review.reviewed_at,
    )


# ==============================================================================
# AUTO-GRADE ENGINE: BULK ANSWER-SHEET UPLOAD & ASYNCHRONOUS BATCH PROCESSING
# ==============================================================================


async def _serialize_batch(db: AsyncSession, batch: GradingBatch) -> GradingBatchOut:
    items_res = await db.execute(
        select(GradingBatchItem)
        .filter(GradingBatchItem.batch_id == batch.id)
        .order_by(GradingBatchItem.created_at.asc())
    )
    items = list(items_res.scalars().all())
    valid_items = [i for i in items if i.status not in ("invalid", "duplicate")]
    if not valid_items:
        overall_pct = 0
    else:
        overall_pct = round(sum(i.stage_progress for i in valid_items) / len(valid_items))

    return GradingBatchOut(
        id=batch.id,
        school_id=batch.school_id,
        class_id=batch.class_id,
        subject_id=batch.subject_id,
        assessment_id=batch.assessment_id,
        created_by=batch.created_by,
        status=batch.status,
        total_files=batch.total_files,
        valid_files=batch.valid_files,
        invalid_or_duplicate_files=batch.invalid_or_duplicate_files,
        completed_files=batch.completed_files,
        review_required_files=batch.review_required_files,
        failed_files=batch.failed_files,
        concurrency_limit=batch.concurrency_limit,
        overall_progress_pct=overall_pct,
        items=[BatchItemOut.model_validate(it) for it in items],
        created_at=batch.created_at,
    )


@router.post("/batches", response_model=GradingBatchOut, status_code=status.HTTP_201_CREATED)
async def create_grading_batch(
    class_id: str = Form(...),
    subject_id: str = Form(...),
    assessment_id: str = Form(...),
    split_multi_pdf: bool = Form(False),
    concurrency_limit: int = Form(3),
    files: List[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
    educator: User = Depends(require_roles("admin", "principal", "teacher")),
):
    """
    Uploads single or multiple scanned student answer sheets into a GradingBatch.
    Validates each file independently, detects duplicates, optionally splits multi-student PDFs,
    and pre-identifies students for the Batch Configuration Review Screen.
    """
    if len(files) == 0:
        raise HTTPException(status_code=400, detail="Please select at least one answer sheet to upload.")
    if len(files) > 50:
        raise HTTPException(status_code=400, detail="Maximum batch size is 50 answer sheets per batch.")

    asm_res = await db.execute(select(Assessment).filter(Assessment.id == assessment_id))
    assessment = asm_res.scalars().first()
    if not assessment:
        raise HTTPException(status_code=404, detail="Selected Test / Assessment not found.")

    if not assessment.questions_json or len(assessment.questions_json) == 0:
        raise HTTPException(
            status_code=400,
            detail="Selected test has no questions or authoritative answer key configured.",
        )

    students_res = await db.execute(select(Student).filter(Student.class_id == class_id))
    students = list(students_res.scalars().all())

    batch_id = f"batch-{uuid.uuid4().hex[:12]}"
    batch = GradingBatch(
        id=batch_id,
        school_id=educator.school_id or assessment.school_id or "school-1",
        class_id=class_id,
        subject_id=subject_id,
        assessment_id=assessment_id,
        created_by=educator.id,
        status="configuring",
        concurrency_limit=max(1, min(concurrency_limit, 10)),
    )
    db.add(batch)
    await db.flush()

    seen_hashes = set()
    seen_filenames = set()
    valid_count = 0
    invalid_dup_count = 0
    total_items_created = 0

    for idx, file in enumerate(files):
        detail = await storage_service.save_upload_detailed(file)
        fname = detail["file_name"]

        if not detail["valid"]:
            invalid_dup_count += 1
            total_items_created += 1
            db.add(
                GradingBatchItem(
                    id=f"bitem-{uuid.uuid4().hex[:12]}",
                    batch_id=batch_id,
                    file_name=fname,
                    file_size=detail["file_size"],
                    mime_type=detail["mime_type"],
                    page_count=1,
                    status="invalid",
                    stage_progress=0,
                    error_message=detail["error"],
                    max_marks=assessment.total_marks,
                )
            )
            continue

        c_hash = detail["content_hash"]
        if c_hash in seen_hashes or fname.lower() in seen_filenames:
            invalid_dup_count += 1
            total_items_created += 1
            db.add(
                GradingBatchItem(
                    id=f"bitem-{uuid.uuid4().hex[:12]}",
                    batch_id=batch_id,
                    file_name=fname,
                    file_size=detail["file_size"],
                    mime_type=detail["mime_type"],
                    page_count=detail["page_count"],
                    content_hash=c_hash,
                    status="duplicate",
                    stage_progress=0,
                    error_message=f"Duplicate answer sheet '{fname}' detected in current batch.",
                    max_marks=assessment.total_marks,
                )
            )
            continue

        seen_hashes.add(c_hash)
        seen_filenames.add(fname.lower())

        # Save underlying Document record
        doc = Document(
            id=detail["file_id"],
            school_id=batch.school_id,
            uploader_id=educator.id,
            subject_id=subject_id,
            doc_type="answer_sheet",
            file_name=fname,
            file_size=detail["file_size"],
            mime_type=detail["mime_type"],
            storage_path=detail["storage_path"],
            page_count=detail["page_count"],
            content_hash=c_hash,
            extracted_text=detail["extracted_text"],
            status="ready",
        )
        db.add(doc)

        # Multi-student PDF splitting support when requested and PDF has multiple student pages
        is_multi_bundle = (
            split_multi_pdf
            and detail["mime_type"] == "application/pdf"
            and (detail["page_count"] >= 2 or any(k in fname.lower() for k in ("bundle", "combined", "multi", "class_pack")))
        )
        if is_multi_bundle:
            num_splits = min(len(students) or 3, max(2, detail["page_count"] // 2))
            for s_idx in range(num_splits):
                matched_st = students[s_idx % len(students)] if students else None
                page_range_str = f"Pages {s_idx * 2 + 1}-{s_idx * 2 + 2}"
                valid_count += 1
                total_items_created += 1
                db.add(
                    GradingBatchItem(
                        id=f"bitem-{uuid.uuid4().hex[:12]}",
                        batch_id=batch_id,
                        document_id=doc.id,
                        file_name=f"{fname} ({page_range_str})",
                        file_size=detail["file_size"] // num_splits,
                        mime_type=detail["mime_type"],
                        page_count=2,
                        page_range=page_range_str,
                        content_hash=f"{c_hash}-part-{s_idx + 1}",
                        status="uploaded",
                        stage_progress=15,
                        student_id=matched_st.id if matched_st else None,
                        student_name=matched_st.name if matched_st else None,
                        student_confidence=0.89 if matched_st else 0.4,
                        extracted_text=detail["extracted_text"],
                        max_marks=assessment.total_marks,
                    )
                )
        else:
            matched_st, st_conf = match_student_from_filename_or_text(
                fname, detail["extracted_text"] or "", students, fallback_index=idx
            )
            valid_count += 1
            total_items_created += 1
            db.add(
                GradingBatchItem(
                    id=f"bitem-{uuid.uuid4().hex[:12]}",
                    batch_id=batch_id,
                    document_id=doc.id,
                    file_name=fname,
                    file_size=detail["file_size"],
                    mime_type=detail["mime_type"],
                    page_count=detail["page_count"],
                    content_hash=c_hash,
                    status="uploaded",
                    stage_progress=15,
                    student_id=matched_st.id if (matched_st and st_conf >= 0.70) else None,
                    student_name=matched_st.name if (matched_st and st_conf >= 0.70) else None,
                    student_confidence=st_conf,
                    extracted_text=detail["extracted_text"],
                    max_marks=assessment.total_marks,
                    requires_review=st_conf < 0.80,
                    review_reasons_json=(
                        ["Manual student identification required before finalizing grade"]
                        if st_conf < 0.80
                        else []
                    ),
                )
            )

    batch.total_files = total_items_created
    batch.valid_files = valid_count
    batch.invalid_or_duplicate_files = invalid_dup_count

    audit = AuditEvent(
        timestamp=utc_now().strftime("%Y-%m-%d %H:%M"),
        user_id=educator.id,
        user_name=educator.name,
        action="Created Auto-Grading Upload Batch",
        details=f"Uploaded {total_items_created} answer sheet(s) ({valid_count} valid, {invalid_dup_count} invalid/duplicate) for '{assessment.title}'.",
        category="assessment",
    )
    db.add(audit)
    await db.commit()
    await db.refresh(batch)

    return await _serialize_batch(db, batch)


@router.get("/batches", response_model=List[GradingBatchOut])
async def list_grading_batches(
    assessment_id: Optional[str] = Query(None),
    class_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(GradingBatch)
    if current_user.role != "admin" and current_user.school_id:
        query = query.filter(GradingBatch.school_id == current_user.school_id)
    if assessment_id:
        query = query.filter(GradingBatch.assessment_id == assessment_id)
    if class_id:
        query = query.filter(GradingBatch.class_id == class_id)
    res = await db.execute(query.order_by(GradingBatch.created_at.desc()).limit(20))
    batches = list(res.scalars().all())
    return [await _serialize_batch(db, b) for b in batches]


@router.get("/batches/{batch_id}", response_model=GradingBatchOut)
async def get_grading_batch(
    batch_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    res = await db.execute(select(GradingBatch).filter(GradingBatch.id == batch_id))
    batch = res.scalars().first()
    if not batch:
        raise HTTPException(status_code=404, detail="Grading batch not found.")
    return await _serialize_batch(db, batch)


@router.post("/batches/{batch_id}/start", response_model=GradingBatchOut)
async def start_grading_batch(
    batch_id: str,
    wait_for_completion: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    educator: User = Depends(require_roles("admin", "principal", "teacher")),
):
    """
    Confirms and starts asynchronous background processing for all valid uploaded papers in the batch.
    """
    res = await db.execute(select(GradingBatch).filter(GradingBatch.id == batch_id))
    batch = res.scalars().first()
    if not batch:
        raise HTTPException(status_code=404, detail="Grading batch not found.")

    if batch.valid_files == 0:
        raise HTTPException(status_code=400, detail="No valid answer sheets in this batch to process.")

    batch.status = "processing"
    await db.commit()

    if wait_for_completion:
        await run_grading_batch_job(batch_id, fast_mode=True)
    else:
        asyncio.create_task(run_grading_batch_job(batch_id, fast_mode=False))

    db.expire_all()
    await db.refresh(batch)
    return await _serialize_batch(db, batch)


@router.post("/batches/{batch_id}/cancel", response_model=GradingBatchOut)
async def cancel_grading_batch(
    batch_id: str,
    db: AsyncSession = Depends(get_db),
    educator: User = Depends(require_roles("admin", "principal", "teacher")),
):
    res = await db.execute(select(GradingBatch).filter(GradingBatch.id == batch_id))
    batch = res.scalars().first()
    if not batch:
        raise HTTPException(status_code=404, detail="Grading batch not found.")

    cancel_batch_job(batch_id)

    items_res = await db.execute(
        select(GradingBatchItem).filter(
            GradingBatchItem.batch_id == batch_id,
            GradingBatchItem.status.in_(["uploaded", "queued"]),
        )
    )
    for it in items_res.scalars().all():
        it.status = "cancelled"

    batch.status = "cancelled"
    await db.commit()
    await db.refresh(batch)
    return await _serialize_batch(db, batch)


@router.delete("/batches/{batch_id}/items/{item_id}", response_model=GradingBatchOut)
async def remove_batch_item(
    batch_id: str,
    item_id: str,
    db: AsyncSession = Depends(get_db),
    educator: User = Depends(require_roles("admin", "principal", "teacher")),
):
    res = await db.execute(
        select(GradingBatchItem).filter(
            GradingBatchItem.id == item_id,
            GradingBatchItem.batch_id == batch_id,
        )
    )
    item = res.scalars().first()
    if not item:
        raise HTTPException(status_code=404, detail="Batch item not found.")

    await db.delete(item)
    await db.commit()
    await recalculate_batch_counters(batch_id)
    db.expire_all()

    batch_res = await db.execute(select(GradingBatch).filter(GradingBatch.id == batch_id))
    batch = batch_res.scalars().first()
    return await _serialize_batch(db, batch)


@router.post("/batches/{batch_id}/items/{item_id}/retry", response_model=GradingBatchOut)
async def retry_batch_item(
    batch_id: str,
    item_id: str,
    wait_for_completion: bool = Query(True),
    db: AsyncSession = Depends(get_db),
    educator: User = Depends(require_roles("admin", "principal", "teacher")),
):
    res = await db.execute(
        select(GradingBatchItem).filter(
            GradingBatchItem.id == item_id,
            GradingBatchItem.batch_id == batch_id,
        )
    )
    item = res.scalars().first()
    if not item:
        raise HTTPException(status_code=404, detail="Batch item not found.")

    item.retry_count = (item.retry_count or 0) + 1
    item.status = "queued"
    item.stage_progress = 10
    item.error_message = None
    await db.commit()

    semaphore = asyncio.Semaphore(1)
    if wait_for_completion:
        await process_single_batch_item(batch_id, item_id, semaphore, fast_mode=True)
    else:
        asyncio.create_task(process_single_batch_item(batch_id, item_id, semaphore, fast_mode=False))

    db.expire_all()
    batch_res = await db.execute(select(GradingBatch).filter(GradingBatch.id == batch_id))
    batch = batch_res.scalars().first()
    return await _serialize_batch(db, batch)


@router.put("/batches/{batch_id}/items/{item_id}", response_model=BatchItemOut)
async def update_batch_item_review(
    batch_id: str,
    item_id: str,
    req: BatchItemUpdateRequest,
    db: AsyncSession = Depends(get_db),
    educator: User = Depends(require_roles("admin", "principal", "teacher")),
):
    """
    Allows teacher to manually confirm/assign student identity and correct question marks/feedback
    before final approval.
    """
    res = await db.execute(
        select(GradingBatchItem).filter(
            GradingBatchItem.id == item_id,
            GradingBatchItem.batch_id == batch_id,
        )
    )
    item = res.scalars().first()
    if not item:
        raise HTTPException(status_code=404, detail="Batch item not found.")

    if req.student_id is not None:
        st_res = await db.execute(select(Student).filter(Student.id == req.student_id))
        st = st_res.scalars().first()
        if not st:
            raise HTTPException(status_code=404, detail="Selected student not found.")
        item.student_id = st.id
        item.student_name = st.name
        item.student_confidence = 1.0

    if req.question_evaluations is not None:
        item.question_evaluations_json = req.question_evaluations
        item.marks_obtained = sum(int(q.get("awarded_marks", 0)) for q in req.question_evaluations)

    if req.marks_obtained is not None:
        item.marks_obtained = max(0, min(item.max_marks, req.marks_obtained))

    item.percentage = round((item.marks_obtained / max(1, item.max_marks)) * 100)
    item.grade = compute_letter_grade(item.percentage)

    if req.clear_review_flag and item.student_id:
        item.requires_review = False
        item.review_reasons_json = []
        if item.status == "requires_review":
            item.status = "completed"

    await db.commit()
    await recalculate_batch_counters(batch_id)
    await db.refresh(item)
    return BatchItemOut.model_validate(item)


async def _publish_item_submission(
    db: AsyncSession,
    batch: GradingBatch,
    item: GradingBatchItem,
    educator: User,
) -> None:
    if not item.student_id:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot publish grade for '{item.file_name}': Student identity must be confirmed first.",
        )

    st_res = await db.execute(select(Student).filter(Student.id == item.student_id))
    student = st_res.scalars().first()
    if not student:
        raise HTTPException(status_code=404, detail="Student record not found.")

    asm_res = await db.execute(select(Assessment).filter(Assessment.id == batch.assessment_id))
    asm = asm_res.scalars().first()

    comp = item.competency_scores_json or {}
    lu = int(comp.get("LU", student.lu_score))
    cu = int(comp.get("CU", student.cu_score))
    au = int(comp.get("AU", student.au_score))
    ct = int(comp.get("CT", student.ct_score))
    overall = round((lu + cu + au + ct) / 4)

    sub = AssessmentSubmission(
        assessment_id=batch.assessment_id,
        student_id=student.id,
        student_name=student.name,
        marks_obtained=item.marks_obtained,
        total_marks=item.max_marks,
        percentage=item.percentage,
        lu_score=lu,
        cu_score=cu,
        au_score=au,
        ct_score=ct,
        overall_score=overall,
        feedback=f"Auto-Grade Engine verified by {educator.name} ({item.file_name}). Grade: {item.grade} ({item.percentage}%).",
        submission_date=utc_now().strftime("%Y-%m-%d"),
        is_scanned=True,
    )
    db.add(sub)
    await db.flush()

    student.lu_score = lu
    student.cu_score = cu
    student.au_score = au
    student.ct_score = ct
    student.overall_score = overall
    student.needs_support = item.percentage < 65

    snapshot = StudentCompetencySnapshot(
        student_id=student.id,
        cycle_number=asm.cycle_number if asm else 2,
        lu_score=lu,
        cu_score=cu,
        au_score=au,
        ct_score=ct,
        overall_score=overall,
        notes=f"Batch Auto-Graded & Teacher Approved: {item.file_name}",
    )
    db.add(snapshot)

    item.is_approved = True
    item.requires_review = False
    item.status = "approved"
    item.submission_id = sub.id


@router.post("/batches/{batch_id}/items/{item_id}/approve", response_model=BatchItemOut)
async def approve_batch_item(
    batch_id: str,
    item_id: str,
    db: AsyncSession = Depends(get_db),
    educator: User = Depends(require_roles("admin", "principal", "teacher")),
):
    batch_res = await db.execute(select(GradingBatch).filter(GradingBatch.id == batch_id))
    batch = batch_res.scalars().first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found.")

    item_res = await db.execute(
        select(GradingBatchItem).filter(
            GradingBatchItem.id == item_id,
            GradingBatchItem.batch_id == batch_id,
        )
    )
    item = item_res.scalars().first()
    if not item:
        raise HTTPException(status_code=404, detail="Batch item not found.")

    if item.is_approved:
        return BatchItemOut.model_validate(item)

    await _publish_item_submission(db, batch, item, educator)

    audit = AuditEvent(
        timestamp=utc_now().strftime("%Y-%m-%d %H:%M"),
        user_id=educator.id,
        user_name=educator.name,
        action="Approved Auto-Graded Student Paper",
        details=f"Verified & published {item.marks_obtained}/{item.max_marks} ({item.percentage}%) for {item.student_name}.",
        category="assessment",
    )
    db.add(audit)

    await db.commit()
    await recalculate_batch_counters(batch_id)
    await db.refresh(item)
    return BatchItemOut.model_validate(item)


@router.post("/batches/{batch_id}/approve-all", response_model=GradingBatchOut)
async def approve_all_verified_batch_items(
    batch_id: str,
    db: AsyncSession = Depends(get_db),
    educator: User = Depends(require_roles("admin", "principal", "teacher")),
):
    """
    Approves and publishes all completed, high-confidence items that do not require manual review.
    Uncertain items remain flagged for individual teacher verification.
    """
    batch_res = await db.execute(select(GradingBatch).filter(GradingBatch.id == batch_id))
    batch = batch_res.scalars().first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found.")

    items_res = await db.execute(
        select(GradingBatchItem).filter(
            GradingBatchItem.batch_id == batch_id,
            GradingBatchItem.status == "completed",
            GradingBatchItem.requires_review == False,
            GradingBatchItem.is_approved == False,
        )
    )
    eligible_items = [it for it in items_res.scalars().all() if it.student_id]

    approved_count = 0
    for it in eligible_items:
        await _publish_item_submission(db, batch, it, educator)
        approved_count += 1

    if approved_count > 0:
        audit = AuditEvent(
            timestamp=utc_now().strftime("%Y-%m-%d %H:%M"),
            user_id=educator.id,
            user_name=educator.name,
            action="Bulk Approved Auto-Graded Batch",
            details=f"Approved and published {approved_count} verified student paper(s) in batch {batch.id}.",
            category="assessment",
        )
        db.add(audit)

    await db.commit()
    await recalculate_batch_counters(batch_id)
    await db.refresh(batch)
    return await _serialize_batch(db, batch)
