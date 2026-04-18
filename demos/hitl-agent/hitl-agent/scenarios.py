# scenarios.py
"""Run scripted HITL scenarios. Each scenario's approval behavior is
scripted in YAML; the harness drives the graph and scores the result.

python3 scenarios.py                   # all scenarios, summary
python3 scenarios.py -v                # verbose trace
python3 scenarios.py --only s5 -v      # one scenario, verbose
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import yaml
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

import tracing
from graph import build_graph

DIM, RESET = "\033[2m", "\033[0m"
GREEN, RED, YELLOW, CYAN = "\033[32m", "\033[31m", "\033[33m", "\033[36m"

_RUN_SUFFIX = f"{int(time.time())}"
THREAD_FOR = lambda sid: f"scenario-{sid}-{_RUN_SUFFIX}"


def _pending_interrupts(snap) -> list:
    direct = getattr(snap, "interrupts", None)
    if direct:
        return list(direct)
    out = []
    for t in getattr(snap, "tasks", ()) or ():
        out.extend(getattr(t, "interrupts", ()) or ())
    return out


def h(text: str, ch: str = "-") -> str:
    return f"{ch * 3} {text} {ch * max(3, 72 - len(text))}"


def run_scenario(case: dict, checkpointer, verbose: bool) -> dict:
    sid = case["id"]
    tag = case["tag"]
    thread_id = THREAD_FOR(sid)
    config = {"configurable": {"thread_id": thread_id}}
    graph = build_graph(checkpointer=checkpointer)

    if verbose:
        print()
        print(h(f"scenario={sid}  |  tag={tag}", "="))
        print(f"  message: {case['message']!r}")
        tracing.trace_thread(thread_id)

    result = {"id": sid, "tag": tag, "gates_fired": [], "status": "running"}

    try:
        state = graph.invoke(
            {"messages": [{"role": "user", "content": case["message"]}]},
            config=config,
        )
    except Exception as e:
        result["status"] = f"error: {e}"
        return result

    interrupts_handled = 0
    while interrupts_handled < 5:
        snap = graph.get_state(config)
        interrupts = _pending_interrupts(snap)
        if not interrupts:
            break
        payload = interrupts[0].value
        kind = payload.get("kind")
        result["gates_fired"].append(kind)

        decision = _decide(case, kind, interrupts_handled)
        if decision == "__crash__":
            if verbose:
                print(f"  {YELLOW}SIMULATED CRASH{RESET}")
            return _resume_in_child(case, thread_id, verbose)
        if decision == "__timeout__":
            t = case.get("timeout_seconds", 2)
            if verbose:
                print(f"  {YELLOW}TIMEOUT ({t}s) -> default reject{RESET}")
            time.sleep(t)
            decision = {"action": "reject", "reason": "approval timed out"}
        if verbose:
            print(f"  resume with: {decision}")
        state = graph.invoke(Command(resume=decision), config=config)
        interrupts_handled += 1

    result["status"] = "timed_out" if case.get("approval_timeout") else "completed"
    result["sent"] = _did_send()
    if verbose:
        color = GREEN if result["status"] in ("completed", "timed_out") else RED
        print(f"  {color}status={result['status']}  "
              f"gates={result['gates_fired']}  sent={result['sent']}{RESET}")
    return result


def _decide(case, kind, idx):
    if case.get("crash_before_approval") and idx == 0:
        return "__crash__"
    if case.get("approval_timeout"):
        return "__timeout__"
    if kind == "pre_approval":
        a = case.get("approval")
        if a == "approve":
            return {"action": "approve"}
        if a == "reject":
            return {"action": "reject", "reason": case.get("approval_reason", "")}
    if kind == "post_review":
        a = case.get("review")
        if a == "approve":
            return {"action": "approve"}
        if a == "reject":
            return {"action": "reject", "reason": case.get("review_reason", "")}
    return {"action": "reject", "reason": "no scripted response"}


def _resume_in_child(case, thread_id, verbose):
    if verbose:
        print(f"  {CYAN}spawning child process to resume{RESET}")
    action = case.get("approval_after_resume", "approve")
    cmd = [sys.executable, __file__,
           "--resume-scenario", case["id"],
           "--resume-thread", thread_id,
           "--resume-action", action]
    if verbose:
        cmd.append("-v")
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if verbose:
        sys.stdout.write(textwrap.indent(proc.stdout, "  | "))
    return {
        "id": case["id"], "tag": case["tag"],
        "gates_fired": ["pre_approval"],
        "status": "completed" if proc.returncode == 0 else "child_failed",
        "sent": _did_send(),
    }


def _resume_entry(sid, thread_id, action, verbose):
    config = {"configurable": {"thread_id": thread_id}}
    with SqliteSaver.from_conn_string("hitl.sqlite") as ckpt:
        graph = build_graph(checkpointer=ckpt)
        snap = graph.get_state(config)
        interrupts = _pending_interrupts(snap)
        if not interrupts:
            print(f"(no pending interrupt for {thread_id!r})")
            return 1
        if verbose:
            tracing.trace_resume(thread_id,
                                 list(snap.values.keys()) if hasattr(snap, "values") else [])
        state = graph.invoke(Command(resume={"action": action}), config=config)
        msgs = state.get("messages", [])
        if msgs:
            c = getattr(msgs[-1], "content", "")
            if c:
                print(f"agent > {c}")
    return 0


def _did_send() -> bool:
    import sqlite3
    try:
        conn = sqlite3.connect("hitl.sqlite")
        row = conn.execute(
            "SELECT COUNT(*) FROM sent_log WHERE sent_at >= ?",
            (float(_RUN_SUFFIX),),
        ).fetchone()
        conn.close()
        return (row[0] or 0) > 0
    except Exception:
        return False


def summary_table(results):
    print()
    print(h("SUMMARY", "="))
    print(f"{'id':<4} {'tag':<14} {'gates':<18} {'status':<14} {'sent':<6}")
    print("-" * 60)
    for r in results:
        gates = ",".join(r["gates_fired"]) or "-"
        ok = r["status"] in ("completed", "timed_out")
        color = GREEN if ok else RED
        print(f"{r['id']:<4} {r['tag']:<14} {gates:<18} "
              f"{color}{r['status']:<14}{RESET} {str(r.get('sent')):<6}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-v", "--verbose", action="store_true")
    ap.add_argument("--only")
    ap.add_argument("--resume-scenario", help=argparse.SUPPRESS)
    ap.add_argument("--resume-thread", help=argparse.SUPPRESS)
    ap.add_argument("--resume-action", default="approve", help=argparse.SUPPRESS)
    args = ap.parse_args()

    if args.resume_scenario:
        tracing.VERBOSE = args.verbose
        return _resume_entry(args.resume_scenario, args.resume_thread,
                             args.resume_action, args.verbose)

    tracing.VERBOSE = args.verbose

    cases = yaml.safe_load(Path("scenarios.yaml").read_text())["cases"]
    if args.only:
        cases = [c for c in cases if c["id"] == args.only]
        if not cases:
            print(f"No scenario matches id={args.only!r}")
            return 1

    results = []
    with SqliteSaver.from_conn_string("hitl.sqlite") as ckpt:
        for case in cases:
            results.append(run_scenario(case, ckpt, args.verbose))
    summary_table(results)
    return 1 if any(r["status"] not in ("completed", "timed_out") for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
