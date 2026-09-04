"""Cryptographic evidence service for Agent Trust Gateway.

Links the full authorization chain and provides integrity verification:
Intent → Authorization → Agent → Proposal → Decision → Razorpay → Outcome
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

import database as db


def _hash(data: str) -> str:
    """SHA-256 hash of a string."""
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def create_evidence(
    transaction_id: str,
    intent_id: str,
    agent_id: str,
    raw_intent: str,
    structured_auth: dict,
    proposal: dict,
    decision: dict,
    razorpay_result: dict | None,
    outcome: str,
) -> dict:
    """Build and store an evidence record with cryptographic hashes."""

    structured_str = json.dumps(structured_auth, sort_keys=True, default=str)
    proposal_str = json.dumps(proposal, sort_keys=True, default=str)
    decision_str = json.dumps(decision, sort_keys=True, default=str)
    razorpay_str = json.dumps(razorpay_result, sort_keys=True, default=str) if razorpay_result else "{}"

    # Hash individual components
    intent_hash = _hash(f"{intent_id}:{raw_intent}:{structured_str}")
    decision_hash = _hash(f"{transaction_id}:{decision_str}")

    # Master evidence hash — chain all components
    chain = f"{intent_hash}|{agent_id}|{proposal_str}|{decision_hash}|{razorpay_str}|{outcome}"
    evidence_hash = _hash(chain)

    evidence = {
        "transaction_id": transaction_id,
        "intent_id": intent_id,
        "agent_id": agent_id,
        "raw_intent": raw_intent,
        "structured_authorization": structured_str,
        "agent_proposal": proposal_str,
        "policy_decision": decision_str,
        "razorpay_result": razorpay_str,
        "outcome": outcome,
        "intent_hash": intent_hash,
        "decision_hash": decision_hash,
        "evidence_hash": evidence_hash,
        "verified": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    db.save_audit_evidence(evidence)
    return evidence


def verify_evidence(transaction_id: str) -> tuple[bool, dict]:
    """Recompute evidence hash and verify integrity.

    Returns (is_valid, details_dict).
    """
    evidence = db.get_audit_evidence(transaction_id)
    if not evidence:
        return False, {"error": "Evidence not found"}

    # Recompute hashes from stored data
    recomputed_intent_hash = _hash(
        f"{evidence['intent_id']}:{evidence['raw_intent']}:{evidence['structured_authorization']}"
    )
    recomputed_decision_hash = _hash(
        f"{transaction_id}:{evidence['policy_decision']}"
    )
    chain = (
        f"{recomputed_intent_hash}|{evidence['agent_id']}|{evidence['agent_proposal']}"
        f"|{recomputed_decision_hash}|{evidence['razorpay_result']}|{evidence['outcome']}"
    )
    recomputed_evidence_hash = _hash(chain)

    intent_ok = recomputed_intent_hash == evidence["intent_hash"]
    decision_ok = recomputed_decision_hash == evidence["decision_hash"]
    evidence_ok = recomputed_evidence_hash == evidence["evidence_hash"]

    is_valid = intent_ok and decision_ok and evidence_ok

    # Update verification status
    evidence["verified"] = is_valid
    db.save_audit_evidence(evidence)

    return is_valid, {
        "intent_hash_valid": intent_ok,
        "decision_hash_valid": decision_ok,
        "evidence_hash_valid": evidence_ok,
        "stored_evidence_hash": evidence["evidence_hash"],
        "recomputed_evidence_hash": recomputed_evidence_hash,
        "overall_valid": is_valid,
    }
