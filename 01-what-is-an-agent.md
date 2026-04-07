# Chapter 1 — What Is an Agent?

[← Index](./README.md) · [Next →](./02-anatomy-of-an-llm-call.md)

## The concept

An **agent** is an LLM that can take actions on the world and decide what to do next based on the results. Three pieces, always:

1. A **language model** that can read text and emit text
2. **Tools** (functions) the model can call to do things (read a file, query a database, send an email)
3. A **loop** that lets the model see the result of its action and decide what to do next

Anthropic's working definition is the simplest one: *"An agent is an LLM that uses tools in a loop."* That's it. Everything else in this guide is about how to do that well.

## Agent vs chatbot vs workflow

These three terms get conflated. They're meaningfully different:

| | Has tools? | Has a loop? | LLM decides next step? |
|---|---|---|---|
| **Chatbot** | No | No | N/A |
| **Workflow** | Sometimes | Yes (hardcoded) | No (humans wire the steps) |
| **Agent** | Yes | Yes | Yes |

A chatbot answers a question and stops. A workflow is `step1 → step2 → step3`, hardcoded by you. An agent decides for itself: *"to answer this, I need to call tool A, then based on what it returns, maybe call tool B."*

## When to use an agent (and when not to)

**Use an agent when:**
- The path to the answer depends on intermediate results you can't predict
- The user's input could mean many different things
- You need to combine multiple tools/data sources in a way that varies per request

**Don't use an agent when:**
- You can hardcode the steps (then it's a workflow — simpler, faster, cheaper)
- A single LLM call with a good prompt can do the job (then it's just a function)
- The task is fully deterministic (then it's just code)

> **Heuristic**: If you can write down all the steps as a flowchart with no LLM-driven branches, you don't need an agent. Use a workflow. Agents are for when "what to do next" is itself a decision the LLM should make.

## The spectrum: deterministic code → tool-augmented LLM → full agent

These aren't binary categories. There's a spectrum from "all code, no LLM" to "LLM decides everything," and most production systems sit somewhere in the middle. Knowing where on the spectrum a given task belongs is half the design work.

**Tier 0 — Pure deterministic code.** No LLM at all. The right answer for anything where the input/output mapping is known: parse a CSV, validate a form, query a database with known parameters, send a notification on a schedule.

```python
def is_business_hours(dt: datetime) -> bool:
    return dt.weekday() < 5 and 9 <= dt.hour < 17
```

If you can write the function, write the function. LLMs are slower, more expensive, and less reliable than code for things code can do.

**Tier 1 — Single LLM call with no tools.** The model takes input, returns output. Use for tasks where the *transformation* is hard but the *flow* is fixed: classify a support ticket, summarize a meeting transcript, translate text, extract structured fields from a paragraph.

```python
def classify_ticket(text: str) -> str:
    return llm.invoke([
        {"role": "system", "content": "Classify the ticket as: bug, feature, question, other."},
        {"role": "user", "content": text},
    ]).content.strip()
```

This isn't an agent. It's an LLM-as-function. No loop, no tools, no decisions about what to do next.

**Tier 2 — LLM with tools, but a fixed plan.** The model uses tools, but *you* decide what tools to call and in what order. The LLM is doing reasoning, but the orchestration is hardcoded:

```python
def answer_with_search(question: str) -> str:
    # Step 1: search (always)
    results = search(question)
    # Step 2: summarize results (always)
    return llm.invoke([
        {"role": "system", "content": "Answer the question using the search results."},
        {"role": "user", "content": f"Question: {question}\n\nResults: {results}"},
    ]).content
```

This is sometimes called a **workflow with LLM steps** or a **chain**. It uses LLMs but it isn't an agent — there's no decision-making loop. Use this whenever the steps are predictable. It's more reliable, cheaper, and easier to debug than a full agent.

**Tier 3 — Full agent with tool-calling loop.** The LLM decides which tools to call, in what order, with what arguments, and when to stop. Use this when the *plan itself* depends on intermediate results: the user's question could go in many directions, and the right next action isn't knowable until the model sees the result of the last one.

```python
def run_agent(message, tools, max_iter=10):
    messages = [system_prompt, message]
    for _ in range(max_iter):
        response = llm.invoke(messages, tools=tools)
        messages.append(response)
        if not response.tool_calls:
            return response.content
        for tc in response.tool_calls:
            messages.append({"role": "tool", "content": execute(tc)})
```

This is the focus of the rest of this guide. It's the most flexible, the most expensive, and the hardest to get right.

## How to pick a tier

Walk down the list, top to bottom. Use the first tier that can do the job:

1. **Can you write it as deterministic code?** → Tier 0. Don't even think about an LLM.
2. **Is there one transformation step that needs an LLM?** → Tier 1. One call, no tools.
3. **Are the steps predictable, even if individual steps need LLMs?** → Tier 2. Hardcoded chain.
4. **Does the plan itself need to be decided based on intermediate results?** → Tier 3. Full agent.

Most teams default to Tier 3 because "agents" are exciting. They'd be better served by a Tier 2 chain that's faster, cheaper, and easier to reason about. **Reach for the agent only when the lower tiers genuinely can't do the job.**

## A worked example: customer support triage

Imagine you're building a system that classifies incoming support tickets, attaches relevant docs, and either auto-responds or escalates to a human.

A naive design says: "Build an agent. Give it tools for classification, doc lookup, response generation, and escalation. Let the LLM figure it out."

A better design walks the tiers:

| Step | Tier | Why |
|---|---|---|
| Strip HTML, extract metadata | 0 (code) | Deterministic parsing |
| Classify ticket urgency from headers | 0 (code) | Lookup table on headers |
| Classify ticket topic from body | 1 (LLM, no tools) | One transformation, no decisions |
| Look up relevant docs by topic | 0 (code) | DB query with known key |
| Decide if auto-response is appropriate | 1 (LLM, no tools) | Single classification |
| Generate auto-response if appropriate | 1 (LLM, no tools) | Template fill |
| Escalate to human if not | 0 (code) | Conditional |

There's no agent in this design. The LLM is doing the things only an LLM can do (understanding language, generating responses), but everything else is code. The whole system is faster, cheaper, more debuggable, and more reliable than a Tier-3 agent doing the same job.

**When would you actually need a Tier-3 agent here?** Maybe if a "research" tier escalation lets the agent freely investigate a complex bug across multiple systems before answering. The agent's value is the unbounded exploration; the rest of the pipeline doesn't need it.

**The middle ground matters.** Tier 2 (LLMs as steps in a fixed chain) is where most production AI lives. It's neither pure code nor a full agent. It's the most underrated tier in the whole spectrum.

## The minimum viable agent (in pseudocode)

```python
def run_agent(user_message: str, tools: list) -> str:
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": user_message},
    ]

    while True:
        response = llm.invoke(messages, tools=tools)
        messages.append(response)

        if not response.tool_calls:
            return response.content  # done — model decided to respond, not act

        for tool_call in response.tool_calls:
            result = execute_tool(tool_call)
            messages.append({"role": "tool", "content": result})
```

That's the whole pattern. Everything in the next 20 chapters is about making this loop:

- Reliable (Chapter 5, 19)
- Smart enough to know when to stop (Chapter 5)
- Well-equipped with the right tools (Chapter 3, 4)
- Aware of its prior conversations (Chapter 8, 10, 11)
- Able to coordinate with other agents (Chapter 13–16)
- Production-grade (Chapter 17–23)

## A note on what this guide doesn't cover

This guide is about **conversational, text-based agents** — the workhorse pattern where a user sends a message, the agent uses tools to do work, and the agent replies. That's the most common shape of production agent system, but it's not the only one. Out of scope:

- **Voice agents.** Real-time speech in / speech out using APIs like OpenAI's Realtime or Anthropic's voice. Different streaming model, different latency budget, different prompt patterns.
- **Computer use / browser agents.** Agents that take screenshots and emit mouse/keyboard actions (Anthropic Computer Use, OpenAI Operator). Different toolset entirely — the "tools" are pixels and clicks.
- **Multi-modal ingestion.** Agents that primarily process images, PDFs, or audio at the input layer. Closer to vision/document AI than to conversational agents.
- **Background / proactive agents.** Agents that run on a schedule and surface insights without being asked. Different trigger model; the conversational principles still mostly apply but the streaming/UX layer doesn't.

When you need any of these, the foundations from this guide still help — tool design, state management, reliability, observability — but the specific patterns differ enough to need their own treatment.

## Key takeaway

An agent is a language model that calls tools in a loop until it decides it's done. If your problem doesn't need that decision-making, use something simpler.

[← Index](./README.md) · [Next: Anatomy of an LLM call →](./02-anatomy-of-an-llm-call.md)
