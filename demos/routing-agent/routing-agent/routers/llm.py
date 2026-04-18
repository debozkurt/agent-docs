# routers/llm.py
"""LLM classifier. gpt-4o-mini returns one of four labels.
temperature=0, max_tokens=8, validated output."""
from __future__ import annotations

from langchain_openai import ChatOpenAI

from intents import DEFAULT_INTENT, INTENTS
from timing import cost_of, timer

MODEL = "gpt-4o-mini"
_llm = ChatOpenAI(model=MODEL, temperature=0, max_tokens=8)

ROUTER_PROMPT = """You classify a customer-support message into ONE intent.
Return ONLY the label, lowercase, nothing else.

account   - login, password, profile, 2FA, account access
billing   - invoices, refunds, charges, subscription plans, payments
technical - how-to questions, bug reports, integrations, APIs, setup
chitchat  - greetings, thanks, small talk

Examples:
"I can't log into my account" -> account
"why was I charged twice this month?" -> billing
"how do I enable SSO?" -> technical
"thanks!" -> chitchat

If uncertain, default to technical."""


async def route(message: str):
    with timer() as t:
        resp = await _llm.ainvoke([
            {"role": "system", "content": ROUTER_PROMPT},
            {"role": "user",   "content": message},
        ])
    raw_text = (resp.content or "").strip()
    tokens = raw_text.lower().split()
    label = tokens[0] if tokens else ""
    validated = label in INTENTS
    intent = label if validated else DEFAULT_INTENT

    usage = (resp.response_metadata or {}).get("token_usage", {}) or {}
    pt = usage.get("prompt_tokens", 0)
    ct = usage.get("completion_tokens", 0)
    details = {
        "model": MODEL,
        "system_prompt": ROUTER_PROMPT,
        "raw_response": raw_text,
        "validated": validated,
        "fell_back_to_default": not validated,
        "prompt_tokens": pt,
        "completion_tokens": ct,
    }
    return intent, t.ms, cost_of(MODEL, pt, ct), details
