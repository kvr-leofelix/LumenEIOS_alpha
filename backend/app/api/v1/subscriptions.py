"""PayPal subscriptions for schools.

A principal pays for their school with two PayPal subscriptions:
  - "base": a flat monthly plan for the school (quantity 1)
  - "seats": a per-teacher monthly plan (quantity = number of teachers)
PayPal calls our webhook when a subscription is approved, suspended or cancelled.
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.dependencies import require_roles
from backend.app.core.config import settings
from backend.app.core.logging import logger
from backend.app.db.session import get_db
from backend.app.models.entities import PayPalSubscription, User
from backend.app.services import paypal

router = APIRouter(tags=["Subscriptions"])

ACTIVE_STATUSES = {"ACTIVE"}
OPEN_STATUSES = {"APPROVAL_PENDING", "APPROVED", "ACTIVE", "SUSPENDED"}

# Maps PayPal webhook event types to the subscription status we store.
EVENT_STATUS = {
    "BILLING.SUBSCRIPTION.ACTIVATED": "ACTIVE",
    "BILLING.SUBSCRIPTION.RE-ACTIVATED": "ACTIVE",
    "BILLING.SUBSCRIPTION.SUSPENDED": "SUSPENDED",
    "BILLING.SUBSCRIPTION.CANCELLED": "CANCELLED",
    "BILLING.SUBSCRIPTION.EXPIRED": "EXPIRED",
}


class StartSubscriptionIn(BaseModel):
    teacher_count: int = Field(ge=1, le=500)


class ChangeSeatsIn(BaseModel):
    teacher_count: int = Field(ge=1, le=500)


class SubscriptionOut(BaseModel):
    id: str
    kind: str
    status: str
    quantity: int
    paypal_subscription_id: Optional[str]


class StartSubscriptionOut(BaseModel):
    subscriptions: List[SubscriptionOut]
    # The principal must approve each subscription on PayPal, one after the other.
    approve_links: List[str]


def _approve_link(body: dict) -> Optional[str]:
    for link in body.get("links", []):
        if link.get("rel") == "approve":
            return link.get("href")
    return None


def _to_out(row: PayPalSubscription) -> SubscriptionOut:
    return SubscriptionOut(
        id=row.id, kind=row.kind, status=row.status,
        quantity=row.quantity, paypal_subscription_id=row.paypal_subscription_id,
    )


def _paypal_http_error(exc: paypal.PayPalError) -> HTTPException:
    logger.warning("PayPal request failed (%s): %s", exc.status_code, exc)
    return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"PayPal error: {exc}")


async def school_has_active_subscription(db: AsyncSession, school_id: str) -> bool:
    """Gate features on this: the school needs an active base subscription."""
    result = await db.execute(
        select(PayPalSubscription).where(
            PayPalSubscription.school_id == school_id,
            PayPalSubscription.kind == "base",
            PayPalSubscription.status.in_(ACTIVE_STATUSES),
        )
    )
    return result.scalars().first() is not None


@router.post("/subscriptions/start", response_model=StartSubscriptionOut, status_code=status.HTTP_201_CREATED)
async def start_subscriptions(
    payload: StartSubscriptionIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("principal")),
):
    if not paypal.is_configured() or not settings.PAYPAL_BASE_PLAN_ID or not settings.PAYPAL_SEAT_PLAN_ID:
        raise HTTPException(status_code=503, detail="PayPal subscriptions are not configured on this server.")
    if not current_user.school_id:
        raise HTTPException(status_code=400, detail="Your account is not linked to a school.")

    existing = await db.execute(
        select(PayPalSubscription).where(
            PayPalSubscription.school_id == current_user.school_id,
            PayPalSubscription.status.in_(OPEN_STATUSES),
        )
    )
    if existing.scalars().first():
        raise HTTPException(status_code=409, detail="This school already has a subscription in progress or active.")

    plans = [("base", settings.PAYPAL_BASE_PLAN_ID, 1), ("seats", settings.PAYPAL_SEAT_PLAN_ID, payload.teacher_count)]
    rows: List[PayPalSubscription] = []
    approve_links: List[str] = []
    try:
        for kind, plan_id, quantity in plans:
            body = await paypal.create_subscription(
                plan_id=plan_id,
                quantity=quantity,
                return_url=settings.PAYPAL_RETURN_URL,
                cancel_url=settings.PAYPAL_CANCEL_URL,
            )
            row = PayPalSubscription(
                school_id=current_user.school_id,
                principal_user_id=current_user.id,
                kind=kind,
                paypal_subscription_id=body["id"],
                plan_id=plan_id,
                quantity=quantity,
                status=body.get("status", "APPROVAL_PENDING"),
            )
            db.add(row)
            rows.append(row)
            link = _approve_link(body)
            if link:
                approve_links.append(link)
    except paypal.PayPalError as exc:
        await db.rollback()
        raise _paypal_http_error(exc)

    await db.commit()
    return StartSubscriptionOut(subscriptions=[_to_out(r) for r in rows], approve_links=approve_links)


@router.get("/subscriptions/status", response_model=List[SubscriptionOut])
async def subscription_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("principal", "admin")),
):
    if not current_user.school_id:
        return []
    result = await db.execute(
        select(PayPalSubscription).where(PayPalSubscription.school_id == current_user.school_id)
        .order_by(PayPalSubscription.created_at)
    )
    return [_to_out(r) for r in result.scalars().all()]


@router.post("/subscriptions/seats", response_model=SubscriptionOut)
async def change_teacher_seats(
    payload: ChangeSeatsIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("principal")),
):
    result = await db.execute(
        select(PayPalSubscription).where(
            PayPalSubscription.school_id == current_user.school_id,
            PayPalSubscription.kind == "seats",
            PayPalSubscription.status.in_(ACTIVE_STATUSES),
        )
    )
    row = result.scalars().first()
    if not row or not row.paypal_subscription_id:
        raise HTTPException(status_code=404, detail="No active teacher seat subscription for this school.")
    try:
        await paypal.revise_quantity(row.paypal_subscription_id, payload.teacher_count)
    except paypal.PayPalError as exc:
        raise _paypal_http_error(exc)
    row.quantity = payload.teacher_count
    await db.commit()
    return _to_out(row)


@router.post("/subscriptions/webhook", status_code=status.HTTP_200_OK)
async def paypal_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Called by PayPal. We only trust events whose signature PayPal verifies."""
    event = await request.json()
    headers = {k.lower(): v for k, v in request.headers.items()}
    try:
        verified = await paypal.verify_webhook_signature(headers, event)
    except paypal.PayPalError as exc:
        logger.warning("PayPal webhook verification call failed: %s", exc)
        raise HTTPException(status_code=502, detail="Could not verify webhook with PayPal.")
    if not verified:
        raise HTTPException(status_code=400, detail="Webhook signature check failed.")

    event_type = event.get("event_type", "")
    resource = event.get("resource", {})
    subscription_id = resource.get("id")
    new_status = EVENT_STATUS.get(event_type) or resource.get("status")
    if not subscription_id or not new_status:
        return {"ignored": True}

    result = await db.execute(
        select(PayPalSubscription).where(PayPalSubscription.paypal_subscription_id == subscription_id)
    )
    row = result.scalars().first()
    if row:
        row.status = new_status
        await db.commit()
    return {"ok": True}
