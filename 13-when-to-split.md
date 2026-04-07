# Chapter 13 — When to Split into Multiple Agents

[← Previous](./12-state-recovery.md) · [Index](./README.md) · [Next →](./14-routing-patterns.md)

## The concept

Most agent problems can be solved with one well-built agent. Splitting into multiple specialized agents adds real complexity — routing, shared state, coordination — and you should only do it when one agent is *measurably* hurting.

This chapter is about recognizing the symptoms of "one agent doing too much" and the criteria for when splitting actually helps.

## Symptoms of an overloaded agent

You should consider splitting when you see two or more of these:

1. **Tool count is creeping past 6–7.** The model starts second-guessing tool selection. Adding tool #8 makes accuracy noticeably worse.
2. **The system prompt has multiple "modes" or "personalities."** "When the user asks X, behave like Y; when they ask A, behave like B" baked into one prompt.
3. **The decision tree in the prompt is getting deep.** Pattern A, Pattern B, Pattern C, Pattern D... If you need 6+ branches to describe what the agent should do, the agent is doing too much.
4. **Examples conflict with each other.** Your few-shot examples for "creating a todo" pull the model in a different direction than your examples for "answering a question."
5. **The model is over-acting.** It tries to be helpful by doing extra things. This is a symptom of an agent with too many tools and too many possible interpretations.

If you only see ONE of these, fix the prompt first. If you see THREE, consider splitting.

## Symptoms that DO NOT mean you should split

- "The prompt is long" — long is fine if it's focused
- "I want to use a different model for one tool" — that's a tool-level concern, not an agent split
- "I want to add a feature" — most features are new tools, not new agents
- "It's slow" — splitting adds latency, doesn't reduce it
- "I think it would be cleaner architecturally" — clean isn't a goal; correctness and reliability are

## What splitting actually buys you

Two real benefits:

**1. Smaller decision space per agent.** Instead of "given any input, pick the right tool from 8 options," each specialized agent gets "given an input I know is in my domain, pick from 2–3 options." Models do this much more accurately.

**2. Specialized prompts.** A capture agent prompt is focused on capturing facts. A management agent prompt is focused on structured updates. Each prompt can be ruthlessly tuned for its job without conflicting with other concerns.

The cost: an extra routing step (Chapter 14 — could be a rule-based check, an embedding lookup, an LLM classifier, or an agent handoff), extra orchestration code, and a real risk that users will send messages spanning multiple specialties (Chapter 15).

## What should each agent be responsible for?

A useful test: **can you describe the agent's job in one sentence without using "or"?**

- ✅ "Save informational facts to memory."
- ✅ "Answer the user's questions about their data."
- ✅ "Make structured changes to the user's data."
- ❌ "Save facts AND create todos AND answer questions." ← needs splitting

If the description naturally has "and" or "or" in it, the agent is multi-purpose.

## How many agents is too many?

There's a cliff around 5–6 specialized agents where the routing complexity starts to outweigh the per-agent simplicity. Below that, you're fine. Above that, you're probably over-decomposing.

A common, sustainable shape:
- **1 router** (cheap, fast)
- **3–5 specialized sub-agents** (one per major intent)
- **1 fallback** (small talk, default behavior)

This is what we built and it's roughly what Anthropic and OpenAI both recommend for production systems.

## Splitting is hard to undo

Once you have a router and four specialized agents, *removing* one of them (because users were sending cross-cutting messages it couldn't handle) is real surgery. You're not just deleting a class; you're rewriting routing logic, merging prompts, redistributing tools.

**Consequence**: don't pre-split. Build one agent first. Wait for the symptoms above. Then split with conviction.

## Heuristic

> **Splitting is for fixing real symptoms, not for architectural elegance.** If the current agent works at the accuracy and latency you need, do not split. When you do split, draw the boundaries around *intents the user has*, not around *tools you have*.

## Key takeaway

Splitting helps when an agent is clearly overloaded (too many tools, conflicting modes, deep decision trees). It costs orchestration complexity and creates new failure modes. Default to one agent until the symptoms force a split.

[← Previous](./12-state-recovery.md) · [Index](./README.md) · [Next: Routing patterns →](./14-routing-patterns.md)
