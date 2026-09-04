"""SQLite database layer for Razorpay Agent Trust Gateway."""
from __future__ import annotations

import sqlite3
import json
import os
from pathlib import Path
from contextlib import contextmanager

DB_PATH = Path(__file__).parent / "gateway.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def get_db():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    """Create all tables if they don't exist."""
    with get_db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS agents (
            agent_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            owner_id TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            permissions TEXT NOT NULL DEFAULT '["create_order"]',
            spending_limit REAL,
            total_spent REAL DEFAULT 0.0,
            transaction_count INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS intents (
            intent_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            raw_text TEXT NOT NULL,
            purpose TEXT,
            category TEXT,
            max_amount REAL,
            currency TEXT DEFAULT 'INR',
            merchant_requirement TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            expires_at TEXT,
            created_at TEXT NOT NULL,
            parsed_json TEXT
        );

        CREATE TABLE IF NOT EXISTS transaction_proposals (
            transaction_id TEXT PRIMARY KEY,
            agent_id TEXT NOT NULL,
            intent_id TEXT NOT NULL,
            action TEXT DEFAULT 'create_order',
            amount REAL NOT NULL,
            currency TEXT DEFAULT 'INR',
            category TEXT,
            merchant_id TEXT,
            merchant_name TEXT,
            description TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL,
            FOREIGN KEY (agent_id) REFERENCES agents(agent_id),
            FOREIGN KEY (intent_id) REFERENCES intents(intent_id)
        );

        CREATE TABLE IF NOT EXISTS policy_decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transaction_id TEXT NOT NULL,
            decision TEXT NOT NULL,
            checks_json TEXT NOT NULL,
            reason_code TEXT,
            reason_detail TEXT,
            evaluated_at TEXT NOT NULL,
            FOREIGN KEY (transaction_id) REFERENCES transaction_proposals(transaction_id)
        );

        CREATE TABLE IF NOT EXISTS razorpay_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transaction_id TEXT NOT NULL,
            razorpay_order_id TEXT,
            razorpay_payment_id TEXT,
            amount REAL NOT NULL,
            currency TEXT DEFAULT 'INR',
            status TEXT DEFAULT 'created',
            receipt TEXT,
            is_simulated INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY (transaction_id) REFERENCES transaction_proposals(transaction_id)
        );

        CREATE TABLE IF NOT EXISTS audit_evidence (
            transaction_id TEXT PRIMARY KEY,
            intent_id TEXT NOT NULL,
            agent_id TEXT NOT NULL,
            raw_intent TEXT,
            structured_authorization TEXT,
            agent_proposal TEXT,
            policy_decision TEXT,
            razorpay_result TEXT,
            outcome TEXT,
            intent_hash TEXT,
            decision_hash TEXT,
            evidence_hash TEXT,
            verified INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY (transaction_id) REFERENCES transaction_proposals(transaction_id)
        );
        """)


# ── Agent CRUD ──

def save_agent(agent_dict: dict):
    with get_db() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO agents
            (agent_id, name, owner_id, status, permissions, spending_limit, total_spent, transaction_count, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            agent_dict["agent_id"], agent_dict["name"], agent_dict["owner_id"],
            agent_dict["status"], json.dumps(agent_dict.get("permissions", ["create_order"])),
            agent_dict.get("spending_limit"), agent_dict.get("total_spent", 0.0),
            agent_dict.get("transaction_count", 0), agent_dict["created_at"],
        ))


def get_agent(agent_id: str) -> dict | None:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM agents WHERE agent_id = ?", (agent_id,)).fetchone()
        if row:
            d = dict(row)
            d["permissions"] = json.loads(d["permissions"])
            return d
    return None


def list_agents() -> list[dict]:
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM agents ORDER BY created_at DESC").fetchall()
        result = []
        for row in rows:
            d = dict(row)
            d["permissions"] = json.loads(d["permissions"])
            result.append(d)
        return result


# ── Intent CRUD ──

def save_intent(intent_dict: dict):
    with get_db() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO intents
            (intent_id, user_id, raw_text, purpose, category, max_amount, currency,
             merchant_requirement, status, expires_at, created_at, parsed_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            intent_dict["intent_id"], intent_dict["user_id"], intent_dict["raw_text"],
            intent_dict.get("purpose"), intent_dict.get("category"),
            intent_dict.get("max_amount"), intent_dict.get("currency", "INR"),
            intent_dict.get("merchant_requirement"), intent_dict.get("status", "active"),
            intent_dict.get("expires_at"), intent_dict["created_at"],
            intent_dict.get("parsed_json"),
        ))


def get_intent(intent_id: str) -> dict | None:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM intents WHERE intent_id = ?", (intent_id,)).fetchone()
        return dict(row) if row else None


def list_intents() -> list[dict]:
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM intents ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]


# ── Transaction CRUD ──

def save_transaction(txn_dict: dict):
    with get_db() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO transaction_proposals
            (transaction_id, agent_id, intent_id, action, amount, currency,
             category, merchant_id, merchant_name, description, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            txn_dict["transaction_id"], txn_dict["agent_id"], txn_dict["intent_id"],
            txn_dict.get("action", "create_order"), txn_dict["amount"],
            txn_dict.get("currency", "INR"), txn_dict.get("category"),
            txn_dict.get("merchant_id"), txn_dict.get("merchant_name"),
            txn_dict.get("description"), txn_dict.get("status", "pending"),
            txn_dict["created_at"],
        ))


def update_transaction_status(transaction_id: str, status: str):
    with get_db() as conn:
        conn.execute("UPDATE transaction_proposals SET status = ? WHERE transaction_id = ?",
                      (status, transaction_id))


def get_transaction(transaction_id: str) -> dict | None:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM transaction_proposals WHERE transaction_id = ?",
                           (transaction_id,)).fetchone()
        return dict(row) if row else None


def list_transactions() -> list[dict]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM transaction_proposals ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]


# ── Policy Decision CRUD ──

def save_policy_decision(transaction_id: str, decision_dict: dict):
    with get_db() as conn:
        conn.execute("""
            INSERT INTO policy_decisions
            (transaction_id, decision, checks_json, reason_code, reason_detail, evaluated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            transaction_id, decision_dict["decision"],
            json.dumps(decision_dict["checks"]),
            decision_dict.get("reason_code"), decision_dict.get("reason_detail"),
            decision_dict["evaluated_at"],
        ))


def get_policy_decision(transaction_id: str) -> dict | None:
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM policy_decisions WHERE transaction_id = ? ORDER BY id DESC LIMIT 1",
            (transaction_id,)
        ).fetchone()
        if row:
            d = dict(row)
            d["checks"] = json.loads(d["checks_json"])
            return d
    return None


# ── Razorpay Transaction CRUD ──

def save_razorpay_transaction(transaction_id: str, rz_dict: dict):
    with get_db() as conn:
        conn.execute("""
            INSERT INTO razorpay_transactions
            (transaction_id, razorpay_order_id, razorpay_payment_id, amount, currency,
             status, receipt, is_simulated, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            transaction_id, rz_dict.get("razorpay_order_id"),
            rz_dict.get("razorpay_payment_id"), rz_dict["amount"],
            rz_dict.get("currency", "INR"), rz_dict.get("status", "created"),
            rz_dict.get("receipt"), 1 if rz_dict.get("is_simulated") else 0,
            rz_dict["created_at"],
        ))


def get_razorpay_transaction(transaction_id: str) -> dict | None:
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM razorpay_transactions WHERE transaction_id = ? ORDER BY id DESC LIMIT 1",
            (transaction_id,)
        ).fetchone()
        if row:
            d = dict(row)
            d["is_simulated"] = bool(d["is_simulated"])
            return d
    return None


# ── Audit Evidence CRUD ──

def save_audit_evidence(evidence_dict: dict):
    with get_db() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO audit_evidence
            (transaction_id, intent_id, agent_id, raw_intent, structured_authorization,
             agent_proposal, policy_decision, razorpay_result, outcome,
             intent_hash, decision_hash, evidence_hash, verified, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            evidence_dict["transaction_id"], evidence_dict["intent_id"],
            evidence_dict["agent_id"], evidence_dict.get("raw_intent", ""),
            evidence_dict.get("structured_authorization", ""),
            evidence_dict.get("agent_proposal", ""),
            evidence_dict.get("policy_decision", ""),
            evidence_dict.get("razorpay_result", ""),
            evidence_dict.get("outcome", ""),
            evidence_dict.get("intent_hash", ""),
            evidence_dict.get("decision_hash", ""),
            evidence_dict.get("evidence_hash", ""),
            1 if evidence_dict.get("verified") else 0,
            evidence_dict["created_at"],
        ))


def get_audit_evidence(transaction_id: str) -> dict | None:
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM audit_evidence WHERE transaction_id = ?", (transaction_id,)
        ).fetchone()
        if row:
            d = dict(row)
            d["verified"] = bool(d["verified"])
            return d
    return None


def list_audit_evidence() -> list[dict]:
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM audit_evidence ORDER BY created_at DESC").fetchall()
        result = []
        for row in rows:
            d = dict(row)
            d["verified"] = bool(d["verified"])
            result.append(d)
        return result


# ── Stats ──

def get_stats() -> dict:
    with get_db() as conn:
        total = conn.execute("SELECT COUNT(*) FROM transaction_proposals").fetchone()[0]
        executed = conn.execute("SELECT COUNT(*) FROM transaction_proposals WHERE status='executed'").fetchone()[0]
        blocked = conn.execute("SELECT COUNT(*) FROM transaction_proposals WHERE status='blocked'").fetchone()[0]
        review = conn.execute("SELECT COUNT(*) FROM transaction_proposals WHERE status='review'").fetchone()[0]
        return {
            "total_authorizations": total,
            "transactions_executed": executed,
            "requires_review": review,
            "blocked": blocked,
        }


def reset_db():
    """Drop and recreate all tables. Use for testing only."""
    if DB_PATH.exists():
        os.remove(str(DB_PATH))
    init_db()
