# agent.py
"""REPL. `python3 agent.py --router llm` picks which router drives the graph.

Every turn prints the live flow trace (START → router → intent_dispatch →
<intent>_handler → END) with latency, cost, and the router's decision on the
edges. Pass -v/--verbose to additionally dump the router internals (cosine
scores, raw LLM response, etc.) and the handler's full system + response."""
from __future__ import annotations

import argparse
import asyncio

from graph import build_graph
from compare import paint_graph, print_case


async def chat(router: str, verbose: bool):
    graph = build_graph(router)
    mode = "verbose" if verbose else "flow"
    print(f"Support Agent · router={router} · {mode}  (blank line to exit)\n")
    while True:
        try:
            msg = input("you › ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not msg:
            return
        result = await graph.ainvoke({"message": msg})
        tr = result["trace"]
        if verbose:
            # Reuse compare.py's full per-message renderer — no "expected"
            # label in free chat.
            print_case(router, msg, None, tr)
        else:
            # Flow-only: the message walks through each node of the graph.
            print(paint_graph(router, tr))
        print(f"agent › {result['response']}\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--router", default="hybrid",
                    choices=["rules", "embeddings", "llm", "hybrid"])
    ap.add_argument("-v", "--verbose", action="store_true",
                    help="Also print router internals and handler I/O.")
    args = ap.parse_args()
    asyncio.run(chat(args.router, args.verbose))


if __name__ == "__main__":
    main()
