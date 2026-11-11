import os
import uuid
import hashlib
import aiofiles
from typing import Tuple, Dict, Any
from fastapi import UploadFile, HTTPException, status
from backend.app.core.config import settings

ALLOWED_MIME_TYPES = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "application/pdf": ".pdf",
    "text/plain": ".txt",
    "text/markdown": ".md",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
}

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf", ".txt", ".md", ".docx"}

MAX_FILE_SIZE = 15 * 1024 * 1024  # 15 MB limit


class StorageService:
    def __init__(self):
        self.upload_dir = settings.STORAGE_LOCAL_DIR
        os.makedirs(self.upload_dir, exist_ok=True)

    async def save_upload(self, file: UploadFile) -> Tuple[str, str, int]:
        """
        Validates and saves an uploaded file to secure private storage.
        Returns: (file_id, relative_path, file_size)
        """
        detail = await self.save_upload_detailed(file)
        if not detail["valid"]:
            status_code = (
                status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
                if "exceeds" in (detail.get("error") or "")
                else status.HTTP_400_BAD_REQUEST
            )
            raise HTTPException(status_code=status_code, detail=detail["error"])
        return detail["file_id"], detail["storage_path"], detail["file_size"]

    async def save_upload_detailed(self, file: UploadFile) -> Dict[str, Any]:
        """
        Validates and saves an uploaded file without raising exceptions on validation failure,
        enabling partial success in bulk upload batches where one invalid file does not block others.
        """
        raw_filename = os.path.basename(file.filename or "uploaded_file")
        _, ext = os.path.splitext(raw_filename.lower())
        content_type = (file.content_type or "application/octet-stream").lower()

        if content_type not in ALLOWED_MIME_TYPES and ext not in ALLOWED_EXTENSIONS:
            return {
                "valid": False,
                "file_name": raw_filename,
                "file_size": 0,
                "mime_type": content_type,
                "error": f"Unsupported file format '{ext or content_type}'. Allowed: PDF, JPG, PNG, TXT, DOCX.",
            }

        normalized_ext = ALLOWED_MIME_TYPES.get(content_type, ext if ext in ALLOWED_EXTENSIONS else ".pdf")
        file_id = f"doc-{uuid.uuid4().hex[:16]}"
        dest_filename = f"{file_id}{normalized_ext}"
        dest_path = os.path.join(self.upload_dir, dest_filename)

        size = 0
        sha256_hasher = hashlib.sha256()
        raw_bytes_preview = bytearray()

        try:
            async with aiofiles.open(dest_path, "wb") as out_file:
                while chunk := await file.read(1024 * 64):
                    size += len(chunk)
                    if size > MAX_FILE_SIZE:
                        await out_file.close()
                        if os.path.exists(dest_path):
                            os.remove(dest_path)
                        return {
                            "valid": False,
                            "file_name": raw_filename,
                            "file_size": size,
                            "mime_type": content_type,
                            "error": f"File '{raw_filename}' exceeds the 15 MB maximum size limit.",
                        }
                    sha256_hasher.update(chunk)
                    if len(raw_bytes_preview) < 16384:
                        raw_bytes_preview.extend(chunk[: 16384 - len(raw_bytes_preview)])
                    await out_file.write(chunk)
        except Exception as exc:
            if os.path.exists(dest_path):
                try:
                    os.remove(dest_path)
                except OSError:
                    pass
            return {
                "valid": False,
                "file_name": raw_filename,
                "file_size": size,
                "mime_type": content_type,
                "error": f"Storage write error: {str(exc)}",
            }

        if size == 0:
            if os.path.exists(dest_path):
                os.remove(dest_path)
            return {
                "valid": False,
                "file_name": raw_filename,
                "file_size": 0,
                "mime_type": content_type,
                "error": f"File '{raw_filename}' is empty (0 bytes).",
            }

        content_hash = sha256_hasher.hexdigest()

        # Estimate page count and extract text where available
        page_count = 1
        extracted_text = ""
        if normalized_ext in (".txt", ".md"):
            extracted_text = raw_bytes_preview.decode("utf-8", errors="ignore").strip()
            page_count = max(1, len(extracted_text) // 1800 + 1)
        elif normalized_ext == ".pdf":
            # Count "/Type /Page" occurrences or estimate from size
            pdf_page_markers = raw_bytes_preview.count(b"/Page")
            page_count = max(1, min(25, pdf_page_markers if pdf_page_markers > 0 else (size // 85000) + 1))
            # Extract ASCII strings or fallback grounded summary from filename
            decoded_ascii = "".join(
                chr(b) if 32 <= b < 127 else " " for b in raw_bytes_preview
            )
            cleaned = " ".join(w for w in decoded_ascii.split() if len(w) > 3 and w.isalpha())
            extracted_text = (
                f"Document Reference: {raw_filename}. "
                + (cleaned[:800] if len(cleaned) > 60 else f"Curriculum source material from {raw_filename} ({page_count} pages).")
            )
        else:
            extracted_text = f"Uploaded visual/document source: {raw_filename} ({size} bytes)."

        return {
            "valid": True,
            "file_id": file_id,
            "file_name": raw_filename,
            "storage_path": dest_path,
            "file_size": size,
            "mime_type": content_type if content_type in ALLOWED_MIME_TYPES else "application/pdf",
            "page_count": page_count,
            "content_hash": content_hash,
            "extracted_text": extracted_text,
            "error": None,
        }

    def get_file_path(self, storage_path: str) -> str:
        if os.path.exists(storage_path):
            return storage_path
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document file not found in storage."
        )


storage_service = StorageService()
