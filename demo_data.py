"""Demo data seeder for Agent Trust Gateway.

Seeds three demo scenarios on startup:
1. ALLOW  — "Buy running shoes under ₹8,000" → ₹6,999 → all pass → Razorpay order
2. BLOCK  — Same auth → ₹12,999 → AMOUNT_EXCEEDED → no Razorpay
3. REVIEW — "Buy me a good work laptop" (no budget) → ₹1,45,000 → needs human review
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone, timedelta

import database as db
from models import AgentStatus, IntentStatus
import transaction_service


def is_seeded() -> bool:
    """Check if demo data already exists."""
    agents = db.list_agents()
    return len(agents) > 0


def seed_demo_data():
    """Seed all demo agents, intents, and run the three demo scenarios."""
    if is_seeded():
        return

    now = datetime.now(timezone.utc)

    # ── Agents ──
    agents = [
        {
            "agent_id": "agent_001",
            "name": "IT Asset Auto-Provisioner",
            "owner_id": "user_001",
            "status": AgentStatus.ACTIVE.value,
            "permissions": ["create_order"],
            "spending_limit": 100000.0,
            "total_spent": 0.0,
            "transaction_count": 0,
            "created_at": (now - timedelta(days=7)).isoformat(),
        },
        {
            "agent_id": "agent_002",
            "name": "DevOps Cloud Auto-Scaler",
            "owner_id": "user_001",
            "status": AgentStatus.ACTIVE.value,
            "permissions": ["create_order"],
            "spending_limit": 500000.0,
            "total_spent": 0.0,
            "transaction_count": 0,
            "created_at": (now - timedelta(days=5)).isoformat(),
        },
        {
            "agent_id": "agent_003",
            "name": "Sales Travel Copilot",
            "owner_id": "user_002",
            "status": AgentStatus.INACTIVE.value,
            "permissions": ["create_order"],
            "spending_limit": 200000.0,
            "total_spent": 0.0,
            "transaction_count": 0,
            "created_at": (now - timedelta(days=3)).isoformat(),
        },
    ]
    for a in agents:
        db.save_agent(a)

    # ── Intents ──
    intents = [
        {
            "intent_id": "intent_001",
            "user_id": "user_001",
            "raw_text": "Buy running shoes under ₹8,000 from a trusted seller.",
            "purpose": "purchase",
            "category": "running_shoes",
            "max_amount": 8000.0,
            "currency": "INR",
            "merchant_requirement": "trusted",
            "status": IntentStatus.ACTIVE.value,
            "expires_at": (now + timedelta(hours=24)).isoformat(),
            "created_at": (now - timedelta(minutes=30)).isoformat(),
            "parsed_json": json.dumps({
                "purpose": "purchase",
                "category": "running_shoes",
                "max_amount": 8000,
                "currency": "INR",
                "merchant_requirement": "trusted",
            }),
        },
        {
            "intent_id": "intent_002",
            "user_id": "user_001",
            "raw_text": "Buy me a good work laptop.",
            "purpose": "purchase",
            "category": "laptop",
            "max_amount": None,  # No explicit budget
            "currency": "INR",
            "merchant_requirement": None,
            "status": IntentStatus.ACTIVE.value,
            "expires_at": (now + timedelta(hours=24)).isoformat(),
            "created_at": (now - timedelta(minutes=20)).isoformat(),
            "parsed_json": json.dumps({
                "purpose": "purchase",
                "category": "laptop",
                "max_amount": None,
                "currency": "INR",
                "merchant_requirement": None,
            }),
        },
        {
            "intent_id": "intent_003",
            "user_id": "user_001",
            "raw_text": "Buy a laptop for work under ₹70,000 from a trusted seller.",
            "purpose": "purchase",
            "category": "laptop",
            "max_amount": 70000.0,
            "currency": "INR",
            "merchant_requirement": "trusted",
            "status": IntentStatus.ACTIVE.value,
            "expires_at": (now + timedelta(hours=24)).isoformat(),
            "created_at": (now - timedelta(minutes=15)).isoformat(),
            "parsed_json": json.dumps({
                "purpose": "purchase",
                "category": "laptop",
                "max_amount": 70000,
                "currency": "INR",
                "merchant_requirement": "trusted",
            }),
        },
    ]
    for intent in intents:
        db.save_intent(intent)

    # ── Demo Scenario 1: ALLOW ──
    # Running shoes ₹6,999 — within budget, trusted merchant → ALLOW
    transaction_service.create_full_flow(
        agent_id="agent_001",
        intent_id="intent_001",
        amount=6999.0,
        currency="INR",
        category="running_shoes",
        merchant_id="merchant_001",
        merchant_name="Trusted Sports Store",
        description="Nike Air Zoom Pegasus 41",
    )

    # ── Demo Scenario 2: BLOCK ──
    # Running shoes ₹12,999 — exceeds ₹8,000 budget → BLOCK
    transaction_service.create_full_flow(
        agent_id="agent_001",
        intent_id="intent_001",
        amount=12999.0,
        currency="INR",
        category="running_shoes",
        merchant_id="merchant_001",
        merchant_name="Trusted Sports Store",
        description="Nike Vaporfly Next% 3",
    )

    # ── Demo Scenario 3: REVIEW ──
    # Work laptop ₹1,45,000 — no explicit budget, high value → REVIEW
    transaction_service.create_full_flow(
        agent_id="agent_001",
        intent_id="intent_002",
        amount=145000.0,
        currency="INR",
        category="laptop",
        merchant_id="merchant_002",
        merchant_name="Electronics World",
        description="MacBook Pro M4 16-inch",
    )

    # ── Demo Scenario 4: ALLOW (laptop within budget) ──
    # Laptop ₹64,990 within ₹70,000 budget → ALLOW
    transaction_service.create_full_flow(
        agent_id="agent_001",
        intent_id="intent_003",
        amount=64990.0,
        currency="INR",
        category="laptop",
        merchant_id="merchant_001",
        merchant_name="Trusted Electronics",
        description="Dell Latitude 5540",
    )
