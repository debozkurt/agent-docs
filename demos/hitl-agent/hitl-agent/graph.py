# graph.py
"""LangGraph StateGraph for the HITL messaging agent.

Flow: START -> agent -> [pre_gate | tool] -> [tool | post_gate] -> agent -> END
Every node emits tracing calls. The checkpointer writes after every step.
"""
from __future__ import annotations

from langchain_core.messages import AIMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

import tracing
from policy import gate_for
from state import AgentState
from tools import (
    draft_message,
    generate_campaign_list,
    list_contacts,
    send_message,
)

TOOLS = [list_contacts, draft_message, send_message, generate_campaign_list]
TOOLS_BY_NAME = {t.name: t for t in TOOLS}

SYSTEM_PROMPT = """You are a careful messaging assistant.

Tools:
  list_contacts          - search contacts
  draft_message          - create a local draft (not sent)
  send_message           - send a draft (IRREVERSIBLE)
  generate_campaign_list - build a recipient list for a campaign

Always draft before sending. For campaigns, generate the list and wait
for review before proceeding. Be concise."""

llm = ChatOpenAI(model="gpt-4o", temperature=0).bind_tools(TOOLS)
_shown_system_prompt = False


# ─────────────────────── nodes ─────────────────────────────────────────────

def agent_node(state: AgentState) -> dict:
    """One LLM call. Produces either a tool call or a final answer."""
    global _shown_system_prompt
    messages = state.get("messages", [])

    # If the last gate rejected, inject a note so the LLM apologises.
    decisions = state.get("approval_decisions", []) or []
    if decisions and decisions[-1].get("decision") == "rejected" \
            and not decisions[-1].get("_agent_handled"):
        decisions[-1]["_agent_handled"] = True
        messages = messages + [
            AIMessage(content=(
                f"(Human rejected my {decisions[-1]['tool']!r} action. "
                f"Acknowledge and offer alternatives.)"
            )),
        ]

    # Trace: show system prompt on first call only (it's static).
    if not _shown_system_prompt:
        tracing.trace_system_prompt(SYSTEM_PROMPT)
        _shown_system_prompt = True

    # Trace: what we're sending.
    last_msg = ""
    for m in reversed(messages):
        c = getattr(m, "content", "")
        if c:
            last_msg = c[:120]
            break
    tracing.trace_llm_call(len(messages) + 1, last_msg)  # +1 for system

    response = llm.invoke(
        [{"role": "system", "content": SYSTEM_PROMPT}] + messages
    )

    # Trace: what came back.
    usage = (response.response_metadata or {}).get("token_usage", {}) or {}
    tracing.trace_llm_response(
        tool_calls=response.tool_calls or [],
        text=response.content or "",
        prompt_tokens=usage.get("prompt_tokens", 0),
        completion_tokens=usage.get("completion_tokens", 0),
    )

    out: dict = {"messages": [response]}
    if getattr(response, "tool_calls", None):
        tc = response.tool_calls[0]
        out["pending_tool_call"] = {"name": tc["name"], "args": tc["args"]}
        out["pending_tool_call_id"] = tc["id"]
    else:
        out["pending_tool_call"] = None
        out["pending_tool_call_id"] = None
    return out


def tool_node(state: AgentState) -> dict:
    """Execute the pending tool call and append a ToolMessage."""
    pending = state["pending_tool_call"]
    tool_id = state["pending_tool_call_id"]
    tool = TOOLS_BY_NAME[pending["name"]]

    # Tool functions emit their own trace_tool_call / trace_tool_result.
    result = tool.invoke(pending["args"])

    return {
        "messages": [ToolMessage(
            content=str(result),
            tool_call_id=tool_id,
            name=pending["name"],
        )],
        "last_tool_result": result if isinstance(result, dict) else {"raw": result},
        "last_tool_name": pending["name"],
        "pending_tool_call": None,
        "pending_tool_call_id": None,
    }


def pre_approval_gate(state: AgentState) -> dict:
    """Pause BEFORE a sensitive tool runs.

    IMPORTANT: this node runs TWICE across a pause/resume cycle.
    First pass: interrupt() pauses the graph. Second pass (after resume):
    interrupt() returns the decision dict. Everything above interrupt() is
    idempotent — reading state and building a payload has no side effects.
    """
    pending = state["pending_tool_call"]
    payload = {
        "kind": "pre_approval",
        "tool": pending["name"],
        "args": pending["args"],
        "preview": _preview_for(pending),
    }
    tracing.trace_gate("pre_approval", payload)

    # ← graph pauses here. On resume, returns the decision dict.
    decision = interrupt(payload)

    tracing.trace_gate_decision("pre_approval", pending["name"],
                                decision.get("action"),
                                decision.get("reason", ""))

    decisions = list(state.get("approval_decisions") or [])
    decisions.append({
        "kind": "pre_approval",
        "tool": pending["name"],
        "decision": decision.get("action"),
        "reason": decision.get("reason", ""),
    })

    if decision.get("action") == "approve":
        # Don't clear pending_tool_call — tool_node reads it next.
        return {"approval_decisions": decisions}

    # Rejected. Emit a ToolMessage so the LLM's tool_call_id has a
    # matching response (required by the API).
    return {
        "approval_decisions": decisions,
        "messages": [ToolMessage(
            content=f"Human rejected. Reason: {decision.get('reason') or 'none'}.",
            tool_call_id=state["pending_tool_call_id"],
            name=pending["name"],
        )],
        "pending_tool_call": None,
        "pending_tool_call_id": None,
    }


def post_review_gate(state: AgentState) -> dict:
    """Pause AFTER a post-review tool returned its result.

    Same idempotency rules as pre_approval_gate. The tool already ran —
    rejecting here doesn't undo the side effect; it tells the agent not
    to use the output in downstream steps."""
    payload = {
        "kind": "post_review",
        "tool": state["last_tool_name"],
        "result": state["last_tool_result"],
    }
    tracing.trace_gate("post_review", payload)

    decision = interrupt(payload)

    tracing.trace_gate_decision("post_review", state["last_tool_name"],
                                decision.get("action"),
                                decision.get("reason", ""))

    decisions = list(state.get("approval_decisions") or [])
    decisions.append({
        "kind": "post_review",
        "tool": state["last_tool_name"],
        "decision": decision.get("action"),
        "reason": decision.get("reason", ""),
    })

    if decision.get("action") == "approve":
        return {"approval_decisions": decisions}

    return {
        "approval_decisions": decisions,
        "messages": [AIMessage(content=(
            f"(Human rejected {state['last_tool_name']!r} result. "
            f"Do not proceed with downstream action.)"
        ))],
    }


# ─────────────────────── routing ───────────────────────────────────────────

def route_after_agent(state: AgentState) -> str:
    pending = state.get("pending_tool_call")
    if not pending:
        return "end"
    if gate_for(pending["name"]) == "pre_approval":
        return "pre_gate"
    return "tool"


def route_after_pre_gate(state: AgentState) -> str:
    last = (state.get("approval_decisions") or [])[-1]
    return "tool" if last["decision"] == "approve" else "agent"


def route_after_tool(state: AgentState) -> str:
    if gate_for(state.get("last_tool_name") or "") == "post_review":
        return "post_gate"
    return "agent"


def route_after_post_gate(_state: AgentState) -> str:
    return "agent"


# ─────────────────────── helpers ───────────────────────────────────────────

def _preview_for(pending: dict) -> dict:
    if pending["name"] == "send_message":
        from db import connect
        draft_id = pending["args"].get("draft_id", "")
        conn = connect()
        try:
            row = conn.execute(
                "SELECT recipient, subject, body FROM drafts WHERE draft_id = ?",
                (draft_id,),
            ).fetchone()
        finally:
            conn.close()
        if row:
            return {"to": row[0], "subject": row[1], "body": row[2]}
    return pending["args"]


# ─────────────────────── graph builder ─────────────────────────────────────

def build_graph(checkpointer=None):
    g = StateGraph(AgentState)
    g.add_node("agent", agent_node)
    g.add_node("tool", tool_node)
    g.add_node("pre_gate", pre_approval_gate)
    g.add_node("post_gate", post_review_gate)

    g.add_edge(START, "agent")
    g.add_conditional_edges("agent", route_after_agent, {
        "pre_gate": "pre_gate", "tool": "tool", "end": END,
    })
    g.add_conditional_edges("pre_gate", route_after_pre_gate, {
        "tool": "tool", "agent": "agent",
    })
    g.add_conditional_edges("tool", route_after_tool, {
        "post_gate": "post_gate", "agent": "agent",
    })
    g.add_conditional_edges("post_gate", route_after_post_gate, {
        "agent": "agent",
    })

    return g.compile(checkpointer=checkpointer) if checkpointer \
        else g.compile()
