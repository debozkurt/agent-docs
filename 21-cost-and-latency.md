# Chapter 21 — Cost and Latency Optimization

[← Previous](./20-guardrails-prompt-injection-security.md) · [Index](./README.md) · [Next →](./22-observability.md)

## The concept

Agents are expensive. Every turn might involve an LLM call (or three), a vector store lookup, several API requests, and a few seconds of wall-clock time. At small scale this doesn't matter. At 100k turns/month, even small inefficiencies add up to real money and real user-perceived lag.

The good news: most optimization is structural, not algorithmic. A few well-placed decisions cut cost and latency by 5–10x without sacrificing capability.

## Model selection: the biggest knob

The single highest-leverage decision: **don't use the most expensive model for everything.** Modern LLM providers offer three rough tiers, each with a different cost/latency/capability profile:

| Tier | Examples (illustrative) | Use for |
|---|---|---|
| **Fast / cheap** | OpenAI gpt-4o-mini, Claude Haiku | Classification, routing, small talk, format conversion, high-volume background tasks |
| **Smart / balanced** | OpenAI gpt-4o, Claude Sonnet | Tool-using sub-agents, multi-step reasoning, anything user-facing with > 2 tools |
| **Reasoning** | OpenAI o-series, Claude with extended thinking | Hard reasoning where the smart tier is wrong, complex planning, math, deep code analysis |

Rough cost ratios: smart is 10–20× cheap per token; reasoning is another 5–10× on top, plus latency. A correctly routed system uses each tier only where it earns its cost.

```python
# Router uses cheap tier — single label, low stakes
router_model = make_model(tier="cheap", temperature=0, max_tokens=8)

# Sub-agents use smart tier — tool reasoning matters
agent_model = make_model(tier="smart", temperature=0)
```

Specific model names go stale quickly. The principle (cheap for routing, smart for tool use, reasoning only when smart isn't enough) holds across vendors and across releases.

## Reasoning models: a third tier worth knowing

OpenAI's o-series and Claude's *extended thinking* mode introduced a new model class around 2024–2025: models that do significant internal reasoning before responding[^reasoning]. They're meaningfully better at multi-step problems but have a different cost/latency profile than chat models:

- **Latency**: 2–10× slower per turn — they think before they speak
- **Cost**: thinking tokens are billed at output rates, plus the model is more expensive per token
- **Quality**: dramatically better on math, planning, complex code, multi-hop reasoning

**When to use a reasoning model:**

- Tasks where the smart tier is consistently wrong on the same kinds of problems
- Multi-step planning that the agent currently fakes by chaining many tool calls
- Background analysis (latency-tolerant) where quality matters more than speed

**When NOT to use one:**

- Simple lookups, single-step actions, format conversion — overkill, slower with no benefit
- Latency-sensitive user-facing turns
- Anything the smart tier already handles correctly

Reasoning models are an *escalation*, not a default. Most tool-using agents do best with the smart tier and never need to reach for reasoning.

[^reasoning]: Anthropic's [extended thinking docs](https://platform.claude.com/docs/en/build-with-claude/extended-thinking) describe budget tuning and tradeoffs in detail. OpenAI's o-series follows similar principles.

## Prompt caching: usually the biggest cost win

Both major providers will bill repeated prompt prefixes at a fraction of the normal input rate — typically a 50–90% reduction on the cached portion with zero behavior change. **OpenAI** caches automatically (no API changes; ~50% discount on cached tokens, cached prefixes start at 1024 tokens). **Anthropic** uses explicit `cache_control` breakpoints (~90% off cache reads; writes cost a small premium).

This is the closest thing to a free lunch in LLM cost optimization. The catch is that "prefix" means *exact byte-for-byte prefix*, which makes prompt structure a performance contract — not just a stylistic choice. The full discipline (cache-friendly prompt layout, what destroys cache hits, the order from most-stable to least-stable) is in [Chapter 9: Context & Cache Engineering](./09-context-and-cache-engineering.md). Set caching up early; structure the prompt with cache hits in mind from day one.

## Conditional work: skip what you don't need

A second high-leverage knob: **don't load data the agent isn't going to use this turn.**

The most common waste: loading vector memory on every turn, even for "thanks" or "hi". Vector lookup is ~500ms and adds to the prompt's token cost. Skip it when the intent doesn't need it:

```python
intent = await classify_intent(message)

memories = []
if intent in ("CAPTURE", "QUERY"):  # only intents that benefit from memory
    memories = await load_memories(query=message)
```

Same idea applies to:

- **System prompt sections**: only inject CMA data into the prompt for the QueryAgent, not all four agents
- **Tool inventories**: each sub-agent only sees its 2–4 tools, not the full set
- **History trimming**: drop old conversation turns aggressively

## Caching within a turn

If two tools in the same turn call the same expensive API, cache the result. The simplest cache is a dict scoped to the agent instance (Chapter 16):

```python
def make_tools(config, cache: dict):
    @tool
    async def get_state() -> str:
        if "state" in cache:
            return cache["state"]
        result = await expensive_call()
        cache["state"] = result
        return result
    return [get_state]
```

This is invisible to the LLM but cuts an n-call turn down to 1 call. Significant for chatty agents.

## Parallelize independent steps

Async lets you do multiple things at once. The router classifies intent in 200ms while the database fetches the user's profile in 300ms — running them sequentially takes 500ms, running them in parallel takes 300ms.

```python
import asyncio

intent_task = asyncio.create_task(classify_intent(message))
profile_task = asyncio.create_task(fetch_user_profile(user_id))

intent, profile = await asyncio.gather(intent_task, profile_task)
```

Be careful: only parallelize **truly independent** operations. If step B depends on step A's result, you can't parallelize them — and trying to will introduce subtle bugs.

## Prompt token discipline

Every token in the system prompt is sent on **every turn**. A 5000-token prompt × 100,000 turns/month = 500M tokens × 100,000 = (do the math at current pricing). Audit prompts:

- Are all the few-shot examples earning their tokens?
- Is the same rule stated three times in three sections?
- Can the decision tree be one paragraph instead of ten bullet points?

Set a per-agent budget (say 2000 tokens) and hold the line. When you add a new section, drop an old one or trim it.

## Latency budget per turn

Decide what's acceptable end-to-end:

| Budget | Use case |
|---|---|
| < 1s | Hard real-time (rare for agents) |
| 1-3s | Snappy chat experience |
| 3-5s | Acceptable for tool-using agents |
| > 5s | Streaming becomes essential — the user must see something happening |

Then break the budget down by component:

```
Total target: 3s
  Router       200ms
  Tool fetches 800ms (parallelizable)
  LLM call     1500ms
  Streaming    starts at 200ms (perceived as fast)
```

If your turn is consistently over budget, profile to find the bottleneck. The usual culprits: too many sequential tool calls, oversized prompts, or using the smart model when the cheap one would do.

## What NOT to optimize prematurely

- **Don't pre-compute embeddings of every possible query.** You don't know what users will ask.
- **Don't add caching layers for things that are rarely repeated.** Measure first.
- **Don't switch to a smaller model "for cost" without measuring quality.** A small model that gets things wrong is more expensive (in user experience and retries) than a larger one that gets them right.
- **Don't optimize the router from a cheap LLM to a fine-tuned classifier** until you have a real volume problem. At scale, the better upgrade is usually embedding-based routing (see [Chapter 14](./14-routing-patterns.md)) — it's faster, deterministic, and an order of magnitude cheaper than even the cheapest LLM call.

## A worked example: doing the math before you build

Optimizations are easier to choose when you have a number to push around. Here's the same calculation laid out for a hypothetical agent so you can do the same for yours.

**Setup.** A customer-facing chat agent. 100,000 turns/month. Each turn:

- A 2,000-token system prompt (stable; same bytes every turn)
- ~500 tokens of tool definitions (also stable)
- ~800 tokens of conversation history (varies)
- ~150 tokens of user message (varies)
- ~250 tokens of assistant response (varies)
- Average 2 tool calls per turn (negligible token cost in the request, modest in the response)

Round numbers, current pricing, smart-tier model: input ~$3 / 1M tokens, output ~$15 / 1M tokens. (Specific numbers go stale; the *shape* of the math doesn't.)

**Naive cost (no caching, no routing, smart model for everything).**

```
Per turn input:  2,000 + 500 + 800 + 150 ≈ 3,450 tokens
Per turn output: 250 + ~200 (tool args) ≈ 450 tokens
Per turn cost:   3,450 × $3/M + 450 × $15/M ≈ $0.0103 + $0.0068 ≈ $0.017
Per month:       $0.017 × 100,000 ≈ $1,700/month
```

**With prompt caching on the stable prefix.** The first 2,500 tokens (system prompt + tools) never change. Cache reads cost ~10% of input rate.

```
Cached portion:   2,500 × ($3 × 0.10)/M ≈ $0.00075
Uncached input:   950 × $3/M ≈ $0.00285
Output:           450 × $15/M ≈ $0.00675
Per turn:         ≈ $0.0104  (≈ 39% reduction)
Per month:        ≈ $1,040/month
```

**With caching + cheap-tier router** that handles 30% of turns (small talk, simple acknowledgments, narrow lookups) without invoking the smart model at all. Router cost is negligible (cheap model, ~50 tokens out).

```
70,000 smart turns × $0.0104 ≈ $728
30,000 cheap turns × ~$0.0006 ≈ $18
Per month:                    ≈ $746/month  (≈ 56% reduction from naive)
```

**With caching + router + conditional context loading** (skip the 800-token history on small-talk turns, skip vector memory unless the intent benefits):

```
~$650/month  (≈ 62% reduction from naive)
```

The point isn't that these specific percentages will hold for your agent — they won't. The point is that **structural decisions compound multiplicatively**: cache hits, model tiering, and conditional work each trim a slice, and stacking them is what turns "we can't afford to ship this" into "we shipped this and it pays for itself." Do the back-of-envelope math *before* writing the agent, and again after the first week of real traffic. The two numbers are usually wildly different, and that gap is your real optimization roadmap.

## A typical cost breakdown

For the system we built (multi-agent, with router + sub-agents + memory):

| Component | Share of cost | Why |
|---|---|---|
| Router | < 5% | Cheap model, single call, tiny output |
| Sub-agent LLM calls | 70-80% | Smart model, multi-call tool loops |
| Embedding generation | < 5% | Cheap embedding model |
| Vector retrieval | 0% | No LLM, just DB query |
| Background interpretation | 10-15% | If you do it; smart model in background |

The sub-agent LLM calls dominate. That's where to focus optimization (model selection, conditional work, caching) — not the router.

## Heuristic

> **Use the cheap model for classification, the smart model for reasoning. Skip work the agent doesn't need this turn. Cache repeated calls within a turn. Audit prompt tokens periodically. Measure before optimizing.**

## Key takeaway

Cost and latency optimization is mostly structural. Pick the right model per role, skip work conditionally, cache within a turn, parallelize independent steps, keep prompts lean. These four things cover 90% of the savings without algorithmic cleverness.

[← Previous](./20-guardrails-prompt-injection-security.md) · [Index](./README.md) · [Next: Observability →](./22-observability.md)
