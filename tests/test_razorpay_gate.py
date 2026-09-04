"""Tests for the Razorpay execution gate security invariant.

CRITICAL INVARIANT:
  BLOCK  → zero Razorpay calls
  REVIEW → zero Razorpay calls
  ALLOW  → exactly one Razorpay call (real or simulated)
"""
import sys
import os
import json
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database as db
from models import TransactionProposal, Decision
import policy_engine
import transaction_service
import razorpay_adapter


@pytest.fixture(autouse=True)
def fresh_db():
    """Reset DB before each test."""
    db.reset_db()
    yield
    if db.DB_PATH.exists():
        os.remove(str(db.DB_PATH))


def _seed_agent(agent_id="agent_test"):
    db.save_agent({
        "agent_id": agent_id,
        "name": "Test Agent",
        "owner_id": "user_test",
        "status": "active",
        "permissions": ["create_order"],
        "spending_limit": 100000,
        "total_spent": 0,
        "transaction_count": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })


def _seed_intent(intent_id="intent_test", max_amount=10000, category="shoes"):
    db.save_intent({
        "intent_id": intent_id,
        "user_id": "user_test",
        "raw_text": "Buy test item",
        "purpose": "purchase",
        "category": category,
        "max_amount": max_amount,
        "currency": "INR",
        "merchant_requirement": None,
        "status": "active",
        "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "parsed_json": "{}",
    })


class TestRazorpayExecutionGate:
    """Test that the security boundary prevents Razorpay calls on BLOCK/REVIEW."""

    @patch("razorpay_adapter.create_order")
    def test_block_never_calls_razorpay(self, mock_create_order):
        """BLOCK transactions must NEVER call Razorpay."""
        _seed_agent()
        _seed_intent(max_amount=8000)

        # Amount exceeds limit → BLOCK
        result = transaction_service.create_full_flow(
            agent_id="agent_test",
            intent_id="intent_test",
            amount=12999.0,
            category="shoes",
        )

        assert result["decision"] == "BLOCK"
        assert result["executed"] == False
        assert result["razorpay_order_id"] is None
        mock_create_order.assert_not_called()

    @patch("razorpay_adapter.create_order")
    def test_review_never_calls_razorpay(self, mock_create_order):
        """REVIEW transactions must NEVER call Razorpay."""
        _seed_agent()
        _seed_intent(max_amount=None)  # No budget → REVIEW for high value

        result = transaction_service.create_full_flow(
            agent_id="agent_test",
            intent_id="intent_test",
            amount=145000.0,
            category="shoes",
        )

        assert result["decision"] == "REVIEW"
        assert result["executed"] == False
        assert result["razorpay_order_id"] is None
        mock_create_order.assert_not_called()

    @patch("razorpay_adapter.create_order")
    def test_allow_calls_razorpay_exactly_once(self, mock_create_order):
        """ALLOW transactions must call Razorpay exactly once."""
        mock_create_order.return_value = {
            "razorpay_order_id": "order_test123",
            "razorpay_payment_id": None,
            "amount": 6999.0,
            "currency": "INR",
            "status": "created",
            "receipt": "test_rcpt",
            "is_simulated": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        _seed_agent()
        _seed_intent(max_amount=10000)

        result = transaction_service.create_full_flow(
            agent_id="agent_test",
            intent_id="intent_test",
            amount=6999.0,
            category="shoes",
        )

        assert result["decision"] == "ALLOW"
        assert result["executed"] == True
        assert result["razorpay_order_id"] == "order_test123"
        mock_create_order.assert_called_once()

    def test_execute_rejects_block_even_when_called_directly(self):
        """Direct call to execute_transaction must reject BLOCK."""
        _seed_agent()
        _seed_intent(max_amount=8000)

        proposal = TransactionProposal(
            transaction_id="txn_direct_block",
            agent_id="agent_test",
            intent_id="intent_test",
            amount=12999.0,
            category="shoes",
        )

        # Evaluate first
        decision_dict = transaction_service.evaluate_transaction(proposal)
        assert decision_dict["decision"] == "BLOCK"

        # Try to execute anyway
        with patch("razorpay_adapter.create_order") as mock_rz:
            exec_result = transaction_service.execute_transaction("txn_direct_block")
            assert exec_result["executed"] == False
            mock_rz.assert_not_called()

    def test_execute_rejects_review_even_when_called_directly(self):
        """Direct call to execute_transaction must reject REVIEW."""
        _seed_agent()
        _seed_intent(max_amount=None)

        proposal = TransactionProposal(
            transaction_id="txn_direct_review",
            agent_id="agent_test",
            intent_id="intent_test",
            amount=145000.0,
            category="shoes",
        )

        decision_dict = transaction_service.evaluate_transaction(proposal)
        assert decision_dict["decision"] == "REVIEW"

        with patch("razorpay_adapter.create_order") as mock_rz:
            exec_result = transaction_service.execute_transaction("txn_direct_review")
            assert exec_result["executed"] == False
            mock_rz.assert_not_called()


class TestRazorpayAdapterHealth:
    """Test the connection status reporting."""

    def test_no_credentials_returns_simulated(self):
        with patch.dict(os.environ, {"RAZORPAY_KEY_ID": "", "RAZORPAY_KEY_SECRET": ""}, clear=False):
            status = razorpay_adapter.get_connection_status()
            assert status["mode"] == "SIMULATED"
            assert status["connected"] == False

    def test_credentials_present_returns_test(self):
        with patch.dict(os.environ, {"RAZORPAY_KEY_ID": "rzp_test_abc123", "RAZORPAY_KEY_SECRET": "secret123"}, clear=False):
            status = razorpay_adapter.get_connection_status()
            assert status["mode"] == "TEST"
            assert status["connected"] == True
            assert "rzp_test_abc" in status["detail"]

    def test_demo_simulation_flag_forces_simulated(self):
        with patch.dict(os.environ, {
            "RAZORPAY_KEY_ID": "rzp_test_abc123",
            "RAZORPAY_KEY_SECRET": "secret123",
            "DEMO_SIMULATION": "true",
        }, clear=False):
            status = razorpay_adapter.get_connection_status()
            assert status["mode"] == "SIMULATED"
            assert status["connected"] == True

    def test_simulated_order_has_sim_prefix(self):
        with patch.dict(os.environ, {"RAZORPAY_KEY_ID": "", "RAZORPAY_KEY_SECRET": ""}, clear=False):
            order = razorpay_adapter.create_order(amount=1000.0)
            assert order["is_simulated"] == True
            assert order["razorpay_order_id"].startswith("sim_order_")


class TestEvidenceForAllDecisions:
    """Verify evidence is created for ALL decision types."""

    def test_allow_creates_evidence(self):
        _seed_agent()
        _seed_intent(max_amount=10000)

        result = transaction_service.create_full_flow(
            agent_id="agent_test",
            intent_id="intent_test",
            amount=5000.0,
            category="shoes",
        )

        evidence = db.get_audit_evidence(result["transaction_id"])
        assert evidence is not None
        assert evidence["outcome"] == "EXECUTED"

    def test_block_creates_evidence(self):
        _seed_agent()
        _seed_intent(max_amount=8000)

        result = transaction_service.create_full_flow(
            agent_id="agent_test",
            intent_id="intent_test",
            amount=12999.0,
            category="shoes",
        )

        evidence = db.get_audit_evidence(result["transaction_id"])
        assert evidence is not None
        assert evidence["outcome"] == "NOT_EXECUTED_BLOCK"

    def test_review_creates_evidence(self):
        _seed_agent()
        _seed_intent(max_amount=None)

        result = transaction_service.create_full_flow(
            agent_id="agent_test",
            intent_id="intent_test",
            amount=145000.0,
            category="shoes",
        )

        evidence = db.get_audit_evidence(result["transaction_id"])
        assert evidence is not None
        assert evidence["outcome"] == "NOT_EXECUTED_REVIEW"
