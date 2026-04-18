# routers/rules.py
"""Keyword/pattern-based router. Deterministic, ~0 ms, $0. Brittle on
natural phrasing — that's the trade-off we're highlighting."""
from __future__ import annotations

from timing import timer

CHITCHAT_TOKENS = {"hi", "hello", "hey", "thanks", "thank you", "ok", "okay", "cool"}
BILLING_TERMS = ("refund", "charge", "charged", "invoice", "billing",
                 "subscription", "plan", "pricing", "payment")
ACCOUNT_TERMS = ("password", "log in", "login", "sign in", "2fa",
                 "two-factor", "account", "profile")


async def route(message: str):
    matched = None
    with timer() as t:
        msg = message.lower().strip().rstrip("!.")
        intent = "technical"  # safe default
        if msg in CHITCHAT_TOKENS:
            intent, matched = "chitchat", msg
        else:
            for term in BILLING_TERMS:
                if term in msg:
                    intent, matched = "billing", term
                    break
            if matched is None:
                for term in ACCOUNT_TERMS:
                    if term in msg:
                        intent, matched = "account", term
                        break
    details = {
        "matched_keyword": matched,
        "used_default": matched is None,
        "default_intent": "technical",
    }
    return intent, t.ms, 0.0, details
