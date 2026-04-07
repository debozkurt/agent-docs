# Chapter 19 — Reliability: Retries, Validation, Idempotency

[← Previous](./18-human-in-the-loop.md) · [Index](./README.md) · [Next →](./20-guardrails-prompt-injection-security.md)

## The concept

Agents are distributed systems on top of distributed systems. The LLM is a flaky network call. Each tool is another flaky network call. Things will fail — usually transiently. Reliability is about deciding what to do when they do.

Three layers of defense:

1. **Validation** — catch bad inputs before they hit downstream systems
2. **Retry** — automatically recover from transient failures
3. **Graceful degradation** — when retries exhaust, fail in a way the system can recover from

## Idempotency: the prerequisite for everything

Before you can safely retry anything, you need to know whether the operation is **idempotent**: does running it twice produce the same result as running it once?

| Operation | Idempotent | Why |
|---|---|---|
| `GET /users/123` | ✅ | Read-only, no side effects |
| `PATCH /todos/123 status=completed` | ✅ | Same status either call |
| `PUT /users/123 {name: "Alice"}` | ✅ | Same end state |
| Upsert by id with merge | ✅ | Same input → same merged output |
| `POST /todos` (create) | ❌ | Creates two todos |
| `POST /emails/send` | ❌ | Sends two emails |

**Idempotent calls are safe to retry. Non-idempotent calls are not.** This single distinction governs your entire retry strategy.

If you have non-idempotent operations you absolutely need to retry, add **idempotency keys**: the caller passes a unique ID with the request, the server stores recent IDs, and duplicate requests return the original result instead of doing the work again.

## Validation at the tool layer

The LLM is going to send you garbage occasionally. Catch it before it hits Django, the database, the email service. Validate inside the tool function:

```python
@tool
async def complete_todo(todo_id: str) -> str:
    if not is_valid_uuid(todo_id):
        return (
            f"ERROR: '{todo_id}' is not a valid UUID. Call get_todos to fetch "
            f"real IDs and retry. Do NOT make up UUIDs."
        )

    if todo_id not in (await get_recent_todos()):
        return f"ERROR: No pending todo found with id '{todo_id}'."

    # ... actually do the work
```

The error message is part of the prompt. It tells the model what went wrong and what to try next. Write it like instructions to a junior engineer.

Common things to validate:
- **UUIDs** (use `uuid.UUID(value)`)
- **Enums** (status, condition, type)
- **Dates** (parseable, in valid range)
- **References** (the entity actually exists)
- **Permissions** (the user can actually modify this)

## Retry logic: only on idempotent calls

A simple retry helper for HTTP calls:

```python
import asyncio
import httpx

_TRANSIENT = (
    httpx.TimeoutException,
    httpx.ConnectError,
    httpx.ReadError,
    httpx.RemoteProtocolError,
)

async def request_with_retry(method, url, **kwargs):
    """Wrap an httpx call with one retry on transient network failures.

    ONLY use for idempotent operations.
    """
    for attempt in (1, 2):
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                return await client.request(method, url, **kwargs)
        except _TRANSIENT as e:
            if attempt == 1:
                await asyncio.sleep(0.2)
                continue
            raise
```

A few principles:

- **One retry is usually enough.** If two attempts fail, the system is genuinely down — keep retrying just delays the user pain.
- **Exponential backoff for more retries.** If you need more attempts, double the wait each time (200ms, 400ms, 800ms).
- **Never retry POST creates.** Period. Use idempotency keys instead.
- **Catch only specific exceptions.** Don't retry on `ValueError` — that's a bug in your code, not a transient fault.

## Graceful degradation

When retries exhaust, what should happen? You have two basic choices:

**1. Surface the error to the LLM.** The tool returns an error string; the LLM sees it and apologizes to the user or asks them to try again.

```python
try:
    result = await request_with_retry("POST", url, json=payload)
except _TRANSIENT:
    return (
        "ERROR: Network failure. Tell the user there was a connectivity "
        "issue and ask if they'd like to retry."
    )
```

**2. Fall back to a degraded but functional result.** If the vector store is down, return zero memories instead of crashing — the agent runs without recall.

```python
try:
    memories = await vector_store.search(query)
except VectorStoreError:
    memories = []  # degraded mode — agent runs but without recall
```

The right choice depends on whether the operation is **essential** (must succeed for the agent to function) or **enhancing** (nice to have, optional). Memory retrieval is enhancing. Persisting a user's todo is essential.

## Recursion limits as reliability

The agent's tool loop can run forever if the model keeps calling tools without making progress. **Always set a recursion limit.** LangGraph has `recursion_limit` on the graph config; in a hand-rolled loop it's the `for _ in range(N)`.

A limit of 8 catches most runaway loops without restricting legitimate multi-step reasoning. When the limit is hit, raise an error and surface "I got stuck — can you rephrase that?" to the user.

## What NOT to do

- **Don't retry on every exception.** Catch specific transient ones.
- **Don't retry POST creates.** You'll get duplicates.
- **Don't retry forever.** One or two attempts.
- **Don't swallow errors silently.** Log them, return error messages to the LLM, surface to monitoring.
- **Don't add a circuit breaker before you have basic retry working.** Premature complexity.

## Heuristic

> **Make tools idempotent so retries are safe; make retries safe so the agent doesn't propagate transient failures into user-facing errors.**

## Key takeaway

Reliability = idempotency + validation + retry. Make tools idempotent first. Validate inputs at the tool layer. Retry transient failures on idempotent calls only. Set recursion limits. Degrade gracefully when essentials fail.

[← Previous](./18-human-in-the-loop.md) · [Index](./README.md) · [Next: Guardrails, prompt injection & security →](./20-guardrails-prompt-injection-security.md)
