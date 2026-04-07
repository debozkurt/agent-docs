# Chapter 7 — Prompts as Code

[← Previous](./06-state-and-messages.md) · [Index](./README.md) · [Next →](./08-three-kinds-of-state.md)

## The concept

The system prompt is not "instructions in English." It's the **interface contract** between your code and the language model. Treat it like code: structured, versioned, composable, tested.

Sloppy prompts are the #1 source of agent failures. Good architecture and bad prompts will still produce a bad agent.

## What goes in a system prompt

A well-structured prompt has predictable sections:

```
1. ROLE          — who is the agent, what is its job
2. RULES         — hard constraints (always X, never Y)
3. TOOLS         — when to use which (this can also live in tool docstrings)
4. EXAMPLES      — few-shot demonstrations of correct behavior
5. CONTEXT       — dynamic info injected at runtime (the user's name, etc.)
6. STYLE         — how the agent should respond
```

Not every prompt needs all six sections. A minimal one might just be ROLE + STYLE. A complex multi-tool agent needs all of them.

## Few-shot examples

The single highest-leverage technique. Show the model 2–4 examples of the input → output behavior you want, and the model imitates the pattern.

```
## Examples

User: "appliances include dishwasher, fridge, microwave, oven, all from 2017"
Tool calls:
  save_fact("Dishwasher installed 2017")
  save_fact("Refrigerator installed 2017")
  save_fact("Microwave installed 2017")
  save_fact("Oven installed 2017")
Reply: "Got it — noted all four from 2017."
```

Show *what good looks like*. The model will pattern-match. Be careful: examples bias the model toward the specific names/values you use, so vary them.

## Negative constraints work

Contrary to old folklore, modern instruction-tuned models follow "DO NOT" rules well. Use them. Often a clear negative is more effective than a vague positive:

- ❌ "Be careful with the user's data"
- ✅ "DO NOT delete or modify any item the user did not explicitly mention"

## Composability — prompts as functions

As prompts grow, you'll want to assemble them from reusable pieces:

```python
def build_capture_prompt(config: AgentConfig) -> str:
    sections = [
        ROLE_CAPTURE,
        DECISION_TREE_CAPTURE,
        format_categories_list(config.categories),
        MEMORY_USAGE_RULES,
        STYLE_BRIEF,
    ]
    return "\n\n".join(sections)
```

This pays for itself the first time you want to update a rule across multiple agents. Don't string-concat at call sites; build from named parts.

## The brace escaping pitfall

If you use a prompt template engine (`ChatPromptTemplate.from_messages` etc.), `{variable}` is a substitution placeholder. Literal `{` and `}` in your prompt text — for example a JSON example like `{"name": "Weber"}` — will break the template or be interpreted as variable references.

The fix is to **double-escape literal braces** (`{{` and `}}`) in any text destined for a template. Most frameworks unescape them on render.

```python
# Bad — will fail with KeyError or ValueError
prompt = 'Use update(metadata={"key": "value"})'

# Good — escaped
prompt = 'Use update(metadata={{"key": "value"}})'
```

This bites everyone the first time. Consider using `.replace()` for substitution and writing prompts with literal braces, escaping all of them at the end:

```python
def escape_braces(text: str) -> str:
    return text.replace("{", "{{").replace("}", "}}").replace("{{var}}", "{var}")  # restore real placeholders
```

## Token budget discipline

Your prompt has a cost: every token in it is sent on every call. A 5000-token prompt across 100,000 turns is significant. Audit prompts periodically:

- Are all the examples earning their tokens?
- Is the same rule stated three times in three sections?
- Can the decision tree be one paragraph instead of six bullet points?

Set a budget per agent (say 2000 tokens) and hold the line.

## Versioning

Prompts are part of your codebase. They should be:
- Tracked in git like any other source file
- Reviewed in PRs
- Tested with eval cases (see Chapter 23)
- Tagged with versions if you do A/B testing

Don't hardcode prompts inline in handler functions. Pull them into constants or builder functions in a `prompts.py` module.

## Heuristic

> **If editing a prompt feels scary because you don't know what will break, you don't have an eval suite — and you should.** A 10-case test suite catches 90% of regressions.

## Key takeaway

Prompts are interface contracts. Structure them in named sections, use few-shot examples, lean on negative constraints, escape your braces, and version them in code.

[← Previous](./06-state-and-messages.md) · [Index](./README.md) · [Next: Three kinds of state →](./08-three-kinds-of-state.md)
