# Chapter 2 — The Anatomy of an LLM Call

[← Previous](./01-what-is-an-agent.md) · [Index](./README.md) · [Next →](./03-tools.md)

## The concept

An LLM is **stateless**. Every time you call it, you send the *entire* conversation. The model has no memory between calls. That single fact dominates how agents are built.

Three things go in, one thing comes out:

```
INPUT                          OUTPUT
─────                          ──────
[messages list]                response message
[tool definitions]    ──→
[parameters]                   - text content, OR
                               - tool_calls (a list of "please run X with these args")
```

## Messages

A message is `{"role": ..., "content": ...}`. Four roles:

- **`system`** — instructions to the model (always first, sometimes the only one you write)
- **`user`** — what the human said
- **`assistant`** — what the model said previously
- **`tool`** — the result of a tool call the model made

A conversation is a list of messages. To continue the conversation, you append to the list and call again.

```python
messages = [
    {"role": "system", "content": "You are Cid, a property assistant."},
    {"role": "user", "content": "Add a todo to clean the HVAC."},
]
response = client.chat.completions.create(model="gpt-4o", messages=messages, tools=TOOLS)
messages.append(response.choices[0].message)
# now messages has 3 entries; next call sends all 3
```

## Tools (in the protocol)

A tool is a JSON schema describing a function the model can request. You give the model the schema; the model decides whether and how to call it; you actually run the function and pass back the result.

```python
TOOLS = [{
    "type": "function",
    "function": {
        "name": "create_todo",
        "description": "Create a new to-do item for the homeowner.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Short description"},
                "due_date": {"type": "string", "format": "date"},
            },
            "required": ["title"],
        },
    },
}]
```

When the model decides to call this tool, the response will contain `tool_calls`:

```python
response.choices[0].message.tool_calls
# [{"id": "call_abc", "function": {"name": "create_todo",
#   "arguments": '{"title": "Clean HVAC", "due_date": "2026-04-13"}'}}]
```

You parse the args, run your actual function, and return a `tool` message with the result. The model never runs your code; you do.

## Context window and token budget

Every model has a maximum number of tokens it can process per call (the *context window*). gpt-4o is ~128k tokens; smaller models are smaller. Three things eat into it:

1. **System prompt** — the instructions you wrote
2. **Conversation history** — every prior message
3. **Tool definitions** — schemas count too

If you blow the budget, you get truncated or an error. You manage this by trimming history, tightening prompts, and not loading every tool on every call (Chapter 9, 14).

## Temperature and determinism

`temperature` controls randomness. `0.0` is deterministic-ish (same input → same output, mostly). `1.0` is creative. For agents, **always use a low temperature** (0.0–0.3). You want the model to follow instructions reliably, not get creative about whether to call a tool.

Routing classifiers and tool-using agents should be at `temperature=0`. Free-form generation (small talk, summaries) can go higher.

## What this means for agent design

Because the LLM is stateless and you're paying per token:

- Every call is a fresh start — there is no "memory" beyond what you pass in
- Your job as the agent designer is **deciding what goes into the context window** for each call
- The conversation history is *your* state, not the model's
- "Memory" features (vector stores, etc.) are external systems you stuff into the context

## Key takeaway

An LLM call is just `(messages, tools) → message`. The model has no memory; you assemble its context every turn. Designing an agent is mostly about *what to put in that context*.

[← Previous](./01-what-is-an-agent.md) · [Index](./README.md) · [Next: Tools →](./03-tools.md)
