"""SourceStores bundle resolved from source_id."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

from app.core.config import settings
from app.services.bm25_service import Bm25Service
from app.services.database_catalog import DatabaseCatalog
from app.services.fewshot_vector_service import FewShotVectorService
from app.services.schema_index_service import SchemaIndexService
from app.services.semantic_model_service import SemanticModelService
from app.services.stores.data_group_store import DataGroupStore
from app.services.stores.precomputed_store import PrecomputedQueryStore
from app.services.stores.provider_factory import get_vector_provider
from app.services.value_index_service import ValueIndexService
from app.services.vector_search_service import VectorSearchService


@dataclass
class SourceStores:
    source_id: str
    catalog: "DatabaseCatalog"
    schema_index: SchemaIndexService
    vector_search: VectorSearchService
    fewshots: FewShotVectorService
    values: ValueIndexService
    precomputed: PrecomputedQueryStore
    data_groups: DataGroupStore
    semantic: "SemanticModelService"
    bm25: Bm25Service
    provider: object


def build_source_stores(source_id: str, provider=None) -> SourceStores:
    provider = provider or get_vector_provider()
    schema_index = SchemaIndexService(source_id)
    try:
        rows = provider.fetch_all("schemas", source_id)
        schema_index.load_from_rows(rows)
    except Exception:
        pass
    return SourceStores(
        source_id=source_id,
        catalog=DatabaseCatalog(source_id),
        schema_index=schema_index,
        vector_search=VectorSearchService(provider, source_id),
        fewshots=FewShotVectorService(provider, source_id),
        values=ValueIndexService(provider, source_id),
        precomputed=PrecomputedQueryStore(provider, source_id),
        data_groups=DataGroupStore(provider, source_id),
        semantic=SemanticModelService(
            provider,
            source_id,
            enable_flag=settings.semantic_layer_enabled_for(source_id),
        ),
        bm25=Bm25Service(
            enabled=settings.ENABLE_BM25_RETRIEVAL,
            k1=settings.BM25_K1,
            b=settings.BM25_B,
        ),
        provider=provider,
    )


@lru_cache(maxsize=64)
def resolve_source_stores(source_id: str) -> SourceStores:
    return build_source_stores(source_id)
