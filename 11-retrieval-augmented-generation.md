# Chapter 11 — Retrieval-Augmented Generation (RAG) for Agents

[← Previous](./10-long-term-memory.md) · [Index](./README.md) · [Next →](./12-state-recovery.md)

## The concept

Chapter 10 covered **long-term memory**: things the *agent* remembers about the *user* and the *world*. RAG is its sibling, and the distinction matters: **RAG is about giving the agent access to a body of knowledge that already exists outside the conversation** — your product docs, your codebase, last quarter's incident reports, the IRS tax code. The agent didn't write it, the user didn't say it, but the agent needs to ground its answers in it.

The two patterns share machinery (embeddings, vector indexes, retrieval) but solve different problems and fail in different ways. Confusing them is a common architectural mistake.

| | Long-term memory (Ch 10) | RAG |
|---|---|---|
| **Source** | Things said in past conversations | A pre-existing knowledge corpus |
| **Writer** | The agent (it stores observations) | A separate ingestion pipeline |
| **Granularity** | Facts, preferences, events | Documents, sections, code |
| **Update rate** | Continuous, per turn | Periodic, batch |
| **Failure mode** | Stale/contradictory facts | Wrong chunk retrieved, hallucinated citation |

## The pipeline

A minimal RAG pipeline has four stages. Each one is where things go wrong, so each is worth understanding independently.

**1. Chunking.** Split documents into pieces small enough to fit in context but large enough to be self-contained. Naive fixed-size chunking (e.g. 500 tokens) is the easiest mistake — it cuts sentences in half and strips headers from the body they describe. Better: split on semantic boundaries (sections, paragraphs, function definitions), and include a small overlap between chunks so an answer near a boundary isn't lost.

**2. Embedding.** Each chunk is encoded into a vector by an embedding model. Embeddings are not interchangeable across model families — pick one (e.g. `text-embedding-3-large`, `voyage-3`) and stick with it; switching means re-embedding the entire corpus.

**3. Retrieval.** At query time, embed the user's question and find the *k* nearest chunks in the index. This is the step everyone thinks of when they hear "RAG," and it's also the weakest link.

**4. Generation.** Pass the retrieved chunks to the model alongside the user's question, with an instruction to answer *only* from the provided context.

## Why naive RAG underperforms

The honest version: stage 3 retrieval is much harder than the tutorials suggest. Three failure modes you should know by name:

- **Vocabulary mismatch.** The user asks about "logging in," the doc says "authentication." Pure vector search may miss it; the embedding captures *some* synonymy but not all. **Hybrid search** (combine vector similarity with keyword/BM25 search) usually outperforms either alone.
- **Wrong-granularity matches.** The top-k chunks are *similar* to the question but not *useful* for answering it (e.g. they describe the feature without containing the steps). **Rerankers** — a second-stage model that scores `(query, chunk)` pairs directly — fix this. Retrieve 20 with vector search, rerank to top 5, pass those to the generator.
- **Bad query formulation.** The user's question is conversational ("yeah but what about the other thing?"). Embedding it directly retrieves nothing useful. **Query rewriting** — a small LLM call that turns the conversational question into a standalone search query, optionally using the message history — is a cheap fix that's usually worth its cost.

A common stack: **chunk semantically → embed → hybrid search → rerank → pass top-k to generator**. Each stage adds latency and cost; add them in order and stop when your eval scores plateau.

## Why hybrid search works

"Use hybrid search" is so common as a recommendation that it's almost a slogan, but the *why* is worth understanding because it tells you when it'll help and when it won't. The short version is that embedding search and lexical (keyword) search fail in different, complementary ways — and combining them covers both gaps.

**Embeddings excel at semantic matching.** "How do I log in?" and "authentication procedure" land near each other in vector space even with zero word overlap. This is the magic, and it's why pure keyword search misses paraphrases, synonyms, and conceptually related content.

**Embeddings struggle with literal-token matching.** Specifically:

- **Rare proper nouns and identifiers.** `acme-prod-eu-1`, `CVE-2024-3094`, the name of an obscure library. Embedding models normalize and generalize; they're bad at "match this exact string."
- **Code symbols and error codes.** `getUserById`, `ECONNREFUSED`, `0x80004005`. The model's training corpus didn't teach it that these mean specific things.
- **Numbers and exact quantities.** "the 95th percentile" vs "the 99th percentile" embed almost identically; lexical search distinguishes them instantly.
- **Negation.** "without authentication" and "with authentication" are dangerously close in vector space.

**Lexical search (BM25 is the classical scoring function) is the inverse.** It nails exact tokens, identifiers, codes, and rare terms — but completely misses paraphrases. Search for "how do I log in?" against a doc that says "authentication procedure" and BM25 returns nothing.

The hybrid combines them — typically by running both, normalizing the scores, and merging (Reciprocal Rank Fusion is the most common merging algorithm). Where one fails, the other usually catches it. In domains heavy on identifiers or codes (developer docs, security advisories, anything with SKUs or part numbers) the lexical half does most of the work; in conversational content it's the embedding half. Most real corpora are both, which is why hybrid wins.

**When hybrid is *not* worth the complexity.** Small corpora where embedding alone works fine, content that's purely natural language with no identifiers or codes, or domains where you've measured that BM25 doesn't move your eval scores. Like every optimization in this guide, measure before you adopt.

## Two architectural choices

**Retrieval as preprocessing** (the classic RAG shape). Before the agent runs, retrieve top-k chunks for the user's message and inject them into the prompt. Simple, predictable, one extra round trip. Good when every turn needs the same kind of grounding.

**Retrieval as a tool the agent calls.** Expose a `search_docs(query)` tool. The agent decides whether and how to query, and can refine its query based on what it finds. More flexible, more expensive, occasionally surprising (the agent may not call the tool when it should). Good when only some turns need RAG, or when multi-step research is the point.

You can combine them: preprocess for the obvious case, expose a tool for follow-up depth.

## When *not* to use RAG

- **Tiny corpora** (< 50 documents) — just put them all in the system prompt. Cheaper, simpler, no retrieval errors.
- **Highly structured data** — if it lives in a database, query the database with a tool. Don't embed your customers table.
- **Anything requiring exact recall of long passages** — RAG is lossy. Use a tool that fetches the canonical document by ID.
- **Frequently changing facts where freshness matters more than depth** — go through an API, not an index.

## Citing sources (and how it lies to you)

If your RAG agent is user-facing, you almost certainly want it to cite the chunks it used. Two warnings:

- **Models will fabricate citations.** Even when handed the chunks, a model may invent a plausible-looking source. Validate that every cited chunk ID actually appears in the retrieved set, and strip or flag any that don't.
- **Cited ≠ used.** A model will sometimes cite a chunk it didn't actually rely on, or rely on a chunk it didn't cite. Citations are a signal, not a proof of grounding. Pair them with eval cases that check answer correctness independently.

## Heuristic

> **RAG quality is mostly retrieval quality. Spend your optimization budget on chunking, hybrid search, rerankers, and query rewriting before you touch the generator prompt.**

## Key takeaway

RAG and long-term memory share parts but solve different problems: memory captures what the conversation produces, RAG grounds the conversation in what already exists. Treat retrieval as the hard part — the generation step is mostly fine if it's given the right chunks. And know when not to reach for RAG at all; for small or structured data, simpler tools beat it.

[← Previous](./10-long-term-memory.md) · [Index](./README.md) · [Next: State recovery →](./12-state-recovery.md)
