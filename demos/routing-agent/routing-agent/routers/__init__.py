# routers/__init__.py
"""Router registry. Each router is an async callable returning
(intent, router_ms, router_cost, details)."""
from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict, Tuple

RouteFn = Callable[[str], Awaitable[Tuple[str, float, float, Dict[str, Any]]]]


def get_router(name: str) -> RouteFn:
    if name == "rules":
        from routers.rules import route as fn
    elif name == "embeddings":
        from routers.embeddings import route as fn
    elif name == "llm":
        from routers.llm import route as fn
    elif name == "hybrid":
        from routers.hybrid import route as fn
    else:
        raise ValueError(
            f"Unknown router '{name}'. Choose: rules, embeddings, llm, hybrid."
        )
    return fn
