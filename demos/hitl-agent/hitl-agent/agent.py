# agent.py
"""Interactive REPL with verbose mode.

python3 agent.py                  # normal
python3 agent.py -v               # verbose — see everything
python3 agent.py --resume         # resume paused thread from SQLite
"""
from __future__ import annotations

import argparse
import sys
import time

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

import tracing
from graph import build_graph


def _default_thread() -> str:
    """Fresh thread_id per session so old state never bleeds in.

    Each REPL session gets its own thread. For crash-resume, use --thread
    to name it explicitly, then --resume --thread <name> to pick it up."""
    return f"demo-{int(time.time())}"


def _pending_interrupts(snap) -> list:
    """Get pending interrupts from a StateSnapshot — portable across
    LangGraph versions (0.2+ uses .interrupts; older uses .tasks)."""
    direct = getattr(snap, "interrupts", None)
    if direct:
        return list(direct)
    out = []
    for t in getattr(snap, "tasks", ()) or ():
        out.extend(getattr(t, "interrupts", ()) or ())
    return out


def render_interrupt(payload: dict) -> None:
    """Print the gate payload in a human-readable box."""
    print()
    print("+" + "-" * 74 + "+")
    print(f"| {'APPROVAL REQUIRED':^74}|")
    print("+" + "-" * 74 + "+")
    print(f"| kind: {payload.get('kind'):<67}|")
    print(f"| tool: {payload.get('tool'):<67}|")
    if payload.get("kind") == "pre_approval":
        for k, v in (payload.get("preview") or {}).items():
            line = f"| {k:10} {v}"
            if len(line) > 74:
                line = line[:71] + "..."
            print(f"{line:<75}|")
    else:
        for k, v in (payload.get("result") or {}).items():
            if k == "full_list":
                continue
            line = f"| {k:10} {v}"
            if len(line) > 74:
                line = line[:71] + "..."
            print(f"{line:<75}|")
    print("+" + "-" * 74 + "+")


def prompt_decision() -> dict:
    while True:
        ans = input("  approve / reject > ").strip().lower()
        if ans in ("a", "approve"):
            return {"action": "approve"}
        if ans in ("r", "reject"):
            reason = input("  reason (optional) > ").strip()
            return {"action": "reject", "reason": reason}
        print("  (type 'approve' or 'reject')")


def run_until_done(graph, thread_id: str, invoke_args=None) -> dict:
    config = {"configurable": {"thread_id": thread_id}}
    tracing.trace_thread(thread_id)

    if invoke_args is not None:
        state = graph.invoke(invoke_args, config=config)
    else:
        state = graph.invoke(None, config=config)

    while True:
        snap = graph.get_state(config)
        interrupts = _pending_interrupts(snap)
        if not interrupts:
            break
        render_interrupt(interrupts[0].value)
        decision = prompt_decision()
        state = graph.invoke(Command(resume=decision), config=config)

    return state


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-v", "--verbose", action="store_true",
                    help="Show LLM calls, tool I/O, gates, checkpoints, DB writes.")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--thread", default=None,
                    help="Thread id. Defaults to a fresh timestamped id per session. "
                         "Name it explicitly for crash-resume demos.")
    args = ap.parse_args()

    tracing.VERBOSE = args.verbose

    # --resume requires an explicit --thread (which thread to resume?)
    if args.resume and not args.thread:
        ap.error("--resume requires --thread <thread_id> "
                 "(which paused thread do you want to resume?)")

    # Default: fresh thread per session so old state never interferes.
    thread_id = args.thread or _default_thread()

    with SqliteSaver.from_conn_string("hitl.sqlite") as ckpt:
        graph = build_graph(checkpointer=ckpt)

        if args.resume:
            print(f"Resuming thread={thread_id!r}...")
            tracing.trace_resume(thread_id, ["(loading...)"])
            state = run_until_done(graph, thread_id)
            _print_final(state)
            return

        print(f"Messaging Agent | thread={thread_id}  (blank line to exit)\n")
        while True:
            try:
                msg = input("you > ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                return
            if not msg:
                return
            tracing.section("USER", msg)
            state = run_until_done(
                graph, thread_id,
                invoke_args={"messages": [{"role": "user", "content": msg}]},
            )
            _print_final(state)


def _print_final(state: dict) -> None:
    msgs = state.get("messages", [])
    if msgs:
        content = getattr(msgs[-1], "content", "") or ""
        if content:
            print(f"agent > {content}\n")
    decisions = state.get("approval_decisions") or []
    if decisions:
        summary = ", ".join(f"{d['tool']}:{d['decision']}" for d in decisions)
        print(f"  [decisions: {summary}]\n")


if __name__ == "__main__":
    main()
