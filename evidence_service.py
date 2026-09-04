"""Cryptographic evidence service for Agent Trust Gateway.

Links the full authorization chain and provides integrity verification:
Intent → Authorization → Agent → Proposal → Decision → Razorpay → Outcome
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
from datetime import datetime, timezone

import database as db


def _canonical_json(obj: dict | str) -> str:
    """Return a strictly formatted canonical JSON string for hashing (RFC 8785 style)."""
    if isinstance(obj, str):
        # If already string, assume it's raw text (like raw_intent), just wrap it
        return obj
    return json.dumps(obj, separators=(",", ":"), sort_keys=True)


def _hash(data: dict | str) -> str:
    """SHA-256 hash of canonical JSON data."""
    canonical_data = _canonical_json(data)
    return hashlib.sha256(canonical_data.encode("utf-8")).hexdigest()


def generate_agentic_token(evidence_hash: str, agent_id: str) -> str:
    """Generate a HMAC-SHA256 signed Mandate Token (Agentic Token).
    
    Proves the transaction cleared the local deterministic policy engine.
    """
    secret = os.getenv("GATEWAY_SECRET", "demo-secret-key-123").encode("utf-8")
    payload = f"{agent_id}:{evidence_hash}"
    signature = hmac.new(secret, payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"agt_{payload.encode('utf-8').hex()}_{signature}"



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

    # Hash individual components using structured dictionaries
    intent_hash = _hash({
        "intent_id": intent_id,
        "raw_intent": raw_intent,
        "structured_authorization": structured_auth
    })
    
    decision_hash = _hash({
        "transaction_id": transaction_id,
        "policy_decision": decision
    })

    # Master evidence hash — chain all components securely
    evidence_hash = _hash({
        "intent_hash": intent_hash,
        "agent_id": agent_id,
        "agent_proposal": proposal,
        "decision_hash": decision_hash,
        "razorpay_result": razorpay_result or {},
        "outcome": outcome
    })

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
    # Note: We load the JSON strings back into dicts to use the canonical JSON logic
    recomputed_intent_hash = _hash({
        "intent_id": evidence['intent_id'],
        "raw_intent": evidence['raw_intent'],
        "structured_authorization": json.loads(evidence['structured_authorization']) if evidence['structured_authorization'] else {}
    })
    
    recomputed_decision_hash = _hash({
        "transaction_id": transaction_id,
        "policy_decision": json.loads(evidence['policy_decision']) if evidence['policy_decision'] else {}
    })
    
    recomputed_evidence_hash = _hash({
        "intent_hash": recomputed_intent_hash,
        "agent_id": evidence['agent_id'],
        "agent_proposal": json.loads(evidence['agent_proposal']) if evidence['agent_proposal'] else {},
        "decision_hash": recomputed_decision_hash,
        "razorpay_result": json.loads(evidence['razorpay_result']) if evidence['razorpay_result'] else {},
        "outcome": evidence['outcome']
    })

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
