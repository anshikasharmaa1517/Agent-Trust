"""Transaction service for Agent Trust Gateway.

CRITICAL SECURITY BOUNDARY:
- evaluate_transaction() → runs policy, returns decision, NEVER moves money
- execute_transaction() → only proceeds if latest decision == ALLOW

These are intentionally separate functions. execute MUST reject REVIEW and BLOCK.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

import database as db
from models import TransactionProposal, Decision
import policy_engine
import razorpay_adapter
import evidence_service


def evaluate_transaction(proposal: TransactionProposal) -> dict:
    """Evaluate a transaction proposal against all policies.

    Returns the policy decision dict. NEVER moves money.
    """
    # Save the proposal
    db.save_transaction(proposal.to_dict())

    # Run deterministic policy engine
    decision = policy_engine.evaluate(proposal)
    decision_dict = decision.to_dict()

    # Save decision
    db.save_policy_decision(proposal.transaction_id, decision_dict)

    # Update transaction status
    status_map = {
        Decision.ALLOW: "evaluated",
        Decision.REVIEW: "review",
        Decision.BLOCK: "blocked",
    }
    db.update_transaction_status(proposal.transaction_id, status_map[decision.decision])

    return decision_dict


def execute_transaction(transaction_id: str) -> dict:
    """Execute a transaction ONLY if the latest policy decision is ALLOW.

    MUST reject REVIEW. MUST reject BLOCK.
    Returns execution result dict.
    """
    # Fetch the transaction
    txn = db.get_transaction(transaction_id)
    if not txn:
        return {"error": "Transaction not found", "executed": False}

    # Fetch the latest policy decision
    decision = db.get_policy_decision(transaction_id)
    if not decision:
        return {"error": "No policy evaluation found. Evaluate first.", "executed": False}

    # CRITICAL: Only ALLOW can execute
    if decision["decision"] != Decision.ALLOW.value:
        return {
            "error": f"Cannot execute. Policy decision is {decision['decision']}.",
            "decision": decision["decision"],
            "reason_code": decision.get("reason_code"),
            "executed": False,
        }

    # Call Razorpay adapter
    intent = db.get_intent(txn["intent_id"])
    description = txn.get("description") or (intent.get("raw_text", "") if intent else "")

    rz_result = razorpay_adapter.create_order(
        amount=txn["amount"],
        currency=txn.get("currency", "INR"),
        receipt=f"agt_rcpt_{transaction_id[-8:]}",
        description=description[:100],
        notes={
            "transaction_id": transaction_id,
            "agent_id": txn["agent_id"],
            "intent_id": txn["intent_id"],
        },
    )

    # Save Razorpay result
    db.save_razorpay_transaction(transaction_id, rz_result)

    # Update transaction status
    db.update_transaction_status(transaction_id, "executed")

    # Update agent stats
    agent = db.get_agent(txn["agent_id"])
    if agent:
        agent["total_spent"] = agent.get("total_spent", 0) + txn["amount"]
        agent["transaction_count"] = agent.get("transaction_count", 0) + 1
        db.save_agent(agent)

    # Build evidence
    structured_auth = {}
    if intent:
        structured_auth = {
            "purpose": intent.get("purpose"),
            "category": intent.get("category"),
            "max_amount": intent.get("max_amount"),
            "currency": intent.get("currency"),
            "merchant_requirement": intent.get("merchant_requirement"),
        }

    evidence_service.create_evidence(
        transaction_id=transaction_id,
        intent_id=txn["intent_id"],
        agent_id=txn["agent_id"],
        raw_intent=intent.get("raw_text", "") if intent else "",
        structured_auth=structured_auth,
        proposal=txn,
        decision=decision,
        razorpay_result=rz_result,
        outcome="EXECUTED",
    )

    return {
        "executed": True,
        "transaction_id": transaction_id,
        "razorpay_order_id": rz_result.get("razorpay_order_id"),
        "amount": txn["amount"],
        "currency": txn.get("currency", "INR"),
        "is_simulated": rz_result.get("is_simulated", True),
    }


def create_full_flow(
    agent_id: str,
    intent_id: str,
    amount: float,
    currency: str = "INR",
    category: str | None = None,
    merchant_id: str | None = None,
    merchant_name: str | None = None,
    description: str | None = None,
) -> dict:
    """Convenience: create proposal → evaluate → execute if allowed → evidence.

    Returns a summary dict with all stages.
    """
    txn_id = f"agt_tx_{uuid.uuid4().hex[:8]}"

    proposal = TransactionProposal(
        transaction_id=txn_id,
        agent_id=agent_id,
        intent_id=intent_id,
        amount=amount,
        currency=currency,
        category=category,
        merchant_id=merchant_id,
        merchant_name=merchant_name,
        description=description,
    )

    # Stage 1: Evaluate
    decision_dict = evaluate_transaction(proposal)
    decision_value = decision_dict["decision"]

    result = {
        "transaction_id": txn_id,
        "decision": decision_value,
        "policy_checks": decision_dict.get("checks", {}),
        "reason_code": decision_dict.get("reason_code"),
        "reason_detail": decision_dict.get("reason_detail"),
        "razorpay_order_id": None,
        "executed": False,
        "is_simulated": None,
    }

    # Stage 2: Execute only if ALLOW
    if decision_value == Decision.ALLOW.value:
        exec_result = execute_transaction(txn_id)
        result["executed"] = exec_result.get("executed", False)
        result["razorpay_order_id"] = exec_result.get("razorpay_order_id")
        result["is_simulated"] = exec_result.get("is_simulated")
    else:
        # Build evidence for non-executed transactions too
        intent = db.get_intent(intent_id)
        structured_auth = {}
        if intent:
            structured_auth = {
                "purpose": intent.get("purpose"),
                "category": intent.get("category"),
                "max_amount": intent.get("max_amount"),
                "currency": intent.get("currency"),
                "merchant_requirement": intent.get("merchant_requirement"),
            }

        evidence_service.create_evidence(
            transaction_id=txn_id,
            intent_id=intent_id,
            agent_id=agent_id,
            raw_intent=intent.get("raw_text", "") if intent else "",
            structured_auth=structured_auth,
            proposal=proposal.to_dict(),
            decision=decision_dict,
            razorpay_result=None,
            outcome=f"NOT_EXECUTED_{decision_value}",
        )

    return result
