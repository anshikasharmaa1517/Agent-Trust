"""Razorpay Agent Trust — Merchant Dashboard."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone, timedelta

import streamlit as st
from dotenv import load_dotenv

import database as db
from models import Decision, AgentStatus, IntentStatus, TransactionProposal
import transaction_service
import intent_parser
import ai_explainer
import evidence_service
import razorpay_adapter
import demo_data

load_dotenv()

# ─────────────────────────────────────────────────────────────────
# Page config
# ─────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Agent Trust — Razorpay Dashboard",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────────
# Init DB + seed demo
# ─────────────────────────────────────────────────────────────────
db.init_db()
demo_data.seed_demo_data()

if "page" not in st.session_state:
    st.session_state.page = "overview"

# ─────────────────────────────────────────────────────────────────
# CSS — Razorpay Dashboard Design Language
# ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

*, *::before, *::after { box-sizing: border-box; }

:root {
  --rz-blue: #1a73e8;
  --rz-blue-hover: #1557b0;
  --rz-green: #1e8e3e;
  --rz-yellow: #e37400;
  --rz-red: #d93025;
  --rz-text: #1a1a1a;
  --rz-text-secondary: #6b7280;
  --rz-text-muted: #9ca3af;
  --rz-border: #e5e7eb;
  --rz-bg: #f4f5f7;
  --rz-white: #ffffff;
  --rz-bg-hover: #f9fafb;
}

html, body, .stApp {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    font-size: 13px;
    background: var(--rz-bg) !important;
    color: var(--rz-text);
    line-height: 1.5;
}

#MainMenu, footer, .stDeployButton, [data-testid="stAppDeployButton"] { display: none !important; }
[data-testid="stToolbar"] { right: 24px !important; top: 16px !important; z-index: 9999999 !important; }
header { background: transparent !important; box-shadow: none !important; }
.block-container { padding: 6rem 2rem 2rem 2rem !important; max-width: 100% !important; }
div[data-testid="stMainBlockContainer"] { padding: 6rem 2rem 2rem 2rem !important; max-width: 100% !important; }
div[data-testid="stAppViewBlockContainer"] { padding: 6rem 2rem 2rem 2rem !important; max-width: 100% !important; }

/* ── Global Top Bar ── */
.rz-topnav {
    background: #1b2733;
    padding: 0 20px;
    height: 48px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    z-index: 999;
}
.rz-topnav-left {
    display: flex;
    align-items: center;
    gap: 0;
}
.rz-logo {
    display: flex;
    align-items: center;
    gap: 8px;
    padding-right: 20px;
    margin-right: 0;
}
.rz-logo svg { width: 20px; height: 20px; }
.rz-logo-text { color: #fff; font-size: 14px; font-weight: 600; letter-spacing: -0.2px; }
.rz-topnav-link {
    color: rgba(255,255,255,0.6);
    font-size: 14px;
    font-weight: 400;
    padding: 14px 16px;
    text-decoration: none;
    transition: color 0.15s;
    cursor: default;
    border-bottom: 2px solid transparent;
}
.rz-topnav-link:hover { color: #fff; }
.rz-topnav-link.active { color: #fff; font-weight: 600; border-bottom: 2px solid #fff; }
.rz-topnav-right {
    display: flex;
    align-items: center;
    gap: 12px;
}
.rz-topnav-search {
    background: rgba(255,255,255,0.08);
    border: 1px solid rgba(255,255,255,0.12);
    border-radius: 4px;
    color: rgba(255,255,255,0.5);
    font-size: 12px;
    padding: 7px 14px 7px 32px;
    width: 280px;
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='14' height='14' fill='rgba(255,255,255,0.4)' viewBox='0 0 16 16'%3E%3Cpath d='M11.742 10.344a6.5 6.5 0 1 0-1.397 1.398l3.85 3.85a1 1 0 0 0 1.415-1.414l-3.85-3.85zm-5.242.156a5 5 0 1 1 0-10 5 5 0 0 1 0 10z'/%3E%3C/svg%3E");
    background-repeat: no-repeat;
    background-position: 10px center;
}
.rz-topnav-icon {
    color: rgba(255,255,255,0.5);
    font-size: 16px;
    cursor: pointer;
    padding: 4px;
}
.rz-topnav-avatar {
    width: 28px; height: 28px;
    border-radius: 50%;
    background: #3b82f6;
    color: #fff;
    display: flex; align-items: center; justify-content: center;
    font-size: 11px; font-weight: 600;
}
.rz-test-badge {
    background: #34d399;
    color: #064e3b;
    font-size: 10px;
    font-weight: 700;
    padding: 2px 8px;
    border-radius: 3px;
    letter-spacing: 0.5px;
    margin-left: 8px;
}

/* ── Page Header ── */
.rz-page-header {
    background: var(--rz-white);
    border-bottom: 1px solid var(--rz-border);
    padding: 16px 24px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin: 0 -2rem;
}
.rz-page-title { font-size: 20px; font-weight: 600; color: var(--rz-text); margin: 0; }
.rz-page-subtitle { font-size: 13px; color: var(--rz-text-secondary); margin-top: 2px; }
.rz-page-actions { display: flex; gap: 8px; align-items: center; }

/* ── Content area ── */
.rz-content { padding: 20px 24px 40px; max-width: 100%; }

/* ── KPI row ── */
.rz-kpi-row { display: flex; gap: 12px; margin-bottom: 20px; }
.rz-kpi {
    background: var(--rz-white);
    border: 1px solid var(--rz-border);
    border-radius: 4px;
    padding: 14px 16px;
    flex: 1;
}
.rz-kpi-value { font-size: 22px; font-weight: 700; color: var(--rz-text); margin-bottom: 2px; }
.rz-kpi-label { font-size: 12px; color: var(--rz-text-secondary); font-weight: 500; }

/* ── Tables ── */
.rz-table-wrap {
    background: var(--rz-white);
    border: 1px solid var(--rz-border);
    border-radius: 4px;
    overflow: hidden;
    margin-bottom: 16px;
}
.rz-tbl { width: 100%; border-collapse: collapse; font-size: 13px; }
.rz-tbl th {
    text-align: left;
    padding: 10px 14px;
    font-size: 11px;
    font-weight: 600;
    color: var(--rz-text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.3px;
    background: #f9fafb;
    border-bottom: 1px solid var(--rz-border);
    white-space: nowrap;
}
.rz-tbl td {
    padding: 10px 14px;
    border-bottom: 1px solid #f3f4f6;
    color: var(--rz-text);
    vertical-align: middle;
}
.rz-tbl tr:last-child td { border-bottom: none; }
.rz-tbl tr:hover td { background: #f9fafb; }
.rz-tbl .mono {
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px;
    color: var(--rz-blue);
}
.rz-tbl .muted { color: var(--rz-text-muted); font-size: 12px; }
.rz-tbl .amt { text-align: right; font-weight: 600; font-variant-numeric: tabular-nums; }
.rz-tbl .nowrap { white-space: nowrap; }

/* ── Section ── */
.rz-section-title {
    font-size: 14px;
    font-weight: 600;
    color: var(--rz-text);
    margin: 0 0 12px 0;
}
.rz-section-subtitle {
    font-size: 12px;
    color: var(--rz-text-secondary);
    margin: -8px 0 12px 0;
}

/* ── Cards ── */
.rz-card {
    background: var(--rz-white);
    border: 1px solid var(--rz-border);
    border-radius: 4px;
    padding: 16px;
    margin-bottom: 12px;
}
.rz-card-header {
    font-size: 12px;
    font-weight: 600;
    color: var(--rz-text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.3px;
    margin-bottom: 12px;
    padding-bottom: 8px;
    border-bottom: 1px solid #f3f4f6;
}

/* ── Badges ── */
.rz-badge {
    display: inline-block;
    font-size: 11px;
    font-weight: 600;
    padding: 2px 8px;
    border-radius: 3px;
    text-transform: uppercase;
    letter-spacing: 0.2px;
    white-space: nowrap;
    line-height: 1.5;
}
.rz-badge-allow { background: #e6f4ea; color: #137333; }
.rz-badge-block { background: #fce8e6; color: #c5221f; }
.rz-badge-review { background: #fef7e0; color: #b06000; }
.rz-badge-active { background: #e6f4ea; color: #137333; }
.rz-badge-inactive { background: #f3f4f6; color: #5f6368; }
.rz-badge-info { background: #e8f0fe; color: #1967d2; }
.rz-badge-sim { background: #f3f4f6; color: #5f6368; }
.rz-badge-test { background: #e6f4ea; color: #137333; }

/* ── Detail rows ── */
.rz-detail-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 0;
    border-bottom: 1px solid #f3f4f6;
    font-size: 13px;
}
.rz-detail-row:last-child { border-bottom: none; }
.rz-detail-label { color: var(--rz-text-secondary); }
.rz-detail-value { color: var(--rz-text); font-weight: 500; }

/* ── Check rows ── */
.rz-check {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 6px 0;
    font-size: 13px;
    border-bottom: 1px solid #f9fafb;
}
.rz-check:last-child { border-bottom: none; }
.rz-check-pass { color: var(--rz-green); font-weight: 600; }
.rz-check-fail { color: var(--rz-red); font-weight: 600; }
.rz-check-warn { color: var(--rz-yellow); font-weight: 600; }

/* ── Chain ── */
.rz-chain-step {
    display: flex;
    align-items: flex-start;
    gap: 12px;
    padding: 8px 0 8px 12px;
    border-left: 2px solid #e5e7eb;
    margin-left: 6px;
}
.rz-chain-step:last-child { border-left-color: transparent; }
.rz-chain-dot {
    width: 8px; height: 8px;
    border-radius: 50%;
    flex-shrink: 0;
    margin-top: 5px;
    margin-left: -17px;
    border: 2px solid var(--rz-white);
}
.rz-chain-dot.green { background: var(--rz-green); }
.rz-chain-dot.red { background: var(--rz-red); }
.rz-chain-dot.yellow { background: var(--rz-yellow); }
.rz-chain-dot.blue { background: var(--rz-blue); }
.rz-chain-label {
    font-size: 11px;
    font-weight: 600;
    color: var(--rz-text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.3px;
}
.rz-chain-value { font-size: 13px; color: var(--rz-text); margin-top: 2px; }

/* ── AI panel ── */
.rz-ai-panel {
    background: #f8f9ff;
    border: 1px solid #e0e7ff;
    border-radius: 4px;
    padding: 14px;
    margin-top: 12px;
}

/* ── Progress bars ── */
.rz-bar-wrap { margin-bottom: 8px; }
.rz-bar-labels {
    display: flex;
    justify-content: space-between;
    font-size: 12px;
    margin-bottom: 4px;
}
.rz-bar-track {
    background: #f3f4f6;
    border-radius: 2px;
    height: 6px;
    overflow: hidden;
}
.rz-bar-fill { height: 100%; border-radius: 2px; }

/* ── Code block ── */
.rz-code {
    background: #f8f9fa;
    border: 1px solid var(--rz-border);
    border-radius: 4px;
    padding: 10px 12px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px;
    color: var(--rz-text);
    overflow-x: auto;
    white-space: pre-wrap;
}

/* ── Sidebar ── */
section[data-testid="stSidebar"] {
    background: var(--rz-white) !important;
    border-right: 1px solid var(--rz-border) !important;
}

/* Make the collapse button visible inside the open sidebar */
[data-testid="stSidebarCollapseButton"] {
    position: absolute !important;
    top: 16px !important;
    right: 16px !important;
    background: rgba(0, 0, 0, 0.1) !important;
    border-radius: 4px !important;
    width: 32px !important;
    height: 32px !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    z-index: 9999999 !important;
    color: #000000 !important;
    visibility: visible !important;
    cursor: pointer !important;
}
[data-testid="stSidebarCollapseButton"] svg,
[data-testid="stSidebarCollapseButton"] span[data-testid="stIconMaterial"] {
    display: block !important;
    color: #000000 !important;
    fill: #000000 !important;
    stroke: #000000 !important;
}

/* 
 * Ultra-bulletproof target for the Streamlit sidebar toggle (when closed).
 * We target the specific button that contains a Material Icon anywhere in the header
 * (except the ones we explicitly hid).
 */
header[data-testid="stHeader"] button:has(span[data-testid="stIconMaterial"]) {
    position: fixed !important;
    left: 12px !important;
    top: 16px !important;
    z-index: 9999999 !important;
    background: rgba(255, 255, 255, 0.1) !important;
    border-radius: 4px !important;
    border: 1px solid rgba(255, 255, 255, 0.2) !important;
    width: 40px !important;
    height: 40px !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
}
header[data-testid="stHeader"] button:has(span[data-testid="stIconMaterial"]):hover {
    background: rgba(255, 255, 255, 0.2) !important;
}

/* Force all Material icons and SVGs in the Streamlit header to be pure white */
header[data-testid="stHeader"] span[data-testid="stIconMaterial"],
header[data-testid="stHeader"] svg {
    color: #ffffff !important;
    fill: #ffffff !important;
    stroke: #ffffff !important;
}

/* Target the radio group specifically used for navigation */
section[data-testid="stSidebar"] div[data-testid="stRadio"] > div {
    gap: 0 !important;
}
section[data-testid="stSidebar"] div[data-testid="stRadio"] label {
    padding: 10px 20px !important;
    margin: 0 !important;
    border-left: 4px solid transparent !important;
    width: 100% !important;
    cursor: pointer !important;
    border-radius: 0 !important;
    display: flex !important;
    align-items: center !important;
}
section[data-testid="stSidebar"] div[data-testid="stRadio"] label:hover {
    background: #f9fafb !important;
}
section[data-testid="stSidebar"] div[data-testid="stRadio"] label:has(input:checked) {
    background: #f4f5f7 !important;
    border-left: 4px solid var(--rz-blue) !important;
}
section[data-testid="stSidebar"] div[data-testid="stRadio"] label:has(input:checked) p {
    font-weight: 600 !important;
    color: #1a1a1a !important;
}
section[data-testid="stSidebar"] div[data-testid="stRadio"] label p {
    color: #374151 !important;
    font-size: 14px !important;
    font-weight: 500 !important;
    margin: 0 !important;
}
/* Hide the radio circle */
section[data-testid="stSidebar"] div[data-testid="stRadio"] label > div:not(:has(p)) {
    display: none !important;
}

/* ── Test Mode Banner ── */
.rz-test-banner {
    background: #fffbeb;
    border-bottom: 1px solid #fef3c7;
    padding: 8px 24px;
    font-size: 12px;
    color: #92400e;
    display: flex;
    align-items: center;
    justify-content: space-between;
}
.rz-test-badge {
    background: #059669;
    color: #ffffff;
    font-size: 10px;
    font-weight: 700;
    padding: 2px 8px;
    border-radius: 10px;
    letter-spacing: 0.5px;
}

/* ── Help & Support Button ── */
.rz-help-btn {
    position: fixed;
    bottom: 20px;
    right: 24px;
    background: #1b2733;
    color: #ffffff;
    border-radius: 20px;
    padding: 8px 16px;
    font-size: 13px;
    font-weight: 500;
    display: flex;
    align-items: center;
    gap: 8px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.18);
    z-index: 9999;
    cursor: pointer;
    transition: transform 0.15s;
}
.rz-help-btn:hover { transform: translateY(-2px); }

/* ── Streamlit overrides ── */
.stButton > button {
    background: #ffffff !important;
    color: #374151 !important;
    border: 1px solid #d1d5db !important;
    border-radius: 6px !important;
    font-size: 12px !important;
    font-weight: 500 !important;
    padding: 5px 12px !important;
    height: auto !important;
    line-height: 1.4 !important;
    box-shadow: 0 1px 2px rgba(0,0,0,0.05) !important;
    transition: all 0.15s ease !important;
}
.stButton > button:hover {
    background: #f9fafb !important;
    border-color: #9ca3af !important;
    color: #111827 !important;
}
button[kind="primary"], .stButton > button[data-testid="stBaseButton-primary"] {
    background: #0066ff !important;
    color: #ffffff !important;
    border: none !important;
    font-weight: 600 !important;
    box-shadow: 0 1px 3px rgba(0,102,255,0.3) !important;
}
button[kind="primary"]:hover, .stButton > button[data-testid="stBaseButton-primary"]:hover {
    background: #0052cc !important;
    color: #ffffff !important;
}
.stTextInput > div > div > input,
.stTextArea > div > div > textarea,
.stNumberInput > div > div > input {
    background: var(--rz-white) !important;
    color: var(--rz-text) !important;
    border: 1px solid #d1d5db !important;
    border-radius: 6px !important;
    font-size: 13px !important;
}
.stSelectbox > div > div {
    background: var(--rz-white) !important;
    color: var(--rz-text) !important;
    border: 1px solid #d1d5db !important;
    border-radius: 6px !important;
}
div[data-baseweb="select"] { background: var(--rz-white) !important; }
div[data-baseweb="select"] > div { background: var(--rz-white) !important; color: var(--rz-text) !important; }
.stExpander {
    background: var(--rz-white) !important;
    border: 1px solid var(--rz-border) !important;
    border-radius: 6px !important;
}
.stExpander > div:first-child { background: var(--rz-white) !important; }
.stExpander p, .stExpander span { color: var(--rz-text) !important; }
div.stAlert {
    background: var(--rz-white) !important;
    border: 1px solid var(--rz-border) !important;
    border-radius: 6px !important;
    color: var(--rz-text) !important;
}
label { color: var(--rz-text) !important; font-size: 13px !important; font-weight: 500 !important; }

/* Align table buttons */
div[data-testid="column"] div[data-testid="stButton"] button { margin-top: -10px; }

/* scrollbar */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: #d1d5db; border-radius: 3px; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────
def _badge(d: str) -> str:
    cls = {"ALLOW": "rz-badge-allow", "BLOCK": "rz-badge-block", "REVIEW": "rz-badge-review"}.get(d, "rz-badge-inactive")
    return f'<span class="rz-badge {cls}">{d}</span>'

def _status_badge(s: str) -> str:
    cls = {"active": "rz-badge-active", "inactive": "rz-badge-inactive", "suspended": "rz-badge-block"}.get(s, "rz-badge-inactive")
    return f'<span class="rz-badge {cls}">{s.title()}</span>'

def _check_icon(result: str) -> str:
    if result == "PASS": return '<span class="rz-check-pass">✓</span>'
    if result == "FAIL": return '<span class="rz-check-fail">✗</span>'
    return '<span class="rz-check-warn">⚠</span>'

def _amt(a) -> str:
    try: return f"₹{float(a):,.0f}"
    except: return str(a)

def _sid(s: str) -> str:
    return s[-8:] if len(s) > 8 else s

def _ago(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        diff = datetime.now(timezone.utc) - dt
        mins = int(diff.total_seconds() / 60)
        if mins < 1: return "just now"
        if mins < 60: return f"{mins}m ago"
        hrs = mins // 60
        if hrs < 24: return f"{hrs}h ago"
        return f"{hrs // 24}d ago"
    except:
        return iso[:16] if iso else "—"


# ─────────────────────────────────────────────────────────────────
# Global Shell — Top nav
# ─────────────────────────────────────────────────────────────────
rz_status = razorpay_adapter.get_connection_status()
rz_connected = rz_status['mode'] == 'TEST'

st.markdown(f"""
<div class="rz-topnav" style="height: 72px; padding: 0 24px 0 76px; background: linear-gradient(90deg, #0f172a 0%, #1e293b 100%); display: flex; align-items: center; justify-content: flex-start; gap: 16px; border-bottom: 1px solid rgba(255,255,255,0.05); box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);">
  <div style="width: 40px; height: 40px; border-radius: 10px; background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%); display: flex; align-items: center; justify-content: center; box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);">
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path></svg>
  </div>
  <div style="display: flex; flex-direction: column; justify-content: center; gap: 2px;">
    <div style="color: white; font-size: 20px; font-weight: 700; letter-spacing: 0.5px;">Agent Trust</div>
    <div style="color: #94a3b8; font-size: 13px; font-weight: 400;">Control what your AI agents are authorized to do.</div>
  </div>
</div>

<div class="rz-help-btn">
  <svg width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 16h-2v-2h2v2zm0-4h-2V7h2v7z"/></svg> Help & Support
</div>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────
# Sidebar — Razorpay-style navigation
# ─────────────────────────────────────────────────────────────────
NAV_AGENT_TRUST = [
    ("overview",      "Overview"),
    ("agents",        "Agents"),
    ("intents",       "Authorizations"),
    ("transactions",  "Transactions"),
    ("review",        "Pending Review"),
    ("audit",         "Audit & Evidence"),
]

def render_sidebar():
    stats = db.get_stats()
    with st.sidebar:
        # Top section header
        st.markdown("""
        <div style="padding:16px 24px 8px;font-size:11px;font-weight:600;color:#6b7280;text-transform:uppercase;letter-spacing:0.5px">
          AGENT TRUST
        </div>
        """, unsafe_allow_html=True)

        current = st.session_state.page
        if current == "txn_detail": current = "transactions"
        
        options = []
        key_map = {}
        current_idx = 0
        
        for i, (key, label) in enumerate(NAV_AGENT_TRUST):
            options.append(label)
            key_map[label] = key
            if current == key:
                current_idx = i

        selected = st.radio("", options=options, index=current_idx, label_visibility="collapsed")
        new_page = key_map[selected]
        
        if new_page != st.session_state.page:
            # Only rerun if it's an actual change in the logical page
            if st.session_state.page == "txn_detail" and new_page == "transactions":
                pass
            else:
                st.session_state.page = new_page
                st.rerun()




# ─────────────────────────────────────────────────────────────────
# PAGE: Overview
# ─────────────────────────────────────────────────────────────────
def page_overview():
    stats = db.get_stats()
    txns = db.list_transactions()
    agents = db.list_agents()

    # Page header removed since it's now in the top black banner

    st.markdown('<div class="rz-content">', unsafe_allow_html=True)

    # KPIs
    st.markdown(f"""
    <div class="rz-kpi-row">
      <div class="rz-kpi"><div class="rz-kpi-value">{stats['total_authorizations']}</div><div class="rz-kpi-label">Authorizations</div></div>
      <div class="rz-kpi"><div class="rz-kpi-value">{stats['transactions_executed']}</div><div class="rz-kpi-label">Transactions</div></div>
      <div class="rz-kpi"><div class="rz-kpi-value">{stats['requires_review']}</div><div class="rz-kpi-label">Pending Review</div></div>
      <div class="rz-kpi"><div class="rz-kpi-value">{stats['blocked']}</div><div class="rz-kpi-label">Blocked</div></div>
    </div>
    """, unsafe_allow_html=True)

    # ── Recent Transactions (full width) ──
    st.markdown('<div class="rz-section-title">Recent Transactions</div>', unsafe_allow_html=True)

    rows = ""
    for t in txns[:10]:
        dec = db.get_policy_decision(t["transaction_id"])
        decision_val = dec["decision"] if dec else "PENDING"
        badge = _badge(decision_val)
        agent = db.get_agent(t["agent_id"])
        agent_name = agent["name"] if agent else t["agent_id"]
        intent = db.get_intent(t["intent_id"])
        intent_text = (intent["raw_text"][:60] + "…") if intent and len(intent["raw_text"]) > 60 else (intent["raw_text"] if intent else "—")
        rows += f"""
        <tr>
          <td class="mono nowrap">{_sid(t['transaction_id'])}</td>
          <td class="nowrap">{agent_name}</td>
          <td style="max-width:320px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#5f6368">{intent_text}</td>
          <td class="amt">{_amt(t['amount'])}</td>
          <td>{badge}</td>
          <td class="muted nowrap">{_ago(t['created_at'])}</td>
        </tr>"""

    st.markdown(f"""
    <div class="rz-table-wrap">
    <table class="rz-tbl">
      <thead><tr>
        <th>Transaction</th><th>Agent</th><th>Intent</th>
        <th style="text-align:right">Amount</th><th>Decision</th><th>Time</th>
      </tr></thead>
      <tbody>{rows}</tbody>
    </table>
    </div>
    """, unsafe_allow_html=True)


    # ── Bottom row: Decision Summary + Pending Review + Agent Activity ──
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown('<div class="rz-section-title">Decision Summary</div>', unsafe_allow_html=True)
        total = max(stats["total_authorizations"], 1)
        allowed_pct = int(stats["transactions_executed"] / total * 100)
        review_pct = int(stats["requires_review"] / total * 100)
        blocked_pct = int(stats["blocked"] / total * 100)
        st.markdown(f"""
        <div class="rz-card">
          <div class="rz-bar-wrap">
            <div class="rz-bar-labels"><span style="color:#1e8e3e">Allowed</span><span class="muted">{allowed_pct}%</span></div>
            <div class="rz-bar-track"><div class="rz-bar-fill" style="background:#1e8e3e;width:{allowed_pct}%"></div></div>
          </div>
          <div class="rz-bar-wrap">
            <div class="rz-bar-labels"><span style="color:#e37400">Review</span><span class="muted">{review_pct}%</span></div>
            <div class="rz-bar-track"><div class="rz-bar-fill" style="background:#e37400;width:{review_pct}%"></div></div>
          </div>
          <div class="rz-bar-wrap">
            <div class="rz-bar-labels"><span style="color:#d93025">Blocked</span><span class="muted">{blocked_pct}%</span></div>
            <div class="rz-bar-track"><div class="rz-bar-fill" style="background:#d93025;width:{blocked_pct}%"></div></div>
          </div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        # Pending Review summary
        review_txns = [t for t in txns if db.get_policy_decision(t["transaction_id"]) and db.get_policy_decision(t["transaction_id"])["decision"] == "REVIEW"]
        st.markdown(f'<div class="rz-section-title">Pending Review · {len(review_txns)}</div>', unsafe_allow_html=True)
        
        rows_html = ""
        if review_txns:
            for rt in review_txns[:3]:
                agent = db.get_agent(rt["agent_id"])
                agent_name = agent["name"] if agent else rt["agent_id"]
                rows_html += f'<div class="rz-detail-row"><span style="font-size:12px">{agent_name} · {_amt(rt["amount"])}</span><span class="muted" style="font-size:11px">{_ago(rt["created_at"])}</span></div>'
        else:
            rows_html = '<div style="font-size:12px;color:#9ca3af;padding:4px 0">No pending reviews.</div>'

        st.markdown(f'<div class="rz-card">{rows_html}</div>', unsafe_allow_html=True)
        if review_txns:
            if st.button("View all →", key="ov_review_all"):
                st.session_state.page = "review"
                st.rerun()

    with col3:
        # Agent Activity summary (top 3 only)
        st.markdown(f'<div class="rz-section-title">Agent Activity · {len(agents)}</div>', unsafe_allow_html=True)
        activity_html = ""
        for a in agents[:3]:
            dot_color = "#1e8e3e" if a["status"] == "active" else "#9ca3af"
            activity_html += f'<div class="rz-detail-row"><span style="font-size:12px"><span style="width:6px;height:6px;border-radius:50%;background:{dot_color};display:inline-block;margin-right:6px"></span>{a["name"]}</span><span class="muted" style="font-size:11px">{a["transaction_count"]} txns · {_amt(a.get("total_spent", 0))}</span></div>'
        if len(agents) > 3:
            activity_html += f'<div style="font-size:11px;color:#9ca3af;padding-top:4px">+{len(agents) - 3} more</div>'
            
        st.markdown(f'<div class="rz-card">{activity_html}</div>', unsafe_allow_html=True)
        if st.button("View all →", key="ov_agents_all"):
            st.session_state.page = "agents"
            st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────
# PAGE: Agents
# ─────────────────────────────────────────────────────────────────
def page_agents():
    all_agents = db.list_agents()

    st.markdown("""
    <div class="rz-page-header">
      <div><div class="rz-page-title">Agents</div></div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown('<div class="rz-content">', unsafe_allow_html=True)

    detail_id = getattr(st.session_state, "agent_detail_id", None)
    if detail_id:
        if st.button("← Back to Agents", key="agents_back_list"):
            st.session_state.agent_detail_id = None
            st.rerun()
            
        a = db.get_agent(detail_id)
        if a:
            st.markdown(f'<div class="rz-section-title" style="margin-top:16px">{a["name"]}</div>', unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            with c1:
                st.markdown(f"""
                <div class="rz-card">
                <div class="rz-card-header">Agent Details</div>
                <div class="rz-detail-row"><span class="rz-detail-label">Agent ID</span><span class="mono" style="color:var(--rz-blue)">{a['agent_id']}</span></div>
                <div class="rz-detail-row"><span class="rz-detail-label">Status</span>{_status_badge(a['status'])}</div>
                <div class="rz-detail-row"><span class="rz-detail-label">Owner</span><span class="rz-detail-value">{a['owner_id']}</span></div>
                <div class="rz-detail-row"><span class="rz-detail-label">Created</span><span class="muted">{_ago(a['created_at'])}</span></div>
                </div>
                """, unsafe_allow_html=True)
            with c2:
                st.markdown(f"""
                <div class="rz-card">
                <div class="rz-card-header">Activity</div>
                <div class="rz-detail-row"><span class="rz-detail-label">Transactions</span><span class="rz-detail-value">{a['transaction_count']}</span></div>
                <div class="rz-detail-row"><span class="rz-detail-label">Total Spent</span><span class="rz-detail-value">{_amt(a.get('total_spent', 0))}</span></div>
                <div class="rz-detail-row"><span class="rz-detail-label">Spending Limit</span><span class="rz-detail-value">{_amt(a['spending_limit']) if a.get('spending_limit') else '—'}</span></div>
                <div class="rz-detail-row"><span class="rz-detail-label">Permissions</span><span class="rz-detail-value">{', '.join(a.get('permissions', []))}</span></div>
                </div>
                """, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        return

    if st.button("← Overview", key="agents_back_ov"):
        st.session_state.page = "overview"
        st.rerun()

    # Filters
    fc1, fc2, _, _ = st.columns([2, 1, 1, 2])
    with fc1:
        search_q = st.text_input("Search", placeholder="Search agents…", key="agent_search", label_visibility="collapsed")
    with fc2:
        status_filter = st.selectbox("Status", ["All", "Active", "Inactive", "Suspended"], key="agent_status_filter", label_visibility="collapsed")

    # Apply filters
    agents = all_agents
    if search_q:
        sq = search_q.lower()
        agents = [a for a in agents if sq in a["name"].lower() or sq in a["agent_id"].lower()]
    if status_filter != "All":
        agents = [a for a in agents if a["status"] == status_filter.lower()]

    # Pagination
    page_size = 10
    total_pages = max(1, (len(agents) + page_size - 1) // page_size)
    if "agents_page" not in st.session_state:
        st.session_state.agents_page = 0
    current_pg = st.session_state.agents_page
    paged_agents = agents[current_pg * page_size : (current_pg + 1) * page_size]

    # Agent table using columns so Agent names are clickable buttons
    h1, h2, h3, h4, h5, h6 = st.columns([2.0, 1.2, 1.2, 1.4, 1.4, 1.2])
    with h1:
        st.markdown('<div style="font-size:11px;font-weight:600;color:#5f6368;text-transform:uppercase;padding:4px 0">Agent</div>', unsafe_allow_html=True)
    with h2:
        st.markdown('<div style="font-size:11px;font-weight:600;color:#5f6368;text-transform:uppercase;padding:4px 0">Status</div>', unsafe_allow_html=True)
    with h3:
        st.markdown('<div style="font-size:11px;font-weight:600;color:#5f6368;text-transform:uppercase;padding:4px 0">Transactions</div>', unsafe_allow_html=True)
    with h4:
        st.markdown('<div style="font-size:11px;font-weight:600;color:#5f6368;text-transform:uppercase;padding:4px 0;text-align:right">Spent</div>', unsafe_allow_html=True)
    with h5:
        st.markdown('<div style="font-size:11px;font-weight:600;color:#5f6368;text-transform:uppercase;padding:4px 0;text-align:right">Limit</div>', unsafe_allow_html=True)
    with h6:
        st.markdown('<div style="font-size:11px;font-weight:600;color:#5f6368;text-transform:uppercase;padding:4px 0">Last Activity</div>', unsafe_allow_html=True)

    st.markdown('<div style="border-bottom:1px solid #e5e7eb;margin-bottom:8px"></div>', unsafe_allow_html=True)

    if not paged_agents:
        st.markdown('<div style="font-size:13px;color:#9ca3af;padding:20px;text-align:center">No agents match filters.</div>', unsafe_allow_html=True)

    for a in paged_agents:
        c1, c2, c3, c4, c5, c6 = st.columns([2.0, 1.2, 1.2, 1.4, 1.4, 1.2])
        with c1:
            if st.button(a['name'], key=f"agent_name_btn_{a['agent_id']}", use_container_width=True):
                st.session_state.agent_detail_id = a["agent_id"]
                st.rerun()
        with c2:
            st.markdown(f'<div style="padding-top:4px">{_status_badge(a["status"])}</div>', unsafe_allow_html=True)
        with c3:
            st.markdown(f'<div style="padding-top:6px;font-size:13px;color:#111827">{a["transaction_count"]}</div>', unsafe_allow_html=True)
        with c4:
            st.markdown(f'<div style="padding-top:6px;text-align:right;font-weight:600;font-size:13px;color:#111827">{_amt(a.get("total_spent", 0))}</div>', unsafe_allow_html=True)
        with c5:
            st.markdown(f'<div style="padding-top:6px;text-align:right;font-size:13px;color:#111827">{_amt(a["spending_limit"]) if a.get("spending_limit") else "—"}</div>', unsafe_allow_html=True)
        with c6:
            st.markdown(f'<div style="padding-top:6px;color:#9ca3af;font-size:12px">{_ago(a["created_at"])}</div>', unsafe_allow_html=True)

        st.markdown('<div style="border-bottom:1px solid #f3f4f6;margin:4px 0 8px"></div>', unsafe_allow_html=True)

    # Pagination controls
    if total_pages > 1:
        pg_cols = st.columns([1, 1, 4])
        with pg_cols[0]:
            if st.button("← Previous", key="agents_prev", disabled=current_pg == 0):
                st.session_state.agents_page = max(0, current_pg - 1)
                st.rerun()
        with pg_cols[1]:
            if st.button("Next →", key="agents_next", disabled=current_pg >= total_pages - 1):
                st.session_state.agents_page = current_pg + 1
                st.rerun()
        with pg_cols[2]:
            st.markdown(f'<div style="padding-top:8px;font-size:11px;color:#9ca3af">Page {current_pg + 1} of {total_pages} · {len(agents)} agents</div>', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────
# PAGE: Authorizations (was Intents)
# ─────────────────────────────────────────────────────────────────
def page_intents():
    st.markdown("""
    <div class="rz-page-header">
      <div><div class="rz-page-title">Authorizations</div></div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown('<div class="rz-content">', unsafe_allow_html=True)

    # Create Authorization
    st.markdown('<div class="rz-section-title">Create Authorization</div>', unsafe_allow_html=True)
    with st.container(border=True):
        st.markdown('<div style="font-size:13px;color:#5f6368;margin-bottom:8px">Describe what the agent is allowed to do.</div>', unsafe_allow_html=True)

        raw_text = st.text_area("Instruction", placeholder='e.g. "Buy running shoes under ₹8,000 from a trusted seller."', height=68, key="intent_input", label_visibility="collapsed")

        c1, c2 = st.columns([1, 2])
        with c1:
            if st.button("Create Authorization", key="parse_btn", use_container_width=True, disabled=not raw_text):
                if raw_text.strip():
                    with st.spinner("Parsing…"):
                        parsed, used_ai = intent_parser.parse_intent(raw_text.strip())

                    intent_id = f"intent_{uuid.uuid4().hex[:6]}"
                    now = datetime.now(timezone.utc)
                    intent_dict = {
                        "intent_id": intent_id,
                        "user_id": "user_001",
                        "raw_text": raw_text.strip(),
                        "purpose": parsed.get("purpose"),
                        "category": parsed.get("category"),
                        "max_amount": parsed.get("max_amount"),
                        "currency": parsed.get("currency", "INR"),
                        "merchant_requirement": parsed.get("merchant_requirement"),
                        "status": IntentStatus.ACTIVE.value,
                        "expires_at": (now + timedelta(hours=24)).isoformat(),
                        "created_at": now.isoformat(),
                        "parsed_json": json.dumps(parsed),
                    }
                    db.save_intent(intent_dict)
                    st.session_state.last_parsed_intent = intent_dict
                    st.session_state.last_used_ai = used_ai
                    st.rerun()

        with c2:
            parser_label = "✦ Claude AI" if intent_parser.is_ai_available() else "⚡ Regex parser"
            st.markdown(f'<div style="padding-top:8px;font-size:11px;color:#9ca3af">{parser_label}</div>', unsafe_allow_html=True)

    # Last parsed result — Authorization Preview
    if hasattr(st.session_state, "last_parsed_intent") and st.session_state.last_parsed_intent:
        intent = st.session_state.last_parsed_intent
        used_ai = getattr(st.session_state, "last_used_ai", False)
        parsed = json.loads(intent.get("parsed_json", "{}"))

        st.markdown('<div class="rz-section-title">Authorization Preview</div>', unsafe_allow_html=True)
        left, right = st.columns(2)
        with left:
            st.markdown(f"""
            <div class="rz-card">
              <div class="rz-card-header">Original Intent</div>
              <div style="font-size:13px;color:#1a1a1a;padding:10px;background:#f8f9fa;border-radius:4px;border:1px solid #e5e7eb;font-style:italic">"{intent['raw_text']}"</div>
              <div style="margin-top:8px;font-size:11px;color:#9ca3af">
                ID: <span style="color:var(--rz-blue)">{intent['intent_id']}</span> ·
                Parser: <span class="rz-badge {'rz-badge-info' if used_ai else 'rz-badge-inactive'}">{'Claude AI' if used_ai else 'Regex'}</span>
              </div>
            </div>
            """, unsafe_allow_html=True)
        with right:
            st.markdown(f"""
            <div class="rz-card">
              <div class="rz-card-header">Structured Authorization</div>
              <div class="rz-code">{json.dumps(parsed, indent=2)}</div>
            </div>
            """, unsafe_allow_html=True)

    # All authorizations table
    intents = db.list_intents()
    if intents:
        st.markdown('<div class="rz-section-title">All Authorizations</div>', unsafe_allow_html=True)
        rows = ""
        for intent in intents:
            status_cls = "rz-badge-active" if intent["status"] == "active" else "rz-badge-inactive"
            rows += f"""
            <tr>
              <td class="mono nowrap">{intent['intent_id']}</td>
              <td style="max-width:280px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{intent['raw_text']}</td>
              <td>{intent.get('category') or '—'}</td>
              <td class="amt">{_amt(intent['max_amount']) if intent.get('max_amount') else '<span class="muted">no limit</span>'}</td>
              <td>{intent.get('currency', 'INR')}</td>
              <td><span class="rz-badge {status_cls}">{intent['status']}</span></td>
              <td class="muted nowrap">{_ago(intent['created_at'])}</td>
            </tr>"""
        st.markdown(f"""
        <div class="rz-table-wrap">
        <table class="rz-tbl">
          <thead><tr><th>Authorization</th><th>Purpose</th><th>Category</th><th style="text-align:right">Max Amount</th><th>Currency</th><th>Status</th><th>Created</th></tr></thead>
          <tbody>{rows}</tbody>
        </table>
        </div>
        """, unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────
# PAGE: Transactions
# ─────────────────────────────────────────────────────────────────
def page_transactions():
    st.markdown("""
    <div class="rz-page-header">
      <div><div class="rz-page-title">Transactions</div></div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown('<div class="rz-content">', unsafe_allow_html=True)

    if st.button("← Overview", key="txns_back_ov"):
        st.session_state.page = "overview"
        st.rerun()
    with st.expander("+ Create Transaction", expanded=False):
        tc1, tc2 = st.columns(2)
        with tc1:
            agents_list = db.list_agents()
            agent_opts = {a["name"]: a["agent_id"] for a in agents_list}
            agent_name = st.selectbox("Agent", list(agent_opts.keys()), key="txn_agent")
            intents_list = db.list_intents()
            active_intents = [i for i in intents_list if i["status"] == "active"]
            intent_opts = {f"{i['intent_id']}: {i['raw_text'][:40]}": i["intent_id"] for i in active_intents}
            intent_sel = st.selectbox("Authorization", list(intent_opts.keys()), key="txn_intent") if intent_opts else None
        with tc2:
            amount = st.number_input("Amount (₹)", min_value=1.0, value=6999.0, key="txn_amount")
            category = st.text_input("Category", value="", key="txn_category")
            merchant = st.text_input("Merchant", value="", key="txn_merchant")
            description = st.text_input("Description", value="", key="txn_desc")

        if st.button("Submit Transaction", key="txn_submit", disabled=not intent_sel):
            if intent_sel:
                result = transaction_service.create_full_flow(
                    agent_id=agent_opts[agent_name],
                    intent_id=intent_opts[intent_sel],
                    amount=amount,
                    category=category or None,
                    merchant_id="merchant_custom",
                    merchant_name=merchant or None,
                    description=description or None,
                )
                st.session_state.page = "txn_detail"
                st.session_state.detail_txn_id = result["transaction_id"]
                st.rerun()

    # Filters
    fc1, fc2, fc3, fc4 = st.columns([2, 1, 1, 1])
    with fc1:
        txn_search = st.text_input("Search", placeholder="Search transactions…", key="txn_search", label_visibility="collapsed")
    with fc2:
        decision_filter = st.selectbox("Decision", ["All", "ALLOW", "BLOCK", "REVIEW"], key="txn_filter", label_visibility="collapsed")
    with fc3:
        agent_filter_opts = ["All Agents"] + [a["name"] for a in db.list_agents()]
        agent_filter = st.selectbox("Agent", agent_filter_opts, key="txn_agent_filter", label_visibility="collapsed")

    # Transaction table
    all_txns = db.list_transactions()
    if not all_txns:
        st.info("No transactions yet. Create one above.")
        st.markdown('</div>', unsafe_allow_html=True)
        return

    # Apply filters
    filtered_txns = []
    for t in all_txns:
        dec = db.get_policy_decision(t["transaction_id"])
        decision_val = dec["decision"] if dec else "PENDING"
        if decision_filter != "All" and decision_val != decision_filter:
            continue
        if agent_filter != "All Agents":
            agent = db.get_agent(t["agent_id"])
            if agent and agent["name"] != agent_filter:
                continue
        if txn_search:
            sq = txn_search.lower()
            intent = db.get_intent(t["intent_id"])
            searchable = f"{t['transaction_id']} {t.get('description','')} {intent['raw_text'] if intent else ''}".lower()
            if sq not in searchable:
                continue
        filtered_txns.append(t)

    # Pagination
    page_size = 15
    total_pages = max(1, (len(filtered_txns) + page_size - 1) // page_size)
    if "txns_page" not in st.session_state:
        st.session_state.txns_page = 0
    current_pg = st.session_state.txns_page
    paged_txns = filtered_txns[current_pg * page_size : (current_pg + 1) * page_size]

    # Render table header and rows with parallel Action column
    h1, h2, h3, h4, h5, h6, h7, h8 = st.columns([1.1, 1.3, 2.2, 1.1, 1.1, 1.5, 0.8, 1.0])
    with h1:
        st.markdown('<div style="font-size:11px;font-weight:600;color:#5f6368;text-transform:uppercase;padding:4px 0">Transaction ID</div>', unsafe_allow_html=True)
    with h2:
        st.markdown('<div style="font-size:11px;font-weight:600;color:#5f6368;text-transform:uppercase;padding:4px 0">Agent</div>', unsafe_allow_html=True)
    with h3:
        st.markdown('<div style="font-size:11px;font-weight:600;color:#5f6368;text-transform:uppercase;padding:4px 0">Intent</div>', unsafe_allow_html=True)
    with h4:
        st.markdown('<div style="font-size:11px;font-weight:600;color:#5f6368;text-transform:uppercase;padding:4px 0;text-align:right">Amount</div>', unsafe_allow_html=True)
    with h5:
        st.markdown('<div style="font-size:11px;font-weight:600;color:#5f6368;text-transform:uppercase;padding:4px 0">Decision</div>', unsafe_allow_html=True)
    with h6:
        st.markdown('<div style="font-size:11px;font-weight:600;color:#5f6368;text-transform:uppercase;padding:4px 0">Razorpay ID</div>', unsafe_allow_html=True)
    with h7:
        st.markdown('<div style="font-size:11px;font-weight:600;color:#5f6368;text-transform:uppercase;padding:4px 0">Created</div>', unsafe_allow_html=True)
    with h8:
        st.markdown('<div style="font-size:11px;font-weight:600;color:#5f6368;text-transform:uppercase;padding:4px 0;text-align:center">Action</div>', unsafe_allow_html=True)

    st.markdown('<div style="border-bottom:1px solid #e5e7eb;margin-bottom:8px"></div>', unsafe_allow_html=True)

    if not paged_txns:
        st.markdown('<div style="font-size:13px;color:#9ca3af;padding:20px;text-align:center">No transactions match filters.</div>', unsafe_allow_html=True)

    for t in paged_txns:
        dec = db.get_policy_decision(t["transaction_id"])
        decision_val = dec["decision"] if dec else "PENDING"
        badge = _badge(decision_val)
        agent = db.get_agent(t["agent_id"])
        agent_name = agent["name"] if agent else t["agent_id"]
        intent = db.get_intent(t["intent_id"])
        intent_text = (intent["raw_text"][:40] + "…") if intent and len(intent["raw_text"]) > 40 else (intent["raw_text"] if intent else "—")
        rz = db.get_razorpay_transaction(t["transaction_id"])
        rz_id = rz["razorpay_order_id"][:16] + "…" if rz and rz.get("razorpay_order_id") else "—"

        c1, c2, c3, c4, c5, c6, c7, c8 = st.columns([1.1, 1.3, 2.2, 1.1, 1.1, 1.5, 0.8, 1.0])
        with c1:
            st.markdown(f'<div class="mono" style="padding-top:4px;font-size:13px;color:#111827">{_sid(t["transaction_id"])}</div>', unsafe_allow_html=True)
        with c2:
            st.markdown(f'<div style="padding-top:4px;font-size:13px;font-weight:500;color:#111827">{agent_name}</div>', unsafe_allow_html=True)
        with c3:
            st.markdown(f'<div style="padding-top:4px;color:#5f6368;font-size:13px">{intent_text}</div>', unsafe_allow_html=True)
        with c4:
            st.markdown(f'<div style="padding-top:4px;text-align:right;font-weight:600;font-size:13px;color:#111827">{_amt(t["amount"])}</div>', unsafe_allow_html=True)
        with c5:
            st.markdown(f'<div style="padding-top:2px">{badge}</div>', unsafe_allow_html=True)
        with c6:
            st.markdown(f'<div class="mono" style="padding-top:4px;color:#9ca3af;font-size:11px">{rz_id}</div>', unsafe_allow_html=True)
        with c7:
            st.markdown(f'<div style="padding-top:4px;color:#9ca3af;font-size:12px">{_ago(t["created_at"])}</div>', unsafe_allow_html=True)
        with c8:
            if st.button("View", key=f"txn_act_{t['transaction_id']}", use_container_width=True):
                st.session_state.page = "txn_detail"
                st.session_state.detail_txn_id = t["transaction_id"]
                st.rerun()

        st.markdown('<div style="border-bottom:1px solid #f3f4f6;margin:4px 0 8px"></div>', unsafe_allow_html=True)

    # Pagination controls
    if total_pages > 1:
        pg_cols = st.columns([1, 1, 4])
        with pg_cols[0]:
            if st.button("← Previous", key="txns_prev", disabled=current_pg == 0):
                st.session_state.txns_page = max(0, current_pg - 1)
                st.rerun()
        with pg_cols[1]:
            if st.button("Next →", key="txns_next", disabled=current_pg >= total_pages - 1):
                st.session_state.txns_page = current_pg + 1
                st.rerun()
        with pg_cols[2]:
            st.markdown(f'<div style="padding-top:8px;font-size:11px;color:#9ca3af">Page {current_pg + 1} of {total_pages} · {len(filtered_txns)} transactions</div>', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────
# PAGE: Pending Review
# ─────────────────────────────────────────────────────────────────
def page_review():
    st.markdown("""
    <div class="rz-page-header">
      <div><div class="rz-page-title">Pending Review</div><div class="rz-page-subtitle">Transactions requiring human approval.</div></div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown('<div class="rz-content">', unsafe_allow_html=True)

    if st.button("← Overview", key="review_back_ov"):
        st.session_state.page = "overview"
        st.rerun()

    txns = db.list_transactions()
    review_txns = []
    for t in txns:
        dec = db.get_policy_decision(t["transaction_id"])
        if dec and dec["decision"] == "REVIEW":
            review_txns.append((t, dec))

    if not review_txns:
        st.info("No transactions pending review.")
        st.markdown('</div>', unsafe_allow_html=True)
        return

    # Render table header and rows with parallel Action column
    h1, h2, h3, h4, h5, h6, h7 = st.columns([1.1, 1.3, 2.3, 1.1, 2.5, 0.8, 1.1])
    with h1:
        st.markdown('<div style="font-size:11px;font-weight:600;color:#5f6368;text-transform:uppercase;padding:4px 0">Transaction</div>', unsafe_allow_html=True)
    with h2:
        st.markdown('<div style="font-size:11px;font-weight:600;color:#5f6368;text-transform:uppercase;padding:4px 0">Agent</div>', unsafe_allow_html=True)
    with h3:
        st.markdown('<div style="font-size:11px;font-weight:600;color:#5f6368;text-transform:uppercase;padding:4px 0">Intent</div>', unsafe_allow_html=True)
    with h4:
        st.markdown('<div style="font-size:11px;font-weight:600;color:#5f6368;text-transform:uppercase;padding:4px 0;text-align:right">Amount</div>', unsafe_allow_html=True)
    with h5:
        st.markdown('<div style="font-size:11px;font-weight:600;color:#5f6368;text-transform:uppercase;padding:4px 0">Reason</div>', unsafe_allow_html=True)
    with h6:
        st.markdown('<div style="font-size:11px;font-weight:600;color:#5f6368;text-transform:uppercase;padding:4px 0">Created</div>', unsafe_allow_html=True)
    with h7:
        st.markdown('<div style="font-size:11px;font-weight:600;color:#5f6368;text-transform:uppercase;padding:4px 0;text-align:center">Action</div>', unsafe_allow_html=True)

    st.markdown('<div style="border-bottom:1px solid #e5e7eb;margin-bottom:8px"></div>', unsafe_allow_html=True)

    for t, dec in review_txns:
        agent = db.get_agent(t["agent_id"])
        agent_name = agent["name"] if agent else t["agent_id"]
        intent = db.get_intent(t["intent_id"])
        intent_text = (intent["raw_text"][:45] + "…") if intent and len(intent["raw_text"]) > 45 else (intent["raw_text"] if intent else "—")
        reason = dec.get("reason_detail", dec.get("reason_code", "—"))

        c1, c2, c3, c4, c5, c6, c7 = st.columns([1.1, 1.3, 2.3, 1.1, 2.5, 0.8, 1.1])
        with c1:
            st.markdown(f'<div class="mono" style="padding-top:4px;font-size:13px;color:#111827">{_sid(t["transaction_id"])}</div>', unsafe_allow_html=True)
        with c2:
            st.markdown(f'<div style="padding-top:4px;font-size:13px;font-weight:500;color:#111827">{agent_name}</div>', unsafe_allow_html=True)
        with c3:
            st.markdown(f'<div style="padding-top:4px;color:#5f6368;font-size:13px">{intent_text}</div>', unsafe_allow_html=True)
        with c4:
            st.markdown(f'<div style="padding-top:4px;text-align:right;font-weight:600;font-size:13px;color:#111827">{_amt(t["amount"])}</div>', unsafe_allow_html=True)
        with c5:
            st.markdown(f'<div style="padding-top:4px;color:#e37400;font-size:12px">{reason}</div>', unsafe_allow_html=True)
        with c6:
            st.markdown(f'<div style="padding-top:4px;color:#9ca3af;font-size:12px">{_ago(t["created_at"])}</div>', unsafe_allow_html=True)
        with c7:
            if st.button("Review", key=f"rev_btn_{t['transaction_id']}", use_container_width=True):
                st.session_state.page = "txn_detail"
                st.session_state.detail_txn_id = t["transaction_id"]
                st.rerun()

        st.markdown('<div style="border-bottom:1px solid #f3f4f6;margin:4px 0 8px"></div>', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────
# PAGE: Transaction Detail
# ─────────────────────────────────────────────────────────────────
def page_txn_detail():
    txn_id = getattr(st.session_state, "detail_txn_id", None)
    if not txn_id:
        st.session_state.page = "transactions"
        st.rerun()
        return

    txn = db.get_transaction(txn_id)
    dec = db.get_policy_decision(txn_id)
    intent = db.get_intent(txn["intent_id"]) if txn else None
    agent = db.get_agent(txn["agent_id"]) if txn else None
    rz = db.get_razorpay_transaction(txn_id)
    evidence = db.get_audit_evidence(txn_id)

    decision_val = dec["decision"] if dec else "UNKNOWN"

    # Page header
    mode_label = ""
    if rz:
        mode_label = f'<span class="rz-badge rz-badge-sim" style="margin-left:8px">SIMULATED</span>' if rz.get("is_simulated") else f'<span class="rz-badge rz-badge-test" style="margin-left:8px">TEST</span>'

    st.markdown(f"""
    <div class="rz-page-header">
      <div>
        <div class="rz-page-title">Transaction #{_sid(txn_id)}{mode_label}</div>
        <div class="rz-page-subtitle">{txn.get('description','—')} · {_amt(txn['amount'])} · {agent['name'] if agent else txn['agent_id']}</div>
      </div>
      <div class="rz-page-actions">{_badge(decision_val)}</div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown('<div class="rz-content">', unsafe_allow_html=True)

    if st.button("← Back to Transactions", key="back_txns"):
        st.session_state.page = "transactions"
        st.rerun()

    # ── Trust Chain ──
    st.markdown('<div class="rz-section-title">Trust Chain</div>', unsafe_allow_html=True)
    chain = []
    if intent:
        chain.append(("blue", "User Intent", f'"{intent["raw_text"]}"'))
    if intent:
        chain.append(("blue", "Structured Authorization", f'Max: {_amt(intent["max_amount"]) if intent.get("max_amount") else "no limit"} · Category: {intent.get("category") or "—"} · Currency: {intent.get("currency", "INR")}'))
    chain.append(("blue", "Agent", f'{agent["name"] if agent else txn["agent_id"]}'))
    chain.append(("blue", "Transaction Proposal", f'{_amt(txn["amount"])} · {txn.get("description") or "—"} · {txn.get("merchant_name") or "—"}'))
    dot_color = "green" if decision_val == "ALLOW" else ("red" if decision_val == "BLOCK" else "yellow")
    chain.append((dot_color, "Policy Decision", _badge(decision_val)))
    if rz and rz.get("razorpay_order_id"):
        chain.append(("green", "Razorpay Transaction", f'Order: <span class="mono" style="color:var(--rz-blue)">{rz["razorpay_order_id"]}</span>'))
    else:
        chain.append(("red", "Razorpay Transaction", "Not executed — blocked before payment"))
    if evidence:
        chain.append(("green" if evidence.get("verified") else "blue", "Evidence", f'Hash: <span class="mono" style="font-size:11px">{evidence.get("evidence_hash","—")[:24]}…</span>'))

    steps_html = "".join([f'<div class="rz-chain-step"><div class="rz-chain-dot {dot_cls}"></div><div><div class="rz-chain-label">{label}</div><div class="rz-chain-value">{value}</div></div></div>' for dot_cls, label, value in chain])
    st.markdown(f'<div class="rz-card" style="padding:16px 16px 8px">{steps_html}</div>', unsafe_allow_html=True)

    # ── Two columns ──
    left, right = st.columns(2)

    with left:
        # Authorization
        if intent:
            auth_items = [
                ("Maximum Amount", _amt(intent['max_amount']) if intent.get('max_amount') else 'no limit'),
                ("Purpose", intent.get('purpose') or '—'),
                ("Category", intent.get('category') or '—'),
                ("Currency", intent.get('currency', 'INR')),
                ("Expiry", _ago(intent.get('expires_at', '')) if intent.get('expires_at') else '—'),
                ("Status", f'<span class="rz-badge rz-badge-active">{intent["status"]}</span>'),
            ]
            rows = "".join([f'<div class="rz-detail-row"><span class="rz-detail-label">{lbl}</span><span class="rz-detail-value">{v}</span></div>' for lbl, v in auth_items])
            st.markdown(f'<div class="rz-card"><div class="rz-card-header">Authorization</div>{rows}</div>', unsafe_allow_html=True)

        # Razorpay Execution
        if rz:
            rz_items = [
                ("Order ID", f'<span class="mono" style="color:var(--rz-blue)">{rz.get("razorpay_order_id", "—")}</span>'),
                ("Status", rz.get("status", "—")),
                ("Amount", _amt(rz.get("amount", 0))),
                ("Mode", '<span class="rz-badge rz-badge-sim">Simulated</span>' if rz.get("is_simulated") else '<span class="rz-badge rz-badge-test">Test Mode</span>'),
            ]
            rows = "".join([f'<div class="rz-detail-row"><span class="rz-detail-label">{lbl}</span><span class="rz-detail-value">{v}</span></div>' for lbl, v in rz_items])
        else:
            rows = '<div style="font-size:13px;color:#d93025;padding:4px 0">Blocked before payment execution. No Razorpay call was made.</div>'
        st.markdown(f'<div class="rz-card"><div class="rz-card-header">Razorpay Execution</div>{rows}</div>', unsafe_allow_html=True)

    with right:
        # Policy Evaluation
        if dec:
            checks = dec.get("checks", {})
            checks_html = ""
            for check_name, result in checks.items():
                icon = _check_icon(result)
                label = check_name.replace("_", " ").title()
                checks_html += f'<div class="rz-check"><span style="color:#1a1a1a">{label}</span>{icon}</div>'
            checks_html += f'<div style="margin-top:8px;padding-top:8px;border-top:1px solid #f3f4f6">Decision: {_badge(decision_val)}</div>'
            st.markdown(f'<div class="rz-card"><div class="rz-card-header">Policy Evaluation</div>{checks_html}</div>', unsafe_allow_html=True)

        # Evidence
        if evidence:
            hashes = [
                ("Intent Hash", evidence.get("intent_hash", "—")),
                ("Decision Hash", evidence.get("decision_hash", "—")),
                ("Evidence Hash", evidence.get("evidence_hash", "—")),
            ]
            rows = "".join([f'<div class="rz-detail-row"><span class="rz-detail-label">{lbl}</span><span class="mono" style="font-size:11px">{h[:28]}…</span></div>' for lbl, h in hashes])
            verified = evidence.get("verified", False)
            v_bg = "#e6f4ea" if verified else "#f3f4f6"
            v_color = "#137333" if verified else "#5f6368"
            v_text = "✓ Evidence integrity verified" if verified else "Not yet verified"
            verified_html = f'<div style="margin-top:8px;padding:6px 10px;border-radius:4px;background:{v_bg};color:{v_color};font-size:12px;font-weight:500">{v_text}</div>'
            st.markdown(f'<div class="rz-card"><div class="rz-card-header">Evidence</div>{rows}{verified_html}</div>', unsafe_allow_html=True)

            if st.button("Verify Evidence", key="verify_ev_detail"):
                is_valid, details = evidence_service.verify_evidence(txn_id)
                if is_valid:
                    st.success("✓ Evidence integrity verified — all hashes match.")
                else:
                    st.error("❌ Evidence integrity invalid")
                    st.json(details)
                st.rerun()

    # AI Explanation
    if dec:
        explanation = ai_explainer.explain_decision(dec, txn, intent)
        st.markdown(f"""
        <div class="rz-ai-panel">
          <div style="font-size:11px;font-weight:600;color:var(--rz-blue);text-transform:uppercase;letter-spacing:0.3px;margin-bottom:6px">
            {'✦ Claude AI Explanation' if intent_parser.is_ai_available() else '⚡ Deterministic Explanation'}
          </div>
          <div style="font-size:13px;color:#1a1a1a;margin-bottom:6px"><strong>{explanation.get('summary','')}</strong></div>
          <div style="font-size:13px;color:#374151;margin-bottom:8px">{explanation.get('detail','')}</div>
          <div style="border-top:1px solid #e0e7ff;padding-top:8px">
            <div style="font-size:11px;font-weight:600;color:var(--rz-blue);text-transform:uppercase;letter-spacing:0.3px;margin-bottom:4px">Recommendation</div>
            <div style="font-size:13px;color:#374151">{explanation.get('recommendation','')}</div>
          </div>
        </div>
        """, unsafe_allow_html=True)

    # Manual Override (if REVIEW)
    if decision_val == "REVIEW":
        st.markdown('<div class="rz-section-title" style="margin-top:16px">Manual Override</div>', unsafe_allow_html=True)
        st.markdown('<div class="rz-card">', unsafe_allow_html=True)
        c1, c2, c3 = st.columns([1, 1, 2])
        with c1:
            if st.button("✓ Approve & Execute", key=f"appr_{txn_id}", type="primary", use_container_width=True):
                res = transaction_service.approve_transaction(txn_id)
                if res.get("error"):
                    st.error(res["error"])
                else:
                    st.success("Transaction Approved and Executed!")
                st.rerun()
        with c2:
            if st.button("✗ Reject & Block", key=f"rej_{txn_id}", use_container_width=True):
                res = transaction_service.reject_transaction(txn_id)
                if res.get("error"):
                    st.error(res["error"])
                else:
                    st.success("Transaction Rejected.")
                st.rerun()
        with c3:
            st.markdown('<div style="font-size:12px;color:#6b7280;padding-top:8px">This will override the policy engine and cryptographically sign the new decision.</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # View full evidence link
    if evidence:
        if st.button("View Full Evidence →", key="view_evidence"):
            st.session_state.page = "audit"
            st.session_state.audit_txn_id = txn_id
            st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────
# PAGE: Audit & Evidence
# ─────────────────────────────────────────────────────────────────
def page_audit():
    st.markdown("""
    <div class="rz-page-header">
      <div><div class="rz-page-title">Audit & Evidence</div><div class="rz-page-subtitle">Cryptographic evidence chain for all transactions.</div></div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown('<div class="rz-content">', unsafe_allow_html=True)

    if st.button("← Overview", key="audit_back_ov"):
        st.session_state.page = "overview"
        st.rerun()

    target_txn = getattr(st.session_state, "audit_txn_id", None)

    evidences = db.list_audit_evidence()
    if not evidences:
        st.info("No audit evidence available yet. Run a transaction first.")
        st.markdown('</div>', unsafe_allow_html=True)
        return

    # Evidence list
    if not target_txn:
        rows = ""
        for ev in evidences:
            dec_data = json.loads(ev.get("policy_decision", "{}"))
            decision_val = dec_data.get("decision", "?")
            badge = _badge(decision_val)
            verified_icon = '<span style="color:#1e8e3e">✓</span>' if ev.get("verified") else '<span style="color:#9ca3af">—</span>'
            rows += f"""
            <tr>
              <td class="muted nowrap">{ev['created_at'][:19]}</td>
              <td class="mono nowrap">{_sid(ev['transaction_id'])}</td>
              <td>{ev.get('outcome','—')}</td>
              <td>{badge}</td>
              <td>{ev.get('agent_id','—')}</td>
              <td>{verified_icon}</td>
            </tr>"""

        st.markdown(f"""
        <div class="rz-table-wrap">
        <table class="rz-tbl">
          <thead><tr><th>Timestamp</th><th>Transaction</th><th>Event</th><th>Decision</th><th>Actor</th><th>Integrity</th></tr></thead>
          <tbody>{rows}</tbody>
        </table>
        </div>
        """, unsafe_allow_html=True)

        cols = st.columns(min(len(evidences), 4))
        for i, ev in enumerate(evidences[:4]):
            with cols[i]:
                if st.button(f"View {_sid(ev['transaction_id'])}", key=f"aud_view_{i}"):
                    st.session_state.audit_txn_id = ev["transaction_id"]
                    st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
        return

    # Detailed evidence view
    ev = db.get_audit_evidence(target_txn)
    if not ev:
        st.error("Evidence not found.")
        st.markdown('</div>', unsafe_allow_html=True)
        return

    if st.button("← Back to Evidence List", key="back_aud"):
        st.session_state.audit_txn_id = None
        st.rerun()

    dec_data = json.loads(ev.get("policy_decision", "{}"))
    decision_val = dec_data.get("decision", "?")

    # Authorization Chain
    st.markdown('<div class="rz-section-title">Authorization Chain</div>', unsafe_allow_html=True)
    chain_steps = [
        ("blue", "User Intent", f'"{ev.get("raw_intent", "—")}"'),
        ("blue", "Structured Authorization", f'<div class="rz-code" style="margin:4px 0;font-size:11px">{ev.get("structured_authorization","—")}</div>'),
        ("blue", "Agent", ev.get("agent_id", "—")),
        ("blue", "Transaction Proposal", f'<div class="rz-code" style="margin:4px 0;font-size:11px">{ev.get("agent_proposal","—")[:200]}</div>'),
        ("green" if decision_val == "ALLOW" else ("red" if decision_val == "BLOCK" else "yellow"),
         "Policy Decision", _badge(decision_val)),
    ]

    rz_data = json.loads(ev.get("razorpay_result", "{}"))
    if rz_data and rz_data.get("razorpay_order_id"):
        chain_steps.append(("green", "Razorpay Transaction", f'Order: <span class="mono" style="color:var(--rz-blue)">{rz_data["razorpay_order_id"]}</span>'))
    else:
        chain_steps.append(("red", "Razorpay Transaction", "Not executed — blocked before payment"))

    chain_steps.append(("green" if ev.get("outcome","").startswith("EXECUTED") else "red",
                        "Outcome", ev.get("outcome", "—")))

    steps_html = "".join([f'<div class="rz-chain-step"><div class="rz-chain-dot {dot_cls}"></div><div><div class="rz-chain-label">{label}</div><div class="rz-chain-value">{value}</div></div></div>' for dot_cls, label, value in chain_steps])
    st.markdown(f'<div class="rz-card" style="padding:16px 16px 8px">{steps_html}</div>', unsafe_allow_html=True)

    # Cryptographic Integrity
    st.markdown('<div class="rz-section-title">Cryptographic Integrity</div>', unsafe_allow_html=True)
    hashes = [
        ("Intent Hash", ev.get("intent_hash", "—")),
        ("Decision Hash", ev.get("decision_hash", "—")),
        ("Evidence Hash", ev.get("evidence_hash", "—")),
    ]
    rows = "".join([f'<div class="rz-detail-row"><span class="rz-detail-label">{lbl}</span><span class="mono" style="font-size:11px">{h[:32]}…</span></div>' for lbl, h in hashes])
    verified = ev.get("verified", False)
    v_bg = "#e6f4ea" if verified else "#fce8e6"
    v_color = "#137333" if verified else "#c5221f"
    v_text = "✓ Evidence integrity verified" if verified else "❌ Evidence integrity invalid"
    v_box = f'<div style="margin-top:8px;padding:8px 12px;border-radius:4px;background:{v_bg};color:{v_color};font-size:12px;font-weight:500">{v_text}</div>'
    st.markdown(f'<div class="rz-card">{rows}{v_box}</div>', unsafe_allow_html=True)

    if st.button("Verify Evidence", key="verify_ev", use_container_width=False):
        is_valid, details = evidence_service.verify_evidence(target_txn)
        if is_valid:
            st.success("✓ Evidence integrity verified — all hashes match.")
        else:
            st.error("❌ Evidence integrity invalid")
            st.json(details)
        st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────
# PAGE: Settings (Account & Settings)
# ─────────────────────────────────────────────────────────────────
def page_settings():
    st.markdown("""
    <div class="rz-page-header">
      <div><div class="rz-page-title">Account & Settings</div></div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown('<div class="rz-content">', unsafe_allow_html=True)

    ai_ok = intent_parser.is_ai_available()

    # Integrations
    st.markdown('<div class="rz-section-title">Integrations</div>', unsafe_allow_html=True)
    integrations = [
        ("Razorpay API", rz_status['detail'], rz_connected, "Connected" if rz_connected else "Simulated"),
        ("Claude AI", "Intent parsing + explanations" if ai_ok else "Deterministic fallback active", ai_ok, "Active" if ai_ok else "Optional"),
        ("Policy Engine", "10 deterministic checks", True, "Active"),
        ("Evidence Chain", "SHA-256 hashing · Integrity verification", True, "Active"),
    ]
    int_html = ""
    for label, desc, is_on, status in integrations:
        dot_color = "#1e8e3e" if is_on else "#9ca3af"
        badge_cls = "rz-badge-active" if is_on else "rz-badge-inactive"
        int_html += f"""
        <div class="rz-detail-row">
          <div>
            <div style="font-size:13px;color:#1a1a1a"><span style="width:6px;height:6px;border-radius:50%;background:{dot_color};display:inline-block;margin-right:8px"></span>{label}</div>
            <div style="font-size:11px;color:#9ca3af;margin-left:14px">{desc}</div>
          </div>
          <span class="rz-badge {badge_cls}">{status}</span>
        </div>
        """
    st.markdown(f'<div class="rz-card">{int_html}</div>', unsafe_allow_html=True)

    # About
    st.markdown('<div class="rz-section-title">About</div>', unsafe_allow_html=True)
    st.markdown("""
    <div class="rz-card">
      <div style="font-size:14px;font-weight:600;color:#1a1a1a;margin-bottom:8px">Razorpay Agent Trust</div>
      <div style="font-size:13px;color:#5f6368;line-height:1.7">
        <p style="margin:0 0 8px">"Razorpay gives AI agents the ability to transact. Agent Trust gives businesses a verifiable boundary around what those agents are allowed to do."</p>
        <p style="margin:0 0 8px"><strong>AI interprets</strong> the user's intent. <strong>Deterministic policy enforces</strong> it. <strong>Razorpay executes</strong> only authorized transactions.</p>
        <p style="margin:0;color:#9ca3af;font-size:11px">Hackathon MVP · Uses Razorpay Test Mode</p>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # Data Management
    st.markdown('<div class="rz-section-title">Data Management</div>', unsafe_allow_html=True)
    with st.container(border=True):
        if st.button("Reset Demo Data", key="reset_demo"):
            db.reset_db()
            demo_data.seed_demo_data()
            st.success("Demo data reset.")
            st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────
# App Shell — Render
# ─────────────────────────────────────────────────────────────────
render_sidebar()

page = st.session_state.page
if page == "overview":
    page_overview()
elif page == "agents":
    page_agents()
elif page == "intents":
    page_intents()
elif page == "transactions":
    page_transactions()
elif page == "review":
    page_review()
elif page == "txn_detail":
    page_txn_detail()
elif page == "audit":
    page_audit()
elif page == "settings":
    page_settings()
else:
    page_overview()
