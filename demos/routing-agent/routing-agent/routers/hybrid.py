# routers/hybrid.py
"""Embeddings-first, LLM-fallback. ~95% of messages get the fast path;
the ambiguous 5% get the LLM. Aggregates cost and latency across both."""
from __future__ import annotations

import numpy as np

from intents import DEFAULT_INTENT, INTENT_DESCRIPTIONS, INTENTS, Intent
from routers.embeddings import _embedder, _intent_vectors, _cosine, EMBED_MODEL
from routers.llm import _llm, ROUTER_PROMPT, MODEL as LLM_MODEL
from timing import cost_of, timer

HIGH_CONF = 0.40  # above this, trust the embedding match


async def route(message: str):
    with timer() as t:
        vec = np.array(await _embedder.aembed_query(message))
        scores = {n: _cosine(vec, iv) for n, iv in _intent_vectors.items()}
        best: Intent = max(scores, key=scores.get)

        approx_tokens = max(1, len(message.split()))
        cost = cost_of(EMBED_MODEL, approx_tokens, 0)

        details = {
            "embedding_scores": {k: round(float(v), 4) for k, v in scores.items()},
            "embedding_top_intent": best,
            "embedding_top_score": round(float(scores[best]), 4),
            "high_conf_threshold": HIGH_CONF,
            "fell_through_to_llm": False,
        }

        took_fast_path = scores[best] >= HIGH_CONF
        if took_fast_path:
            intent = best
        else:
            # Ambiguous — fall through to the LLM.
            details["fell_through_to_llm"] = True
            resp = await _llm.ainvoke([
                {"role": "system", "content": ROUTER_PROMPT},
                {"role": "user",   "content": message},
            ])
            raw_text = (resp.content or "").strip()
            tokens = raw_text.lower().split()
            label = tokens[0] if tokens else ""
            intent = label if label in INTENTS else DEFAULT_INTENT

            usage = (resp.response_metadata or {}).get("token_usage", {}) or {}
            pt = usage.get("prompt_tokens", 0)
            ct = usage.get("completion_tokens", 0)
            cost += cost_of(LLM_MODEL, pt, ct)

            details.update({
                "llm_model": LLM_MODEL,
                "llm_raw_response": raw_text,
                "llm_intent": intent,
                "llm_prompt_tokens": pt,
                "llm_completion_tokens": ct,
            })

    return intent, t.ms, cost, details
