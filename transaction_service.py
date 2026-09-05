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

    # Generate Cryptographic Mandate Token (Agentic Token)
    # Proves to Razorpay that this transaction cleared the deterministic policy engine
    decision_hash = evidence_service._hash({
        "transaction_id": transaction_id,
        "policy_decision": decision
    })
    agentic_token = evidence_service.generate_agentic_token(decision_hash, txn["agent_id"])

    rz_result = razorpay_adapter.create_order(
        amount=txn["amount"],
        currency=txn.get("currency", "INR"),
        receipt=f"agt_rcpt_{transaction_id[-8:]}",
        description=description[:100],
        notes={
            "transaction_id": transaction_id,
            "agent_id": txn["agent_id"],
            "intent_id": txn["intent_id"],
            "agentic_token": agentic_token,  # <--- AP2 / Mastercard style token
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

import crypto_utils

def create_full_flow(
    agent_id: str,
    intent_id: str,
    amount: float,
    intent_jwt: str = None,
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

    # AP2-style cryptographic verification
    if intent_jwt:
        decoded_intent = crypto_utils.verify_intent_token(intent_jwt)
        if not decoded_intent:
            return {
                "transaction_id": txn_id,
                "decision": Decision.BLOCK.value,
                "reason_code": "INVALID_JWT",
                "reason_detail": "The cryptographic intent signature is missing or invalid.",
                "executed": False,
            }
        # In a real system, we'd verify that decoded_intent matches intent_id in DB here.

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


def approve_transaction(transaction_id: str, reason: str = "Manual approval by admin") -> dict:
    """Manually approve a transaction in REVIEW state and execute it."""
    existing_dec = db.get_policy_decision(transaction_id)
    if not existing_dec or existing_dec["decision"] != Decision.REVIEW.value:
        return {"error": "Can only approve transactions in REVIEW state."}
    
    new_decision = {
        "decision": Decision.ALLOW.value,
        "checks": existing_dec.get("checks", {}),
        "reason_code": "MANUAL_APPROVAL",
        "reason_detail": reason,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
    }
    db.save_policy_decision(transaction_id, new_decision)
    db.update_transaction_status(transaction_id, "evaluated")
    
    return execute_transaction(transaction_id)


def reject_transaction(transaction_id: str, reason: str = "Manual rejection by admin") -> dict:
    """Manually reject a transaction in REVIEW state."""
    existing_dec = db.get_policy_decision(transaction_id)
    if not existing_dec or existing_dec["decision"] != Decision.REVIEW.value:
        return {"error": "Can only reject transactions in REVIEW state."}
    
    new_decision = {
        "decision": Decision.BLOCK.value,
        "checks": existing_dec.get("checks", {}),
        "reason_code": "MANUAL_REJECTION",
        "reason_detail": reason,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
    }
    db.save_policy_decision(transaction_id, new_decision)
    db.update_transaction_status(transaction_id, "blocked")
    
    txn = db.get_transaction(transaction_id)
    intent = db.get_intent(txn["intent_id"]) if txn else None
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
        decision=new_decision,
        razorpay_result=None,
        outcome="NOT_EXECUTED_BLOCK",
    )
    return {"executed": False, "status": "blocked", "transaction_id": transaction_id}
