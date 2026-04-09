# Chapter 3 — Tools, the Agent's Hands

[← Previous](./02-anatomy-of-an-llm-call.md) · [Index](./README.md) · [Next →](./04-mcp-tools-as-protocol.md)

## The concept

A tool is a function the LLM can request. It's how the agent does anything in the world: read a database, call an API, write a file, send an email. The model decides *when* to call which tool and with what arguments; your code actually executes it and returns the result.

The shape of your tools determines almost everything about how well your agent works. Bad tools = bad agent, no matter how clever the prompt.

## What makes a good tool

**1. One clear purpose.** A tool should have one verb and one object. `create_activity`, `get_user_profile`, `send_email`. Not `manage_things`. The model picks tools by name + description; ambiguous tools get picked at random.

**2. A docstring written for the LLM, not for you.** The model reads the docstring to decide whether to use the tool. Include:
- What it does in one sentence
- When to use it (positive examples)
- When NOT to use it (negative examples)
- What each parameter means and how to format it

```python
@tool
async def complete_activity(activity_id: str) -> str:
    """Mark a to-do or reminder as completed.

    USE WHEN: the user reports finishing something with past-tense language
    ("I got it done", "we finished", "called the guy", "took care of that").

    DO NOT USE WHEN: the user is just observing ("the dishwasher is leaking")
    or planning ("I should fix that"). Those are not completions.

    Args:
        activity_id: Full UUID from get_home_context. Must look like
            '550e8400-e29b-41d4-a716-446655440000'. Do NOT pass placeholder
            strings like 'todo-id-here'.
    """
```

Negative examples are weighted heavily by modern models. "DO NOT USE" is more powerful than "use only when".

**3. Few parameters.** The more arguments a tool has, the more ways the model can get them wrong. Three required + a few optional is fine. Twelve required is a sign you should split the tool.

**4. Strict schemas — let the API enforce types.** Both major providers now support **grammar-constrained sampling** that guarantees the model's tool inputs match your JSON Schema exactly[^strict]. Set `strict: true` on the tool definition (Anthropic) or use the strict mode of function calling (OpenAI). The model will never return `"two"` when you asked for an integer; it will never omit a required field.

```python
# OpenAI: strict structured outputs on a tool
tool = {
    "type": "function",
    "function": {
        "name": "create_todo",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "due_date": {"type": "string", "format": "date"},
            },
            "required": ["title", "due_date"],
            "additionalProperties": False,
        },
    },
}

# Anthropic: same idea, different shape
tool = {
    "name": "create_todo",
    "strict": True,
    "input_schema": {
        "type": "object",
        "properties": {...},
        "required": ["title"],
        "additionalProperties": False,
    },
}
```

Strict mode eliminates a whole category of validation work. You still validate semantically (does this UUID exist? is this date in the past?), but you don't need to validate that the model returned a UUID-shaped string at all — the API guarantees it.

Use strict mode for any tool that takes structured input. There's almost no downside.

[^strict]: [OpenAI Structured Outputs](https://openai.com/index/introducing-structured-outputs-in-the-api/) | [Anthropic Strict Tool Use](https://platform.claude.com/docs/en/agents-and-tools/tool-use/strict-tool-use)

**5. Validation at the tool layer.** Even with strict schemas, semantic validation belongs in the tool. Schemas can't enforce that a UUID *exists* in your database, that a date is *in the future*, that a user *has permission* to perform the operation. Validate those inside the tool, *before* calling your downstream system. Return a clear error message that tells the model what to fix.

```python
if not is_valid_uuid(activity_id):
    return (
        f"ERROR: '{activity_id}' is not a valid UUID. Call get_home_context "
        f"first to fetch real activity IDs, then retry."
    )
```

The error message is part of the prompt. It's the LLM's only signal about what went wrong. Write it like you're talking to the model.

## Idempotency — the most important property

A tool is **idempotent** if calling it twice with the same arguments produces the same result as calling it once. Examples:

| Operation | Idempotent? |
|---|---|
| `GET /users/123` | Yes — read-only |
| `PATCH status=completed` | Yes — same status either way |
| `POST /emails/send` | **No** — sends two emails |
| `POST /todos/create` | **No** — creates two todos |
| Upsert by id with merge | Yes — same input, same output |

This matters because:
- **Idempotent tools can be retried** safely on transient failures
- **Non-idempotent tools cannot** — retrying creates duplicates
- The agent might call the same tool twice if the prompt is ambiguous

Design tools to be idempotent when possible. Use upserts instead of inserts. Use status patches instead of "create completed entry". When that's not possible, use **idempotency keys** (the caller passes a unique id, the server dedupes).

## Tool docstrings as instructions

Two quirks worth knowing:

**Negative examples are powerful.** Saying "DO NOT use this when X" is more reliable than saying "use this only when not X". Modern instruction-tuned models follow negative constraints well.

**Examples bias the model.** If your docstring shows `id="weber-grill"`, the model will tend to use `weber-grill` even in unrelated cases. Use varied, generic examples.

## Tools as a typed return channel

Strict mode does double duty. Most people think of it as input validation, but the same machinery makes the *return* path useful: if a tool returns structured data (a Pydantic model, a TypedDict, a JSON-shaped string), the model can pattern-match on the fields without you having to teach it your serialization format. This is why "use a tool call" is now the standard way to coax a model into producing structured output even when no real side effect is needed — define a `submit_answer(...)` tool with a strict schema and your downstream code receives a typed object instead of a string you have to parse. The agent loop becomes the boundary; the tool layer is your typed contract.

Treat tools, then, as a *bidirectional* typed interface: strict input schemas constrain what the model sends in, and structured returns constrain what your code reads out. Both halves are part of the same discipline.

## Tool binding is your safety boundary

There's a related decision that gets less attention than it deserves: which tools the model can call on a given turn. That set is determined when you bind tools to the model (`llm.bind_tools([...])`, `Agent(tools=[...])`, or whatever your framework calls it), and the resulting set is the **strongest safety constraint in the agent**.

Prompts can be ignored. The model can hallucinate a tool name. Runtime validators can be bypassed by a future refactor. But a tool that isn't in the bound set *literally cannot be called* — there's no function for the model to invoke. This is a hard constraint enforced by the framework, not a soft constraint enforced by the model's good behavior.

Use the property deliberately. Read-only handlers should bind only read tools. Write handlers should bind only the writes they need. If you've split into specialized sub-agents (Chapter 13–14), each one should bind the minimum tool set for its job — not the union of everything any specialist might want. A "query" agent that has the write tools available is one prompt failure away from mutating state it had no business touching.

The discipline this enables is the **negative assertion in tests**: not "this handler calls the right tool" but "this handler must NOT have any write tools bound at all." The negative version is stricter and catches the failure mode that matters — a future refactor that accidentally widens the bound set, or a copy-paste error that gives a read-only handler the full toolkit. A one-line test (`assert WRITE_TOOLS.isdisjoint(agent.bound_tools)`) is the strongest safety check available, because it doesn't depend on the model behaving well at runtime.

## Tool ecosystems: a quick note on MCP

Beyond your own application, tools have an emerging open standard: the **Model Context Protocol (MCP)**, introduced by Anthropic in late 2024 and now broadly adopted across Claude, ChatGPT, Cursor, VS Code, Claude Code, and others. MCP turns tools from app-internal functions into portable, isolated services with their own trust scope. It's a big enough topic — and a big enough architectural shift — to deserve its own chapter; the next one is about it.

For now, the only thing you need to know is that *the principles in this chapter apply to MCP tools too*. Strict schemas, idempotency, clear docstrings, semantic validation — they all matter the same whether your tool is a Python function in your codebase or a separate MCP server you connect to.

## Heuristic

> **Tools should be discoverable from their name and disambiguatable from their docstring.** If you have to read the source code to know when to call a tool, the model can't either.

## Key takeaway

Tools are the agent's only way to affect the world. Design them with one clear purpose, validate inputs, and make them idempotent so retries are safe. The docstring is the user manual the LLM reads.

[← Previous](./02-anatomy-of-an-llm-call.md) · [Index](./README.md) · [Next: MCP — tools as a protocol →](./04-mcp-tools-as-protocol.md)
