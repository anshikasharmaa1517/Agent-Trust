"""Razorpay Test Mode adapter for Agent Trust Gateway.

Clean adapter interface — all Razorpay-specific code is isolated here.
Uses the official Razorpay Python SDK.

API used: POST /v1/orders (via razorpay.Client().order.create())
Docs: https://razorpay.com/docs/api/orders/create/

Fallback to simulation ONLY when:
  - credentials are genuinely unavailable, OR
  - DEMO_SIMULATION=true is explicitly set
"""
from __future__ import annotations

import os
import logging
import uuid
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Configure logging for this module
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")


def get_connection_status() -> dict:
    """Return a structured health/status indicator for the Razorpay integration.

    Returns:
        dict with keys: connected, mode, detail
    """
    key_id = os.getenv("RAZORPAY_KEY_ID", "").strip()
    key_secret = os.getenv("RAZORPAY_KEY_SECRET", "").strip()
    demo_sim = os.getenv("DEMO_SIMULATION", "false").lower() == "true"

    if not key_id or not key_secret:
        return {
            "connected": False,
            "mode": "SIMULATED",
            "detail": "Credentials not configured. Set RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET in .env",
        }

    if demo_sim:
        return {
            "connected": True,
            "mode": "SIMULATED",
            "detail": "DEMO_SIMULATION flag is enabled. Real API will not be called.",
        }

    # Credentials present and simulation not forced
    return {
        "connected": True,
        "mode": "TEST",
        "detail": f"Razorpay Test Mode connected (key: {key_id[:12]}…)",
    }


def is_razorpay_available() -> bool:
    """Check if Razorpay test mode credentials are configured and simulation is not forced."""
    status = get_connection_status()
    return status["connected"] and status["mode"] == "TEST"


def create_order(amount: float, currency: str = "INR", receipt: str = "",
                 description: str = "", notes: dict | None = None) -> dict:
    """Create a Razorpay order in test mode.

    Execution path:
      1. If real credentials configured and DEMO_SIMULATION != true:
         → call Razorpay POST /v1/orders
         → if API fails, raise (do NOT silently fall back)
      2. Otherwise:
         → return simulated order

    Returns a dict with order details.
    """
    amount_paise = int(amount * 100)  # Razorpay uses paise

    status = get_connection_status()

    if status["mode"] == "TEST":
        logger.info("Razorpay execution started: credentials present, calling POST /v1/orders")
        logger.info(f"  amount={amount_paise} paise, currency={currency}")
        return _create_real_order(amount_paise, currency, receipt, description, notes)

    # Simulation path
    logger.info(f"Razorpay simulation mode: {status['detail']}")
    return _create_simulated_order(amount_paise, currency, receipt, description)


def _create_real_order(amount_paise: int, currency: str, receipt: str,
                       description: str, notes: dict | None) -> dict:
    """Call the real Razorpay Test Mode API.

    Uses: POST https://api.razorpay.com/v1/orders
    Auth: Basic Auth (key_id:key_secret)
    Docs: https://razorpay.com/docs/api/orders/create/
    """
    import razorpay

    key_id = os.getenv("RAZORPAY_KEY_ID")
    key_secret = os.getenv("RAZORPAY_KEY_SECRET")

    client = razorpay.Client(auth=(key_id, key_secret))

    receipt_val = receipt or f"agt_rcpt_{uuid.uuid4().hex[:8]}"
    order_data = {
        "amount": amount_paise,
        "currency": currency,
        "receipt": receipt_val,
        "notes": notes or {},
    }

    logger.info(f"HTTP request: POST /v1/orders  payload={order_data}")

    try:
        order = client.order.create(data=order_data)
    except Exception as e:
        logger.error(f"Razorpay API call FAILED: {e}")
        # Do NOT silently fall back to simulation when real credentials are configured
        raise

    order_id = order["id"]
    order_status = order.get("status", "created")

    logger.info(f"HTTP/API call succeeded.")
    logger.info(f"  Razorpay order ID returned: {order_id}")
    logger.info(f"  Order status: {order_status}")
    logger.info(f"  Amount: {amount_paise} paise ({amount_paise / 100} {currency})")

    result = {
        "razorpay_order_id": order_id,
        "razorpay_payment_id": None,
        "amount": amount_paise / 100,
        "currency": currency,
        "status": order_status,
        "receipt": receipt_val,
        "is_simulated": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    logger.info(f"Transaction persisted: order_id={order_id}, is_simulated=False")
    return result


def _create_simulated_order(amount_paise: int, currency: str,
                            receipt: str, description: str) -> dict:
    """Create a simulated order for demo purposes.

    Only used when credentials are genuinely unavailable or DEMO_SIMULATION=true.
    """
    order_id = f"sim_order_{uuid.uuid4().hex[:16]}"

    logger.info(f"Simulated order created: {order_id}")
    logger.info(f"  ⚠ This is NOT a real Razorpay order.")

    return {
        "razorpay_order_id": order_id,
        "razorpay_payment_id": None,
        "amount": amount_paise / 100,
        "currency": currency,
        "status": "created",
        "receipt": receipt or f"rcpt_{uuid.uuid4().hex[:8]}",
        "is_simulated": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def fetch_order(order_id: str) -> dict | None:
    """Fetch an order from Razorpay. Returns None if unavailable."""
    if not is_razorpay_available():
        return None

    try:
        import razorpay
        client = razorpay.Client(
            auth=(os.getenv("RAZORPAY_KEY_ID"), os.getenv("RAZORPAY_KEY_SECRET"))
        )
        return client.order.fetch(order_id)
    except Exception as e:
        logger.warning(f"Failed to fetch order {order_id}: {e}")
        return None
