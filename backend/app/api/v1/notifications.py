from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.dependencies import get_current_user
from backend.app.db.session import get_db
from backend.app.models.entities import Notification, Announcement, User
from backend.app.schemas.common import NotificationOut, AnnouncementCreate, AnnouncementOut

router = APIRouter(tags=["Notifications & Announcements"])


@router.get("/notifications", response_model=List[NotificationOut])
async def list_notifications(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    res = await db.execute(
        select(Notification).filter(
            (Notification.user_id == current_user.id) | (Notification.user_id == "user-active")
        ).order_by(Notification.created_at.desc())
    )
    return res.scalars().all()


@router.post("/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    res = await db.execute(select(Notification).filter(Notification.id == notification_id))
    notif = res.scalars().first()
    if notif:
        notif.is_read = True
        await db.commit()
    return {"message": "Notification marked as read."}


@router.post("/notifications/read-all")
async def mark_all_notifications_read(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    res = await db.execute(select(Notification).filter(Notification.user_id == current_user.id))
    for n in res.scalars().all():
        n.is_read = True
    await db.commit()
    return {"message": "All notifications marked as read."}


@router.post("/announcements", response_model=AnnouncementOut)
async def create_announcement(
    req: AnnouncementCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    ann = Announcement(
        school_id=current_user.school_id or "school-1",
        sender_id=current_user.id,
        sender_name=current_user.name,
        title=req.title,
        content=req.content,
        target_role=req.target_role
    )
    db.add(ann)
    await db.commit()
    await db.refresh(ann)
    return ann


@router.get("/announcements", response_model=List[AnnouncementOut])
async def list_announcements(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    res = await db.execute(select(Announcement).order_by(Announcement.created_at.desc()))
    return res.scalars().all()

