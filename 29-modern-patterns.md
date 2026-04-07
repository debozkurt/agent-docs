# Chapter 29 — Modern Agent Patterns and Harnesses

[← Previous](./28-tips-and-tricks.md) · [Index](./README.md)

> *Last verified: early 2026. The harness ecosystem moves fast — treat the specific tool list as a snapshot, not gospel. The patterns underneath are stabilizing.*

## Why this chapter exists

The first 28 chapters of this guide focus on **chat-style agents** — a user sends a message, the agent calls some tools, the agent responds. That's the workhorse pattern and it covers most production use cases.

But over 2024–2026, a different shape of agent became dominant in another domain: **autonomous coding agents** like Claude Code, OpenHands, Aider, Cursor, Codex, and Goose. These agents don't just answer messages — they live alongside a developer, run for hours or days, edit files, run commands, and iterate until a task is complete.

The patterns that make these agents work are different enough from chat agents to deserve their own treatment. This chapter is the brief tour: what an agent harness is, what the Ralph loop is, how multi-layer memory works in this world, and how these patterns connect back to the foundations from the rest of the guide.

If you're building chat agents, you can skim this chapter — most of it doesn't apply directly. If you're building developer tools, automation pipelines, or anything long-running and autonomous, the patterns here are the state of the art.

This chapter also touches on **multimodal and computer-use agents** — a different shape again, where the tool surface is a screen or a microphone instead of an API. They share the harness foundation; what's different is how they perceive and act.

## What's an "agent harness"?

An **agent harness** is the wrapper system around an LLM that turns it from a chat completion API into a usable autonomous agent. Tool definitions, prompt engineering, memory management, orchestration, file system access, command execution, safety guardrails — all the surrounding machinery the model needs to do real work.

You can think of the LLM as the engine and the harness as the car. A 1000-horsepower engine with no transmission, no steering, no brakes is useless. The harness is what makes the engine drive[^harness].

Modern coding agents are mostly *harness*. The model is a relatively small part of what makes Claude Code or Cursor effective; the harness is where most of the engineering goes.

Examples of agent harnesses (early 2026):

| Harness | Origin | Primary use case |
|---|---|---|
| **Claude Code** | Anthropic | Terminal-based coding agent, file editing, command execution |
| **OpenHands** (formerly OpenDevin) | Open source | Autonomous coding agent, web UI, full dev environment |
| **Aider** | Open source | Terminal pair-programming, git-aware |
| **Cursor** | Anysphere | IDE-integrated coding agent |
| **Codex** | OpenAI | Coding agent CLI and integrations |
| **Goose** | Block (Square) | General-purpose local agent with MCP |
| **OpenClaw** | Open source | Local-first general agent runtime, 24/7 operation, gateway architecture |
| **Warp** | Warp | Terminal with built-in agent |

The specific tools come and go. The patterns underneath them are stabilizing and worth knowing.

[^harness]: Parallel.ai's [What is an agent harness?](https://parallel.ai/articles/what-is-an-agent-harness) is a good introduction to the concept.

## OpenClaw: a different harness shape

Most of the harnesses in the table above are **coding agents** — they live in a terminal or an IDE, react to a developer's prompts, and operate inside some kind of sandbox. OpenClaw is a different beast: a **continuously-running personal assistant** that connects to your messaging apps and runs on its own timer. It's worth understanding in detail because its architecture exemplifies a pattern that doesn't fit any of the other chapters cleanly[^openclaw].

The key architectural pieces are the **Gateway**, the **Agent Runtime**, **file-based state**, and the **Heartbeat**. None of them are exotic individually; the combination is what makes OpenClaw feel like a different kind of agent.

### The Gateway: channel-agnostic input routing

OpenClaw uses a **hub-and-spoke** architecture. A single component called the Gateway sits between the outside world and a single Agent Runtime. Inputs from WhatsApp, iMessage, Slack, Telegram, the macOS app, the CLI, and 30+ other channels all flow through the Gateway. The Gateway normalizes them and hands them to the Agent Runtime, which doesn't need to know or care which channel the message came from.

This is *channel routing* — a different shape than the *intent routing* covered in [Chapter 14](./14-routing-patterns.md). In intent routing, the question is "which agent should handle this message?" In channel routing, the question is "where did this message come from, and how do I normalize it?" OpenClaw does the second so its agent can focus only on the first.

The Gateway also tracks **session state** keyed by user/channel pair, so a conversation that starts in WhatsApp can be picked up in Slack and the agent has the same context.

### The five input types

The Agent Runtime doesn't only respond to user messages. The Gateway feeds it five different kinds of input, and the agent treats them all uniformly:

| Input type | Source | When it fires |
|---|---|---|
| **Messages** | Chat apps (WhatsApp, Slack, etc.) | When the user sends something |
| **Heartbeats** | Internal timer | On a regular schedule (e.g., every 30 min) |
| **Crons** | Scheduled tasks | At configured times |
| **Hooks** | Internal lifecycle events | On startup, shutdown, etc. |
| **Webhooks** | External systems (email, GitHub, Jira) | When events arrive from outside |

This is the architectural insight: the agent doesn't have a separate "background worker" or "scheduled job runner." All five input types invoke *the same agent loop*, just with different triggers. To the agent, "user said hi" and "the heartbeat timer fired" are both just contexts to reason about and act on.

### The Agent Runtime (a familiar ReAct loop)

The actual agent loop is the standard ReAct shape from [Chapter 5](./05-execution-loop.md): assemble context (session history + memory), invoke the LLM with bound tools, execute tool calls, append results, loop until the model is done. Tools include browser automation, file operations, scheduled job creation, Canvas, and others.

What's notable is what *isn't* there: no checkpointer, no graph state machine, no separate orchestration framework. The runtime is intentionally simple — the loop is small and the architecture's complexity lives in the Gateway and the state layer, not the agent itself.

### File-based state (Ralph in a different form)

OpenClaw stores state as Markdown files on disk. Session history, memory, breadcrumbs, todos — all files. This is the same insight as the Ralph Loop (next section): **the LLM's context is ephemeral and lossy; durable progress lives in files.**

The agent reads from and writes to these files via tools. The next heartbeat run, the next user message, the next webhook — each one starts fresh, reads the current state from disk, and proceeds. Long-running tasks ("I'm tracking your weekly podcast outline") work because the state isn't trapped in any single conversation's context window.

This isn't just an implementation detail. It's why OpenClaw can run for weeks on the same task without context rot. The file system is the agent's actual memory; the LLM's context window is just a workspace.

### The Heartbeat pattern in detail

The Heartbeat is the most distinctive thing OpenClaw does. It's a scheduled agent run — typically every 30 minutes — that invokes the *same* agent runtime with a "check in" context. The agent looks at its files, decides if anything needs attention, and either takes action or quietly does nothing.

This is what makes the agent *feel* autonomous even though there's nothing magical underneath. Most chat agents only run when the user types, so they're effectively dead between messages. OpenClaw is alive every 30 minutes — it might notice an unanswered email, a deadline approaching, an event needing a reminder, a task that should be moved forward — and surface it to the user *before* they ask.

Implementation-wise, the Heartbeat is just an entry in the same five-input event loop. The Gateway fires it on a timer; the agent receives a context block that says "this is a routine check-in, look at your todos and current state, decide if anything needs attention." It uses the same tools, the same memory, the same model as user-message turns.

This pattern generalizes: **if you want an agent that feels alive between user interactions, give it a heartbeat.** Don't build a separate scheduled-task system; reuse the same agent loop with a different trigger.

### What OpenClaw deliberately doesn't have

To understand the design, you have to understand the trade-offs it's accepting:

- **No sandbox.** OpenClaw runs in the user's environment with full filesystem access. There's no Docker container, no approval gates per tool call, no permission system. The trust boundary is "the user installed it on their own machine."
- **No isolation between concerns.** The agent that checks email is the same agent that edits files is the same agent that runs commands. There's one agent, one runtime, one trust scope.
- **Single-user.** OpenClaw is built for one human paired with one agent. Multi-user, multi-tenant, audit-logged setups would need substantial reworking.

These are deliberate. OpenClaw is optimized for the "personal assistant on my own machine" use case, which is a fundamentally different deployment model than "AI coding agent in a developer's CI pipeline" (Claude Code, OpenHands) or "customer-facing chat agent in a SaaS app" (the focus of the rest of this guide).

### When the OpenClaw shape makes sense

This pattern fits well when:

- **One trusted user, one agent**, no multi-tenancy
- **Long-running tasks** that span days or weeks
- **Multi-channel inputs** (the user wants to chat from any device/app)
- **Proactive behavior** matters more than approval gating
- **The user is the security boundary** — installed locally, full filesystem access acceptable

It fits poorly when:

- You need multi-user support, audit trails, or per-action permissions
- The agent runs in a server-side environment where filesystem access is risky
- You can't tolerate the agent acting without explicit user approval per action
- You need strict separation between concerns

For most production agents covered in this guide — chat-style, customer-facing, multi-tenant — the OpenClaw shape is wrong. For the specific niche of "my personal AI assistant running on my machine," it's a meaningful design point worth understanding.

[^openclaw]: OpenClaw is open-source and self-hosted. Project docs at [openclaw.ai](https://openclaw.ai). The architecture pattern here (gateway + heartbeat + file state) generalizes beyond OpenClaw itself.

## The Ralph Loop

In late 2025, Geoffrey Huntley popularized a deliberately simple pattern called the **Ralph Wiggum loop** (after the lovably persistent Simpsons character). The pattern: keep running the same prompt against the agent in an infinite loop until the task is actually done[^ralph].

```
while True:
    run agent with PROMPT.md as input
    check completion criteria
    if done: break
```

That's it. No state preservation in the LLM's context, no clever multi-turn orchestration, no checkpoint/resume machinery. Just a `while` loop.

### Why this works

The crucial insight: **the LLM's context window is ephemeral and lossy.** Long conversations degrade ("context rot"). The model forgets early instructions. Compaction events corrupt subtle constraints. Trying to maintain agent state across many turns *inside* the model is fighting the model's nature.

The Ralph loop sidesteps this entirely:

- **Progress lives in the filesystem and git history**, not the model's context
- **Each iteration starts fresh** — same prompt, same spec, same checklist
- **The agent reads the current state from disk** at the start of every iteration
- **Completion is checked externally** — by tests, by a checklist file, by a verification command — not by asking the model "are you done?"

The model is treated as a *worker* that executes one iteration at a time. The *agent* — the persistent entity making progress — is the loop, the files, and the git history.

### A concrete example

```bash
# PROMPT.md
You are working on the auth-refactor task. Your current state:
- Read TODO.md for the task list
- Read CLAUDE.md for constraints
- Make progress on the next unchecked TODO item
- Update TODO.md when you complete an item
- Run `pytest` and fix any failures
- When TODO.md has no unchecked items AND pytest passes, you are done

# Driver
while true; do
    claude-code --prompt PROMPT.md
    if all_todos_done && tests_pass; then
        break
    fi
done
```

The model sees a fresh context every iteration. It re-reads `TODO.md` and `CLAUDE.md`. It picks up where it left off based on what's in the files, not what's in its memory. Context rot becomes irrelevant because the context is small and rebuilt every time.

### When the Ralph loop is the right answer

- **Long-running tasks** that exceed any reasonable single context window
- **Tasks with verifiable completion criteria** (tests pass, checklist complete, file exists)
- **Repetitive iteration on a clear spec** — refactoring, migrating, applying a pattern across many files
- **When you want to throw model capability at the wall** — Ralph is "embarrassingly parallel" with the cost of more API calls in exchange for more reliability

### When it's not

- **User-facing real-time conversations** — the user can't watch a `while true` loop
- **Tasks where the spec changes during execution** — Ralph re-reads the spec every iteration; if you keep editing it, the agent can churn
- **When each iteration is expensive enough that you can't afford to over-iterate** — Ralph is intentionally inefficient; cost is the trade-off for reliability

Ralph is the simplest pattern that works for autonomous long-running agents. It's not elegant. That's the point — elegance is what got everyone stuck trying to make LLMs maintain state across 50-turn conversations.

[^ralph]: [How to Ralph Wiggum](https://github.com/ghuntley/how-to-ralph-wiggum) (Geoffrey Huntley's repo) and [Ralph Loop (Goose docs)](https://block.github.io/goose/docs/tutorials/ralph-loop/) cover the pattern in detail.

## Multi-layer memory in coding agents

Chapter 8 covered three kinds of state (conversation, session, long-term). Coding agent harnesses use a more elaborate multi-layer scheme that's worth knowing because it generalizes:

1. **The compact index** — a small (~200 lines) index of "what exists in the project" that stays in the model's context at all times. Cheap to keep loaded; tells the agent what's *available*.
2. **On-demand topic files** — larger documentation files loaded when the agent decides they're relevant to the current task. The agent reads them via tools.
3. **Full transcripts** — complete history of past sessions, stored on disk, only searched when explicitly needed.

This three-tier scheme keeps the always-loaded context tiny (cheap, fits in any window) while making any historical detail recoverable on demand. Compare it to vector memory (Chapter 10): it serves the same need but with more structure and less reliance on semantic search.

The Anthropic [Effective Context Engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) essay covers this pattern in depth — it's the "context engineering" approach replacing pure prompt engineering for long-running agents.

## Multi-scope instructions

Coding agents almost always load instructions from *multiple* files at *multiple* scopes:

- **Organization-level** (`~/.claude/CLAUDE.md`, etc.) — preferences that apply to all your projects
- **User-level** — personal coding style, language preferences
- **Project root** (`./CLAUDE.md`, `./AGENTS.md`) — project-specific conventions
- **Parent directory** — submodule or subsystem rules
- **Current working directory** — local conventions for this part of the codebase

The agent sees a *merged view*: organization rules + user rules + project rules + local rules, with more specific scopes overriding broader ones. As the agent moves through the codebase, the rules change to match the local context.

This is more sophisticated than the single-system-prompt model from Chapter 7, but the principle is the same: **the prompt is composed from named sections, not hand-written per call.** The harness just composes from more sources.

## Subagent fan-out

Multi-agent architecture (Chapters 13–16) covered routing and supervisor patterns for chat agents. Coding agents use a related but distinct pattern: **subagent fan-out**.

The orchestrator agent:
1. Receives a complex task
2. Decomposes it into subtasks
3. Spawns one **subagent per subtask**, each with:
   - Its own fresh context window
   - A *restricted* tool set (only what that subtask needs)
   - A focused prompt
4. Each subagent works independently and returns *only its result* to the orchestrator (not its full working context)
5. The orchestrator integrates the results

The key difference from chat-style routing: each subagent runs in a **completely isolated context window**. The orchestrator never sees the subagent's intermediate work — only the final output. This keeps the orchestrator's context small and prevents one subagent's failures from polluting another.

It's the same idea as the chat-style multi-agent split (Chapter 13), but optimized for parallel exploration rather than user-facing dispatch. Use this when:

- A task naturally decomposes into independent pieces
- Each piece can be specified completely up front (no mid-execution coordination needed)
- You'd rather pay for parallel context windows than serialize the work

## How MCP fits in

The harness ecosystem converged on **Model Context Protocol (MCP)** as the standard way to plug in tools (Chapters 3 and 4). Most modern harnesses are MCP clients out of the box: Claude Code, Cursor, Goose, Warp, ChatGPT, OpenClaw, and others.

This means tools you build as MCP servers work in any of them. A filesystem MCP server, a Postgres MCP server, a GitHub MCP server — write once, plug into any harness. The proliferation of harnesses and the standardization on MCP are mutually reinforcing: harnesses that speak MCP get the ecosystem of tools, and tools published as MCP servers get the ecosystem of harnesses.

If you're writing a tool that you might want multiple agents to use, **publish it as an MCP server.** That's the modern path to portability.

## Multimodal and computer-use agents

The last variant worth a brief tour is the agent whose tools aren't APIs at all — they're a screen, a keyboard, a mouse, a microphone, a camera. **Computer-use agents** like Anthropic's Computer Use, OpenAI's Operator, and the various browser-automation harnesses see screenshots and emit click/type/scroll actions. **Voice agents** consume audio and produce audio in real time. **Vision-first agents** ingest images, PDFs, charts, and dashboards as their primary input.

The deep architecture in this guide still applies: there's still a loop, still tools, still state, still context engineering, still evals. What's different in each case is the tool interface and the consequences of getting it wrong.

**What changes for computer-use agents:**

- The "tools" are `screenshot`, `click(x, y)`, `type(text)`, `scroll`. Each one is small but the combinatorial space is enormous.
- Latency is *much* worse — every action requires a screenshot, a model call, and a UI render. A turn that's 5 tool calls in the API world can be 50 in the screen world.
- Recovery is harder — there's no clean "tool error" channel. The agent finds out something went wrong by looking at the next screenshot and noticing the page is wrong.
- Prompt injection is even more dangerous: any web page the agent visits is untrusted content the model will literally read. Restricted tool surfaces (Chapter 20) become non-negotiable.

**What changes for voice agents:**

- Streaming isn't optional — the user is *talking*, not typing. Token-by-token TTS, mid-utterance interrupt handling, and barge-in support are first-class concerns.
- Context windows include audio, which is expensive in tokens.
- The "user message" is no longer text — it's a transcript that may be wrong, partial, or arrive in chunks. Treat it as a noisy input source.
- Latency budgets are much tighter. A 2-second pause feels broken in voice; in chat it feels normal.

**What changes for vision/document agents:**

- "Reading a document" is now a real operation with real cost. Image tokens are expensive; PDF parsing is lossy; tables and charts confuse models in different ways than they confuse humans.
- RAG (Chapter 11) often becomes "retrieve the right page" rather than "retrieve the right paragraph."
- Hallucinated citations are worse — the model can fabricate a "the chart on page 4 shows…" claim that's plausible and entirely wrong.

For all three: build the eval suite first. The failure modes are visible only when you watch the agent fail repeatedly on real inputs, and the fixes often involve changing the tool surface rather than the prompt. Computer-use, voice, and vision are *not* "chat agents with extra modalities" — they're different deployment shapes that happen to share the model and the loop.

If you're building one of these, treat this section as a starting point and the rest of the guide as the foundation. The principles travel; the specifics need their own chapter that this guide doesn't yet have.

## How these patterns fit with the rest of the guide

The patterns in this chapter aren't replacements for what came earlier — they're variations on the same themes for a different deployment shape. Cross-references:

| This chapter | Connects to |
|---|---|
| Agent harness as a wrapper | [Chapter 5 (execution loop)](./05-execution-loop.md), [Chapter 26 (reference architecture)](./26-reference-architecture.md) |
| Ralph loop | [Chapter 5 (execution loop)](./05-execution-loop.md), [Chapter 12 (state recovery)](./12-state-recovery.md) — files as durable state |
| Multi-layer memory | [Chapter 8 (three kinds of state)](./08-three-kinds-of-state.md), [Chapter 9 (context engineering)](./09-context-and-cache-engineering.md), [Chapter 10 (long-term memory)](./10-long-term-memory.md) |
| Multi-scope instructions | [Chapter 7 (prompts as code)](./07-prompts-as-code.md) — composability |
| Subagent fan-out | [Chapter 13 (when to split)](./13-when-to-split.md), [Chapter 14 (routing)](./14-routing-patterns.md), [Chapter 16 (shared state)](./16-shared-state.md) |
| MCP for tools | [Chapter 3 (tools)](./03-tools.md), [Chapter 4 (MCP)](./04-mcp-tools-as-protocol.md) |

The foundations are the same. The shapes are different. Knowing both lets you pick the right pattern for the right problem.

## What if I'm building a chat agent, not a coding agent?

Most of this chapter still informs your decisions, even if you don't use it directly:

- **The Ralph loop principle** — "store progress in durable storage, not the LLM's context" — applies to any long-running agent. Even chat agents benefit from treating the conversation history as truth and the LLM's context as a temporary view of it.
- **Multi-layer memory** — the compact index + on-demand load pattern works for any agent that needs to know about a large body of background data.
- **Subagent fan-out** — when a chat user asks "compare these 5 things," fanning out to 5 isolated subagents and integrating the results often beats sequential reasoning.
- **MCP** — the same standard that lets coding agents share tools lets your chat agent share tools.

The patterns generalize. Coding agents are just a forcing function that made the patterns explicit because the consequences of getting them wrong (hours of wasted compute, bad code merged) are more visible than in chat.

## Heuristic

> **The harness is where the engineering lives.** A 1000-horsepower model in a bad harness is worse than a 200-horsepower model in a great one. Spend your effort on the harness — context layout, tool design, iteration patterns, file-as-state — and the model gets to do what only the model can do.

## Key takeaway

Modern agent patterns — Ralph loops, multi-layer memory, subagent fan-out, MCP-based tool ecosystems — emerged from the coding agent world but generalize. The core insight is that you should **let durable storage hold progress and let the LLM's context be ephemeral.** The patterns in this chapter are different shapes; the principles from Chapters 1–22 still apply underneath.

---

[← Previous: Tips and tricks](./28-tips-and-tricks.md) · [Index](./README.md) · [Glossary →](./glossary.md)
