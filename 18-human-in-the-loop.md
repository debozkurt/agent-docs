# Chapter 18 — Human-in-the-Loop

[← Previous](./17-streaming.md) · [Index](./README.md) · [Next →](./19-reliability.md)

## The concept

So far the agent loop in this guide runs to completion: model decides, tools fire, model writes a final response, done. For a lot of capabilities that's the wrong shape. Some actions are too consequential for the agent to take alone — sending a contract, paying an invoice, deleting a customer, merging a PR. For those, the agent should **pause**, present its plan, and wait for a human to approve, edit, or reject it. That pattern is **human-in-the-loop** (HITL), and it's a first-class concept in every modern agent framework[^hitl].

HITL isn't only a safety feature. It's also how you let humans **steer** the agent mid-execution: "actually, use the staging database, not prod" or "skip the third item in your plan." Without HITL the only steering mechanism is a new turn from scratch, which loses all the agent's working state.

## Three patterns

**Pre-tool-call interrupt (approval gate).** Before executing a sensitive tool, the agent surfaces the call (`send_email`, args=`{...}`) to a human and waits for approve/deny/edit. The classic shape and the right default for destructive operations.

**Post-tool-call review.** The tool runs, returns its result, and the agent surfaces both the call *and* the result for review before continuing. Useful when the side effect is reversible but expensive (e.g. provisioning infrastructure), or when the human wants to verify something landed correctly before letting the agent proceed.

**Mid-stream cancel.** The agent is streaming a long response or running a long tool; the user clicks "stop." The harness aborts the in-flight call and either discards the partial state or hands it to the model with a `user_cancelled` note so the next turn can pick up sensibly.

These compose. A complex agent might have an approval gate on `send_email`, a review checkpoint after `provision_database`, and a cancel button on every turn.

## What it actually requires

HITL has one hard architectural prerequisite: **the agent's state must be durable across the pause**. If the user takes ten minutes to approve, your process can't be holding the entire run in memory and dying at the next deploy. This is exactly the problem [Chapter 12 (state recovery)](./12-state-recovery.md) solves: a checkpointer persists the agent's state at every step, and the run can be resumed by a different process at a later time. **HITL is built on top of checkpointing.** If you want approval gates, build a checkpointer first.

The industry term for this property is **durable execution** — the run survives process restarts, deploys, and long pauses because every step is persisted. LangGraph's checkpointer is one implementation; Temporal, Inngest, and Restate are the heavy-duty options teams reach for when the durability requirements go beyond "survive a deploy" (think: hours-to-days-long workflows, strict exactly-once semantics). You don't need Temporal for a chat approval gate, but it's worth knowing the word — when someone says "we put the agent on a durable execution engine," this is what they mean.

The other piece is an **interrupt API** in your agent loop. Both LangGraph and the OpenAI Agents SDK expose this directly: a node can call `interrupt(payload)`, which suspends execution and returns control to the caller with the payload. The caller (your application) presents the payload to a human, collects a response, and resumes the graph with that response as the interrupt's "return value." From the agent's perspective, `interrupt()` is a function that takes minutes to return.

```python
# LangGraph sketch — pre-tool-call approval gate
from langgraph.types import interrupt

def approve_send_email(state):
    decision = interrupt({
        "kind": "approval_required",
        "tool": "send_email",
        "args": state["pending_tool_call"]["args"],
        "preview": state["pending_tool_call"]["args"]["body"][:500],
    })
    if decision["action"] == "approve":
        return {"approved": True}
    if decision["action"] == "edit":
        return {"approved": True, "args_override": decision["args"]}
    return {"approved": False, "reason": decision.get("reason", "rejected")}
```

The application listens for interrupts of `kind=approval_required`, renders a UI, and resumes the graph with whatever the user clicks.

## Designing the approval surface

The hard part of HITL is rarely the wiring — it's deciding **what to show the human**. Three rules learned the hard way:

1. **Show the action, not the reasoning.** Humans approving an email don't want to read the agent's chain of thought. They want the recipient, the subject, the body, and two buttons. Bury the trace one click away.
2. **Show the diff for edits.** If the human can edit before approving, show what changed from the agent's draft. People will skim and miss subtle edits otherwise.
3. **Default to reject on timeout.** If an approval sits for an hour, expire it. A "yes" that arrives after the user's context is gone is not a real "yes."

## Which actions should require approval

This is the same question as the decision framework "Should the agent be allowed to do this without confirmation?" in [Chapter 25](./25-decision-frameworks.md). The short version:

| | Approve first | Direct |
|---|---|---|
| **Reversibility** | Hard to undo | Easy to undo |
| **Blast radius** | Affects others / charges money / sends external messages | Local, visible to user |
| **Frequency** | Rare | Routine |
| **Cost of false approval** | High | Low |

Don't gate everything — approval fatigue is real, and a user who reflexively clicks "approve" is providing zero safety. Gate the few actions whose worst-case is genuinely bad and let everything else through.

## Heuristic

> **Add an approval gate the first time you imagine a story that starts with "the agent did X and we couldn't undo it." Don't add gates speculatively — they cost user trust as well as latency.**

## Key takeaway

HITL is durable interrupts plus a thoughtful approval UI, sitting on top of a checkpointer. Use it for the small set of actions whose worst case is genuinely bad. Build the checkpointer first; it's the foundation that makes everything else possible.

[^hitl]: [LangGraph Human-in-the-Loop](https://langchain-ai.github.io/langgraph/concepts/human_in_the_loop/) · [OpenAI Agents SDK Guardrails & Handoffs](https://openai.github.io/openai-agents-python/) · [Claude Agent SDK](https://platform.claude.com/docs/en/agent-sdk/overview).

[← Previous](./17-streaming.md) · [Index](./README.md) · [Next: Reliability →](./19-reliability.md)
