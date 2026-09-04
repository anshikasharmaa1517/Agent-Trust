"""Deterministic policy engine for Razorpay Agent Trust Gateway.

This is the CRITICAL security boundary. The policy engine:
- Runs 10 deterministic checks
- Returns ALLOW / REVIEW / BLOCK
- Has NO AI dependency
- Cannot be overridden by LLM output

If deterministic policy says BLOCK, the transaction MUST NOT execute.
"""
from __future__ import annotations

from datetime import datetime, timezone
from models import (
    TransactionProposal, PolicyDecision, PolicyCheck, Decision, CheckResult,
    AgentStatus, IntentStatus,
)
import database as db


def evaluate(proposal: TransactionProposal) -> PolicyDecision:
    """Run all policy checks against a transaction proposal. Returns a PolicyDecision."""
    checks: list[PolicyCheck] = []
    has_block = False
    has_warn = False

    # ── 1. Agent exists ──
    agent = db.get_agent(proposal.agent_id)
    if not agent:
        checks.append(PolicyCheck("agent_exists", CheckResult.FAIL, f"Agent '{proposal.agent_id}' not found"))
        has_block = True
    else:
        checks.append(PolicyCheck("agent_exists", CheckResult.PASS, f"Agent '{agent['name']}' found"))

    # ── 2. Agent is active ──
    if agent:
        if agent["status"] == AgentStatus.ACTIVE.value:
            checks.append(PolicyCheck("agent_active", CheckResult.PASS, "Agent is active"))
        else:
            checks.append(PolicyCheck("agent_active", CheckResult.FAIL, f"Agent status: {agent['status']}"))
            has_block = True
    else:
        checks.append(PolicyCheck("agent_active", CheckResult.FAIL, "Agent not found"))
        has_block = True

    # ── 3. Agent has permission ──
    if agent:
        perms = agent.get("permissions", [])
        if proposal.action in perms:
            checks.append(PolicyCheck("agent_permission", CheckResult.PASS, f"Permission '{proposal.action}' granted"))
        else:
            checks.append(PolicyCheck("agent_permission", CheckResult.FAIL, f"Permission '{proposal.action}' not in {perms}"))
            has_block = True
    else:
        checks.append(PolicyCheck("agent_permission", CheckResult.FAIL, "Agent not found"))
        has_block = True

    # ── 4. Intent exists ──
    intent = db.get_intent(proposal.intent_id)
    if not intent:
        checks.append(PolicyCheck("intent_exists", CheckResult.FAIL, f"Intent '{proposal.intent_id}' not found"))
        has_block = True
    else:
        checks.append(PolicyCheck("intent_exists", CheckResult.PASS, f"Intent '{proposal.intent_id}' found"))

    # ── 5. Intent is active ──
    if intent:
        if intent["status"] == IntentStatus.ACTIVE.value:
            checks.append(PolicyCheck("intent_active", CheckResult.PASS, "Authorization is active"))
        elif intent["status"] == IntentStatus.REVOKED.value:
            checks.append(PolicyCheck("intent_active", CheckResult.FAIL, "Authorization has been revoked"))
            has_block = True
        else:
            checks.append(PolicyCheck("intent_active", CheckResult.FAIL, f"Authorization status: {intent['status']}"))
            has_block = True
    else:
        checks.append(PolicyCheck("intent_active", CheckResult.FAIL, "Intent not found"))
        has_block = True

    # ── 6. Intent not expired ──
    if intent:
        expires = intent.get("expires_at")
        if expires:
            try:
                exp_dt = datetime.fromisoformat(expires)
                if exp_dt.tzinfo is None:
                    exp_dt = exp_dt.replace(tzinfo=timezone.utc)
                now = datetime.now(timezone.utc)
                if now > exp_dt:
                    checks.append(PolicyCheck("intent_expiry", CheckResult.FAIL, f"Authorization expired at {expires}"))
                    has_block = True
                else:
                    checks.append(PolicyCheck("intent_expiry", CheckResult.PASS, f"Expires {expires}"))
            except (ValueError, TypeError):
                checks.append(PolicyCheck("intent_expiry", CheckResult.WARN, "Could not parse expiry date"))
                has_warn = True
        else:
            checks.append(PolicyCheck("intent_expiry", CheckResult.PASS, "No expiry set"))
    else:
        checks.append(PolicyCheck("intent_expiry", CheckResult.FAIL, "Intent not found"))
        has_block = True

    # ── 7. Amount within limit ──
    if intent:
        max_amount = intent.get("max_amount")
        if max_amount is not None:
            if proposal.amount <= max_amount:
                checks.append(PolicyCheck("amount_limit", CheckResult.PASS,
                    f"₹{proposal.amount:,.0f} ≤ ₹{max_amount:,.0f} limit"))
            else:
                checks.append(PolicyCheck("amount_limit", CheckResult.FAIL,
                    f"₹{proposal.amount:,.0f} exceeds ₹{max_amount:,.0f} limit"))
                has_block = True
        else:
            # No explicit budget — high-value check
            if proposal.amount > 50000:
                checks.append(PolicyCheck("amount_limit", CheckResult.WARN,
                    f"No explicit budget set. ₹{proposal.amount:,.0f} is a high-value transaction"))
                has_warn = True
            else:
                checks.append(PolicyCheck("amount_limit", CheckResult.PASS,
                    f"No explicit limit. Amount ₹{proposal.amount:,.0f} within reasonable range"))
    else:
        checks.append(PolicyCheck("amount_limit", CheckResult.FAIL, "Intent not found"))
        has_block = True

    # ── 8. Currency matches ──
    if intent:
        intent_currency = intent.get("currency", "INR")
        if proposal.currency == intent_currency:
            checks.append(PolicyCheck("currency_match", CheckResult.PASS,
                f"Currency {proposal.currency} matches"))
        else:
            checks.append(PolicyCheck("currency_match", CheckResult.FAIL,
                f"Proposed {proposal.currency} ≠ authorized {intent_currency}"))
            has_block = True
    else:
        checks.append(PolicyCheck("currency_match", CheckResult.FAIL, "Intent not found"))
        has_block = True

    # ── 9. Category matches ──
    if intent:
        intent_category = intent.get("category")
        if intent_category:
            # Fuzzy match: check if proposal category contains or is contained by intent category
            prop_cat = (proposal.category or "").lower()
            int_cat = intent_category.lower()
            if prop_cat and (int_cat in prop_cat or prop_cat in int_cat or prop_cat == int_cat):
                checks.append(PolicyCheck("category_match", CheckResult.PASS,
                    f"Category '{proposal.category}' matches '{intent_category}'"))
            elif not prop_cat:
                checks.append(PolicyCheck("category_match", CheckResult.WARN,
                    f"No category specified in proposal; intent requires '{intent_category}'"))
                has_warn = True
            else:
                checks.append(PolicyCheck("category_match", CheckResult.FAIL,
                    f"Category '{proposal.category}' ≠ authorized '{intent_category}'"))
                has_block = True
        else:
            checks.append(PolicyCheck("category_match", CheckResult.PASS,
                "No category restriction in authorization"))
    else:
        checks.append(PolicyCheck("category_match", CheckResult.FAIL, "Intent not found"))
        has_block = True

    # ── 10. Merchant satisfies policy ──
    if intent:
        merchant_req = intent.get("merchant_requirement")
        if merchant_req and merchant_req.lower() == "trusted":
            # For demo, we accept merchants with "trusted" in name or specific merchant IDs
            mn = (proposal.merchant_name or "").lower()
            if "trusted" in mn or proposal.merchant_id in ("merchant_001", "merchant_002"):
                checks.append(PolicyCheck("merchant_policy", CheckResult.PASS,
                    f"Merchant '{proposal.merchant_name}' is trusted"))
            elif not proposal.merchant_name:
                checks.append(PolicyCheck("merchant_policy", CheckResult.WARN,
                    "No merchant specified; authorization requires trusted merchant"))
                has_warn = True
            else:
                checks.append(PolicyCheck("merchant_policy", CheckResult.FAIL,
                    f"Merchant '{proposal.merchant_name}' is not in trusted list"))
                has_block = True
        else:
            checks.append(PolicyCheck("merchant_policy", CheckResult.PASS,
                "No merchant restriction in authorization"))
    else:
        checks.append(PolicyCheck("merchant_policy", CheckResult.FAIL, "Intent not found"))
        has_block = True

    # ── Final decision ──
    if has_block:
        # Find the first failing check for the reason code
        first_fail = next((c for c in checks if c.result == CheckResult.FAIL), None)
        reason_code = _reason_code_from_check(first_fail.name if first_fail else "UNKNOWN")
        decision = PolicyDecision(
            decision=Decision.BLOCK,
            checks=checks,
            reason_code=reason_code,
            reason_detail=first_fail.detail if first_fail else "Policy violation detected",
        )
    elif has_warn:
        first_warn = next((c for c in checks if c.result == CheckResult.WARN), None)
        decision = PolicyDecision(
            decision=Decision.REVIEW,
            checks=checks,
            reason_code="REQUIRES_REVIEW",
            reason_detail=first_warn.detail if first_warn else "Transaction requires human review",
        )
    else:
        decision = PolicyDecision(
            decision=Decision.ALLOW,
            checks=checks,
        )

    return decision


def _reason_code_from_check(check_name: str) -> str:
    """Map check name to a reason code."""
    mapping = {
        "agent_exists": "INVALID_AGENT",
        "agent_active": "AGENT_INACTIVE",
        "agent_permission": "PERMISSION_DENIED",
        "intent_exists": "INVALID_AUTHORIZATION",
        "intent_active": "AUTHORIZATION_REVOKED",
        "intent_expiry": "AUTHORIZATION_EXPIRED",
        "amount_limit": "AMOUNT_EXCEEDED",
        "currency_match": "CURRENCY_MISMATCH",
        "category_match": "CATEGORY_MISMATCH",
        "merchant_policy": "MERCHANT_NOT_TRUSTED",
    }
    return mapping.get(check_name, "POLICY_VIOLATION")
