# Chapter 6 — State and Messages

[← Previous](./05-execution-loop.md) · [Index](./README.md) · [Next →](./07-prompts-as-code.md)

## The concept

The conversation history is your agent's state. Every call sends the entire list; every response gets appended. State is **append-only by default** — you accumulate messages, you don't mutate them.

This sounds simple. The subtle part is deciding **what should go in messages versus what should go elsewhere** (prompt, tool results, external storage). Get this wrong and your agent gets confused or leaks state across turns.

## The append-only mental model

```
Turn 1:  [system, user_1]                             → assistant_1
         [system, user_1, assistant_1]                ← state after turn 1

Turn 2:  [system, user_1, assistant_1, user_2]        → assistant_2
         [system, user_1, assistant_1, user_2, assistant_2]   ← state after turn 2

...and so on.
```

Each turn, you load the prior state, append the new user message, call the model, append the response, and persist the new state.

In LangGraph, `MessagesState` does this for you. Returning `{"messages": [new_msg]}` from a node *appends* — it doesn't replace.

## Where things should live

This is the most important design question of the whole guide. Three places to put information:

| Lives in... | Persistence | Visible to LLM? | Use for... |
|---|---|---|---|
| **System prompt** | Static (set per turn) | Yes | Role, rules, tools, context that's true *right now* |
| **Messages** | Append-only history | Yes | Things the user said, things the agent said, tool results |
| **Tool returns** | One-shot per call | Yes (as tool message) | Fresh fetched data the agent needs to act on |
| **External state** | Persistent (DB, vector store) | No | Things you'll fetch via tools when needed |

The common mistake is putting **dynamic state in the system prompt**. It feels efficient ("the model already knows the user's preferences without a tool call!") but it's a trap:

- Prompt content is *snapshot at turn start* and goes stale immediately
- The model can't tell which prompt content is fresh vs stale
- The model treats prompt facts as authoritative even when reality has changed

The fix: **fetch state via tools, not prompt injection**. The system prompt has rules and role; tools provide current facts.

## Sanitizing messages

OpenAI's API has one strict rule that bites people: **every `tool_call` from the assistant must be followed by a `tool` message with a matching `tool_call_id`.** If your conversation history has an orphaned tool call (e.g. the previous turn was interrupted mid-execution), the next call will fail with `"tool_call_id did not have response"`.

Defense:

```python
def sanitize(messages):
    """Drop orphaned tool calls and orphaned tool messages."""
    tool_response_ids = {
        m.tool_call_id for m in messages
        if isinstance(m, ToolMessage)
    }

    cleaned = []
    for m in messages:
        if isinstance(m, AIMessage) and m.tool_calls:
            valid_calls = [tc for tc in m.tool_calls if tc["id"] in tool_response_ids]
            if valid_calls:
                cleaned.append(AIMessage(content=m.content, tool_calls=valid_calls))
            elif m.content:
                cleaned.append(AIMessage(content=m.content))
        elif isinstance(m, ToolMessage):
            # only keep if the corresponding tool_call survived
            if any(
                isinstance(c, AIMessage) and any(tc["id"] == m.tool_call_id for tc in c.tool_calls)
                for c in cleaned
            ):
                cleaned.append(m)
        else:
            cleaned.append(m)
    return cleaned
```

Run this *before* every model invocation if your message source can have gaps.

## Trimming history

Long conversations bloat the context window. You'll need to trim:

- **Drop oldest messages** (sliding window)
- **Summarize older sections** ("conversation so far: X")
- **Keep only the last N turns** (the simplest)

Three turns is a good default for tight, action-oriented agents. More for exploratory or reference-y assistants. Always include the system message and the current user message; trim the middle.

Long-term context that needs to survive trimming should live in external memory (Chapter 10), not in the message list.

## Heuristic

> **If it changes during a session, it doesn't belong in the system prompt.** Put it in messages (if it's a user/agent statement), in tool results (if you fetch it), or in external storage (if you need to persist it across sessions).

## Key takeaway

Messages are your canonical state — append-only, sanitized before every call, trimmed when too long. The system prompt is for static rules; dynamic state lives in messages or comes from tools.

[← Previous](./05-execution-loop.md) · [Index](./README.md) · [Next: Prompts as code →](./07-prompts-as-code.md)
