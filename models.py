"""Data models for Razorpay Agent Trust Gateway."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Optional
from datetime import datetime, timezone
import json


# ── Enums ──

class Decision(str, Enum):
    ALLOW = "ALLOW"
    REVIEW = "REVIEW"
    BLOCK = "BLOCK"


class CheckResult(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARN = "WARN"
    SKIP = "SKIP"


class AgentStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


class IntentStatus(str, Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
    USED = "used"


class TransactionStatus(str, Enum):
    PENDING = "pending"
    EVALUATED = "evaluated"
    EXECUTED = "executed"
    BLOCKED = "blocked"
    REVIEW = "review"


# ── Data Classes ──

@dataclass
class Agent:
    agent_id: str
    name: str
    owner_id: str
    status: AgentStatus = AgentStatus.ACTIVE
    permissions: list[str] = field(default_factory=lambda: ["create_order"])
    spending_limit: Optional[float] = None
    total_spent: float = 0.0
    transaction_count: int = 0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        d = asdict(self)
        d["status"] = self.status.value
        return d


@dataclass
class Intent:
    intent_id: str
    user_id: str
    raw_text: str
    purpose: Optional[str] = None
    category: Optional[str] = None
    max_amount: Optional[float] = None
    currency: str = "INR"
    merchant_requirement: Optional[str] = None
    status: IntentStatus = IntentStatus.ACTIVE
    expires_at: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    parsed_json: Optional[str] = None  # Full structured JSON from AI

    def to_dict(self) -> dict:
        d = asdict(self)
        d["status"] = self.status.value
        return d

    def structured_view(self) -> dict:
        """Return the clean structured authorization view."""
        return {
            "purpose": self.purpose,
            "category": self.category,
            "max_amount": self.max_amount,
            "currency": self.currency,
            "merchant_requirement": self.merchant_requirement,
            "expires_at": self.expires_at,
            "status": self.status.value,
        }


@dataclass
class TransactionProposal:
    transaction_id: str
    agent_id: str
    intent_id: str
    action: str = "create_order"
    amount: float = 0.0
    currency: str = "INR"
    category: Optional[str] = None
    merchant_id: Optional[str] = None
    merchant_name: Optional[str] = None
    description: Optional[str] = None
    status: TransactionStatus = TransactionStatus.PENDING
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        d = asdict(self)
        d["status"] = self.status.value
        return d


@dataclass
class PolicyCheck:
    name: str
    result: CheckResult
    detail: str = ""

    def to_dict(self) -> dict:
        return {"name": self.name, "result": self.result.value, "detail": self.detail}


@dataclass
class PolicyDecision:
    decision: Decision
    checks: list[PolicyCheck] = field(default_factory=list)
    reason_code: Optional[str] = None
    reason_detail: Optional[str] = None
    evaluated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return {
            "decision": self.decision.value,
            "checks": {c.name: c.result.value for c in self.checks},
            "violations": [c.to_dict() for c in self.checks if c.result == CheckResult.FAIL],
            "warnings": [c.to_dict() for c in self.checks if c.result == CheckResult.WARN],
            "reason_code": self.reason_code,
            "reason_detail": self.reason_detail,
            "evaluated_at": self.evaluated_at,
        }


@dataclass
class RazorpayTransaction:
    razorpay_order_id: Optional[str] = None
    razorpay_payment_id: Optional[str] = None
    amount: float = 0.0
    currency: str = "INR"
    status: str = "created"
    receipt: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    is_simulated: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AuditEvidence:
    transaction_id: str
    intent_id: str
    agent_id: str
    raw_intent: str = ""
    structured_authorization: str = ""  # JSON string
    agent_proposal: str = ""  # JSON string
    policy_decision: str = ""  # JSON string
    razorpay_result: str = ""  # JSON string
    outcome: str = ""
    intent_hash: str = ""
    decision_hash: str = ""
    evidence_hash: str = ""
    verified: bool = False
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AIExplanation:
    summary: str = ""
    detail: str = ""
    recommendation: str = ""
    confidence: str = "medium"
    available: bool = False

    def to_dict(self) -> dict:
        return asdict(self)
