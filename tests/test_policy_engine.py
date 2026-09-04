"""Tests for the deterministic policy engine.

Test invariant: NO transaction may execute unless policy decision == ALLOW.
"""
import sys
import os
import pytest
from datetime import datetime, timezone, timedelta

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database as db
from models import TransactionProposal, Decision, AgentStatus, IntentStatus
import policy_engine
import transaction_service


@pytest.fixture(autouse=True)
def fresh_db():
    """Reset DB before each test."""
    db.reset_db()
    yield
    # Cleanup
    if db.DB_PATH.exists():
        os.remove(str(db.DB_PATH))


def _seed_agent(agent_id="agent_test", status="active", permissions=None):
    db.save_agent({
        "agent_id": agent_id,
        "name": "Test Agent",
        "owner_id": "user_test",
        "status": status,
        "permissions": permissions or ["create_order"],
        "spending_limit": 100000,
        "total_spent": 0,
        "transaction_count": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })


def _seed_intent(intent_id="intent_test", max_amount=10000, category="shoes",
                 status="active", expires_at=None, merchant_requirement=None):
    if expires_at is None:
        expires_at = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    db.save_intent({
        "intent_id": intent_id,
        "user_id": "user_test",
        "raw_text": "Buy test item",
        "purpose": "purchase",
        "category": category,
        "max_amount": max_amount,
        "currency": "INR",
        "merchant_requirement": merchant_requirement,
        "status": status,
        "expires_at": expires_at,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "parsed_json": "{}",
    })


def _make_proposal(amount=5000, category="shoes", agent_id="agent_test",
                   intent_id="intent_test", merchant_name=None):
    return TransactionProposal(
        transaction_id=f"txn_test_{amount}",
        agent_id=agent_id,
        intent_id=intent_id,
        amount=amount,
        category=category,
        merchant_name=merchant_name,
    )


# ── Amount limit tests ──

def test_amount_within_limit():
    _seed_agent()
    _seed_intent(max_amount=10000)
    proposal = _make_proposal(amount=5000)
    decision = policy_engine.evaluate(proposal)
    assert decision.decision == Decision.ALLOW


def test_amount_exceeds_limit():
    _seed_agent()
    _seed_intent(max_amount=8000)
    proposal = _make_proposal(amount=12999)
    decision = policy_engine.evaluate(proposal)
    assert decision.decision == Decision.BLOCK
    assert any(c.name == "amount_limit" and c.result.value == "FAIL" for c in decision.checks)


def test_amount_at_exact_limit():
    _seed_agent()
    _seed_intent(max_amount=8000)
    proposal = _make_proposal(amount=8000)
    decision = policy_engine.evaluate(proposal)
    assert decision.decision == Decision.ALLOW


# ── Expiry tests ──

def test_expired_authorization():
    _seed_agent()
    _seed_intent(expires_at=(datetime.now(timezone.utc) - timedelta(hours=1)).isoformat())
    proposal = _make_proposal(amount=5000)
    decision = policy_engine.evaluate(proposal)
    assert decision.decision == Decision.BLOCK
    assert any(c.name == "intent_expiry" and c.result.value == "FAIL" for c in decision.checks)


def test_valid_expiry():
    _seed_agent()
    _seed_intent(expires_at=(datetime.now(timezone.utc) + timedelta(hours=24)).isoformat())
    proposal = _make_proposal(amount=5000)
    decision = policy_engine.evaluate(proposal)
    assert decision.decision == Decision.ALLOW


# ── Revoked authorization ──

def test_revoked_authorization():
    _seed_agent()
    _seed_intent(status="revoked")
    proposal = _make_proposal(amount=5000)
    decision = policy_engine.evaluate(proposal)
    assert decision.decision == Decision.BLOCK


# ── Invalid agent ──

def test_invalid_agent():
    _seed_intent()
    proposal = _make_proposal(agent_id="nonexistent_agent")
    decision = policy_engine.evaluate(proposal)
    assert decision.decision == Decision.BLOCK


def test_inactive_agent():
    _seed_agent(status="inactive")
    _seed_intent()
    proposal = _make_proposal()
    decision = policy_engine.evaluate(proposal)
    assert decision.decision == Decision.BLOCK


# ── Missing permission ──

def test_missing_permission():
    _seed_agent(permissions=["read_only"])
    _seed_intent()
    proposal = _make_proposal()
    decision = policy_engine.evaluate(proposal)
    assert decision.decision == Decision.BLOCK


# ── Category mismatch ──

def test_category_mismatch():
    _seed_agent()
    _seed_intent(category="shoes")
    proposal = _make_proposal(category="electronics")
    decision = policy_engine.evaluate(proposal)
    assert decision.decision == Decision.BLOCK


def test_category_match():
    _seed_agent()
    _seed_intent(category="shoes")
    proposal = _make_proposal(category="running_shoes")
    decision = policy_engine.evaluate(proposal)
    assert decision.decision == Decision.ALLOW  # fuzzy match


# ── Merchant mismatch ──

def test_merchant_not_trusted():
    _seed_agent()
    _seed_intent(merchant_requirement="trusted")
    proposal = _make_proposal(merchant_name="Shady Shop")
    decision = policy_engine.evaluate(proposal)
    assert decision.decision == Decision.BLOCK


def test_merchant_trusted():
    _seed_agent()
    _seed_intent(merchant_requirement="trusted")
    proposal = _make_proposal(merchant_name="Trusted Store")
    decision = policy_engine.evaluate(proposal)
    assert decision.decision == Decision.ALLOW


# ── Valid full transaction ──

def test_valid_transaction_all_checks_pass():
    _seed_agent()
    _seed_intent(max_amount=10000, category="shoes")
    proposal = _make_proposal(amount=6999, category="shoes")
    decision = policy_engine.evaluate(proposal)
    assert decision.decision == Decision.ALLOW
    assert all(c.result.value == "PASS" for c in decision.checks)


# ── Ambiguous intent (no budget, high value) ──

def test_ambiguous_no_budget_high_value():
    _seed_agent()
    _seed_intent(max_amount=None)  # No explicit budget
    proposal = _make_proposal(amount=145000)  # High value
    decision = policy_engine.evaluate(proposal)
    assert decision.decision == Decision.REVIEW


# ── Execute safety: never execute BLOCK/REVIEW ──

def test_execute_rejects_block():
    _seed_agent()
    _seed_intent(max_amount=8000)
    proposal = _make_proposal(amount=12999)
    db.save_transaction(proposal.to_dict())
    decision = policy_engine.evaluate(proposal)
    db.save_policy_decision(proposal.transaction_id, decision.to_dict())
    db.update_transaction_status(proposal.transaction_id, "blocked")

    result = transaction_service.execute_transaction(proposal.transaction_id)
    assert result["executed"] == False


def test_execute_rejects_review():
    _seed_agent()
    _seed_intent(max_amount=None)
    proposal = _make_proposal(amount=145000)
    db.save_transaction(proposal.to_dict())
    decision = policy_engine.evaluate(proposal)
    db.save_policy_decision(proposal.transaction_id, decision.to_dict())
    db.update_transaction_status(proposal.transaction_id, "review")

    result = transaction_service.execute_transaction(proposal.transaction_id)
    assert result["executed"] == False
