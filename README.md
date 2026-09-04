# 🛡️ Payment Change Guardian

**Detect breaking changes in payment APIs. Identify affected merchant integrations. Assess risk automatically.**

Payment Change Guardian is a developer/security tool that compares two versions of a payment API specification (starting with Razorpay), detects breaking changes, scans your merchant integration code for affected references, and generates a comprehensive risk report.

---

## Quick Start

### 1. Create a virtual environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment (optional)

```bash
copy .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY for AI explanations
```

> **Note:** The app works fully without an API key. Claude AI explanations are an optional enhancement.

### 4. Run the application

```bash
streamlit run app.py
```

The app opens at `http://localhost:8501`.

### 5. Run tests

```bash
pytest tests/ -v
```

### 6. Use the demo

Click **"🚀 Load Demo Fixtures"** in the sidebar, then click **"🔍 Analyze Breaking Changes"**.

Or manually upload the files from `fixtures/`:
- `fixtures/old_api.json` — Razorpay API v1.0.0
- `fixtures/new_api.json` — Razorpay API v2.0.0 (with breaking changes)
- `fixtures/merchant_project/` — Sample merchant integration code

---

## What It Does

### Deterministic Analysis (always runs)

1. **API Diff Engine** — Compares two OpenAPI-style JSON specs and detects:
   - Removed endpoints
   - Added required request fields
   - Removed request/response fields
   - Changed field types
   - Removed enum values
   - Webhook payload changes
   - Authentication requirement changes

2. **Code Scanner** — Scans merchant integration code for:
   - API endpoint path references
   - HTTP method calls
   - Field name access (dict keys, attributes, assignments)
   - Webhook event name references
   - Removed enum value literals

3. **Risk Scoring** — Deterministic severity (CRITICAL / HIGH / MEDIUM) based on change type.

4. **Report Generation** — Export as JSON or Markdown with full finding details.

### AI Enhancement (optional, requires `ANTHROPIC_API_KEY`)

After deterministic analysis completes, Claude is sent focused context per finding:
- The specific API change detected
- The affected code snippet and file location
- The old and new schema values
- The calculated severity

Claude returns structured JSON with:
- Technical explanation
- Business impact assessment
- Suggested code fix
- Confidence level

**If the API key is missing or the call fails, the app continues normally with deterministic results.**

---

## Architecture

```
payment_change_guardian/
├── app.py                  # Streamlit dashboard
├── diff_engine.py          # API spec comparison (deterministic)
├── code_scanner.py         # Merchant code reference scanner
├── risk_engine.py          # Severity scoring and report assembly
├── ai_explainer.py         # Optional Claude AI integration
├── report_generator.py     # JSON and Markdown export
├── models.py               # Data models (dataclasses)
├── requirements.txt        # Python dependencies
├── .env.example            # Environment variable template
├── fixtures/
│   ├── old_api.json        # Razorpay API v1 spec
│   ├── new_api.json        # Razorpay API v2 spec (breaking)
│   └── merchant_project/
│       ├── payment_client.py
│       ├── webhook_handler.py
│       └── order_service.py
└── tests/
    ├── test_diff_engine.py
    ├── test_code_scanner.py
    └── test_risk_engine.py
```

---

## Demo Breaking Changes

The fixtures demonstrate these breaking changes:

| # | Change | Type | Severity |
|---|--------|------|----------|
| 1 | `POST /v1/payments` now requires `customer_id` | Required field added | HIGH |
| 2 | Response `status` changed from `string` to `object` | Type changed | HIGH |
| 3 | Response `order_id` removed from payments | Field removed | HIGH |
| 4 | `payment.failed` webhook payload fields removed | Webhook changed | HIGH |
| 5 | `EUR`, `GBP` removed from currency enum; `wallet`, `emi` removed from method enum | Enum removed | MEDIUM |
| 6 | `POST /v1/refunds` endpoint removed | Endpoint removed | CRITICAL |
| 7 | Auth changed from Basic Auth to Bearer/OAuth2 | Auth changed | CRITICAL |

---

## Current Limitations

- **Text-based scanning only** — No AST parsing; relies on regex pattern matching. May produce false positives on common field names.
- **Single provider** — Demo fixtures are Razorpay-style, but the engine accepts any OpenAPI-style JSON.
- **No live API validation** — Works entirely with local spec files. No Razorpay API calls are made.
- **No persistence** — Results are per-session. Export to JSON/Markdown for archival.
- **AI context limit** — Sends at most 5 code references per finding to Claude to stay within token limits.

## Adding Razorpay Live Integration (Future)

1. Fetch the live Razorpay OpenAPI spec from their documentation portal.
2. Store previous spec versions locally or in a database.
3. Schedule periodic comparisons (e.g., daily cron).
4. Use Razorpay's test-mode API keys to validate detected changes against the real API.
5. Integrate with CI/CD to block deployments when critical breaking changes are detected.

---

## License

MIT
