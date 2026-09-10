"""Vector provider factory. Milvus is the only runtime store."""

from functools import lru_cache


@lru_cache(maxsize=1)
def get_vector_provider():
    from app.services.stores.milvus_provider import MilvusProvider

    return MilvusProvider()
