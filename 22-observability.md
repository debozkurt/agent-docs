# Chapter 22 — Observability: The Minimum Viable

[← Previous](./21-cost-and-latency.md) · [Index](./README.md) · [Next →](./23-evals-and-regression-testing.md)

## The concept

Agents are non-deterministic systems that fail in subtle ways. When something goes wrong in production, you need to be able to ask: *what actually happened in this user's turn?* Without observability, you can't answer that — you're guessing from screenshots.

This chapter is the minimum viable instrumentation. Not a deep dive on tracing infrastructure — just the things you should set up before you have your first production user.

## Three things to log

### 1. Per-turn telemetry

Every user message produces one **turn**. For each turn, log a single structured record at the end:

```json
{
  "turn_id": "abc-123",
  "user_id": "user-456",
  "session_id": "session-789",
  "intent": "MANAGE",
  "duration_ms": 3421,
  "llm_calls": 3,
  "tool_calls": 5,
  "prompt_tokens": 4231,
  "completion_tokens": 187,
  "estimated_cost_usd": 0.018,
  "status": "ok",
  "error": null
}
```

Now you can answer: average turn time, cost per intent, which intents fail most, what's the p99 latency. Without this, you're flying blind on production usage.

### 2. Tool call audit trail

Every tool call gets its own log line:

```json
{
  "turn_id": "abc-123",
  "tool": "complete_activity",
  "args": {"activity_id": "550e8400-..."},
  "duration_ms": 234,
  "status": "ok",
  "result_preview": "Activity marked completed."
}
```

This lets you answer: which tools fail most? Which user actions trigger which tool sequences? Did the agent call the right tool for this message?

### 3. Request ID propagation

Every log line in a turn — supervisor, router, sub-agent, tool, downstream API — should carry the same `turn_id`. Without this, you can't reconstruct what happened in a specific user's turn.

```python
import contextvars

current_turn_id: contextvars.ContextVar[str] = contextvars.ContextVar("turn_id", default="")

def log(component: str, message: str, **kwargs):
    print(json.dumps({
        "ts": time.time(),
        "turn_id": current_turn_id.get(),
        "component": component,
        "message": message,
        **kwargs,
    }))

# At the start of a turn:
turn_id = str(uuid4())
current_turn_id.set(turn_id)
```

`contextvars` works correctly with async code, unlike thread-locals. Use them.

## Tracing tools

For deeper visibility, use a tracing platform that understands LLM calls:

- **LangSmith** (LangChain's): integrates natively with LangGraph; sees every node, every tool, every LLM call as a span
- **Langfuse** (open-source alternative): same idea, self-hostable
- **Arize Phoenix**: similar, with stronger eval features
- **OpenAI Traces**: built into the OpenAI dashboard

Tracing platforms let you click on a single turn and see:
- The full prompt sent to the LLM
- The exact tool calls and their results
- Latency per step
- Token usage per step
- Errors with full context

Set this up early — it pays for itself the first time you have to debug a production issue.

## Evals — set them up early, see the next chapter for how

Observability tells you *what happened*; evals tell you *whether what happened was right*. They're a pair, and you can't operate the system in production with one and not the other. The full treatment — golden sets, trajectory vs final-answer evals, LLM-as-judge pitfalls, fast vs full suites — is Chapter 23. The thing to do *now*, while you're wiring up logging, is to start the file: even 10 cases captured from real failures is enough to begin the loop.

## What NOT to do

- **Don't log full conversation history to your main log stream.** It's enormous and contains user data. Sample, redact, or send to a separate sink.
- **Don't print directly with `print()`** in async code without context. Use a structured logger with the turn_id baked in.
- **Don't skip eval suites because they feel premature.** The first prompt regression that ships to production will convince you they were worth setting up earlier.
- **Don't only log success.** Failures are the interesting cases. Log them with full context.

## What good looks like

A mature observability setup answers these questions in seconds:

1. *What was the average turn latency this week?*
2. *Which intent has the highest tool-call count?*
3. *Show me all turns where complete_activity failed.*
4. *Which prompt change broke the recall-memory eval case?*
5. *What does turn `abc-123` look like end-to-end?*

If you can't answer those today, that's your roadmap.

## Heuristic

> **If you can't ask "what happened in this user's turn?" in seconds, you can't operate the system in production. Set up structured per-turn logging with request IDs before you have your first paying user.**

## Key takeaway

Per-turn telemetry, tool call audit trail, request ID propagation, and a small eval suite. These four things make agents operable in production. You don't need a full tracing stack on day one, but you need to be able to reconstruct any single user's turn from logs.

[← Previous](./21-cost-and-latency.md) · [Index](./README.md) · [Next: Evals & regression testing →](./23-evals-and-regression-testing.md)
