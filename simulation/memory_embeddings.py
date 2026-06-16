"""
Semantic memory — embedding cache and similarity search (Gemini, optional).
"""

import json
import logging
import math
import os
import sys
import time

log = logging.getLogger(__name__)

EMBED_MODEL = os.environ.get("GEMINI_EMBED_MODEL", "gemini-embedding-001")
MAX_VECTORS = 120
EMBED_DIM_HINT = 768
_embed_disabled_reason = None


def semantic_memory_enabled():
    if _embed_disabled_reason:
        return False
    if os.environ.get("AISTORY_SKIP_SEMANTIC_MEMORY", "").lower() in ("1", "true", "yes"):
        return False
    from simulation.gemini_client import api_key
    return bool(api_key())


def llm_journal_summary_enabled():
    if os.environ.get("AISTORY_SKIP_LLM_JOURNAL_SUMMARY", "").lower() in ("1", "true", "yes"):
        return False
    from simulation.gemini_client import api_key
    return bool(api_key())


def cosine_similarity(a, b):
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def embed_text(text):
    """Return embedding vector or None if unavailable."""
    global _embed_disabled_reason
    if not text or not semantic_memory_enabled():
        return None
    try:
        from google import genai
        from google.genai import types
        from simulation.gemini_client import require_api_key

        client = genai.Client(api_key=require_api_key())
        result = client.models.embed_content(
            model=EMBED_MODEL,
            contents=str(text)[:8000],
            config=types.EmbedContentConfig(
                output_dimensionality=EMBED_DIM_HINT,
                task_type="RETRIEVAL_DOCUMENT",
            ),
        )
        emb = result.embeddings
        if emb:
            values = getattr(emb[0], "values", None) or emb[0].get("values")
            if values:
                return list(values)
        # alternate response shape
        if hasattr(result, "embedding") and result.embedding:
            return list(result.embedding.values)
    except Exception as e:
        msg = str(e)
        if "404" in msg or "NOT_FOUND" in msg:
            _embed_disabled_reason = msg
            log.warning(
                "Semantic memory disabled for this session (embedding model %s): %s",
                EMBED_MODEL,
                msg,
            )
        else:
            log.warning("Embedding failed: %s", e)
    return None


def _vector_store(player):
    return player.setdefault("memory_vectors", {})


def store_vector(player, key, text, *, meta=None):
    """Cache embedding under key; evict oldest when over cap."""
    vec = embed_text(text)
    if not vec:
        return None
    store = _vector_store(player)
    store[key] = {
        "vector": vec,
        "text": str(text)[:500],
        "meta": meta or {},
    }
    if len(store) > MAX_VECTORS:
        oldest = next(iter(store))
        del store[oldest]
    return vec


def get_vector(player, key):
    rec = _vector_store(player).get(key)
    return rec.get("vector") if rec else None


def rank_by_embedding(query, candidates, player, *, limit=5):
    """
    candidates: list of dicts with keys id, text, score (base keyword score)
    Returns candidates sorted by hybrid score.
    """
    if not semantic_memory_enabled() or not candidates:
        return sorted(candidates, key=lambda c: c.get("score", 0), reverse=True)[:limit]

    qvec = embed_text(query)
    if not qvec:
        return sorted(candidates, key=lambda c: c.get("score", 0), reverse=True)[:limit]

    store = _vector_store(player)
    for c in candidates:
        cid = c.get("id")
        vec = c.get("vector")
        if vec is None and cid:
            vec = (store.get(cid) or {}).get("vector")
        if vec is None and cid and c.get("text"):
            vec = store_vector(player, cid, c["text"], meta={"kind": c.get("kind")})
        sim = cosine_similarity(qvec, vec) if vec else 0.0
        c["semantic_score"] = sim
        c["score"] = c.get("score", 0) + sim * 100

    ranked = sorted(candidates, key=lambda c: c.get("score", 0), reverse=True)
    return ranked[:limit]
