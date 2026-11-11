"""One-time setup: create the PayPal product and the two monthly billing plans.

Run from apps/lumeneios with PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET set in .env:
    python -m backend.scripts.create_paypal_plans

Copy the printed IDs into PAYPAL_BASE_PLAN_ID and PAYPAL_SEAT_PLAN_ID.
Prices: principal base fee and per-teacher seat fee, in USD.
"""
import asyncio

from backend.app.services.paypal import BASE_PRICE, SEAT_PRICE, _request, get_access_token


def _plan_body(product_id: str, name: str, price: str) -> dict:
    return {
        "product_id": product_id,
        "name": name,
        "description": name,
        "status": "ACTIVE",
        "quantity_supported": True,
        "billing_cycles": [
            {
                "frequency": {"interval_unit": "MONTH", "interval_count": 1},
                "tenure_type": "REGULAR",
                "sequence": 1,
                "total_cycles": 0,
                "pricing_scheme": {"fixed_price": {"value": price, "currency_code": "USD"}},
            }
        ],
        "payment_preferences": {
            "auto_bill_outstanding": True,
            "setup_fee_failure_action": "CANCEL",
            "payment_failure_threshold": 3,
        },
    }


async def main() -> None:
    token = await get_access_token()
    product = await _request(
        "POST", "/v1/catalogs/products",
        json={"name": "LumenEIOS School Subscription", "type": "SERVICE", "category": "SOFTWARE"},
        bearer=token,
    )
    base = await _request("POST", "/v1/billing/plans", json=_plan_body(product["id"], "School base", BASE_PRICE), bearer=token)
    seats = await _request("POST", "/v1/billing/plans", json=_plan_body(product["id"], "Teacher seat", SEAT_PRICE), bearer=token)
    print("PAYPAL_BASE_PLAN_ID=" + base["id"])
    print("PAYPAL_SEAT_PLAN_ID=" + seats["id"])


if __name__ == "__main__":
    asyncio.run(main())
