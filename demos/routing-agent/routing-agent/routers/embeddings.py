# routers/embeddings.py
"""Semantic router. Embeds each intent description at startup, then picks the
highest cosine similarity against the user message. Underrated pattern."""
from __future__ import annotations

import numpy as np
from langchain_openai import OpenAIEmbeddings

from intents import DEFAULT_INTENT, INTENT_DESCRIPTIONS, Intent
from timing import cost_of, timer

EMBED_MODEL = "text-embedding-3-small"
_embedder = OpenAIEmbeddings(model=EMBED_MODEL)

# Approximate tokens per intent description — just for cost reporting.
# Embeddings charge per input token; one-time at startup.
_intent_vectors: dict[Intent, np.ndarray] = {
    name: np.array(_embedder.embed_query(desc))
    for name, desc in INTENT_DESCRIPTIONS.items()
}

CONF_THRESHOLD = 0.30  # below this, fall back to the safe default


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


async def route(message: str):
    with timer() as t:
        vec = np.array(await _embedder.aembed_query(message))
        scores = {
            name: _cosine(vec, iv) for name, iv in _intent_vectors.items()
        }
        raw_best = max(scores, key=scores.get)
        below_threshold = scores[raw_best] < CONF_THRESHOLD
        best = DEFAULT_INTENT if below_threshold else raw_best
    approx_tokens = max(1, len(message.split()))
    details = {
        "scores": {k: round(float(v), 4) for k, v in scores.items()},
        "top_intent": raw_best,
        "top_score": round(float(scores[raw_best]), 4),
        "threshold": CONF_THRESHOLD,
        "below_threshold": below_threshold,
        "approx_input_tokens": approx_tokens,
        "model": EMBED_MODEL,
    }
    return best, t.ms, cost_of(EMBED_MODEL, approx_tokens, 0), details
