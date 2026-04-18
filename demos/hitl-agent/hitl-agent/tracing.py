# tracing.py
# ---------------------------------------------------------------------------
# Terminal-formatted verbose tracing for the HITL agent.
#
# Labeled, color-coded blocks that make the invisible visible during
# demos and walkthroughs. Every function is a no-op when
# VERBOSE is False, so the performance cost of leaving trace calls in the
# code is zero.
# ---------------------------------------------------------------------------
from __future__ import annotations

import json
import os
import sys
from typing import Any

# Module-level flag. Set by agent.py or scenarios.py at startup.
VERBOSE = False

BANNER_WIDTH = 76

# ANSI colors — auto-disable when piping or NO_COLOR is set.
_USE_COLOR = os.isatty(1) and not os.environ.get("NO_COLOR")
_CYAN    = "\033[36m" if _USE_COLOR else ""   # user input
_GREEN   = "\033[32m" if _USE_COLOR else ""   # AI / approved
_YELLOW  = "\033[33m" if _USE_COLOR else ""   # tools / gates
_RED     = "\033[31m" if _USE_COLOR else ""   # rejected
_MAGENTA = "\033[35m" if _USE_COLOR else ""   # checkpoints
_DIM     = "\033[2m"  if _USE_COLOR else ""   # DB / meta
_BOLD    = "\033[1m"  if _USE_COLOR else ""
_RESET   = "\033[0m"  if _USE_COLOR else ""

# Label → color mapping. Unlisted labels render in default white.
_LABEL_COLORS = {
    "USER":          _CYAN,
    "SYSTEM PROMPT": _DIM,
    "LLM CALL":     _DIM,
    "LLM RESPONSE":  _GREEN,
    "TOOL CALL":     _YELLOW,
    "TOOL RESULT":   _YELLOW,
    "DB WRITE":      _DIM,
    "DB STATE":      _DIM,
    "GATE:PRE":      _BOLD + _YELLOW,
    "GATE:POST":     _BOLD + _YELLOW,
    "GATE:DECISION": _GREEN,
    "GATE:REJECTED": _RED,
    "CHECKPOINT":    _MAGENTA,
    "RESUME":        _BOLD + _MAGENTA,
    "THREAD":        _DIM,
}


def _banner(label: str, opening: bool = True) -> str:
    tag = f" {label} " if opening else f" /{label} "
    pad = max(BANNER_WIDTH - len(tag), 4)
    left = pad // 2
    right = pad - left
    return ("=" * left) + tag + ("=" * right)


def section(label: str, body: str) -> None:
    """Print a labeled, color-coded block. Short content stays on one line;
    long content gets opening/closing banners."""
    if not VERBOSE:
        return
    body = body.rstrip()
    color = _LABEL_COLORS.get(label, "")
    reset = _RESET if color else ""

    # Single-line compact format for short bodies
    if "\n" not in body and len(body) + len(label) + 5 <= BANNER_WIDTH:
        print(f"{color}{label:<16} | {body}{reset}")
        return

    # Multi-line with banners
    print(f"{color}{_banner(label)}")
    print(body)
    print(f"{_banner(label, opening=False)}{reset}")
    print()


# ─────────────────────────── convenience wrappers ──────────────────────────

def trace_thread(thread_id: str) -> None:
    section("THREAD", f"thread_id = {thread_id!r}")


def trace_system_prompt(prompt: str) -> None:
    """Show the system prompt (first turn only — it's static)."""
    preview = prompt[:400] + ("..." if len(prompt) > 400 else "")
    section("SYSTEM PROMPT", f"({len(prompt)} chars)\n{preview}")


def trace_llm_call(messages_count: int, last_user_msg: str) -> None:
    section("LLM CALL", f"sending {messages_count} messages to gpt-4o\n"
                         f"  last user/tool msg: {last_user_msg[:120]}")


def trace_llm_response(tool_calls: list, text: str,
                       prompt_tokens: int, completion_tokens: int) -> None:
    if tool_calls:
        calls = ", ".join(f"{tc['name']}({_brief(tc['args'])})" for tc in tool_calls)
        section("LLM RESPONSE", f"tool_calls: [{calls}]\n"
                f"  tokens: {prompt_tokens} prompt + {completion_tokens} completion")
    else:
        preview = text[:200] + ("..." if len(text) > 200 else "")
        section("LLM RESPONSE", f"text: {preview}\n"
                f"  tokens: {prompt_tokens} prompt + {completion_tokens} completion")


def trace_tool_call(name: str, args: dict) -> None:
    section("TOOL CALL", f"{name}({_brief(args)})")


def trace_tool_result(name: str, result: Any) -> None:
    preview = str(result)
    if len(preview) > 300:
        preview = preview[:297] + "..."
    section("TOOL RESULT", f"{name} returned:\n  {preview}")


def trace_db_write(table: str, row: dict) -> None:
    """Show a full row dump after a DB write."""
    cols = "\n".join(f"  {k:<14} = {v!r}" for k, v in row.items())
    section("DB WRITE", f"INSERT INTO {table}:\n{cols}")


def trace_db_state(table: str, rows: list[dict]) -> None:
    """Show full rows from a table (e.g. sent_log after send)."""
    if not rows:
        section("DB STATE", f"{table}: (empty)")
        return
    lines = []
    for r in rows:
        lines.append("  " + "  ".join(f"{k}={v!r}" for k, v in r.items()))
    section("DB STATE", f"{table} ({len(rows)} rows):\n" + "\n".join(lines))


def trace_gate(kind: str, payload: dict) -> None:
    """Show the interrupt payload surfaced to the human."""
    label = "GATE:PRE" if kind == "pre_approval" else "GATE:POST"
    body_lines = [f"kind: {kind}", f"tool: {payload.get('tool')}"]
    if kind == "pre_approval":
        preview = payload.get("preview") or payload.get("args") or {}
        for k, v in preview.items():
            line = f"  {k:<12} {v!r}"
            if len(line) > 72:
                line = line[:69] + "..."
            body_lines.append(line)
    else:
        result = payload.get("result") or {}
        for k, v in result.items():
            if k == "full_list":
                body_lines.append(f"  full_list: [{len(v)} items]")
                continue
            line = f"  {k:<12} {v!r}"
            if len(line) > 72:
                line = line[:69] + "..."
            body_lines.append(line)
    section(label, "\n".join(body_lines))


def trace_gate_decision(kind: str, tool: str, decision: str,
                        reason: str = "") -> None:
    label = "GATE:DECISION" if decision == "approve" else "GATE:REJECTED"
    msg = f"{kind} / {tool} → {decision}"
    if reason:
        msg += f" ({reason})"
    section(label, msg)


def trace_checkpoint(step: int, thread_id: str,
                     state_keys: list[str]) -> None:
    section("CHECKPOINT", f"wrote step {step} → thread_id={thread_id!r}\n"
            f"  state keys: {state_keys}")


def trace_resume(thread_id: str, state_keys: list[str]) -> None:
    section("RESUME", f"loaded checkpoint for thread_id={thread_id!r}\n"
            f"  state keys: {state_keys}")


def _brief(args: dict) -> str:
    return ", ".join(f"{k}={v!r}" for k, v in list(args.items())[:3])
