from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.dependencies import get_current_user, require_roles, require_school_access
from backend.app.db.session import get_db
from backend.app.models.entities import Document, User, AuditEvent, utc_now
from backend.app.schemas.ocr import DocumentOut, BulkDocumentItemResult, BulkDocumentUploadResponse
from backend.app.services.storage_service import MAX_FILE_SIZE, storage_service
from backend.app.services.document_search import index_document

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post("/{document_id}/publish-to-assistant")
async def publish_to_assistant(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("admin", "principal", authenticated=True)),
):
    doc = await db.get(Document, document_id)
    if not doc:
        raise HTTPException(404, "Document not found.")
    await require_school_access(db, user, doc.school_id)
    return {"indexed_passages": await index_document(doc)}


@router.get("", response_model=List[DocumentOut])
async def list_documents(
    subject_id: Optional[str] = Query(None),
    doc_type: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(Document)
    if current_user.role != "admin" and current_user.school_id:
        query = query.filter(Document.school_id == current_user.school_id)
    if subject_id:
        query = query.filter((Document.subject_id == subject_id) | (Document.subject_id.is_(None)))
    if doc_type:
        query = query.filter((Document.doc_type == doc_type) | (Document.doc_type.is_(None)))
    res = await db.execute(query.order_by(Document.created_at.desc()))
    return res.scalars().all()


@router.post("/upload", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    subject_id: Optional[str] = Form(None),
    doc_type: str = Form("source_material"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "principal", "teacher")),
):
    detail = await storage_service.save_upload_detailed(file)
    if not detail["valid"]:
        status_code = (
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
            if "exceeds" in (detail.get("error") or "")
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=status_code, detail=detail["error"])

    doc = Document(
        id=detail["file_id"],
        school_id=current_user.school_id or "school-1",
        uploader_id=current_user.id,
        subject_id=subject_id,
        doc_type=doc_type,
        file_name=detail["file_name"],
        file_size=detail["file_size"],
        mime_type=detail["mime_type"],
        storage_path=detail["storage_path"],
        page_count=detail["page_count"],
        content_hash=detail["content_hash"],
        extracted_text=detail["extracted_text"],
        status="ready",
    )
    db.add(doc)

    audit = AuditEvent(
        timestamp=utc_now().strftime("%Y-%m-%d %H:%M"),
        user_id=current_user.id,
        user_name=current_user.name,
        action="Uploaded Curriculum Document",
        details=f"Uploaded {doc.file_name} ({doc.file_size} bytes) to document repository.",
        category="assessment",
    )
    db.add(audit)
    await db.commit()
    await db.refresh(doc)
    return doc


@router.post("/studio-pdf-upload", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_studio_pdf(
    file: UploadFile = File(...),
    subject_id: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "principal", "teacher")),
):
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only PDF files are allowed.")

    content = await file.read(MAX_FILE_SIZE + 1)
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="PDF exceeds the 15 MB maximum size limit.",
        )
    if not content.startswith(b"%PDF-"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The uploaded file is not a valid PDF.")

    try:
        import pymupdf
    except ImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="PDF validation is unavailable. Install backend/requirements.txt.",
        ) from exc
    try:
        with pymupdf.open(stream=content, filetype="pdf") as pdf:
            if pdf.needs_pass:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Password-protected PDFs are not supported.",
                )
            if pdf.page_count == 0 or pdf.page_count > 25:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="PDFs must contain between 1 and 25 pages.",
                )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded PDF could not be opened.",
        ) from exc

    await file.seek(0)
    return await upload_document(file, subject_id, "source_material", db, current_user)


@router.post("/bulk-upload", response_model=BulkDocumentUploadResponse)
async def bulk_upload_documents(
    files: List[UploadFile] = File(...),
    subject_id: Optional[str] = Form(None),
    doc_type: str = Form("source_material"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "principal", "teacher")),
):
    """
    Uploads multiple source documents in one operation.
    Validates each file independently so a failed/invalid file does not block valid files.
    """
    if len(files) > 50:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum batch size is 50 files per bulk upload.",
        )

    school_id = current_user.school_id or "school-1"
    existing_res = await db.execute(select(Document).filter(Document.school_id == school_id))
    existing_docs = list(existing_res.scalars().all())
    existing_hashes = {d.content_hash: d for d in existing_docs if d.content_hash}
    seen_hashes_in_batch = set()

    results: List[BulkDocumentItemResult] = []
    uploaded_count = 0
    duplicate_count = 0
    failed_count = 0

    for file in files:
        detail = await storage_service.save_upload_detailed(file)
        if not detail["valid"]:
            failed_count += 1
            results.append(
                BulkDocumentItemResult(
                    file_name=detail["file_name"],
                    file_size=detail["file_size"],
                    valid=False,
                    duplicate=False,
                    status="failed",
                    error=detail["error"],
                    document=None,
                )
            )
            continue

        c_hash = detail["content_hash"]
        if c_hash in seen_hashes_in_batch or c_hash in existing_hashes:
            duplicate_count += 1
            existing_doc = existing_hashes.get(c_hash)
            results.append(
                BulkDocumentItemResult(
                    file_name=detail["file_name"],
                    file_size=detail["file_size"],
                    valid=True,
                    duplicate=True,
                    status="duplicate",
                    error="Duplicate file content already exists in repository.",
                    document=DocumentOut.model_validate(existing_doc) if existing_doc else None,
                )
            )
            continue

        seen_hashes_in_batch.add(c_hash)

        doc = Document(
            id=detail["file_id"],
            school_id=school_id,
            uploader_id=current_user.id,
            subject_id=subject_id,
            doc_type=doc_type,
            file_name=detail["file_name"],
            file_size=detail["file_size"],
            mime_type=detail["mime_type"],
            storage_path=detail["storage_path"],
            page_count=detail["page_count"],
            content_hash=c_hash,
            extracted_text=detail["extracted_text"],
            status="ready",
        )
        db.add(doc)
        await db.flush()
        existing_hashes[c_hash] = doc
        uploaded_count += 1

        results.append(
            BulkDocumentItemResult(
                file_name=doc.file_name,
                file_size=doc.file_size,
                valid=True,
                duplicate=False,
                status="uploaded",
                error=None,
                document=DocumentOut.model_validate(doc),
            )
        )

    if uploaded_count > 0:
        audit = AuditEvent(
            timestamp=utc_now().strftime("%Y-%m-%d %H:%M"),
            user_id=current_user.id,
            user_name=current_user.name,
            action="Bulk Uploaded Source Documents",
            details=f"Bulk uploaded {uploaded_count} document(s) ({failed_count} failed, {duplicate_count} duplicate).",
            category="assessment",
        )
        db.add(audit)

    await db.commit()

    return BulkDocumentUploadResponse(
        total_selected=len(files),
        uploaded_count=uploaded_count,
        duplicate_count=duplicate_count,
        failed_count=failed_count,
        items=results,
    )


@router.get("/{document_id}", response_model=DocumentOut)
async def get_document_metadata(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    res = await db.execute(select(Document).filter(Document.id == document_id))
    doc = res.scalars().first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    return doc


@router.delete("/{document_id}")
async def delete_document(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "principal", "teacher")),
):
    res = await db.execute(select(Document).filter(Document.id == document_id))
    doc = res.scalars().first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    await db.delete(doc)
    await db.commit()
    return {"status": "deleted", "id": document_id}


@router.get("/{document_id}/download")
async def download_document(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    res = await db.execute(select(Document).filter(Document.id == document_id))
    doc = res.scalars().first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    await require_school_access(db, current_user, doc.school_id)
    file_path = storage_service.get_file_path(doc.storage_path)
    return FileResponse(file_path, media_type=doc.mime_type, filename=doc.file_name)
