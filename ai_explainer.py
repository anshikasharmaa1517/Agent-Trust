"""AI explanation service for Agent Trust Gateway.

AI can EXPLAIN a deterministic decision. AI does NOT make the decision.
The explanation is generated FROM the structured deterministic result,
not independently.
"""
from __future__ import annotations

import json
import os
import logging

logger = logging.getLogger(__name__)


def is_ai_available() -> bool:
    """Check if Groq API is configured."""
    return bool(os.getenv("GROQ_API_KEY", "").strip())


def explain_decision(decision_dict: dict, proposal: dict, intent: dict | None = None) -> dict:
    """Generate an AI explanation of a deterministic policy decision.

    The AI explains WHY the decision was made based on structured data.
    It does NOT independently decide the outcome.

    Returns: {"summary": ..., "detail": ..., "recommendation": ..., "confidence": ..., "available": bool}
    """
    if is_ai_available():
        try:
            return _explain_with_ai(decision_dict, proposal, intent)
        except Exception as e:
            logger.warning(f"AI explanation failed: {e}")

    return _explain_deterministic(decision_dict, proposal, intent)


def _explain_with_ai(decision_dict: dict, proposal: dict, intent: dict | None) -> dict:
    """Use Groq to generate a human-readable explanation."""
    import groq

    decision = decision_dict.get("decision", "UNKNOWN")
    checks = decision_dict.get("checks", {})
    reason_code = decision_dict.get("reason_code", "")
    reason_detail = decision_dict.get("reason_detail", "")
    violations = decision_dict.get("violations", [])

    prompt = f"""You are explaining a deterministic payment authorization decision to a business user.

The decision has ALREADY been made by deterministic policy. You are explaining it, not deciding it.

Decision: {decision}
Reason Code: {reason_code}
Reason Detail: {reason_detail}

Transaction Proposal:
- Amount: ₹{proposal.get('amount', 0):,.0f}
- Category: {proposal.get('category', 'N/A')}
- Merchant: {proposal.get('merchant_name', 'N/A')}
- Description: {proposal.get('description', 'N/A')}

Policy Checks: {json.dumps(checks, indent=2)}
Violations: {json.dumps(violations, indent=2)}

{f"Original User Intent: {intent.get('raw_text', 'N/A')}" if intent else ""}
{f"Authorized Max Amount: ₹{intent['max_amount']:,.0f}" if intent and intent.get('max_amount') else "No explicit budget set" if intent else ""}

Respond with valid JSON only:
{{
  "summary": "One sentence summary of the decision",
  "detail": "2-3 sentence detailed explanation of why this decision was made",
  "recommendation": "What should the user or agent do next",
  "confidence": "high"
}}"""

    client = groq.Groq()
    chat_completion = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model="llama3-8b-8192",
    )

    response_text = chat_completion.choices[0].message.content.strip()
    if "```" in response_text:
        parts = response_text.split("```")
        json_part = parts[1] if len(parts) > 1 else parts[0]
        if json_part.startswith("json"):
            json_part = json_part[4:]
        response_text = json_part.strip()

    result = json.loads(response_text)
    result["available"] = True
    return result


def _explain_deterministic(decision_dict: dict, proposal: dict, intent: dict | None) -> dict:
    """Generate explanation without AI using templates."""
    decision = decision_dict.get("decision", "UNKNOWN")
    reason_code = decision_dict.get("reason_code", "")
    amount = proposal.get("amount", 0)

    templates = {
        "AMOUNT_EXCEEDED": {
            "summary": f"Transaction blocked: amount exceeds authorized limit.",
            "detail": (
                f"The user authorized a maximum spend of ₹{intent['max_amount']:,.0f}, "
                f"but the agent proposed a ₹{amount:,.0f} transaction. "
                f"The request exceeds the authorized amount by ₹{amount - intent['max_amount']:,.0f}, "
                f"so the payment was blocked before execution."
            ) if intent and intent.get("max_amount") else f"Amount ₹{amount:,.0f} exceeds the authorized limit.",
            "recommendation": "Reduce the transaction amount or request a higher authorization limit.",
        },
        "AUTHORIZATION_EXPIRED": {
            "summary": "Transaction blocked: authorization has expired.",
            "detail": "The user's purchasing authorization has passed its expiry time. No transactions can be executed against an expired authorization.",
            "recommendation": "Create a new authorization with an updated expiry window.",
        },
        "AUTHORIZATION_REVOKED": {
            "summary": "Transaction blocked: authorization was revoked.",
            "detail": "The user explicitly revoked this authorization. The agent cannot execute transactions against a revoked authorization.",
            "recommendation": "Create a new authorization if the user wishes to continue.",
        },
        "INVALID_AGENT": {
            "summary": "Transaction blocked: agent not registered.",
            "detail": f"Agent '{proposal.get('agent_id', 'unknown')}' is not registered in the system. Only registered agents can propose transactions.",
            "recommendation": "Register the agent before attempting transactions.",
        },
        "PERMISSION_DENIED": {
            "summary": "Transaction blocked: agent lacks required permission.",
            "detail": f"The agent does not have the '{proposal.get('action', 'create_order')}' permission required to execute this transaction.",
            "recommendation": "Grant the required permission to the agent.",
        },
        "CATEGORY_MISMATCH": {
            "summary": "Transaction blocked: category does not match authorization.",
            "detail": f"The agent proposed a '{proposal.get('category', 'unknown')}' purchase, but the authorization only covers '{intent.get('category', 'unknown')}' purchases." if intent else "Category mismatch.",
            "recommendation": "Create a new authorization covering the desired category, or change the purchase category.",
        },
        "MERCHANT_NOT_TRUSTED": {
            "summary": "Transaction blocked: merchant is not in the trusted list.",
            "detail": f"The authorization requires a trusted merchant, but '{proposal.get('merchant_name', 'unknown')}' is not verified as trusted.",
            "recommendation": "Use a trusted merchant or update the merchant's trust status.",
        },
        "REQUIRES_REVIEW": {
            "summary": "Transaction requires human review.",
            "detail": (
                f"The user authorized the purpose but did not establish a spending limit. "
                f"This ₹{amount:,.0f} transaction is high-value and requires human confirmation."
            ),
            "recommendation": "A human should review and explicitly approve or reject this transaction.",
        },
    }

    if decision == "ALLOW":
        return {
            "summary": "Transaction authorized: all policy checks passed.",
            "detail": f"The ₹{amount:,.0f} transaction meets all authorization constraints. The agent has valid permissions, the amount is within limits, and all other checks passed.",
            "recommendation": "Transaction has been executed successfully.",
            "confidence": "high",
            "available": True,
        }

    template = templates.get(reason_code, {
        "summary": f"Transaction {decision.lower()}: {reason_code}",
        "detail": decision_dict.get("reason_detail", "Policy violation detected."),
        "recommendation": "Review the policy decision details.",
    })

    return {
        "summary": template["summary"],
        "detail": template["detail"],
        "recommendation": template["recommendation"],
        "confidence": "high",
        "available": True,
    }
