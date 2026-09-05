"""LLM-powered intent parser for Razorpay Agent Trust Gateway.

Converts natural-language purchasing requests into structured authorization constraints.
Falls back to regex-based extraction when Claude is unavailable.

CRITICAL: Never invents constraints. Uses null for unspecified values.
"""
from __future__ import annotations

import json
import os
import re
import logging
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an intent extraction service for a payment authorization system.
Convert the user's natural-language purchasing request into structured authorization constraints.

Rules:
- Never invent constraints that are not present in the user's message.
- Use null when a constraint is unspecified by the user.
- Do not authorize transactions. Do not execute payments.
- If the user mentions a price limit, extract it as max_amount (number only, no currency symbol).
- If the user mentions a category or product type, extract it as category.
- If the user mentions "trusted" or specific merchant requirements, extract as merchant_requirement.
- Currency is INR unless explicitly stated otherwise.
- Purpose should be one of: purchase, subscription, donation, service, or other.

Return ONLY valid JSON in this exact format:
{
  "purpose": "purchase",
  "category": "string or null",
  "max_amount": number_or_null,
  "currency": "INR",
  "merchant_requirement": "string or null"
}"""


def is_ai_available() -> bool:
    """Check if Groq API is configured."""
    return bool(os.getenv("GROQ_API_KEY", "").strip())


def parse_intent_ai(raw_text: str) -> dict:
    """Parse intent using Groq. Returns structured dict or raises on failure."""
    import groq

    client = groq.Groq()
    chat_completion = client.chat.completions.create(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": raw_text}
        ],
        model="groq/compound",
    )

    response_text = chat_completion.choices[0].message.content.strip()

    # Extract JSON from potential markdown code blocks
    if "```" in response_text:
        parts = response_text.split("```")
        json_part = parts[1] if len(parts) > 1 else parts[0]
        if json_part.startswith("json"):
            json_part = json_part[4:]
        response_text = json_part.strip()

    result = json.loads(response_text)

    # Validate required fields exist (can be null)
    required = ["purpose", "category", "max_amount", "currency", "merchant_requirement"]
    for field in required:
        if field not in result:
            result[field] = None

    # Ensure max_amount is numeric or null
    if result.get("max_amount") is not None:
        try:
            result["max_amount"] = float(result["max_amount"])
        except (ValueError, TypeError):
            result["max_amount"] = None

    return result


def parse_intent_fallback(raw_text: str) -> dict:
    """Regex-based fallback parser. Extracts what it can, uses null for rest."""
    text = raw_text.lower()

    # Extract amount
    max_amount = None
    amount_patterns = [
        r'under\s*(?:rs\.?|₹|inr)?\s*([\d,]+(?:\.\d+)?)',
        r'(?:below|less than|max|maximum|budget|limit)\s*(?:of\s*)?(?:rs\.?|₹|inr)?\s*([\d,]+(?:\.\d+)?)',
        r'(?:rs\.?|₹|inr)\s*([\d,]+(?:\.\d+)?)',
        r'([\d,]+(?:\.\d+)?)\s*(?:rs|rupees|inr)',
    ]
    for pattern in amount_patterns:
        match = re.search(pattern, text)
        if match:
            max_amount = float(match.group(1).replace(",", ""))
            break

    # Extract category
    category = None
    # Look for "buy [a/an/some] <category>" patterns
    cat_match = re.search(r'buy\s+(?:a\s+|an\s+|some\s+|me\s+(?:a\s+|an\s+|some\s+)?)?(.+?)(?:\s+(?:under|below|from|for|at|less|max|within|budget)|$)', text)
    if cat_match:
        cat_text = cat_match.group(1).strip()
        # Clean up common words
        cat_text = re.sub(r'\b(good|great|nice|best|new|quality)\b', '', cat_text).strip()
        if cat_text and len(cat_text) < 50:
            category = cat_text.replace(" ", "_")

    # Extract purpose
    purpose = "purchase"
    if any(w in text for w in ["subscribe", "subscription"]):
        purpose = "subscription"
    elif any(w in text for w in ["donate", "donation"]):
        purpose = "donation"

    # Extract merchant requirement
    merchant_requirement = None
    if "trusted" in text:
        merchant_requirement = "trusted"
    elif re.search(r'from\s+(\w+)', text):
        m = re.search(r'from\s+a?\s*(\w+(?:\s+\w+)?)\s+(?:seller|store|shop|merchant|vendor)', text)
        if m:
            merchant_requirement = m.group(1).strip()

    return {
        "purpose": purpose,
        "category": category,
        "max_amount": max_amount,
        "currency": "INR",
        "merchant_requirement": merchant_requirement,
    }


def parse_intent(raw_text: str) -> tuple[dict, bool]:
    """Parse a natural-language intent into structured authorization.

    Returns (parsed_dict, used_ai).
    On any failure, returns a best-effort parse with REVIEW-worthy nulls.
    """
    if is_ai_available():
        try:
            result = parse_intent_ai(raw_text)
            return result, True
        except Exception as e:
            logger.warning(f"AI intent parsing failed: {e}. Falling back to regex.")

    result = parse_intent_fallback(raw_text)
    return result, False
