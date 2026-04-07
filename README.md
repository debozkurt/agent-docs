# Building LLM Agents — A Reference Guide

> *Last verified: early 2026. The agent ecosystem moves fast — treat specific product names, model names, and prices as snapshots, not gospel. The patterns and decision frameworks underneath are stabilizing.*

A linear, build-up-from-zero guide to designing and architecting LLM agent systems. Starts with the absolute basics (what is an agent?) and builds up to multi-agent orchestration, context engineering, RAG, evals, security, and production concerns.

The concepts are framework-agnostic, but the worked examples lean on **LangGraph** and the **OpenAI Python SDK**, with notes throughout on how each concept maps to the **Claude Agent SDK** and the **OpenAI Agents SDK**. The principles travel across all of them; the choice of harness is mostly about which one fits your existing stack.

## How to read this guide

- **Newcomers** (you've called the OpenAI or Claude API once or twice): start at Chapter 1, read top to bottom.
- **Intermediate** (you've built a tool-calling agent): skim Part I, start at Chapter 5.
- **Experienced** (you've built multi-agent systems): jump to Part IV (Chapter 13) for architecture patterns and decision frameworks. Then read Part V, especially Chapters 18, 20, and 23 — the additions most often missing from production agents.

Each chapter is short — most run 300–700 words, the deeper ones (long-term memory, routing, evals, security) stretch toward 1500 when the topic earns it. Each chapter stands alone as a reference. Use the index below to jump to a specific topic, and the [glossary](./glossary.md) when a term needs a refresher.

---

## Index

### Part I — Foundations

1. [What is an agent?](./01-what-is-an-agent.md) — vs chatbot vs workflow
2. [The anatomy of an LLM call](./02-anatomy-of-an-llm-call.md) — messages, tools, schemas
3. [Tools — the agent's hands](./03-tools.md) — designing them well, structured outputs, idempotency
4. [MCP — tools as a protocol](./04-mcp-tools-as-protocol.md) — portability, isolation, trust boundary

### Part II — The Single Agent

5. [The execution loop](./05-execution-loop.md) — ReAct, recursion, termination
6. [State and messages](./06-state-and-messages.md) — the canonical state
7. [Prompts as code](./07-prompts-as-code.md) — composition and pitfalls

### Part III — Context, Memory & Knowledge

8. [Three kinds of state](./08-three-kinds-of-state.md) — conversation, session, long-term
9. [Context & cache engineering](./09-context-and-cache-engineering.md) — token budgets, layout, prompt-cache discipline
10. [Long-term memory with vector stores](./10-long-term-memory.md) — retrieval and pollution
11. [Retrieval-augmented generation (RAG)](./11-retrieval-augmented-generation.md) — knowledge corpora, hybrid search, rerankers
12. [State recovery and resumability](./12-state-recovery.md) — checkpointers, async and durable runs

### Part IV — Multi-Agent Architecture

13. [When to split (and when not to)](./13-when-to-split.md)
14. [Routing patterns](./14-routing-patterns.md) — classifiers, supervisors, handoffs vs tool calls vs workers
15. [The merge-vs-split tightrope](./15-merge-vs-split.md)
16. [Shared state across agents](./16-shared-state.md)

### Part V — Production Concerns

17. [Streaming responses](./17-streaming.md)
18. [Human-in-the-loop](./18-human-in-the-loop.md) — interrupts, approval gates, edit-and-resume
19. [Reliability — retries, validation, idempotency](./19-reliability.md)
20. [Guardrails, prompt injection & agent security](./20-guardrails-prompt-injection-security.md)
21. [Cost and latency optimization](./21-cost-and-latency.md) — with a worked example
22. [Observability — the minimum viable](./22-observability.md)
23. [Evals & regression testing](./23-evals-and-regression-testing.md) — golden sets, trajectory evals, LLM-as-judge

### Part VI — Practice and Patterns

24. [Common anti-patterns](./24-anti-patterns.md)
25. [Decision frameworks](./25-decision-frameworks.md)
26. [Reference architecture](./26-reference-architecture.md)
27. [Shipping checklist](./27-shipping-checklist.md)
28. [Tips and tricks (verified patterns)](./28-tips-and-tricks.md)
29. [Modern agent patterns and harnesses](./29-modern-patterns.md) — incl. multimodal and computer-use

### Reference

- [Glossary](./glossary.md) — every term used in the guide, one or two sentences each.
- [Worked example: a todo agent, end to end](./worked-example.md) — one complete agent built across the load-bearing chapters, ~280 lines of Python you can fork.

---

## Mapping concepts to the major SDKs

The guide is framework-agnostic in concept, but the same idea has different names in different SDKs. Quick cheat sheet:

| Concept | LangGraph | OpenAI Agents SDK | Claude Agent SDK |
|---|---|---|---|
| Agent loop | Graph with a tool node | `Agent.run()` | `query()` loop |
| Tools | `@tool` / `bind_tools` | `function_tool` / `Tool` | tool definitions, MCP servers |
| Multi-agent handoff | Edges between nodes | `handoff()` | Sub-agents via tool calls |
| Persistent state | `Checkpointer` | `Session` | Conversation files / hooks |
| Human-in-the-loop | `interrupt()` | `interruption_handler` | Pre-tool-use hooks |
| Guardrails | Custom node | `Guardrail` | Hooks + permission checks |
| Tracing | LangSmith integration | Built-in tracing | OpenTelemetry hooks |

When the worked examples in this guide use one SDK's vocabulary, the same pattern works in the others — the prose flags any meaningful differences.

---

## What this guide is NOT

- A LangGraph or SDK API reference (read each project's official docs for that)
- A prompt engineering guide (focused on architecture, not prompt tricks — though Chapter 9 touches on context engineering)
- A debugging playbook (focused on doing it right, not fixing what's wrong)
- A vector DB benchmark (uses "vector store" generically)
- An academic survey of RAG techniques (Chapter 11 is practical)

## What this guide IS

- A linear progression from "what is an agent?" to "how do I architect a multi-agent system?"
- A set of named patterns and anti-patterns you can reference in design discussions
- A decision framework for the questions that come up over and over (split vs merge, tool vs param, etc.)
- A working mental model that survives framework churn

## Sources and influences

This guide cross-references the most current public material from major LLM providers and frameworks. Where these sources disagree, the guide takes the position that's held up best in practice and explains the trade-off.

**Foundational essays**

- Anthropic, [Building Effective Agents](https://www.anthropic.com/research/building-effective-agents) (Dec 2024) — the canonical short essay on agent design patterns
- Anthropic, [Effective Context Engineering for AI Agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) (Sept 2025) — the follow-up that reframes prompt engineering as context engineering for agentic workflows

**Provider documentation (current)**

- OpenAI: [Function Calling](https://platform.openai.com/docs/guides/function-calling) · [Structured Outputs](https://platform.openai.com/docs/guides/structured-outputs) · [Prompt Caching](https://platform.openai.com/docs/guides/prompt-caching)
- Anthropic: [Tool Use](https://platform.claude.com/docs/en/agents-and-tools/tool-use/overview) · [Strict Tool Use](https://platform.claude.com/docs/en/agents-and-tools/tool-use/strict-tool-use) · [Prompt Caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching) · [Extended Thinking](https://platform.claude.com/docs/en/build-with-claude/extended-thinking)

**Standards and protocols**

- [Model Context Protocol (MCP)](https://modelcontextprotocol.io) — open standard for tool/resource sharing across agents and clients
- [OWASP LLM Top 10](https://owasp.org/www-project-top-10-for-large-language-model-applications/) — canonical threat list for agent security

**Agent frameworks**

- LangChain, [LangGraph](https://langchain-ai.github.io/langgraph/) — graph-based agent orchestration
- OpenAI, [Agents SDK](https://openai.github.io/openai-agents-python/) (Mar 2025) — opinionated Python/TypeScript SDK with handoffs, guardrails, and tracing
- Anthropic, [Claude Agent SDK](https://platform.claude.com/docs/en/agent-sdk/overview) — programmatic SDK built around Claude Code's agent capabilities

The framework choice matters less than the principles. Pick the one that fits your existing stack; the patterns in this guide work across all of them.
