# Chapter 27 — Shipping Checklist

[← Previous](./26-reference-architecture.md) · [Index](./README.md) · [Next →](./28-tips-and-tricks.md)

## The concept

You've built something. Before you put it in front of real users, walk this checklist. Most items take ten minutes; collectively they prevent the embarrassing failures.

This is not a list of things you must do — it's a list of things you should *consciously decide* whether you need. Some you'll skip on purpose. The point is to make the choice deliberately.

---

## Tools

- [ ] Every tool has a docstring written for the LLM (when to use, when NOT to use, parameter formats)
- [ ] Tools that take IDs validate them (UUID format, foreign key existence)
- [ ] Tools return clear error messages on failure ("ERROR: ...") that tell the LLM what to try next
- [ ] Idempotent tools are wrapped in a retry helper
- [ ] Non-idempotent tools have either dedup logic OR a clear "do not retry" comment
- [ ] No tool returns sensitive data the LLM shouldn't see (passwords, PII it doesn't need)
- [ ] Tool count per agent is ≤ 7

## Prompts

- [ ] System prompts are in code, not hand-edited per-call
- [ ] Prompts are versioned in git
- [ ] Each agent prompt has explicit role, rules, examples, and style
- [ ] Few-shot examples cover the common patterns and at least one negative case
- [ ] Literal `{` and `}` in prompts are escaped (`{{` `}}`)
- [ ] Prompts are under your token budget (e.g., 2500 tokens per agent)
- [ ] Today's date is injected if the agent reasons about time

## State

- [ ] Session state persists across turns in a real database, not in-memory
- [ ] Conversation history is trimmed to a reasonable window before the LLM call
- [ ] Orphaned tool calls are sanitized before sending to OpenAI
- [ ] Dynamic state (current todos, current items) is fetched via tools, not injected into prompts
- [ ] Long-term memory (if used) is scoped by user_id / tenant_id metadata
- [ ] Long-term memory has a retention policy (age cap, count cap, or both)

## Reliability

- [ ] Recursion limit is set on every tool loop (8 is a good default)
- [ ] Idempotent operations have retry on transient failures (1–2 attempts, exponential backoff)
- [ ] Non-idempotent operations are NOT retried, OR have idempotency keys
- [ ] Transient errors degrade gracefully (e.g., memory load failure → empty list, agent continues)
- [ ] Tool errors return strings the LLM can read, not exceptions that crash the loop

## Routing & multi-agent

- [ ] Router uses a cheap model (mini / haiku) with `temperature=0`
- [ ] Router output is validated against a known set of intents
- [ ] Router has a fallback default intent on errors or invalid output
- [ ] Each specialized agent has 1–5 tools (not the full set)
- [ ] Cross-cutting messages (touching multiple intents) are tested

## Streaming

- [ ] Responses stream token-by-token to the user
- [ ] Tool result events stream as typed SSE events
- [ ] `X-Accel-Buffering: no` header is set (or equivalent for your proxy)
- [ ] Stream interruption (closed tab, network drop) is handled cleanly
- [ ] Partial state is committed before the agent finishes streaming text

## Cost & latency

- [ ] Smart model is only used where reasoning matters; cheap model for everything else
- [ ] Token count per turn is logged
- [ ] Cost per turn is logged (estimated from token count × model price)
- [ ] You can answer "average / p99 latency per intent" from logs
- [ ] Vector memory is only loaded when the intent benefits from it
- [ ] No expensive work runs on small-talk turns

## Observability

- [ ] Every turn has a `turn_id` propagated through all log lines
- [ ] Per-turn telemetry record (intent, duration, llm_calls, tool_calls, cost, status)
- [ ] Tool call audit log (which tools, what args, success/failure)
- [ ] Errors are logged with full context (turn_id, agent name, tool name, input)
- [ ] Tracing (LangSmith / Langfuse / equivalent) is set up for at least the production environment

## Eval & testing

- [ ] **A golden set exists** — at least 30 cases, version-controlled next to the prompts (Chapter 23)
- [ ] Cases cover known-good behaviors *and* every bug you've ever fixed (every regression becomes a permanent case)
- [ ] **Fast eval suite** runs on every PR — small (20–50 cases), exact/heuristic graders only, under 2 minutes
- [ ] **Full eval suite** runs nightly or pre-deploy — larger, may include LLM-as-judge
- [ ] LLM-as-judge graders use a *different* model family than the one being judged, with rubric-based scoring (not "is this good?")
- [ ] Adversarial eval set covers prompt-injection attempts and jailbreaks (Chapter 20)
- [ ] Trajectory eval cases exist for the multi-step paths that matter most
- [ ] Every regression — even small ones — is investigated, not dismissed as noise
- [ ] Edge cases tested: empty conversation, missing context, long history, conflicting memory
- [ ] **The eval suite is a deploy gate** — a failing run blocks the merge/deploy

## Security & privacy

- [ ] User identity is verified before the agent has access to any user data
- [ ] Tools enforce ownership checks (user can only act on their own data)
- [ ] Internal service keys (LLM-to-application-API, LLM-to-vector-store, etc.) are rotated and not in code
- [ ] Per-user rate limiting is in place
- [ ] PII is not logged by default (or is redacted in log sinks)
- [ ] Long-term memory has a user-facing delete path (or at least an admin one)
- [ ] **Guardrails on inputs, outputs, and tool calls** — implemented with a different model than the agent itself (Chapter 20)
- [ ] **Indirect prompt-injection containment** — when the agent reads untrusted content (web pages, emails, documents), it has a restricted tool surface and high-impact actions require human approval
- [ ] **Tool credentials are scoped per tool**, not held as one giant credential by the agent process
- [ ] **Sandboxed code execution** — any tool that runs model-generated code does so in an isolated environment (container, microVM, separate process)
- [ ] **Outbound network access is allowlisted or logged** for any tool that browses or fetches arbitrary URLs
- [ ] **HITL approval gates** are in place for destructive or hard-to-undo actions (Chapter 18)

## Operational

- [ ] You can deploy a prompt change without redeploying the whole system (or at least with a fast rollback)
- [ ] You have a kill switch to disable a misbehaving agent
- [ ] You have a dashboard showing volume, error rate, latency, cost
- [ ] You have alerts on error rate spikes and latency regressions
- [ ] On-call knows which logs to look at and which dashboards to check

---

## How to use this checklist

Run through it before your first production user. Then run through it again every time you ship a major change. You don't have to check every box — but for any unchecked item, you should be able to articulate *why* you decided not to do it.

The most common failure mode is not skipping items deliberately, but not noticing that an item exists.

## Heuristic

> **A production agent isn't "an agent that works." It's an agent that works, can be debugged when it doesn't, fails gracefully, and tells you when something's wrong. The checklist is the difference.**

## Key takeaway

Walk the checklist before shipping. Skip items deliberately, not by accident. The items aren't all required — but the act of going through them prevents the embarrassing oversights.

[← Previous](./26-reference-architecture.md) · [Index](./README.md) · [Next →](./28-tips-and-tricks.md)

---

## You made it to the end of the main guide

If you've read all 27 chapters in order, you now have a comprehensive mental model for building agent systems. You know:

- What an agent is and isn't
- How the loop works and how to bound it
- How to design tools well, and how MCP turns them into a portable layer
- How to manage three kinds of state, and how to engineer context and the prompt cache
- When to use long-term memory vs RAG, and how to keep both from polluting responses
- When to split into multiple agents, when not to, and how delegation actually works (tool call vs handoff vs worker spawn)
- How routing works and how to use it cost-effectively
- How to share state across agents without tangling them
- How to stream responses, and how to pause for humans without losing state
- How to make the system reliable and how to defend it against guardrail violations and prompt injection
- How to optimize cost and latency, with worked math
- The minimum viable observability — and how it feeds the eval suite that catches regressions
- A field guide to common failure modes
- Decision frameworks for the questions that come up over and over
- A reference architecture you can build toward
- A checklist for shipping

Build the smallest version of this that solves your problem. Add layers as the symptoms force you to. Don't pre-build the architecture.

Good luck. Build something useful.
