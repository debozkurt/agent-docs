# Chapter 16 — Shared State Across Agents

[← Previous](./15-merge-vs-split.md) · [Index](./README.md) · [Next →](./17-streaming.md)

## The concept

When you have multiple agents (or multiple tool calls within one agent), they often need to share data: configuration, the user's identity, fetched state, intermediate results. **How** that data is shared determines whether your system stays simple and correct or becomes a tangled mess.

Three sharing patterns, in order of preference:

1. **Pass-by-value via config** — immutable data injected at agent construction
2. **Per-turn cache via closure** — mutable shared state scoped to one turn
3. **Persistent shared state** — data that survives turns (use very sparingly)

## Pattern 1: Pass-by-value via config

The agent and its tools receive an immutable `Config` dataclass at construction. Tools close over the config; the LLM never sees it; nothing mutates it.

```python
@dataclass
class AgentConfig:
    user_id: str
    tenant_id: str
    auth_token: str
    journal_id: str

def make_tools(config: AgentConfig) -> list:
    @tool
    async def fetch_user_data() -> str:
        # Tool closes over config
        return await api_call(config.user_id, headers={"Auth": config.auth_token})

    return [fetch_user_data]

agent = Agent(config=AgentConfig(...), tools=make_tools(config))
```

This is the cleanest pattern. Tools have everything they need; nothing leaks; the agent is testable.

**Use this for**: identity, auth, IDs, anything that's known at the start of the turn and doesn't change.

## Pattern 2: Per-turn cache via closure

Sometimes multiple tools within the same turn need to share *fetched* data. Example: the agent calls `get_state()`, then `update_thing()`, then `get_state()` again to check the result. Without sharing, the second `get_state()` makes a redundant API call.

The fix: a shared cache dict that all tools close over.

```python
def make_tools(config: AgentConfig) -> list:
    cache: dict[str, Any] = {}  # one cache per agent instance, scoped to one turn

    @tool
    async def get_state() -> str:
        if "state" in cache:
            return cache["state"]
        result = await api_call(config.url)
        cache["state"] = result
        return result

    @tool
    async def update_thing(field: str, value: Any) -> str:
        result = await api_call.patch(config.url, {field: value})
        cache.pop("state", None)  # invalidate — next read fetches fresh
        return "updated"

    return [get_state, update_thing]
```

Three rules for this pattern:

1. **Cache lives on the agent instance**, not globally. Each turn gets a fresh cache. Concurrency-safe by construction.
2. **Mutating tools invalidate the cache.** After a write, the next read must hit the source of truth.
3. **Cache is invisible to the LLM.** It's a performance optimization, not state the model reasons about.

This pattern saves real time: an agent that calls `get_state` 3 times in one turn now hits the API once.

## Pattern 3: Persistent shared state

Sometimes you genuinely need state that survives across turns or across agents in the same turn. **Be very careful here.** This is where bugs live.

If you must:
- **Scope it tightly** (per session, per user, per request)
- **Make it explicit** (named parameters, not global mutables)
- **Document the lifecycle** (when it's created, when it's invalidated)
- **Persist it durably** (a row in Postgres, not an in-memory dict)

In practice, persistent shared state is usually a sign you're trying to avoid using tools when you should just use tools. If Agent A has data Agent B needs, can Agent B fetch it from the same source via a tool?

## What does NOT belong in shared state

- **Tool results from a previous turn** → store in messages instead, the model already sees them
- **The LLM's reasoning** → that's in messages too, not external state
- **User preferences** → those are session state (Chapter 8)
- **Cached embeddings** → that's a vector store concern, not agent shared state

## Multi-agent coordination

When you genuinely need two agents to share intermediate state — say, a router agent that needs to pass extracted entities to a downstream agent — the cleanest approach is **explicit hand-off via state objects**:

```python
# Router agent runs and produces this:
@dataclass
class HandoffPayload:
    intent: str
    extracted_entities: dict
    suggested_next_agent: str

# Supervisor takes the payload and constructs the next agent's input
```

The payload is immutable, explicit, and easy to test. Avoid the temptation to share a mutable "context" dict that any agent can read or write — it makes execution order matter, which is fragile.

In LangGraph, this is what passing data through the graph state does. Each node returns a partial state update; the graph merges them; downstream nodes read from the merged state. **No mutation, just append/replace.**

## A note on the "shared scratchpad" / store

Modern frameworks give you a first-class place for cross-agent state: LangGraph's `Store`, CrewAI's shared memory, the Agents SDK session object. You'll hear this called a **shared scratchpad** or **shared store**. (It's the descendant of the "blackboard" pattern from classical AI, but almost nobody calls it that anymore.)

The rules above still apply. A shared store is just *persistent shared state with a nicer API* — tightly scoped, explicit keys, durable storage underneath. Use it when multiple agents genuinely need a common workspace (a plan being iteratively refined, a running set of findings). Don't use it as a dumping ground.

## Heuristic

> **Default to immutable config + per-turn cache. If you reach for persistent shared state, ask: is there a tool that could fetch this fresh instead?**

## Key takeaway

Share immutable config via dataclass closure. Share fetched data within a turn via a per-instance cache that mutating tools invalidate. Avoid persistent shared state — if multiple agents need the same data, let each fetch it via tools.

[← Previous](./15-merge-vs-split.md) · [Index](./README.md) · [Next: Streaming responses →](./17-streaming.md)
