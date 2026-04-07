# Chapter 23 — Evals & Regression Testing

[← Previous](./22-observability.md) · [Index](./README.md) · [Next →](./24-anti-patterns.md)

## The concept

Every chapter so far has assumed you can tell whether your agent is working. In practice you usually can't, because LLM agents fail in ways that unit tests don't catch: a prompt edit subtly degrades behavior on 8% of inputs, a model upgrade flips edge cases, a tool description change breaks routing. None of those are "the code threw an exception." All of them are real regressions, and the only thing that catches them is **evals**.

An eval suite is to an agent what a test suite is to a regular program. It's the safety net that lets you change anything — a prompt, a model, a tool, a router — and *know* whether you broke something before your users do. If you take one thing from this guide, take this: **without evals, you don't have an agent. You have a demo.**

## Two kinds of evals

The first thing to understand is that there are two fundamentally different things you can test:

**Final-answer evals** check the agent's output against an expected answer. "When asked X, the response should mention Y and not mention Z." Cheap, easy to write, easy to grade. These are what most people start with and they catch most regressions.

**Trajectory evals** check the *path* the agent took, not just the destination. "When asked X, the agent should call `get_user_profile`, then `search_orders`, then respond." These catch a different class of bug — the agent that gets the right answer for the wrong reason, or that wastes 3 tool calls before stumbling into the right one. Trajectory evals are more expensive to write and more brittle (paths legitimately change), but they're the only way to catch silent quality regressions in a multi-tool agent.

Build final-answer evals first. Add trajectory evals once you've shipped a regression where the answer was right but the agent took a clearly wrong route to get there.

## Building the golden set

A **golden set** is the curated collection of inputs you eval against. It is the single most valuable artifact in your agent project, and it grows continuously.

Where the cases come from, in order:

1. **Things that broke.** Every bug becomes an eval case. This is the cheapest way to build a suite that actually reflects reality.
2. **Edge cases you can think of.** The five-word user message. The unusual unicode. The contradictory follow-up. The empty input.
3. **Real production traffic, sampled and labeled.** Once you have logs (Chapter 22), sample 50–200 turns per week, hand-label them, and add the interesting ones. This is what keeps the suite from drifting out of sync with how users actually talk.
4. **Adversarial cases.** Prompt injection attempts, jailbreaks, attempts to get the agent off-topic. These are your security regressions.

Two rules:

- **Every case has an explicit expected behavior.** "The agent should X" or "the agent must NOT Y." A case without an expectation is not an eval, it's a vibe check.
- **Cases live in version control next to the prompts.** The eval suite, the prompts, and the tool definitions are one logical unit; they should change together.

Aim for 30 cases before you ship the first version, 100 before you trust the suite, and growing forever after that.

## Grading: the three options

Once you've run the agent against a case, how do you know if it passed?

**Exact / structural match.** "The response contains the string `confirmed`." "The agent called the `send_email` tool with `to=alice@example.com`." Cheap, deterministic, brittle. Use it wherever you can — exact match has no calibration problems and costs nothing to run.

**Heuristic checks.** Regexes, length bounds, "must contain at least one of these N phrases," "must not mention any of these forbidden topics." Still deterministic, still cheap, more flexible than exact match. Most real-world rules can be expressed this way.

**LLM-as-judge.** A second model reads the output and grades it against a rubric. This is the only thing that scales to subjective qualities ("is the response polite?") but it has real pitfalls:

- **Self-preference.** A model judging its own output rates it higher than it should. Use a *different* model family from the one being evaluated.
- **Position bias.** When comparing two outputs, judges prefer whichever one came first (or sometimes second). Randomize order.
- **Verbosity bias.** Judges reward longer, more confident answers regardless of correctness. Add explicit rubric points that penalize unwarranted length.
- **Calibration drift.** "Is this response good?" is not a stable question. Use rubric-based grading ("does the response contain the user's first name? +1; does it confirm the action taken? +1; does it stay under 80 words? +1") so individual checks are concrete and aggregable.

Use exact/heuristic checks for everything you can. Reach for LLM-as-judge only when no cheaper grader works, and always with a rubric, never with "is this good?"

## An eval case in code

The shapes vary by tooling, but a runnable starter is small. A YAML file holds cases:

```yaml
- name: "appliances inventory should not invent unrelated facts"
  input: "appliances include dishwasher, fridge, microwave, oven, all from 2017"
  context_memory:
    - "Dishwasher is currently leaking water"  # known prior memory, NOT in this turn
  expect:
    intent: CAPTURE
    tool_calls_min: 4
    response_must_not_contain: ["leak", "leaking"]

- name: "complete activity must use a real UUID"
  input: "I finished cleaning the gutters"
  expect:
    tool_called: complete_activity
    tool_args_match:
      activity_id: "^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
```

A small Python loop runs them:

```python
import asyncio, yaml, re

async def run_eval(cases_file: str) -> bool:
    with open(cases_file) as f:
        cases = yaml.safe_load(f)

    passed = failed = 0
    for case in cases:
        result = await run_agent(
            message=case["input"],
            context_memory=case.get("context_memory", []),
        )
        ok = True
        expect = case["expect"]

        # Exact / heuristic graders — cheap, deterministic
        for forbidden in expect.get("response_must_not_contain", []):
            if forbidden.lower() in result.text.lower():
                print(f"FAIL [{case['name']}]: response contained '{forbidden}'")
                ok = False

        if "intent" in expect and result.intent != expect["intent"]:
            print(f"FAIL [{case['name']}]: intent {result.intent} != {expect['intent']}")
            ok = False

        if "tool_calls_min" in expect and len(result.tool_calls) < expect["tool_calls_min"]:
            print(f"FAIL [{case['name']}]: only {len(result.tool_calls)} tool calls")
            ok = False

        if "tool_args_match" in expect:
            for tc in result.tool_calls:
                for arg, pattern in expect["tool_args_match"].items():
                    if arg in tc.args and not re.match(pattern, str(tc.args[arg])):
                        print(f"FAIL [{case['name']}]: {arg}={tc.args[arg]} did not match {pattern}")
                        ok = False

        passed += int(ok)
        failed += int(not ok)

    print(f"\n{passed} passed, {failed} failed")
    return failed == 0

if __name__ == "__main__":
    asyncio.run(run_eval("evals/cases.yaml"))
```

Two things to notice:

- **Every grader here is deterministic** — exact match, regex, count, set membership. No LLM-as-judge yet. This is exactly what the *fast* eval suite needs: cheap, fast, parseable, runnable on every PR.
- **The YAML file is the canonical golden set.** Version it next to your prompts and tools. When a bug comes in, the fix is "add a case to this file" — the file *is* the suite.

LLM-as-judge graders fit the same shape: call an LLM with a rubric inside the loop and add its score to the pass/fail logic. Promote a check to LLM-as-judge only when no deterministic grader covers what you're trying to test.

## Two speeds of eval

Not all evals run at the same time:

**Fast evals** run on every PR. Small (20–50 cases), fast (under 2 minutes total), exact/heuristic graders only. Their job is to fail loudly when an obvious thing breaks. Anyone changing a prompt can run them in seconds.

**Full evals** run nightly or pre-deploy. Larger (hundreds or thousands of cases), slower, may include LLM-as-judge graders, may run against multiple models for comparison. Their job is to catch the subtle stuff and produce the dashboard you look at when deciding whether to ship.

Don't try to make the full suite run on every commit — it's too slow and people will start skipping it. Don't try to make the fast suite cover everything — it'll bloat and stop being fast. Two suites, two purposes.

## Regression discipline

Once the suite exists, the discipline is simple but easy to abandon:

1. **Run it before any prompt or model change.** Capture a baseline.
2. **Run it after the change.** Compare.
3. **Investigate every regression.** Even a 2% drop is information — either the new version is genuinely worse on those cases, or the cases were wrong and need updating. Both outcomes are productive; ignoring it is not.
4. **Promote investigated regressions back into the suite.** When you find the case where the new prompt failed, that case is now part of the permanent suite.

The single biggest reason eval suites die is people ignoring small regressions because they're "probably noise." They are sometimes noise, but the discipline of investigating every one is what keeps the signal honest.

## Where evals plug into the rest of the system

- **Observability (Chapter 22)** is where you get production traffic to label and add to the suite.
- **Reliability (Chapter 19)** failures often need eval cases too — "if the database is unreachable, the agent should apologize, not crash."
- **Guardrails & security (Chapter 20)** have their own adversarial eval set that should run on every change.
- **Shipping checklist (Chapter 27)** treats "does the eval suite pass?" as a deploy gate. If you don't have a suite, you don't have a gate.

## Heuristic

> **Every bug becomes an eval case. Every prompt change runs the suite. Every regression gets investigated, not dismissed. That's the loop. Skip any one step and the suite stops being useful within a month.**

## Key takeaway

Evals are the difference between an agent you can change with confidence and one you're afraid to touch. Start with 30 final-answer cases and exact-match graders, run them on every prompt change, add a case for every bug, and grow the suite forever. Reach for trajectory evals and LLM-as-judge only when simpler graders run out — and when you do, treat their pitfalls (self-preference, position bias, verbosity bias, calibration drift) as engineering problems, not "AI weirdness." This is the most leveraged investment you can make in agent quality.

[← Previous](./22-observability.md) · [Index](./README.md) · [Next: Anti-patterns →](./24-anti-patterns.md)
