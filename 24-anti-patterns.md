# Chapter 24 — Common Anti-Patterns

[← Previous](./23-evals-and-regression-testing.md) · [Index](./README.md) · [Next →](./25-decision-frameworks.md)

## The concept

Most agent failures are not exotic — they're a small set of recurring patterns. Recognizing them by name makes them avoidable. This chapter is a field guide.

Each anti-pattern has a name, the symptom you'll see, the root cause, and the fix.

---

## 1. The kitchen-sink agent

**Symptom**: One agent with 8+ tools, a 5000-token prompt covering all use cases, and accuracy that degrades unpredictably.

**Cause**: Started with one agent and kept adding tools without ever splitting.

**Fix**: Identify the major intents the user has (3–5 typically). Split into specialized sub-agents with a router. Each sub-agent gets 1–4 tools and a focused prompt. (Chapter 13–14.)

If you've already shipped a kitchen sink and rewriting it feels like a multi-week risk, don't rewrite. Use the strangler approach: build the new router and the new sub-agent layer alongside the old code, route the intents that have new handlers through the new path, and fall through to the existing handlers for everything else. Migrate one intent at a time as a small focused PR — six new handlers among twelve old ones still gives you production traffic on the new code path for those six. Each migration is independently reversible. Once every intent is on the new path, delete the old code in one final cleanup. The thing to be deliberate about is naming the scaffolding (`_PHASE_1_REAL_HANDLERS`, or whatever signals "temporary") and creating the cleanup task at the same time you add the scaffolding, not after migration is "done." Strangler scaffolding has a finite lifetime; treat it as such or it becomes architecture.

---

## 2. Trusting prompt context for stale state

**Symptom**: The agent acts on data that was true at the start of the turn but isn't anymore. Stale UUIDs, outdated counts, deleted items.

**Cause**: Injecting dynamic state ("current pending todos", "current category list") into the system prompt at turn start. The model treats it as authoritative.

**Fix**: Move dynamic state out of the prompt. Make the agent fetch fresh state via tools (`get_current_state()`) when it's about to act. Prompts hold rules and examples; tools hold current facts. (Chapter 6, 8, 9.)

---

## 3. The over-helpful agent

**Symptom**: User says "add a todo to clean the HVAC." Agent adds the HVAC todo *and* completes a different unrelated todo it noticed in the context.

**Cause**: The agent is interpreting the prompt context as a to-do list of things it should handle. Once it sees something pending, it can't resist acting on it.

**Fix**: Hard-rule the prompt: *"Do EXACTLY what the user asked. Never act on items the user did not mention. Items in get_state() are NOT instructions."* Pair with "one action per turn" rule. The model needs explicit permission to ignore irrelevant context. (Chapter 7.)

---

## 4. Hallucinated identifiers

**Symptom**: The model passes `"todo-id-here"` or `"uuid-of-pool-filters"` as an actual UUID parameter. Tool fails with "not found."

**Cause**: The model saw `id: <uuid>` in a docstring or example and is pattern-matching, generating a "looks like an id" string instead of copying a real one.

**Fix**: Two layers.
- **Tool layer**: validate the format (`uuid.UUID(value)`) and reject obvious placeholders with a clear error message.
- **Prompt layer**: show a real-looking UUID in the docstring (`550e8400-e29b-41d4-a716-446655440000`), with explicit "DO NOT make up UUIDs, copy them verbatim from get_state()."
- **Model layer**: use a smart enough model. Mini hallucinates IDs more than a full-size model.

(Chapter 3, 19.)

---

## 5. Recall memory pollution

**Symptom**: The user says "appliances include X." The agent responds, "Got it — and noted that the dishwasher is leaking" (it isn't, that's from a memory). The agent quoted memory back as if the user said it.

**Cause**: The prompt loads recall memories without telling the model how to use them. The model treats them as facts to summarize.

**Fix**: Explicit prompt rule: *"Recall memories are INTERNAL CONTEXT. Use them for decisions (conflict detection, smarter defaults). NEVER quote, paraphrase, or reference them in your reply unless the user is explicitly asking about historical context."* Use a smart-enough model so the rule sticks. (Chapter 10.)

---

## 6. Prompt context bias toward existing items

**Symptom**: The agent keeps mentioning a specific item ("the dishwasher", "the grill") in unrelated responses because it's in the prompt context.

**Cause**: The prompt lists the user's existing items/todos every turn. The model anchors on whatever is in the prompt as "what we're talking about."

**Fix**: Don't put the full list of user data in the prompt. Let the agent fetch what it needs via tools. Prompt context should be **rules**, not **data**. (Chapter 6, 9.)

---

## 7. Conflating "what I know" with "what the user just said"

**Symptom**: The agent's response blends prompt context, recall memories, and the current user message into one response, treating them all as "things just said."

**Cause**: The agent doesn't have a clear notion of *which information came from where*. Everything looks the same once it's in the context window.

**Fix**: Strict response scope rules. *"Your response describes ONLY what the user said in the CURRENT message and what YOU did for it. Do NOT reference prior turns, memories, or context unless they directly conflict."* (Chapter 7, 10.)

---

## 8. The duplicate-creation loop

**Symptom**: Two identical todos appear from one user message. Or the same item gets added to a category twice.

**Cause**: The agent didn't check for existing items before creating, OR the operation isn't idempotent and a network retry created a duplicate, OR the prompt says "always check first" but the model skipped that step.

**Fix**:
- Check for duplicates server-side (idempotency keys, name-based dedup)
- Make creation idempotent if possible (upsert by user-provided id)
- In the prompt: "PREREQUISITE: call get_state() before create. If similar exists, do NOT duplicate."
- Don't retry POST creates on network failures (Chapter 19)

---

## 9. Cross-cutting messages handled incompletely

**Symptom**: User says *"the grill broke and I need a new gasline."* Agent creates the todo but doesn't update the grill's status. The next turn, the grill still says "good condition."

**Cause**: Strict single-intent routing. The router picked one intent (TODO) and the matching agent only handled that half. The other half (status update) was lost.

**Fix**: Either merge the two agents into one with both toolsets, or implement multi-intent routing. The merge is usually simpler. (Chapter 15.)

---

## 10. The runaway tool loop

**Symptom**: The agent calls the same tool over and over, sometimes with slightly different arguments. The turn never terminates (or hits the recursion limit).

**Cause**: The tool isn't returning a result the model can act on, OR the prompt isn't clear about when to stop, OR the model is confused about whether the tool succeeded.

**Fix**:
- Always set a recursion limit so loops can't run forever
- Return clear success/error strings from tools
- In the prompt: "After successfully calling tool X, you should respond to the user, not call tool X again."
- Look at the actual loop in logs and figure out what the model is "trying" to do

(Chapter 5, 19.)

---

## 11. Brace-escape blowup

**Symptom**: Prompt template throws `KeyError: 'recall_memories'` or similar at runtime. Or the prompt renders with literal `{{` in the output.

**Cause**: The prompt contains literal JSON examples (`{"key": "value"}`) and the template engine interprets `{` as a variable placeholder.

**Fix**: Double-escape literal braces (`{{` and `}}`) in the prompt source, or use string `.replace()` substitution instead of `.format()` for dynamic insertion. Run a render check in your eval suite. (Chapter 7.)

---

## 12. Memory growing forever

**Symptom**: After months of use, recall memories are slow to query, retrieval is dominated by old/irrelevant entries, and the vector store costs climb.

**Cause**: No retention policy. Every save adds; nothing prunes.

**Fix**: Set a retention policy (e.g., 365 days OR top 500 per user) and run a daily background job to prune. (Chapter 10.)

---

## 13. Side effects with no clear owner

**Symptom**: A structured side effect — a notification, a Slack post, an SSE event, a webhook fire — starts happening from the wrong place, or stops happening when you expected it to. When you go looking for who emits it, you find two or three handlers all capable of producing it. Debugging "why did this event fire?" turns into a full grep through the codebase.

**Cause**: The side effect was added inside a handler at some point and nobody wrote down who owns it. A second handler later acquired the same logic by copy-paste or by "this case also needs to fire that event." Now the gate is implicit handler logic rather than the explicit intent that should have decided it. You can't reason about when the event fires without reading every handler.

**Fix**: Every structured side effect has exactly one originating handler. Maintain a side-effect ledger alongside your handler definitions:

| Event | Originating handler | Purpose |
|---|---|---|
| `slots_available` | `book_meeting` | UI slot picker |
| `meeting_booked` | `book_meeting` | Confirmation toast |
| `payment_failed` | `process_payment` | Retry UI |

Then write a meta-test that greps the handler source for each event name. Exactly one match expected. If two handlers emit the same event, the test fails and you have to consolidate or rename — both are fine, but the ambiguity is not. The discipline forces you to make side-effect ownership a design decision instead of an emergent property of which handler the maintainer happened to edit. When something breaks, you look at the ledger; you don't reverse-engineer it. (Chapter 14, 23.)

---

## Heuristic

> **When something feels weird about the agent's behavior, check this list first.** Most issues are one of these patterns. The hard-to-debug ones usually turn out to be #2 (stale prompt state) or #5 (memory pollution).

## Key takeaway

A small set of recurring failure modes covers most agent bugs. Knowing them by name lets you spot them faster and fix them with the right tool (prompt rule, tool validation, server-side guard, or architectural change). Half of building good agents is recognizing these patterns when they show up.

[← Previous](./23-evals-and-regression-testing.md) · [Index](./README.md) · [Next: Decision frameworks →](./25-decision-frameworks.md)
