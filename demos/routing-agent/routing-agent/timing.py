# timing.py
"""Minimal latency + token-cost tracking. Not a real metrics system;
just enough to make the four-router comparison honest."""
from __future__ import annotations

import time
from dataclasses import dataclass, field

# OpenAI list prices as of April 2026 (USD per 1M tokens).
# Update if pricing changes; numbers only matter for relative comparison.
PRICING = {
    "gpt-4o":                {"input": 2.50, "output": 10.00},
    "gpt-4o-mini":           {"input": 0.15, "output":  0.60},
    "text-embedding-3-small":{"input": 0.02, "output":  0.00},
}


@dataclass
class Trace:
    """Records what happened in one router+handler run."""
    router: str = ""
    intent: str = ""
    router_ms: float = 0.0
    router_cost: float = 0.0
    handler_ms: float = 0.0
    handler_cost: float = 0.0
    tokens: dict = field(default_factory=dict)
    # Router-specific diagnostic info (keyword match, cosine scores, raw
    # LLM response, etc.). Populated by the router; read by verbose mode.
    router_details: dict = field(default_factory=dict)
    handler_system: str = ""
    handler_response: str = ""
    # Sticky-state gate (pre-router bypass). Populated even when the gate
    # doesn't fire, so verbose mode can always show what it checked.
    sticky_bypass: bool = False
    sticky_before: dict | None = None   # the sticky flow that existed on entry
    sticky_reason: str = ""              # why the gate did or did not fire

    @property
    def total_ms(self) -> float:
        return self.router_ms + self.handler_ms

    @property
    def total_cost(self) -> float:
        return self.router_cost + self.handler_cost


def cost_of(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    p = PRICING.get(model)
    if not p:
        return 0.0
    return (prompt_tokens * p["input"] + completion_tokens * p["output"]) / 1_000_000


class timer:
    """Context manager that records wall time in milliseconds."""
    def __enter__(self):
        self.t0 = time.perf_counter()
        return self
    def __exit__(self, *a):
        self.ms = (time.perf_counter() - self.t0) * 1000
