# 🛡️ Agent Trust: Verifiable Risk Management for Agentic Commerce

**Agent Trust** is a robust middleware security and authorization layer designed for the trillion-dollar future of Agentic Commerce. It provides a deterministic, cryptographically verifiable boundary between autonomous AI agents and financial APIs (such as Razorpay).

By shifting the paradigm from *direct API access* to *intent-based authorization*, Agent Trust ensures that non-deterministic AI agents can never execute transactions outside of strict corporate risk policies without explicit human approval.

---

## 📖 The Problem

As enterprises deploy AI agents to autonomously negotiate, procure, and execute financial transactions, a critical vulnerability emerges: **Financial APIs were designed for deterministic software, but LLMs are inherently non-deterministic, hallucinatory, and vulnerable to prompt injection.**

Granting an AI agent raw access to a payment gateway API key is a catastrophic liability. A single hallucinated zero or a malicious prompt injection could drain a corporate treasury instantly. 

**Agent Trust** solves the "black box" problem of AI actions by providing:
1. **Deterministic Risk Boundaries:** Agents propose "Intents" which are evaluated against hardcoded, mathematically verifiable risk policies.
2. **Human-in-the-Loop Quarantine:** High-risk actions are blocked from the API and routed to a human approver.
3. **Cryptographic Auditing:** Every decision, whether automated or human-approved, is hashed into an immutable Evidence Record.

---

## 🏗️ Architecture & Core Components

Agent Trust is built with a decoupled, event-driven architecture that intercepts agent behavior before it touches the financial ledger.

### 1. The Intent Engine (`intent_parser.py` & `mock_agent.py`)
Agents do not make API calls directly. Instead, they generate a signed **Transaction Proposal (Intent)**. 
- The `mock_agent.py` simulates a LangChain/OpenAI agent attempting to purchase server infrastructure or pay a vendor.
- The `intent_parser.py` validates the schema of the intent, ensuring it meets the structural requirements for evaluation.

### 2. The Policy Evaluator (`policy_engine.py`)
A strictly deterministic rules engine that evaluates the parsed Intent against corporate risk policies.
- **Velocity Checks:** Has this agent exceeded its hourly spend limit?
- **Category Restrictions:** Is the agent authorized to purchase from this merchant category?
- **Anomaly Detection:** Is the transaction amount drastically higher than the agent's historical median?

*Decisions are binary: `APPROVE` or `REQUIRES_REVIEW`.*

### 3. The Audit & Evidence Ledger (`crypto_utils.py` & `database.py`)
Trust requires verification. For every transaction, Agent Trust generates a **Cryptographic Evidence Record**.
- Computes a SHA-256 hash of the original LLM prompt, the generated intent payload, the policy engine's deterministic evaluation state, and the final decision.
- This creates an immutable audit trail, providing mathematical proof of *why* an agent made a decision and *who* authorized it, eliminating liability disputes.

### 4. The Control Plane (`app.py`)
A Streamlit-based dashboard serving as the human-in-the-loop interface.
- **Overview:** Real-time system metrics and KPIs.
- **Pending Review:** A quarantine zone for transactions that tripped risk policies, requiring explicit human cryptographic sign-off.
- **Audit & Evidence:** A transparency dashboard allowing security engineers to inspect the exact state and hashes of historical agent actions.

---

## 🚀 Getting Started

### 1. Environment Setup

Ensure you are running Python 3.10+ and set up your virtual environment.

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configuration

Create your local environment file:

```bash
cp .env.example .env
```
Add your `OPENAI_API_KEY` to the `.env` file. This is required for the `mock_agent.py` to simulate live, non-deterministic agent behavior.

### 3. Initialize Database & Run

The application uses a lightweight local SQLite database (`agent_trust.db`) to store policies, intents, and cryptographic evidence.

```bash
# Start the Streamlit Control Plane
streamlit run app.py
```

Navigate to `http://localhost:8502` to view the dashboard. 
*Note: If port 8501 is occupied, Streamlit will automatically increment to the next available port.*

---

## 🧪 Simulating Agent Behavior

Agent Trust includes a built-in simulation environment directly within the Control Plane. 

1. Navigate to the **Agents** tab in the sidebar.
2. Select an active agent (e.g., *IT Asset Auto-Provisioner*).
3. Enter a prompt simulating an autonomous task (e.g., *"Procure 5 new Macbook Pros for the engineering team from Apple."*).
4. Watch as the agent generates an Intent, hits the Policy Engine, and is either executed or quarantined for human review based on the $500 transaction limit policy.

---

## 🔮 Future Scalability & Production Considerations

While this iteration serves as a robust proof-of-concept for Agentic Risk Management, scaling this to handle thousands of concurrent agents requires the following architectural evolutions:

- **Distributed Ledger Integration:** Moving the local SQLite Evidence Ledger to a distributed, tamper-evident datastore (e.g., AWS QLDB or a permissioned blockchain) to guarantee cryptographic immutability across multi-tenant environments.
- **Streaming Policy Evaluation:** Migrating `policy_engine.py` to a stream-processing framework (like Apache Flink) to evaluate temporal velocity policies across millions of events with sub-millisecond latency.
- **Dynamic Policy Generation:** Utilizing a secondary, highly-constrained LLM (a "Policy Agent") to dynamically update deterministic risk thresholds based on macro-economic data and historical agent performance. 


