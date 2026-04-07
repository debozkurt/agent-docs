# Glossary

[← Index](./README.md)

A reference for terms used across the guide. Each entry is one or two sentences. Where useful, the relevant chapter is cited.

---

**Agent.** A program that uses an LLM in a loop, where the model is allowed to call tools and observe their results before deciding what to do next. Distinct from a *workflow* (a fixed sequence) and a *chatbot* (no tools, no loop). See Chapter 1.

**Agent harness.** The runtime that wraps the model loop, manages state, executes tools, handles streaming and interrupts, and exposes the agent to the outside world. Examples: LangGraph, OpenAI Agents SDK, Claude Agent SDK, Claude Code itself. See Chapter 29.

**ANN (Approximate Nearest Neighbor).** A class of indexing algorithms (HNSW, IVF, ScaNN) that find *probably-nearest* vectors to a query much faster than exact search by giving up a small amount of recall in exchange for orders of magnitude in speed. What makes vector search at scale feasible at all. See Chapter 10.

**Approval gate.** A pre-tool-call interrupt that pauses the agent and asks a human to approve, edit, or reject a sensitive action before it executes. See Chapter 18.

**Backoff (exponential).** A retry strategy in which the wait between attempts roughly doubles each time (200ms, 400ms, 800ms…), used to avoid hammering a struggling downstream service. See Chapter 19.

**BM25.** A classical lexical / keyword scoring function that ranks documents by how well their literal tokens match the query, with weighting for term rarity and document length. Complements embedding search because it nails exact identifiers, codes, and rare terms where embeddings struggle — the lexical half of *hybrid search*. See Chapter 11.

**Cache prefix.** The portion of a prompt that exactly matches a recent prior call, byte-for-byte, and so qualifies for prompt caching. A single token of difference invalidates everything after the divergence point. See Chapter 9.

**Channel routing.** Dispatching incoming messages by *where they came from* (Slack, email, web) and normalizing them into a common shape, as opposed to *intent routing* (which dispatches by what the user wants). See Chapter 14.

**Checkpointer.** A durable store that persists agent state at every step of the loop, so a run can be paused, resumed, or recovered after a crash. The prerequisite for human-in-the-loop and long-running agents. See Chapter 12.

**Chunking.** Splitting documents into smaller pieces (paragraphs, sections, fixed token windows) before embedding them for retrieval. The quality of the chunking strategy is one of the largest single factors in RAG quality. See Chapter 11.

**Compaction.** Shrinking the message history when it approaches the context window's limit, either by sliding-window truncation or by summarization. See Chapter 9.

**Context engineering.** The discipline of choosing what goes into the model's context window, in what order, and with what stability — the modern superset of "prompt engineering." See Chapter 9.

**Context window.** The maximum number of tokens (system prompt + tools + history + current input) the model can attend to in a single call. Different models have different limits.

**Conversation state.** The intermediate scratchpad of a single turn — the messages, tool calls, and tool results that accumulate while the loop runs and are usually discarded after. See Chapter 8.

**Cosine similarity.** A distance metric that measures the angle between two vectors, ignoring magnitude. Returns a value in [-1, 1]; higher means more similar. The default for text-embedding workflows; for L2-normalized vectors it is mathematically equivalent to dot product. See Chapter 10.

**Direct prompt injection.** An attack in which a user's own message tries to override the system prompt or extract secrets. The "ignore previous instructions" family. See Chapter 20.

**Distance metric.** The function used to compare two vectors during similarity search — commonly cosine similarity, dot product, or L2 (Euclidean) distance. The choice has to match the embedding model's expectations and the index configuration; mismatches silently degrade retrieval quality without erroring. See Chapter 10.

**Embedding.** A numerical vector representing the semantic content of a piece of text, produced by a learned embedding model that maps text into a fixed-dimensional space where similar meanings land near each other. Used for similarity search in vector stores. See Chapters 10 and 11.

**Embedding dimension.** The fixed size of the vector an embedding model produces (e.g. 384, 768, 1536, 3072). Larger vectors can capture more nuance but cost more to store, search, and compute over. Some modern embedding models support dimension truncation, letting you trade quality for cost without re-embedding. See Chapter 10.

**Eval.** A test case for an agent: a fixed input plus an expected behavior or output, run against the agent so regressions can be detected. See Chapter 23.

**Final-answer eval.** An eval that checks only the agent's output, not the path it took to get there. Cheap, easy, catches most regressions. See Chapter 23.

**Golden set.** The curated, version-controlled collection of eval cases against which the agent is tested on every change. See Chapter 23.

**Grammar-constrained sampling.** A generation mode in which the model is forced to produce output that conforms to a given schema (e.g. JSON Schema). What "strict" tool use is built on. See Chapter 3.

**Guardrail.** An independent check — usually a small classifier or rule — that runs on inputs, outputs, or tool calls and blocks or rewrites anything that violates policy. See Chapter 20.

**Handoff.** A multi-agent pattern in which one agent transfers control of the conversation to another, usually with shared state. Distinct from a tool call (which returns) or a worker spawn (which runs in parallel). See Chapter 14.

**HITL (human-in-the-loop).** Any pattern that pauses the agent to let a human approve, edit, or reject something before continuing. Built on a checkpointer and an interrupt API. See Chapter 18.

**HNSW (Hierarchical Navigable Small World).** The dominant ANN index algorithm in production vector databases. Builds a multi-layer graph of vectors and walks it to find approximate nearest neighbors quickly. Has a tunable recall-vs-latency knob (`ef_search`) — when retrieval quality is mysteriously bad, this is sometimes the cause. See Chapter 10.

**Idempotency.** The property that calling an operation twice with the same arguments produces the same result as calling it once. The prerequisite for safe retry. See Chapters 3 and 19.

**Idempotency key.** A unique ID a caller passes with a non-idempotent request so the server can dedupe duplicates and make the operation safely retryable. See Chapter 19.

**Indirect prompt injection.** An attack in which an attacker hides instructions inside a document the user later asks the agent to read (an email, a webpage, a PDF). The most dangerous prompt-injection variant because the user is acting in good faith. See Chapter 20.

**Intent routing.** Dispatching a user message to one of several specialized agents based on what the user wants. Implemented as rules, embeddings, a small LLM classifier, or a supervisor agent. See Chapter 14.

**Interrupt.** A function in an agent harness that suspends execution, returns control to the caller with a payload, and resumes when the caller provides a response. The mechanism HITL is built on. See Chapter 18.

**L2 normalization.** Scaling a vector to unit length by dividing each component by the vector's Euclidean norm. Most modern embedding models return L2-normalized vectors by default; mixing normalized and un-normalized vectors in the same index silently degrades cosine search quality. See Chapter 10.

**LLM-as-judge.** Using a model to grade the output of another model against a rubric. The only practical way to grade subjective qualities at scale, but subject to self-preference, position bias, verbosity bias, and calibration drift. See Chapter 23.

**Long-term memory.** Information the agent retains across sessions about the user or the world, typically stored in a vector store and retrieved by similarity. Distinct from RAG (which serves a pre-existing knowledge corpus). See Chapter 10.

**Lost in the middle.** The empirical finding that LLMs recall information at the start and end of their context more reliably than information in the middle. Drives prompt-layout decisions. See Chapter 9.

**MCP (Model Context Protocol).** An open standard, introduced by Anthropic in late 2024, for how agents discover and call tools across process boundaries. Servers expose tools, resources, and prompts; clients (agents, IDEs, chat apps) consume them. See Chapter 4.

**Message list.** The ordered sequence of system / user / assistant / tool messages passed to the model on each call. The agent's working memory for one turn. See Chapter 6.

**Orchestrator-worker.** A multi-agent pattern in which a coordinating agent decomposes a task and dispatches sub-tasks to worker agents in parallel, then merges their results. See Chapters 13 and 29.

**PII (personally identifiable information).** Data that can identify an individual — names, emails, phone numbers, addresses, etc. Should be redacted before logs leave the agent process. See Chapter 20.

**Prompt cache.** A provider-side cache that bills repeated prompt prefixes at a fraction of the normal input rate (typically ~10%) and serves them with much lower latency. Sensitive to byte-for-byte prefix stability. See Chapter 9.

**RAG (retrieval-augmented generation).** Grounding an agent's responses in an external knowledge corpus by retrieving relevant chunks at query time and passing them to the model. Distinct from long-term memory. See Chapter 11.

**ReAct.** A loop pattern in which the model alternates between *reasoning* (planning what to do) and *acting* (calling a tool), feeding each tool result back into the next reasoning step. The default shape of a tool-using agent. See Chapter 5.

**Recursion limit.** A hard cap on how many iterations the agent loop can run before being aborted, used to catch runaway loops. See Chapter 19.

**Reranker.** A second-stage retrieval model that scores `(query, chunk)` pairs directly, used to refine the top-k results from a vector search before passing them to the generator. See Chapter 11.

**Resource (MCP).** Read-only data exposed by an MCP server that the model can pull into context — files, database snapshots, documentation. Distinct from a tool, which is callable. See Chapter 4.

**Router.** The component that decides which specialist agent (or which prompt branch) handles a given user message. May be a rule, an embedding lookup, a small LLM, or another agent. See Chapter 14.

**Self-preference (judge).** The bias in which an LLM-as-judge rates outputs from its own model family higher than outputs from other models. Mitigation: use a different model family as the judge. See Chapter 23.

**Session state.** Data that persists across turns of a single user session — user profile, recent context, in-progress task — but isn't part of the message list. Held in your application database. See Chapter 8.

**Strict mode.** A tool definition flag (Anthropic and OpenAI both support it) that uses grammar-constrained sampling to guarantee tool inputs match the JSON Schema exactly. Eliminates a category of validation work. See Chapter 3.

**Supervisor.** A multi-agent pattern in which a top-level agent inspects the user message, decides which specialist to invoke, and possibly orchestrates several specialists in sequence. Generalizes a router. See Chapter 14.

**System prompt.** The first message in the message list, used for stable rules, persona, and instructions. Usually placed at the start because it's cache-friendly and attended to most reliably. See Chapter 6.

**Tool.** A function exposed to the LLM that it can request the harness to call on its behalf. The agent's only way to affect the world or fetch fresh information. See Chapter 3.

**Tool-call guardrail.** A check that runs between the model's tool call and its execution, validating the arguments and the user's permission to perform the call. The last line of defense before the database. See Chapter 20.

**Trajectory eval.** An eval that checks the *sequence of tool calls* the agent took, not just the final answer. Catches cases where the answer was right but the route was wrong. See Chapter 23.

**Trust boundary.** The line between code or data you wrote (trusted) and content from elsewhere (untrusted). Crossing one — by reading user input, an external document, or a tool result — should trigger validation. See Chapter 20.

**Vector store.** A database optimized for nearest-neighbor search over embeddings. The substrate for both long-term memory and RAG. See Chapters 10 and 11.

[← Index](./README.md)
