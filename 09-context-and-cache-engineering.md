# Chapter 9 — Context & Cache Engineering

[← Previous](./08-three-kinds-of-state.md) · [Index](./README.md) · [Next →](./10-long-term-memory.md)

## The concept

"Prompt engineering" was the name we used when the unit of work was a single, hand-tuned string going to a single model call. Modern agents have *many* model calls, *many* sources of context (system prompt, fetched data, message history, retrieved memories, tool results), and a hard token budget. The discipline of choosing **what goes into the context window, in what order, and how often it changes** is closer to systems engineering than to writing — Anthropic now calls it **context engineering**[^ce].

This chapter is about three intertwined concerns:

1. **What to include** (and what to leave out)
2. **Where to put it** (order matters more than newcomers expect)
3. **How to keep the prefix stable** (so the prompt cache actually fires)

Get this right and you cut both cost and latency by an order of magnitude while *improving* model quality. Get it wrong and you pay full price for context the model is ignoring anyway.

## What to include

Every token in the window is a tax: it costs money, it costs latency, and — past a certain point — it costs *quality*, because models exhibit the **lost-in-the-middle** effect[^litm]: information buried in the middle of a long context is recalled less reliably than information at the beginning or end.

A useful question for any piece of context: **does this change the model's next decision?** If the answer is "no" or "probably not," cut it. Specifically:

- **Old tool results** that have been superseded by newer ones — drop or summarize.
- **Long fetched documents** when only a paragraph is relevant — extract the paragraph.
- **Verbose tool errors** the model already recovered from — replace with a one-line note or remove.
- **Examples in the system prompt** that no longer match the failure modes you actually see — every example is also a token bill.

The opposite mistake is also real: stripping context the model genuinely needs to make a good decision. Validate aggressively (does removing this make eval scores drop?), not optimistically.

## Where to put it

LLMs attend most reliably to the **start** and **end** of their context. The middle is where things go to be forgotten. Practical implications:

- **System prompt at the top** — stable rules, tools, persona.
- **Critical instructions also restated near the end** — if there's one rule the model *must* follow ("never invent UUIDs"), put it in the system prompt *and* repeat it just before the user's message.
- **Recent conversation last** — the model's most recent input should be the last thing it sees.
- **Bulk reference material in the middle** — but only if it's small enough that "lost in the middle" doesn't matter, or you've narrowed it via retrieval.

## Compaction: keeping the window from filling up

Long sessions blow the budget. Two compaction strategies, often combined:

**Sliding window.** Keep the last *N* turns verbatim; drop everything older. Simple, deterministic, loses long-range memory. Good for chat where old turns rarely matter.

**Summarization.** When the window approaches its limit, replace the oldest *K* turns with a model-generated summary. Preserves long-range memory at the cost of fidelity and an extra model call. Good for task-oriented agents where early context (the user's goal) must survive.

Both strategies should respect tool-call/tool-result *pairs* — never split them, or the model sees an orphaned result with no call.

For things that genuinely need to persist across compaction, don't try to keep them in the message list at all. Move them to long-term memory (Chapter 10) or RAG (Chapter 11) and re-fetch on demand.

## Cache layout: the optimization that actually moves the needle

Both major providers offer **prompt caching**: if the prefix of your prompt matches a recent call, the cached portion is billed at ~10% of the normal input rate and processed with much lower latency[^cache]. The catch is that "prefix" means *exact byte-for-byte prefix*. A single token difference at byte 1 invalidates everything after.

This makes prompt structure a **performance contract**, not just a stylistic choice. The rule:

> **Order context from most stable to least stable.**

A cache-friendly layout looks like this:

```
[1] Static system prompt        ← never changes → cached forever
[2] Tool definitions            ← stable per agent version → cached
[3] User profile / persona      ← changes per session → cached per session
[4] Long-term memory excerpts   ← changes per turn → not cached
[5] Conversation history        ← changes per turn → not cached
[6] Current user message        ← always new
```

Common mistakes that destroy cache hits:

- **Putting the current timestamp in the system prompt.** Different bytes every call. Move it to a tool result.
- **Re-ordering tool definitions** between calls (some frameworks do this when tools are added dynamically). Sort them.
- **Interpolating user data into the system prompt.** Move user-specific data to its own block, *after* the cached prefix.
- **Trimming history from the front.** Trims the cached portion. Trim from the middle (preserving the stable head) instead.

A well-laid-out agent prompt can hit cache rates above 90% on the system+tools prefix, which is the difference between "this is too expensive to ship" and "we forgot to look at the bill."

## Heuristic

> **Context engineering is two questions: would the model behave worse without this token, and would removing it break my cache prefix? The cheapest token is the one you didn't include; the second cheapest is the one served from cache.**

## Key takeaway

Treat the context window as a managed resource, not a scratchpad. Cut what doesn't change behavior, place what remains by attention order, and structure your prompt so the stable parts come first — that's what makes the cache pay you back. The shift from prompt engineering to context engineering is the single biggest skill upgrade between a hobby agent and a production one.

[^ce]: Anthropic, [Effective Context Engineering for AI Agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) (Sept 2025).
[^litm]: Liu et al., [Lost in the Middle: How Language Models Use Long Contexts](https://arxiv.org/abs/2307.03172).
[^cache]: [Anthropic Prompt Caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching) · [OpenAI Prompt Caching](https://platform.openai.com/docs/guides/prompt-caching).

[← Previous](./08-three-kinds-of-state.md) · [Index](./README.md) · [Next: Long-term memory →](./10-long-term-memory.md)
