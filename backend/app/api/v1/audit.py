from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.dependencies import require_roles
from backend.app.db.session import get_db
from backend.app.models.entities import AuditEvent, User
from backend.app.schemas.common import AuditEventOut

router = APIRouter(prefix="/audit", tags=["Audit & Security"])


@router.get("/events", response_model=List[AuditEventOut])
async def list_audit_events(
    category: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_roles("admin"))
):
    query = select(AuditEvent)
    if category and category != "all":
        query = query.filter(AuditEvent.category == category)
    if search:
        query = query.filter(AuditEvent.action.ilike(f"%{search}%") | AuditEvent.details.ilike(f"%{search}%"))

    res = await db.execute(query.order_by(AuditEvent.created_at.desc()).limit(limit))
    return res.scalars().all()

