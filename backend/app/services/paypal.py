"""Thin async client for the PayPal REST API (subscriptions and webhooks).

Based on the request flow in the standalone paypal learning scripts:
get an OAuth token with client credentials, then call the billing endpoints.
"""
from typing import Any, Dict, Optional

import httpx

from backend.app.core.config import settings

SANDBOX_BASE = "https://api-m.sandbox.paypal.com"
LIVE_BASE = "https://api-m.paypal.com"
BASE_PRICE = "20.00"
SEAT_PRICE = "5.00"


class PayPalError(Exception):
    def __init__(self, status_code: int, message: str, details: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.details = details


def _base_url() -> str:
    return LIVE_BASE if settings.PAYPAL_ENV.lower() == "live" else SANDBOX_BASE


def is_configured() -> bool:
    return bool(settings.PAYPAL_CLIENT_ID and settings.PAYPAL_CLIENT_SECRET.get_secret_value())


async def _request(method: str, path: str, *, json: Optional[dict] = None, data: Optional[dict] = None,
                   auth: Optional[tuple] = None, bearer: Optional[str] = None) -> Dict[str, Any]:
    headers: Dict[str, str] = {}
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    async with httpx.AsyncClient(base_url=_base_url(), timeout=20.0) as client:
        response = await client.request(method, path, json=json, data=data, auth=auth, headers=headers)
    try:
        body = response.json() if response.content else {}
    except ValueError:
        body = {}
    if response.status_code >= 400:
        raise PayPalError(
            response.status_code,
            body.get("message") or body.get("error_description") or "PayPal request failed",
            body.get("details"),
        )
    return body


async def get_access_token() -> str:
    if not is_configured():
        raise PayPalError(503, "PayPal is not configured on this server.")
    body = await _request(
        "POST", "/v1/oauth2/token",
        data={"grant_type": "client_credentials"},
        auth=(settings.PAYPAL_CLIENT_ID, settings.PAYPAL_CLIENT_SECRET.get_secret_value()),
    )
    return body["access_token"]


async def create_subscription(plan_id: str, quantity: int, return_url: str, cancel_url: str) -> Dict[str, Any]:
    token = await get_access_token()
    payload = {
        "plan_id": plan_id,
        "quantity": str(quantity),
        "application_context": {
            "return_url": return_url,
            "cancel_url": cancel_url,
            "user_action": "SUBSCRIBE_NOW",
        },
    }
    return await _request("POST", "/v1/billing/subscriptions", json=payload, bearer=token)


async def get_subscription(subscription_id: str) -> Dict[str, Any]:
    token = await get_access_token()
    return await _request("GET", f"/v1/billing/subscriptions/{subscription_id}", bearer=token)


async def revise_quantity(subscription_id: str, quantity: int) -> Dict[str, Any]:
    """Change the seat count on an existing subscription. Proration follows the plan settings."""
    token = await get_access_token()
    return await _request(
        "POST", f"/v1/billing/subscriptions/{subscription_id}/revise",
        json={"quantity": str(quantity)}, bearer=token,
    )


async def verify_webhook_signature(headers: Dict[str, str], event: Dict[str, Any]) -> bool:
    """Ask PayPal whether a webhook really came from PayPal for our webhook ID."""
    if not settings.PAYPAL_WEBHOOK_ID:
        return False
    token = await get_access_token()
    payload = {
        "auth_algo": headers.get("paypal-auth-algo"),
        "cert_url": headers.get("paypal-cert-url"),
        "transmission_id": headers.get("paypal-transmission-id"),
        "transmission_sig": headers.get("paypal-transmission-sig"),
        "transmission_time": headers.get("paypal-transmission-time"),
        "webhook_id": settings.PAYPAL_WEBHOOK_ID,
        "webhook_event": event,
    }
    body = await _request("POST", "/v1/notifications/verify-webhook-signature", json=payload, bearer=token)
    return body.get("verification_status") == "SUCCESS"
