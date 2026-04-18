# graph.py
"""Builds the LangGraph StateGraph: router node + four handler nodes,
wired by a conditional edge on the router's returned intent."""
from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from handlers import account_node, billing_node, chitchat_node, technical_node
from intents import DEFAULT_INTENT, INTENTS
from routers import get_router
from timing import Trace


class AgentState(TypedDict, total=False):
    message: str
    intent: str
    response: str
    trace: Trace


def _make_router_node(router_name: str):
    route_fn = get_router(router_name)

    async def router_node(state: AgentState) -> AgentState:
        trace = state.get("trace") or Trace(router=router_name)
        intent, router_ms, router_cost, details = await route_fn(state["message"])
        if intent not in INTENTS:
            intent = DEFAULT_INTENT
        trace.router = router_name
        trace.intent = intent
        trace.router_ms = router_ms
        trace.router_cost = router_cost
        trace.router_details = details
        return {"intent": intent, "trace": trace}

    return router_node


def build_graph(router_name: str):
    g = StateGraph(AgentState)
    g.add_node("router", _make_router_node(router_name))
    g.add_node("account", account_node)
    g.add_node("billing", billing_node)
    g.add_node("technical", technical_node)
    g.add_node("chitchat", chitchat_node)

    g.add_edge(START, "router")
    g.add_conditional_edges(
        "router",
        lambda s: s["intent"],
        {i: i for i in INTENTS},
    )
    for i in INTENTS:
        g.add_edge(i, END)

    return g.compile()
