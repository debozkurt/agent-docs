# Chapter 25 — Decision Frameworks

[← Previous](./24-anti-patterns.md) · [Index](./README.md) · [Next →](./26-reference-architecture.md)

## The concept

Building agents involves the same handful of decisions over and over. Should this be a tool or a parameter? A new agent or a new prompt section? Should this state live in messages or in a tool result? Each one feels like a judgment call until you have a rule of thumb.

This chapter is a set of named decision frameworks for the questions that come up most often. Use them as starting points, not absolute laws.

---

## Should this be a tool or a parameter?

You're considering adding a new capability. Should it be a new tool, or a new parameter on an existing tool?

**Default to a parameter** if:
- The new capability is a variant of an existing operation (`update_thing(field=X)` vs `update_thing(field=Y)`)
- It uses the same downstream system
- The tool's purpose statement still fits

**Promote to a tool** if:
- It's a genuinely different operation (different verb)
- It hits a different system
- The existing tool's docstring would have to grow significantly to accommodate it
- You'd add a parameter that's only used 10% of the time

**Why this matters**: each tool adds to the LLM's decision space. Parameters are cheaper than new tools because they don't compete for selection.

---

## Should this be a new agent or a new prompt section?

You want to add support for a new kind of user message. New agent or new prompt branch?

**Add a prompt section** if:
- The current agent's tools can already handle it
- The new behavior is a refinement (more careful about X, better at Y)
- Adding it doesn't push the prompt past the budget

**Split into a new agent** if:
- The new behavior needs different tools the current agent doesn't have
- Adding it would create conflicting examples in the same prompt
- The current agent's accuracy is already degrading and adding more would make it worse
- The new behavior has a clearly different "personality" or response style

**Why this matters**: agents are expensive to add (orchestration, routing). Prompt sections are cheap until they aren't.

---

## Should this state live in messages, prompt, or tool result?

You have a piece of information the agent needs to know. Where does it go?

| If the data is... | Put it in... |
|---|---|
| Static rules / role | System prompt |
| User-said or agent-said | Messages |
| Fetched from a system, possibly stale | Tool result |
| The user's identity or auth | Config (passed to tools, not in prompt) |
| A long-lived fact about the user | Long-term memory (vector store), retrieved via tool |
| Something the agent needs to remember mid-turn | Tool cache (Chapter 16) |

**The strongest signal**: how often does this change? If it changes within a session, it's NOT system prompt material. If it changes between turns, it's NOT message material — it's tool-fetched.

---

## Should this run pre-router or post-router?

You're adding a new processing step. Does it run before classification or after?

**Pre-router** (always runs):
- Loading user context that any agent will need
- Trimming history
- Building input for the router

**Post-router** (runs only for the chosen agent):
- Loading data only relevant to specific intents
- Vector memory retrieval (if not all intents need it)
- Tool inventory specific to the agent

**Why this matters**: pre-router work runs every turn, even for "thanks!" Post-router work is conditional. Move expensive work post-router whenever possible.

---

## Should I add retry to this tool?

The tool sometimes fails on transient network errors. Add retry?

**Yes, if** the tool is **idempotent** (Chapter 19):
- GET requests
- Status update PATCH (sets a value, not increments)
- Upsert by id

**No, if** the tool is **not idempotent**:
- POST create (would create duplicates)
- POST send (would send twice)
- Counter increments (would double-count)

**Maybe, if** you can add an **idempotency key**: include a unique ID in the request, server dedups duplicate calls. Then retry is safe.

---

## Should I use the cheap model or the smart model for this?

**Cheap model** (mini, haiku):
- Routing / intent classification
- Small talk, greetings
- Short summaries
- Format conversion (text → JSON)
- High-volume background tasks

**Smart model** (4o, sonnet):
- Tool-using agents that have to reason about which tool to call
- Multi-step reasoning
- Following complex prompt rules
- Anything user-facing with > 2 tools

**Smartest model** (opus, o1):
- Hard reasoning that the smart model gets wrong
- Final synthesis where quality matters most
- Cases where you've already optimized everything else

**Default**: cheap for routing, smart for everything else. Don't reach for the smartest unless the smart isn't enough — and measure before you upgrade.

---

## Should I add this as an eval test case?

You just fixed a bug. Should it become a permanent test?

**Yes** if:
- The bug came from prompt or routing change (high regression risk)
- It would be embarrassing if it came back
- The fix is subtle (the next person maintaining the prompt won't notice they broke it)

**No** if:
- The bug was a one-off code error (unit tests cover it)
- It's a transient infrastructure issue
- The fix is so obvious nobody could regress it

**Default**: yes. Eval cases are cheap; regressions are expensive. Adding 10 test cases for the 10 weird user messages you've handled is the cheapest investment in agent quality.

---

## Should the agent be allowed to do this without confirmation?

You're adding a new capability that mutates user data. Should the agent commit it directly, or ask first?

**Direct commit** (no confirmation) if:
- Easily undone by the user
- Visible immediately in the UI
- Low blast radius if wrong

**Ask first** if:
- Hard to undo (deletes, sends emails, charges money)
- Affects other users
- Aggregates that would be expensive to recompute

**Default**: direct commit for additive operations, confirm for destructive ones. Users tolerate "oops, let me undo" but hate "oops, can't undo."

---

## When do I move from prototype to production architecture?

You've got a working prototype. When do you invest in routing, evals, observability, retries?

| Signal | Action |
|---|---|
| First user complaint about wrong behavior | Add eval cases |
| First bug from a prompt edit | Add eval suite + version control prompts |
| First production incident | Add structured logs with request IDs |
| Cost > $100/month | Add per-turn cost tracking |
| Latency > 5s consistently | Add streaming + measure components |
| Adding a 5th tool to the same agent | Consider splitting |
| Two distinct user types with different needs | Add a router |

Don't pre-build any of these. Wait for the signal, then invest. Premature architecture is the most common form of waste.

---

## Heuristic

> **The right answer is almost never "add more agents" or "add more tools." It's almost always "make what you have clearer, cheaper, or more reliable."**

## Key takeaway

Most agent design questions have a default answer that's right 80% of the time. Use the frameworks as starting points, override them when you have a real reason, and document your overrides so the next person knows why you chose the harder path.

[← Previous](./24-anti-patterns.md) · [Index](./README.md) · [Next: Reference architecture →](./26-reference-architecture.md)
