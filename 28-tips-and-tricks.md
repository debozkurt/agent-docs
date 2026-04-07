# Chapter 28 — Tips and Tricks (Verified Patterns)

[← Previous](./27-shipping-checklist.md) · [Index](./README.md) · [Next →](./29-modern-patterns.md)

## The concept

A cookbook of small, working patterns. Each one is something I've personally validated or that's well-documented in vendor docs. Copy them, adapt them, ignore them — they're starting points, not gospel.

Organized by what they help with, not by chapter. Each entry: name, why it matters, working code, link if there's authoritative documentation worth pointing at.

---

## Tool design

### Strict tool inputs (OpenAI)

Set `strict: true` to force the model's tool inputs to match your schema exactly. No more "Claude returned 'two' instead of 2."

```python
tool = {
    "type": "function",
    "function": {
        "name": "create_todo",
        "description": "Create a new to-do item.",
        "strict": True,  # ← grammar-constrained sampling
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "due_date": {"type": "string", "format": "date"},
                "priority": {"type": "string", "enum": ["low", "medium", "high"]},
            },
            "required": ["title", "due_date", "priority"],
            "additionalProperties": False,  # ← required for strict
        },
    },
}
```

[OpenAI Structured Outputs](https://platform.openai.com/docs/guides/structured-outputs)

### Strict tool inputs (Anthropic)

Same idea, slightly different shape — `strict: true` lives at the top level of the tool definition.

```python
tool = {
    "name": "create_todo",
    "description": "Create a new to-do item.",
    "strict": True,
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "due_date": {"type": "string", "format": "date"},
        },
        "required": ["title", "due_date"],
        "additionalProperties": False,
    },
}
```

[Anthropic Strict Tool Use](https://platform.claude.com/docs/en/agents-and-tools/tool-use/strict-tool-use)

### UUID validation as a defensive layer

The model occasionally hallucinates IDs — `"todo-id-here"` or `"weber-grill-uuid"`. Catch them in the tool before they reach your database.

```python
from uuid import UUID

def is_valid_uuid(value: str) -> bool:
    if not value or not isinstance(value, str):
        return False
    try:
        UUID(value)
        return True
    except (ValueError, AttributeError, TypeError):
        return False

@tool
async def complete_todo(todo_id: str) -> str:
    if not is_valid_uuid(todo_id):
        return (
            f"ERROR: '{todo_id}' is not a valid UUID. Call get_todos() "
            f"first to fetch real IDs, then retry. DO NOT make up UUIDs."
        )
    # ... actually do the work
```

The error message is the model's only signal about what went wrong. Write it like instructions.

### Tool docstrings with negative examples

LLMs respect "DO NOT" rules well. Use them.

```python
@tool
async def complete_activity(activity_id: str) -> str:
    """Mark an activity as completed.

    USE WHEN: the user reports finishing something with past-tense language
    ("I got it done", "we finished", "called the guy", "took care of that").

    DO NOT USE WHEN: the user is observing ("the dishwasher is leaking")
    or planning ("I should fix that") — those are not completions.

    Args:
        activity_id: Full UUID copied verbatim from get_home_context().
            Looks like '550e8400-e29b-41d4-a716-446655440000'.
            DO NOT make up UUIDs or pass placeholder strings.
    """
```

The exact UUID format example is critical — without it, models pattern-match on `"<uuid>"` and produce literal placeholder strings.

---

## State and caching

### Per-turn snapshot cache via closure

Multiple tools in the same turn often need the same fetched data. Cache it on the agent instance, invalidate on writes.

```python
def make_tools(config: AgentConfig):
    cache: dict = {}  # one cache per agent instance, scoped to one turn

    @tool
    async def get_state() -> str:
        if "state" in cache:
            return cache["state"]
        result = await api_fetch(config.url)
        cache["state"] = result
        return result

    @tool
    async def update_state(field: str, value: Any) -> str:
        result = await api_patch(config.url, {field: value})
        cache.pop("state", None)  # invalidate — next read fetches fresh
        return "updated"

    return [get_state, update_state]
```

The cache is invisible to the LLM. It's a performance optimization, not state the model reasons about.

### Sanitize orphaned tool calls before each LLM invocation

OpenAI requires every assistant `tool_calls` entry to have a matching `tool` message. If your conversation history has gaps (interrupted turns, message trimming), the next call errors with `"tool_call_id did not have response."`

```python
def sanitize_messages(messages):
    """Drop orphaned tool calls and orphaned tool messages."""
    tool_response_ids = {
        m.tool_call_id for m in messages
        if isinstance(m, ToolMessage)
    }
    cleaned = []
    for m in messages:
        if isinstance(m, AIMessage) and m.tool_calls:
            valid = [tc for tc in m.tool_calls if tc["id"] in tool_response_ids]
            if valid:
                cleaned.append(AIMessage(content=m.content, tool_calls=valid))
            elif m.content:
                cleaned.append(AIMessage(content=m.content))
        elif isinstance(m, ToolMessage):
            kept_call = any(
                isinstance(c, AIMessage)
                and any(tc["id"] == m.tool_call_id for tc in c.tool_calls)
                for c in cleaned
            )
            if kept_call:
                cleaned.append(m)
        else:
            cleaned.append(m)
    return cleaned
```

Run this before any model invocation if your message source has any chance of gaps.

---

## Reliability

### Retry helper for idempotent HTTP calls

Wrap `httpx` calls with a single retry on transient failures. Only use this on idempotent operations.

```python
import asyncio
import httpx

_TRANSIENT = (
    httpx.TimeoutException,
    httpx.ConnectError,
    httpx.ReadError,
    httpx.RemoteProtocolError,
)

async def request_with_retry(method: str, url: str, **kwargs) -> httpx.Response:
    """One retry with 200ms backoff on transient network failures.
    SAFE only for idempotent operations (GET, idempotent PATCH, upserts).
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

Catch only specific transient exceptions. Don't retry `ValueError` — that's a bug, not a fault.

### Router with strict output validation

LLM routers occasionally return garbage. Validate the response and fall back to a safe default.

```python
VALID_INTENTS = {"CAPTURE", "MANAGE", "QUERY", "CHAT"}

async def classify_intent(message: str) -> str:
    try:
        response = await router_model.invoke([
            SystemMessage(content=ROUTER_PROMPT),
            HumanMessage(content=message),
        ])
        raw = (response.content or "").strip().upper()
        # Strip punctuation in case the model added some
        for ch in (".", ",", "!", "?", ":", ";", '"', "'"):
            raw = raw.replace(ch, "")
        first_word = raw.split()[0] if raw else ""
        if first_word in VALID_INTENTS:
            return first_word
        return "CAPTURE"  # safe default
    except Exception:
        return "CAPTURE"  # network errors → safe default too
```

Two layers of defense: parse-then-validate, and exception fallback. Both default to the *safest* intent (capture is read-only/append-only — wrong routing is recoverable).

---

## Memory and context

### Cache breakpoint on a static system prompt (Anthropic)

Place `cache_control` on the last block that stays identical across requests. Add `"ttl": "1h"` for the longer TTL. Full discipline in Chapter 9.

```python
response = client.messages.create(
    model="claude-...",
    max_tokens=1024,
    system=[
        {
            "type": "text",
            "text": LARGE_STATIC_SYSTEM_PROMPT,  # 2000+ tokens, never changes
            "cache_control": {"type": "ephemeral"},
        },
    ],
    messages=[{"role": "user", "content": user_msg}],
)
```

### Conditional vector recall

Don't load vector memories on every turn. Skip when the intent doesn't need them. (The pattern is the same regardless of vector store — Milvus, Pinecone, pgvector, Weaviate.)

```python
async def supervisor(message: str, history: list):
    intent = await classify_intent(message)

    # Load memories ONLY for intents that benefit
    memories = []
    if intent in ("CAPTURE", "QUERY"):  # CHAT and pure tool actions skip this
        memories = await load_recall_memories(query=message, k=5, threshold=0.6)

    agent = make_agent_for_intent(intent, recall_memories=memories)
    async for event in agent.stream(message, history):
        yield event
```

Skipping memory load saves ~500ms on the turns that don't need it (typically chat and tool-execution turns).

### Vector recall with relevance threshold

Top-k alone isn't enough — if all 5 results are unrelated, you're injecting noise. Add a similarity floor.

```python
async def load_memories(query: str, k: int = 5, threshold: float = 0.6) -> list[str]:
    results = vector_store.similarity_search_with_relevance_scores(
        query, k=k, expr=user_filter,
    )
    # Filter by threshold — empty is better than noisy
    return [doc.page_content for doc, score in results if score >= threshold]
```

Empty memory beats wrong memory. The agent can always say "I don't have prior context on that."

---

## Streaming

### LangGraph token streaming via `messages` mode

The simplest way to stream tokens: use `stream_mode="messages"` and yield each non-empty chunk.

```python
async for chunk, metadata in graph.astream(
    {"messages": [HumanMessage(user_msg)]},
    config=config,
    stream_mode="messages",
):
    if chunk.content and not chunk.tool_calls:
        yield {"type": "delta", "text": chunk.content}
    elif hasattr(chunk, "tool_call_id"):
        # Tool result — handle separately if needed
        pass
```

Skip empty chunks and skip chunks that only carry tool_calls (those have no user-visible text).

### Server-Sent Events through FastAPI

```python
from fastapi.responses import StreamingResponse
import json

async def event_stream():
    async for event in agent.run(message):
        yield f"data: {json.dumps(event)}\n\n"

@app.post("/chat")
async def chat(req: ChatRequest):
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "X-Accel-Buffering": "no",   # critical — disables nginx buffering
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
```

Without `X-Accel-Buffering: no`, nginx and most other reverse proxies will buffer the stream and defeat streaming entirely.

---

## Prompt engineering

### Brace-escape helper for prompt templates

Templates like `ChatPromptTemplate.from_messages` interpret `{var}` as a placeholder. Literal braces in your prompt (JSON examples, dict literals) blow up rendering. Escape everything except your real placeholders.

```python
_RECALL_PLACEHOLDER = "__RECALL_MEMORIES_PLACEHOLDER__"

def escape_braces_safe(text: str) -> str:
    """Escape literal braces, preserving the {recall_memories} placeholder."""
    text = text.replace("{recall_memories}", _RECALL_PLACEHOLDER)
    text = text.replace("{", "{{").replace("}", "}}")
    text = text.replace(_RECALL_PLACEHOLDER, "{recall_memories}")
    return text
```

If you have multiple real placeholders, use a sentinel for each.

### Composable prompt sections

As your prompt grows, build it from named functions instead of a giant string.

```python
def build_capture_prompt(config: AgentConfig) -> str:
    sections = [
        ROLE_CAPTURE,
        DECISION_TREE_CAPTURE,
        format_categories_list(config.categories),
        MEMORY_USAGE_RULES,
        STYLE_BRIEF,
    ]
    return escape_braces_safe("\n\n".join(sections))
```

Pays for itself the first time you want to update a rule across multiple agents. Don't string-concat at call sites.

### Inject today's date

Models have no concept of "today" beyond their training cutoff. If the agent reasons about time, give it the date.

```python
from datetime import date

def today_section() -> str:
    today = date.today()
    return (
        f"\n## Date Context\n"
        f"Today is {today.strftime('%A')}, {today.isoformat()}. "
        f"Use this to resolve relative references like 'tomorrow', "
        f"'next week', 'before April 13'. Prefer ISO format (YYYY-MM-DD) "
        f"when storing dates.\n"
    )
```

Without this, "remind me next Tuesday" becomes a hallucinated date.

---

## Architecture

### Tool factory with closed-over config

Tools need access to user identity, auth tokens, and per-turn state. Use closures, not globals.

```python
def make_owner_tools(config: OwnerConfig, cache: dict):
    @tool
    async def get_home_context() -> str:
        if "context" in cache:
            return cache["context"]
        result = await fetch_context(
            url=f"{config.api_url}/journals/{config.journal_id}",
            headers={"Authorization": f"Bearer {config.auth_token}"},
        )
        cache["context"] = result
        return result

    return [get_home_context]

# Usage:
agent = Agent(
    config=OwnerConfig(...),
    tools=make_owner_tools(config, cache={}),
)
```

Each agent instance gets its own config and cache. No shared mutable state across requests.

### Multi-user attribution at the data layer

When multiple users can edit the same journal/document, stamp records with `added_by_user_id` and `last_updated_by_user_id` so you can answer "who did what."

```python
def stamp_new_item(item: dict, user_id: str, now_iso: str) -> dict:
    out = dict(item)
    if user_id and "added_by_user_id" not in out:
        out["added_by_user_id"] = user_id
    if "added_at" not in out:
        out["added_at"] = now_iso
    return out

def stamp_updated_item(merged: dict, user_id: str, now_iso: str) -> dict:
    out = dict(merged)
    if user_id:
        out["last_updated_by_user_id"] = user_id
    out["last_updated_at"] = now_iso
    return out
```

Apply at the data layer, not in the agent — keeps the agent simple and the audit trail consistent regardless of which agent (or non-agent code path) made the change.

### Recursion limit on every graph

Always cap iterations. A runaway loop is a real bug, not a hypothetical.

```python
config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 8}

async for chunk, metadata in graph.astream(
    {"messages": messages},
    config=config,
    stream_mode="messages",
):
    yield chunk
```

Eight is a reasonable default — enough for legitimate multi-step turns, tight enough to catch loops fast.

---

## Working with MCP

### Connecting to an MCP server (high-level)

The Anthropic and OpenAI agent SDKs both have built-in MCP client support. Tools from an MCP server appear to your agent as if they were local tools.

```python
# Pseudocode — exact API varies by SDK
from agent_sdk import MCPServer, Agent

mcp_server = MCPServer.from_command(
    command="uvx",
    args=["mcp-server-sqlite", "--db-path", "./data.db"],
)

agent = Agent(
    model="...",
    tools=[*local_tools, *mcp_server.list_tools()],
)
```

The MCP server runs as a subprocess (or HTTP service) and exposes its tools over the protocol. The agent calls them like any other tool.

[Model Context Protocol](https://modelcontextprotocol.io) — full SDK docs and sample servers.

---

## Debugging your own agent

### Per-turn structured log line

A single log record per turn answers most questions in production.

```python
import json, time, uuid

async def run_turn(user_message: str):
    turn_id = str(uuid.uuid4())
    t0 = time.time()
    intent = None
    tool_count = 0
    error = None

    try:
        intent = await classify_intent(user_message)
        result, tool_count = await dispatch(intent, user_message)
        return result
    except Exception as e:
        error = f"{type(e).__name__}: {e}"
        raise
    finally:
        print(json.dumps({
            "ts": time.time(),
            "turn_id": turn_id,
            "intent": intent,
            "tool_calls": tool_count,
            "duration_ms": int((time.time() - t0) * 1000),
            "status": "error" if error else "ok",
            "error": error,
        }))
```

Structured JSON lines are grep-able, parseable by any log aggregator, and answer "what happened in turn X?" instantly.

### Eval harness

The minimal "YAML cases + Python loop" recipe lives in [Chapter 23](./23-evals-and-regression-testing.md), where it belongs alongside the broader eval discipline. Steal it from there.

---

## Heuristic

> **Tips and tricks aren't substitutes for understanding.** Each pattern here exists because of a principle from earlier chapters. When you adapt one for your project, ask: *what principle is this serving?* — that's how you know whether your adaptation will hold up.

## Key takeaway

A small set of well-tested patterns covers most of what you need to build an agent that works in production. Steal liberally; adapt deliberately; understand the principle behind each one. The patterns in this chapter were learned the expensive way so you don't have to.

---

[← Previous: Shipping checklist](./27-shipping-checklist.md) · [Index](./README.md) · [Next: Modern agent patterns →](./29-modern-patterns.md)
