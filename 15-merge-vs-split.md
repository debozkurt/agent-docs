# Chapter 15 — The Merge-vs-Split Tightrope

[← Previous](./14-routing-patterns.md) · [Index](./README.md) · [Next →](./16-shared-state.md)

## The concept

Once you have specialized agents, you'll discover real users send **cross-cutting messages** — single sentences that span two of your specialties. *"The grill broke and I need to schedule a replacement"* might fall under both "status update" and "create todo." A strict single-intent router has to pick one, and the other half of the message is lost.

This is the merge-vs-split tightrope: **agents specialized enough to be accurate, generalized enough to handle real user messages.** Walk it carefully.

## The artificial-boundary trap

It's tempting to draw clean architectural boundaries between concerns: one agent for todos, one for category updates, one for facts. Looks clean on a whiteboard.

Then a real user says: *"We just replaced the dishwasher with a new Kenmore — also marking the old service ticket as done."*

That's:
- A category/spec update (new dishwasher info)
- A todo completion (old ticket)
- Possibly a fact to remember (the old one died)

If your three agents can each only do one of those three things, you've architected away the user's actual experience. They have to send three messages instead of one.

**The artificial-boundary trap**: drawing agent boundaries around *implementation concerns* (what tool category) instead of *user intent* (what the user is trying to accomplish).

## How to recognize an artificial boundary

You've probably split too aggressively if:

1. **A single user message frequently routes to the wrong agent** because it touches multiple agents' jobs and the router has to pick one.
2. **The "winning" agent's response feels incomplete** — it handled half the message and ignored the rest.
3. **You're tempted to add agent-to-agent handoff tools** so Agent A can call Agent B mid-turn.
4. **Sub-agents share most of their tools** with each other.

The first two are usability symptoms. The second two are architecture smells.

## How to recognize a good boundary

A boundary is real (and worth keeping) when:

1. **The agents have genuinely disjoint tools.** If Agent A has 3 tools and Agent B has 3 tools and they don't overlap, the boundary is real.
2. **The agents have genuinely different prompts.** If you can't merge them without making the prompt incoherent, they're doing different jobs.
3. **The user mental model matches.** Users naturally think "I'm asking a question" vs "I'm making a change" — those map to different agents (Query vs Manage).
4. **Cross-cutting messages are rare.** If 90% of messages cleanly belong to one agent, the boundary works even with imperfect routing for the 10%.

## When to merge

If you find yourself fighting the artificial-boundary problem, **merge**. Take two specialized agents and combine them into one with the union of their tools and a unified prompt that handles both jobs.

This sounds like a step backward — toward the "kitchen sink" agent of Chapter 13. It's not, if:

- The merged agent still has < 7 tools
- The merged prompt has a clear unified decision tree (not a Frankenstein "if X do this OR if Y do that")
- The merged agent has *one job*, just defined more broadly ("manage structured data" instead of "manage todos" + "manage categories")

## When to split (revisited)

Conversely, you can split a generalist when:

- A clearly distinct intent emerges that has its own tools (e.g., "answering questions about the home" needs context tools; "searching listings" needs MLS tools — different domains, different tool sets)
- The generalist's prompt is becoming a forest of conditionals
- One slice of users only cares about one slice of functionality

The point is: **let user behavior drive the boundary, not your initial guess.**

## The meta-rule

> **If real users say it in one sentence, it shouldn't span two agents.**

Test your boundaries by writing 10 realistic user messages and seeing where they route. If many of them split awkwardly across agents, the boundaries are wrong. Either merge those agents, or design routing that can dispatch to multiple agents in sequence (the supervisor pattern from Chapter 14).

## A worked example of merging

Suppose you have:
- **TodoAgent**: creates and completes activities
- **SpecsAgent**: updates category specifications

Real user messages that span both:
- *"the grill broke, need a new gasline"* → spec update (grill condition) + new todo (replacement)
- *"got the gasline installed"* → complete todo + spec update (back to good)

Two failure modes:
- TodoAgent handles the message, creates the todo, but never updates the spec
- SpecsAgent handles the message, updates the spec, but never completes the todo

Either way the user's intent is half-served. The fix is to merge them into a `ManageAgent` that has both toolsets and a prompt with explicit "cross-track" patterns.

The merged agent has 5 tools instead of 3. The prompt is a bit longer. But it can handle the full message in one turn, and the routing simplifies (one MANAGE intent instead of distinguishing TODO vs SPECS).

## Heuristic

> **Boundaries should follow user intent, not implementation. When you find a cross-cutting message that gets handled wrong, that's evidence your boundaries are in the wrong place — and the fix is usually to merge, not to add handoffs.**

## Key takeaway

Specialization is good until it gets in the user's way. Watch for cross-cutting messages and merge agents when the boundary becomes a frequent source of failure. The goal is the smallest number of agents whose boundaries match user intent.

[← Previous](./14-routing-patterns.md) · [Index](./README.md) · [Next: Shared state →](./16-shared-state.md)
