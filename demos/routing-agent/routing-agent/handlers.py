# handlers.py
"""Four handler nodes. Each returns a short response and records cost/latency
on the shared Trace object."""
from __future__ import annotations

from langchain_openai import ChatOpenAI

from timing import Trace, cost_of, timer

SMART = "gpt-4o"
CHEAP = "gpt-4o-mini"

_smart = ChatOpenAI(model=SMART, temperature=0)
_cheap = ChatOpenAI(model=CHEAP, temperature=0)


async def _invoke(llm, model: str, system: str, user: str, trace: Trace) -> str:
    with timer() as t:
        resp = await llm.ainvoke([
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ])
    usage = (resp.response_metadata or {}).get("token_usage", {}) or {}
    pt = usage.get("prompt_tokens", 0)
    ct = usage.get("completion_tokens", 0)
    text = resp.content or ""
    trace.handler_ms = t.ms
    trace.handler_cost = cost_of(model, pt, ct)
    trace.tokens = {"prompt": pt, "completion": ct, "model": model}
    trace.handler_system = system
    trace.handler_response = text
    return text


async def account_node(state):
    trace: Trace = state["trace"]
    text = await _invoke(
        _cheap, CHEAP,
        "You are an account-support agent. The user needs help with login, "
        "password, or profile. Respond in one short, friendly line describing "
        "the next step you'd take (e.g. 'Sending a password reset link now').",
        state["message"], trace,
    )
    return {"response": text, "trace": trace}


async def billing_node(state):
    trace: Trace = state["trace"]
    text = await _invoke(
        _smart, SMART,
        "You are a billing agent. Describe the action you would take in one "
        "line, e.g. 'Reviewing the last 2 invoices' or 'Processing a refund "
        "of $X'. Do not actually perform the action.",
        state["message"], trace,
    )
    return {"response": text, "trace": trace}


async def technical_node(state):
    trace: Trace = state["trace"]
    text = await _invoke(
        _smart, SMART,
        "You are a technical-support agent. Answer the user's product or "
        "integration question in one or two sentences. If you don't know, "
        "say so briefly.",
        state["message"], trace,
    )
    return {"response": text, "trace": trace}


async def chitchat_node(state):
    trace: Trace = state["trace"]
    text = await _invoke(
        _cheap, CHEAP,
        "You reply to small talk in one short, friendly sentence.",
        state["message"], trace,
    )
    return {"response": text, "trace": trace}
