# intents.py
"""Intent catalog. Every router returns one of these four labels."""
from __future__ import annotations

from typing import Literal

Intent = Literal["account", "billing", "technical", "chitchat"]

INTENTS: list[Intent] = ["account", "billing", "technical", "chitchat"]

# English descriptions used by the embedding and LLM routers.
# Keep them focused; each should describe the intent's core shape.
INTENT_DESCRIPTIONS: dict[Intent, str] = {
    "account":   "The user needs help with login, password reset, profile "
                 "settings, two-factor authentication, or account access.",
    "billing":   "The user is asking about invoices, charges, refunds, "
                 "subscription plans, payment methods, or pricing.",
    "technical": "The user is asking how to use a feature, reporting a bug, "
                 "or asking about integrations, APIs, setup, or configuration.",
    "chitchat":  "Small talk, greetings, thanks, acknowledgements. "
                 "Social conversation that needs no tools or data lookup.",
}

DEFAULT_INTENT: Intent = "technical"  # safest fallback — route to general support
