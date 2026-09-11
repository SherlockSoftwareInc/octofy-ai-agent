"""Vector provider factory. Prefer Milvus; fall back to SQLite if unreachable."""

from functools import lru_cache
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


def _sqlite_provider():
    from app.services.stores.sqlite_vec_provider import SqliteVecProvider

    provider = SqliteVecProvider()
    provider._connected = True
    return provider


@lru_cache(maxsize=1)
def get_vector_provider():
    configured = (getattr(settings, "VECTOR_PROVIDER", None) or "milvus").strip().lower()
    if configured in {"sqlite", "sqlite_vec", "sqlite-vec"}:
        logger.info("Using SQLite vector store (VECTOR_PROVIDER=%s)", configured)
        return _sqlite_provider()

    from app.services.stores.milvus_provider import MilvusProvider

    provider = MilvusProvider()
    if getattr(provider, "_connected", False):
        return provider

    logger.warning("Milvus is unavailable; using local SQLite vector store so knowledge-base writes can succeed.")
    return _sqlite_provider()
