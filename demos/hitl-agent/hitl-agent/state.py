# state.py
"""Agent state schema. Each field has a comment explaining when it's set,
what reads it, and when it's cleared."""
from __future__ import annotations

from typing import Annotated, Any, Optional, TypedDict

from langgraph.graph.message import add_messages


class AgentState(TypedDict, total=False):
    # Chat and tool-call history. add_messages reducer appends; every node
    # return can yield new messages without rebuilding the full list.
    messages: Annotated[list, add_messages]

    # Set by agent_node when the LLM produces a tool_call. Read by
    # pre_approval_gate (to build the interrupt payload) and tool_node
    # (to execute). Cleared by tool_node after execution, or by
    # pre_approval_gate on reject.
    pending_tool_call: Optional[dict]
    pending_tool_call_id: Optional[str]

    # Written by tool_node. Read by post_review_gate to show the human
    # the tool's output. Survives after the gate (audit trail).
    last_tool_result: Optional[dict]
    last_tool_name: Optional[str]

    # Append-only audit trail of gate decisions: {kind, tool, decision, reason}.
    approval_decisions: list

    # Purely diagnostic — not read by any node.
    trace: Any
