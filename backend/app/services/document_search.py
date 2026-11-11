"""Index approved PDF passages and retrieve them within the viewer's school."""
import asyncio
import json

import httpx
import pymupdf
from fastapi import HTTPException
from sqlalchemy import select

from backend.app.core.config import settings
from backend.app.models.entities import Document
from backend.app.services.storage_service import storage_service

INDEX = "lumeneios-assistant-v1"
STAFF = {"admin", "principal", "teacher"}
LIBRARY_TYPES = {"source_material", "curriculum_guide", "school_policy"}


def client():
    headers = {"Authorization": f"ApiKey {settings.ELASTICSEARCH_API_KEY.get_secret_value()}"} if settings.ELASTICSEARCH_API_KEY.get_secret_value() else {}
    return httpx.AsyncClient(base_url=settings.ELASTICSEARCH_URL.rstrip("/"), headers=headers, timeout=10)


def pdf_passages(path):
    with pymupdf.open(path) as pdf:
        return [
            (page.number + 1, offset, text[offset:offset + 1800])
            for page in pdf
            if (text := " ".join(page.get_text().split()))
            for offset in range(0, len(text), 1500)
        ]


async def index_document(doc):
    if not settings.ELASTICSEARCH_URL:
        raise HTTPException(503, "Elasticsearch is disabled.")
    if doc.doc_type not in LIBRARY_TYPES or doc.status != "ready" or doc.mime_type != "application/pdf":
        raise HTTPException(422, "Choose a ready curriculum or policy PDF.")
    path = storage_service.get_file_path(doc.storage_path)
    passages = await asyncio.to_thread(pdf_passages, path)
    if not passages:
        raise HTTPException(422, "This PDF has no searchable text. Upload a text PDF or an OCR-processed copy.")
    lines = []
    for page, offset, text in passages:
        lines.append(json.dumps({"index": {"_id": f"{doc.id}:{page}:{offset}"}}))
        lines.append(json.dumps({"document_id": doc.id, "school_id": doc.school_id, "page": page, "text": text}))
    try:
        async with client() as elastic:
            result = await elastic.post(f"/{INDEX}/_bulk", params={"refresh": "wait_for"},
                content="\n".join(lines) + "\n", headers={"Content-Type": "application/x-ndjson"})
            result.raise_for_status()
            if result.json()["errors"]:
                raise ValueError("Bulk indexing was incomplete")
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        raise HTTPException(503, "Document indexing failed. Retry to update the same passages.") from exc
    return len(passages)


async def search_documents(db, school_id, message):
    if not settings.ELASTICSEARCH_URL or not school_id:
        return []
    try:
        async with client() as elastic:
            result = await elastic.post(f"/{INDEX}/_search", json={
                "size": 12,
                "query": {"bool": {
                    "filter": {"term": {"school_id.keyword": school_id}},
                    "must": {"match": {"text": {"query": message, "minimum_should_match": "30%"}}},
                }},
            })
            if result.status_code == 404:
                return []
            result.raise_for_status()
            hits = [hit["_source"] for hit in result.json()["hits"]["hits"]]
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        raise HTTPException(503, "School document search is unavailable.") from exc
    documents = {doc.id: doc for doc in await db.scalars(select(Document).where(
        Document.id.in_([hit["document_id"] for hit in hits]),
        Document.school_id == school_id, Document.status == "ready", Document.doc_type.in_(LIBRARY_TYPES),
    ))}
    passages = []
    for hit in hits:
        doc = documents.get(hit["document_id"])
        if doc and 1 <= hit["page"] <= doc.page_count:
            passages.append({"document_id": doc.id, "name": doc.file_name, "page": hit["page"], "text": hit["text"]})
        if len(passages) == 4:
            break
    return passages
