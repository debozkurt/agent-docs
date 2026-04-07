# Chapter 8 — Three Kinds of State

[← Previous](./07-prompts-as-code.md) · [Index](./README.md) · [Next →](./09-context-and-cache-engineering.md)

## The concept

"State" in agent systems is overloaded. There are actually **three different kinds**, with different lifecycles, storage, and use cases. Conflating them is the source of most state-related bugs.

| | Lifetime | Where it lives | Used for |
|---|---|---|---|
| **Conversation state** | One turn | Messages list | Tool calls + intermediate results within the current request |
| **Session state** | One thread/session | Persistent store keyed by session_id | Multi-turn context: prior messages, prior tool results |
| **Long-term memory** | Across sessions, possibly forever | Vector store, structured DB | Things the agent should know about the user across all conversations |

## Conversation state — within one turn

This is the message list as it exists *during a single user request*. The user said something, the agent thought, called tools, got results, called more tools, eventually responded. All those messages are conversation state.

Conversation state is usually thrown away after the turn (unless you persist for resumability — Chapter 12). The next turn starts fresh from session state.

**Lives in**: a Python list during the turn, possibly checkpointed mid-turn.

## Session state — within one conversation thread

The user has been chatting for 20 messages. Session state is "all the prior messages and any side data needed to continue that conversation."

Session state typically lives in a database keyed by `session_id` or `thread_id`. You load it at the start of every turn, append the new user message + agent response, save it back.

What goes in session state:
- The full message history (often trimmed for the model's context window)
- The user's identity (`user_id`)
- Any per-session preferences ("user prefers concise responses")
- Pending state ("waiting for user to confirm a destructive action")

What does NOT go in session state:
- Things that should persist across sessions → long-term memory
- Static rules → the system prompt
- Data you can re-fetch fresh → call a tool when you need it

**Lives in**: Postgres, Redis, or any persistent store. Loaded once per turn, saved at end of turn.

## Long-term memory — across all sessions

The user told the agent in March that they prefer Trane HVAC systems. In June, in a brand new session, the agent should remember that. Session state can't help — different session, different `thread_id`. You need long-term memory.

Long-term memory is typically a **vector store** (for semantic recall) or a **structured database** (for queryable facts). The agent saves things into it during conversations and retrieves relevant entries at the start of new ones.

This is the most powerful and most dangerous kind of state, because:
- The model can write to it freely (potential for noise)
- Retrieval is fuzzy (relevance threshold matters)
- Stale or wrong memories pollute future conversations

Chapter 10 covers this in depth.

## A worked example

User on March 1: *"My HVAC was serviced today, technician said the compressor has 5 more years."*

What gets stored where?

| State kind | What gets stored |
|---|---|
| **Conversation** (this turn) | The user message, the agent's thought process, the tool calls (e.g., `update_category(hvac, last_serviced=...)`, `save_memory("HVAC compressor: 5 years remaining per technician")`), the agent's reply |
| **Session** (this conversation) | The messages above persist if the user keeps chatting in the same thread |
| **Long-term memory** | "HVAC compressor: 5 years remaining (technician estimate, March 2026)" — stored in vector store |
| **Structured DB** (not "state" per se but related) | The category record gets `last_serviced=2026-03-01` and `next_service_due=2026-09-01` |

Three months later, in a brand new session, the user asks: *"Should I worry about my HVAC?"*

The new turn loads:
- Session state: empty (new session)
- Long-term memory: the agent searches "HVAC condition" and pulls the March memory
- Structured DB: the agent calls `get_category(hvac)` and sees the service history

Now the agent can answer with concrete context, even though the conversation history is empty.

## The biggest mistake

Putting **session state in the system prompt**. It feels efficient — "the agent already knows the user's preferences without a tool call!" — but the prompt is a snapshot at turn start. Anything in there becomes stale immediately, and the model can't tell what's fresh vs stale.

**Rule**: the system prompt holds rules and role. State comes from tools or messages.

## Heuristic

> **For each piece of information ask: how long should it survive, and who should fetch it?** That answers which kind of state it belongs in.

## Key takeaway

Three kinds of state: conversation (one turn), session (one thread), long-term (across sessions). Each has its own storage and access pattern. Don't conflate them, and don't put dynamic state in the system prompt.

[← Previous](./07-prompts-as-code.md) · [Index](./README.md) · [Next: Context & cache engineering →](./09-context-and-cache-engineering.md)
