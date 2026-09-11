"""Embedding helper with L1/L2 cache scoped by data_source_id."""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence, Tuple

from app.core.config import settings
from app.core.constants import (
    EmbeddingCacheL1Size,
    EmbeddingCacheL2EvictBatch,
    EmbeddingCacheL2Size,
    EmbeddingDimensions,
)
from app.utils.hashing import sha256_text

_l1: Dict[Tuple[str, str], List[float]] = {}
_l1_lock = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash_embed(text: str, dim: int = EmbeddingDimensions) -> List[float]:
    """Deterministic fallback when no embedding provider is configured (tests)."""
    import hashlib
    import struct

    digest = hashlib.sha256((text or "").encode("utf-8")).digest()
    vals: List[float] = []
    seed = digest
    while len(vals) < dim:
        for i in range(0, len(seed) - 3, 4):
            n = struct.unpack_from(">i", seed, i)[0]
            vals.append((n / 2147483648.0))
            if len(vals) >= dim:
                break
        seed = hashlib.sha256(seed).digest()
    norm = sum(v * v for v in vals) ** 0.5 or 1.0
    return [v / norm for v in vals[:dim]]


def _live_embed(text: str) -> Optional[List[float]]:
    try:
        from app.services.embedding_factory import EmbeddingFactory
        from app.models.schemas import EmbeddingConfig

        config = EmbeddingConfig(
            provider=settings.EMBEDDING_PROVIDER,
            model=settings.EMBEDDING_MODEL,
            api_key=settings.EMBEDDING_API_KEY or settings.LLM_API_KEY,
            base_url=settings.EMBEDDING_BASE_URL,
        )
        client = EmbeddingFactory.create_client(config)
        return client.embed_query(text)
    except Exception:
        return None


def embed_text(text: str, provider, data_source_id: str, model: Optional[str] = None) -> List[float]:
    model_name = model or settings.EMBEDDING_MODEL
    text_hash = sha256_text(f"{model_name}|{text}")
    l1_key = (data_source_id, text_hash)
    with _l1_lock:
        cached = _l1.get(l1_key)
        if cached is not None:
            return cached

    row = None
    try:
        row = provider.fetch_one("embedding_cache", data_source_id, "text_hash", text_hash)
    except Exception:
        row = None
    if row and row.get("embedding_json"):
        vec = json.loads(row["embedding_json"])
        _store_l1(l1_key, vec)
        try:
            provider.upsert(
                "embedding_cache",
                [{
                    **row,
                    "last_accessed_utc": _now(),
                    "access_count": int(row.get("access_count") or 1) + 1,
                }],
            )
        except Exception:
            pass
        return vec

    vec = _live_embed(text) or _hash_embed(text)
    _store_l1(l1_key, vec)
    try:
        provider.upsert(
            "embedding_cache",
            [{
                "data_source_id": data_source_id,
                "text_hash": text_hash,
                "text_content": text[:8000],
                "embedding_json": json.dumps(vec),
                "embedding_model": model_name,
                "created_at_utc": _now(),
                "last_accessed_utc": _now(),
                "access_count": 1,
            }],
        )
        _evict_l2(provider, data_source_id)
    except Exception:
        pass
    return vec


def _store_l1(key: Tuple[str, str], vec: List[float]) -> None:
    with _l1_lock:
        if len(_l1) >= EmbeddingCacheL1Size:
            _l1.clear()
        _l1[key] = vec


def _evict_l2(provider, data_source_id: str) -> None:
    try:
        rows = provider.execute(
            "SELECT COUNT(*) AS c FROM embedding_cache WHERE data_source_id = ?",
            (data_source_id,),
        )
        if rows:
            count = int(rows[0]["c"]) if rows else 0
            if count <= EmbeddingCacheL2Size:
                return
            provider.execute(
                "DELETE FROM embedding_cache WHERE rowid IN ("
                "SELECT rowid FROM embedding_cache WHERE data_source_id = ? "
                "ORDER BY last_accessed_utc ASC LIMIT ?)",
                (data_source_id, EmbeddingCacheL2EvictBatch),
            )
            return
    except Exception:
        pass
    try:
        cached = provider.fetch_all("embedding_cache", data_source_id)
        if len(cached) <= EmbeddingCacheL2Size:
            return
        cached.sort(key=lambda r: r.get("last_accessed_utc") or "")
        for row in cached[:EmbeddingCacheL2EvictBatch]:
            key = row.get("text_hash")
            if key:
                provider.delete("embedding_cache", data_source_id, "text_hash", key)
    except Exception:
        pass
