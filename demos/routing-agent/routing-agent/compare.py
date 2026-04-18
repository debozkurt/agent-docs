# compare.py
"""Run routers through the fixture or an ad-hoc message; print a comparison
table, with optional per-message verbose tracing.

Usage:
    python3 compare.py                         # all routers, fixture, summary only
    python3 compare.py --verbose               # all routers, fixture, full trace
    python3 compare.py --router llm --verbose  # trace one router only
    python3 compare.py --message "..."         # ad-hoc message, all routers
    python3 compare.py --message "..." -v      # ad-hoc + full trace
"""
from __future__ import annotations

import argparse
import asyncio
import textwrap
from pathlib import Path

import yaml

from graph import build_graph
from timing import Trace

ALL_ROUTERS = ["rules", "embeddings", "llm", "hybrid"]

# ─────────────────────────── pretty helpers ─────────────────────────────────

DIM, RESET = "\033[2m", "\033[0m"
GREEN, RED, YELLOW, CYAN = "\033[32m", "\033[31m", "\033[33m", "\033[36m"


def h(text: str, ch: str = "─") -> str:
    return f"{ch * 3} {text} {ch * max(3, 72 - len(text))}"


def indent(s: str, n: int = 5) -> str:
    return textwrap.indent(s, " " * n)


def fmt_cost(x: float) -> str:
    return f"${x:.6f}" if x < 0.001 else f"${x:.5f}"


# ─────────────────────────── live flow trace ────────────────────────────────

# Per-router accent colors — the router node and chosen handler wear this
# color so it's obvious at a glance which style is driving the decision.
MAGENTA = "\033[35m"
ROUTER_COLOR = {
    "rules":      CYAN,
    "embeddings": GREEN,
    "llm":        MAGENTA,
    "hybrid":     YELLOW,
}


HANDLERS_ROW = ["account", "billing", "technical", "chitchat"]


def paint_graph(router: str, trace: Trace) -> str:
    """Render the message's path through the graph as a live-annotated trace:
    START → router → intent_dispatch → {account|billing|technical|chitchat}
    → END. The upper nodes (router, dispatch) are wide boxes with per-node
    annotations on the right; the dispatch arrow fans out to all four handler
    boxes in a row so the graph structure is visible, with the chosen handler
    lit in the router's accent color and the other three dimmed. Handler
    metrics + response text drop from the chosen handler's column down to END."""
    c = ROUTER_COLOR.get(router, "")
    d = trace.router_details or {}
    pt = trace.tokens.get("prompt", 0)
    ct = trace.tokens.get("completion", 0)
    model = trace.tokens.get("model", "?")
    resp = trace.handler_response.strip().replace("\n", " ")
    if len(resp) > 60:
        resp = resp[:57] + "..."

    # One-line decision summary — what the router actually did this turn.
    if router == "rules":
        if d.get("used_default"):
            decision = f"no keyword matched → default '{trace.intent}'"
        else:
            decision = f"keyword {d.get('matched_keyword')!r} → '{trace.intent}'"
    elif router == "embeddings":
        top = max((d.get("scores") or {}).values(), default=0.0)
        decision = f"top cosine {top:.2f} → '{trace.intent}'"
    elif router == "llm":
        decision = f"classified → '{trace.intent}'"
    elif router == "hybrid":
        if d.get("fell_through_to_llm"):
            decision = f"embed < threshold · LLM → '{trace.intent}'"
        else:
            decision = f"embed ≥ threshold → '{trace.intent}'"
    else:
        decision = f"→ '{trace.intent}'"

    # ── Upper section: START → router box → intent_dispatch box ─────────
    W = 34                    # inner box width
    IND = " " * (2 + W // 2)  # column of the vertical arrow between boxes

    def upper_box(label: str, colored: bool) -> tuple[str, str, str]:
        col = c if colored else ""
        rst = RESET if colored else ""
        pad = " " * (W - 1 - len(label))
        return (
            f"  ┌{'─' * W}┐",
            f"  │ {col}{label}{rst}{pad}│",
            f"  └{'─' * ((W // 2) - 1)}┬{'─' * (W - (W // 2))}┘",
        )

    out: list[str] = [f"{IND[:-2]}START", f"{IND}│", f"{IND}▼"]

    top, mid, bot = upper_box(f"router · {router}", colored=True)
    out += [
        top,
        f"{mid}  {trace.router_ms:>5.0f}ms · {fmt_cost(trace.router_cost)}",
        bot,
        f"{IND}│  {DIM}{decision}{RESET}",
        f"{IND}▼",
    ]

    top, mid, bot = upper_box("intent_dispatch", colored=False)
    out += [
        top,
        f"{mid}  {DIM}conditional edge on state.intent{RESET}",
        bot,
        f"{IND}│",
        f"{IND}▼",
    ]

    # ── Fan-out bar + row of 4 handler boxes ────────────────────────────
    # Handler box geometry is chosen so that box 1 (billing) is centered on
    # the same column as the dispatch arrow above (col 19). That makes the
    # bar's ┼ junction sit directly under the dispatch ┬.
    HW, HG, HLM = 11, 2, 1                                   # outer / gap / left margin
    centers = [HLM + i * (HW + HG) + HW // 2 for i in range(4)]  # [6, 19, 32, 45]
    chosen_i = (HANDLERS_ROW.index(trace.intent)
                if trace.intent in HANDLERS_ROW else 1)
    chosen_col = centers[chosen_i]

    # Bar row: ┌─...─┼─...─┬─...─┐  (┼ at col 19 = dispatch entry)
    bar = [" "] * (centers[-1] + 1)
    bar[centers[0]]  = "┌"
    bar[centers[-1]] = "┐"
    for col in centers[1:-1]:
        bar[col] = "┬"
    for a, b in zip(centers, centers[1:]):
        for j in range(a + 1, b):
            bar[j] = "─"
    bar[19] = "┼"  # dispatch arrow enters here

    def _row_at(cols: list[int], ch: str) -> str:
        row = [" "] * (cols[-1] + 1)
        for col in cols:
            row[col] = ch
        return "".join(row)

    def _colorize_col(s: str, col: int) -> str:
        return s[:col] + f"{c}{s[col]}{RESET}" + s[col + 1:]

    out += [
        _colorize_col("".join(bar), chosen_col),
        _colorize_col(_row_at(centers, "│"), chosen_col),
        _colorize_col(_row_at(centers, "▼"), chosen_col),
    ]

    # Handler boxes: chosen gets color `c`, others DIM.
    inner = HW - 2  # 9

    def _row(tile_fn) -> str:
        parts = [" " * HLM]
        for i, name in enumerate(HANDLERS_ROW):
            col = c if i == chosen_i else DIM
            parts.append(f"{col}{tile_fn(name)}{RESET}")
            if i < len(HANDLERS_ROW) - 1:
                parts.append(" " * HG)
        return "".join(parts)

    out += [
        _row(lambda _: "┌" + "─" * inner + "┐"),
        _row(lambda n: "│" + f"{n:^{inner}}" + "│"),
        _row(lambda _: "└" + "─" * inner + "┘"),
    ]

    # ── Drop from chosen handler to END, carrying metrics + response ────
    cind = " " * chosen_col
    out += [
        f"{cind}│  {DIM}{model} · {trace.handler_ms:.0f}ms"
        f" · {fmt_cost(trace.handler_cost)} · ({pt}→{ct} tok){RESET}",
        f"{cind}│  {CYAN}{resp!r}{RESET}",
        f"{cind}▼",
        f"{' ' * (chosen_col - 1)}END",
    ]
    return "\n".join(out)


# ─────────────────────────── verbose tracer ─────────────────────────────────

def trace_router(router: str, trace: Trace) -> str:
    """Render the router-specific internals as a readable block."""
    d = trace.router_details or {}
    lines: list[str] = []

    if router == "rules":
        if d.get("used_default"):
            lines.append(f"no keyword matched → using default "
                         f"intent '{d.get('default_intent')}'")
        else:
            lines.append(f"matched keyword: {CYAN}'{d.get('matched_keyword')}'{RESET} "
                         f"→ {trace.intent}")
        lines.append(f"no model call · cost = $0")

    elif router == "embeddings":
        lines.append(f"model: {d.get('model')}")
        lines.append("cosine similarity scores:")
        for intent, score in sorted(d.get("scores", {}).items(),
                                    key=lambda x: -x[1]):
            marker = " ← top" if intent == d.get("top_intent") else ""
            lines.append(f"  {intent:<10} {score:.4f}{marker}")
        lines.append(f"threshold = {d.get('threshold')}  "
                     f"below_threshold = {d.get('below_threshold')}")
        lines.append(f"chose: {trace.intent}  "
                     f"(~{d.get('approx_input_tokens')} input tokens)")

    elif router == "llm":
        lines.append(f"model: {d.get('model')}  "
                     f"(prompt_tokens={d.get('prompt_tokens')}, "
                     f"completion_tokens={d.get('completion_tokens')})")
        lines.append(f"raw response: {CYAN}{d.get('raw_response')!r}{RESET}")
        if d.get("fell_back_to_default"):
            lines.append(f"{YELLOW}output not in valid set — "
                         f"fell back to default{RESET}")
        lines.append(f"validated label: {trace.intent}")

    elif router == "hybrid":
        lines.append("embedding pass:")
        for intent, score in sorted(d.get("embedding_scores", {}).items(),
                                    key=lambda x: -x[1]):
            marker = " ← top" if intent == d.get("embedding_top_intent") else ""
            lines.append(f"  {intent:<10} {score:.4f}{marker}")
        lines.append(f"high-conf threshold = {d.get('high_conf_threshold')}")
        if d.get("fell_through_to_llm"):
            lines.append(f"{YELLOW}below threshold → falling through to LLM{RESET}")
            lines.append(f"  LLM model: {d.get('llm_model')}")
            lines.append(f"  LLM raw:   {CYAN}{d.get('llm_raw_response')!r}{RESET}")
            lines.append(f"  LLM chose: {d.get('llm_intent')}")
        else:
            lines.append(f"{GREEN}above threshold → skipping LLM{RESET}")
        lines.append(f"final intent: {trace.intent}")

    return "\n".join(lines)


def trace_handler(trace: Trace) -> str:
    model = trace.tokens.get("model", "?")
    pt = trace.tokens.get("prompt", 0)
    ct = trace.tokens.get("completion", 0)
    sysp = trace.handler_system.strip().replace("\n", " ")
    if len(sysp) > 140:
        sysp = sysp[:137] + "..."
    resp = trace.handler_response.strip().replace("\n", " ")
    if len(resp) > 200:
        resp = resp[:197] + "..."
    return (
        f"handler:  {trace.intent}_node  (model: {model})\n"
        f"system:   {DIM}{sysp}{RESET}\n"
        f"response: {CYAN}{resp}{RESET}\n"
        f"tokens:   {pt} prompt + {ct} completion  "
        f"→ {fmt_cost(trace.handler_cost)}"
    )


def trace_gate(trace: Trace) -> str:
    lines: list[str] = []
    if trace.sticky_before is None:
        lines.append(f"sticky state on entry: {DIM}(none){RESET}")
    else:
        lines.append(f"sticky state on entry: {CYAN}{trace.sticky_before}{RESET}")
    lines.append(f"decision: {trace.sticky_reason}")
    if trace.sticky_bypass:
        lines.append(f"{GREEN}✓ BYPASS ROUTER → intent={trace.intent}{RESET}")
    else:
        lines.append(f"{DIM}→ falling through to router{RESET}")
    return "\n".join(lines)


def print_case(router: str, message: str, expected: str | None, trace: Trace):
    got = trace.intent
    correct_mark = ""
    if expected:
        if got == expected:
            correct_mark = f"  {GREEN}✓ CORRECT{RESET}"
        else:
            correct_mark = f"  {RED}✗ WRONG (expected={expected}){RESET}"

    print()
    print(h(f"router={router}  ·  {message!r}{correct_mark}"))
    print(paint_graph(router, trace))

    print(f"  STICKY GATE")
    print(indent(trace_gate(trace)))

    if trace.sticky_bypass:
        print(f"  ROUTER  {DIM}(skipped — gate bypassed){RESET}")
    else:
        print(f"  ROUTER  ({trace.router_ms:.1f}ms · {fmt_cost(trace.router_cost)})")
        print(indent(trace_router(router, trace)))

    print(f"  HANDLER ({trace.handler_ms:.1f}ms · {fmt_cost(trace.handler_cost)})")
    print(indent(trace_handler(trace)))
    print(f"  TOTAL: {trace.router_ms + trace.handler_ms:.0f}ms · "
          f"{fmt_cost(trace.router_cost + trace.handler_cost)}")


# ─────────────────────────── run logic ──────────────────────────────────────

async def run_one(router: str, message: str) -> Trace:
    graph = build_graph(router)
    result = await graph.ainvoke({"message": message})
    return result["trace"]


def summarize(results: list[dict]) -> dict:
    n = len(results)
    correct = sum(r["correct"] for r in results)
    return {
        "accuracy": correct / n,
        "avg_router_ms": sum(r["router_ms"] for r in results) / n,
        "avg_handler_ms": sum(r["handler_ms"] for r in results) / n,
        "total_router_cost": sum(r["router_cost"] for r in results),
        "total_cost": sum(r["router_cost"] + r["handler_cost"] for r in results),
    }


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-v", "--verbose", action="store_true",
                    help="Per-message trace with router internals and handler I/O.")
    ap.add_argument("--router", choices=ALL_ROUTERS,
                    help="Trace only this router (default: all four).")
    ap.add_argument("--message", "-m", type=str,
                    help="Ad-hoc message instead of the fixture.")
    ap.add_argument("--only", type=str,
                    help="Run only one fixture case by id (e.g. c5).")
    args = ap.parse_args()

    routers = [args.router] if args.router else ALL_ROUTERS

    # Ad-hoc single message: verbose by default, no summary table.
    if args.message:
        for router in routers:
            trace = await run_one(router, args.message)
            print_case(router, args.message, None, trace)
        return

    cases = yaml.safe_load(Path("messages.yaml").read_text())["cases"]
    if args.only:
        cases = [c for c in cases if c["id"] == args.only]
        if not cases:
            print(f"No fixture case matches id={args.only!r}")
            return

    all_results: dict[str, list[dict]] = {}
    for router in routers:
        if not args.verbose:
            print(f"Running {router}...")
        results: list[dict] = []
        for case in cases:
            trace = await run_one(router, case["message"])
            results.append({
                "id": case["id"],
                "expected": case["expected"],
                "got": trace.intent,
                "correct": trace.intent == case["expected"],
                "router_ms": trace.router_ms,
                "router_cost": trace.router_cost,
                "handler_ms": trace.handler_ms,
                "handler_cost": trace.handler_cost,
                "kind": case.get("kind", "clear"),
            })
            if args.verbose:
                print_case(router, f"[{case['id']}] {case['message']}",
                           case["expected"], trace)
        all_results[router] = results

    # Summary table (skipped if only one case — noisy)
    if len(cases) > 1:
        print()
        print(h("SUMMARY", "═"))
        print(f"{'router':<12} {'acc':>6} {'router_ms':>10} "
              f"{'route $':>10} {'total $':>10}")
        print("─" * 52)
        for router in routers:
            s = summarize(all_results[router])
            print(
                f"{router:<12} {s['accuracy']:>6.0%} "
                f"{s['avg_router_ms']:>10.1f} "
                f"{s['total_router_cost']:>10.6f} "
                f"{s['total_cost']:>10.6f}"
            )

    # Disagreements (only useful when multiple routers ran)
    if len(routers) > 1 and not args.verbose:
        print()
        print("Disagreements (routers that got it wrong):")
        any_wrong = False
        for case in cases:
            disagree = [
                f"{r}={next(x['got'] for x in all_results[r] if x['id']==case['id'])}"
                for r in routers
                if not next(x['correct'] for x in all_results[r]
                            if x['id'] == case['id'])
            ]
            if disagree:
                any_wrong = True
                print(f"  [{case['id']} · {case['kind']}] {case['message']}")
                print(f"    expected={case['expected']}  {'  '.join(disagree)}")
        if not any_wrong:
            print("  (none — every router got every case right)")


if __name__ == "__main__":
    asyncio.run(main())
