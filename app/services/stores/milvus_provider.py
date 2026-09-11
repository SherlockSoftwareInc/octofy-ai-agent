"""Milvus adapter. Same collection names; data_source_id partition; cosine distance out."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Sequence

from app.core.config import settings
from app.core.constants import EmbeddingDimensions
from app.services.stores.milvus_replicate import (
    DUMMY_VECTOR_DIM,
    DUMMY_VECTOR_FIELD,
    needs_dummy_vector,
    prepare_milvus_row,
    uses_native_vector,
)
from app.services.stores.schema_contracts import COLLECTIONS, COLLECTION_BY_NAME, PARTITION_FIELD
from app.services.stores.score_utils import milvus_score_to_cosine_distance

logger = logging.getLogger(__name__)

_PK_MAX = 1024
_VARCHAR_MAX = 65535
_PARTITION_MAX = 128


class MilvusProvider:
    def __init__(self):
        self._client = None
        self._connected = False
        try:
            from pymilvus import connections, utility, Collection, FieldSchema, CollectionSchema, DataType

            self._pymilvus = {
                "connections": connections,
                "utility": utility,
                "Collection": Collection,
                "FieldSchema": FieldSchema,
                "CollectionSchema": CollectionSchema,
                "DataType": DataType,
            }
            host = getattr(settings, "VECTOR_HOST", None) or settings.MILVUS_HOST
            port = getattr(settings, "VECTOR_PORT", None) or settings.MILVUS_PORT
            connections.connect(alias="default", host=host, port=port, timeout=5)
            self._connected = True
            self.ensure_schema()
        except Exception as exc:
            logger.warning("Milvus provider unavailable: %s", exc)
            self._connected = False

    def drop_all_collections(self) -> List[str]:
        """Drop every contract collection so Reload can recreate a full SQLite replica."""
        dropped: List[str] = []
        if not self._connected:
            return dropped
        utility = self._pymilvus["utility"]
        existing = set(utility.list_collections() or [])
        for spec in COLLECTIONS:
            if spec.name not in existing:
                continue
            if not self._is_contract_collection(spec.name):
                logger.info("skip drop of legacy collection %s", spec.name)
                continue
            try:
                utility.drop_collection(spec.name)
                dropped.append(spec.name)
            except Exception as exc:
                logger.warning("drop %s failed: %s", spec.name, exc)
        self.ensure_schema()
        return dropped

    def _schema_field_names(self, collection: str) -> List[str]:
        Collection = self._pymilvus["Collection"]
        try:
            col = Collection(collection)
            return [field.name for field in col.schema.fields]
        except Exception:
            return []

    def _is_contract_collection(self, collection: str) -> bool:
        names = set(self._schema_field_names(collection))
        return "pk" in names and PARTITION_FIELD in names

    def _collection_needs_recreate(self, collection: str) -> bool:
        names = self._schema_field_names(collection)
        if not names:
            return False
        DataType = self._pymilvus["DataType"]
        Collection = self._pymilvus["Collection"]
        try:
            col = Collection(collection)
            has_vector = any(field.dtype == DataType.FLOAT_VECTOR for field in col.schema.fields)
        except Exception:
            return False
        if "pk" in names and PARTITION_FIELD in names and has_vector:
            return False
        # New contract row that is missing a required field.
        if "pk" in names and (PARTITION_FIELD not in names or not has_vector):
            return True
        # Leave legacy collections (source_guid / embedding) alone.
        return False

    def ensure_schema(self) -> None:
        if not self._connected:
            return
        DataType = self._pymilvus["DataType"]
        FieldSchema = self._pymilvus["FieldSchema"]
        CollectionSchema = self._pymilvus["CollectionSchema"]
        Collection = self._pymilvus["Collection"]
        utility = self._pymilvus["utility"]
        for spec in COLLECTIONS:
            try:
                if utility.has_collection(spec.name) and self._collection_needs_recreate(spec.name):
                    logger.warning("recreating %s so data_source_id and a vector field are present", spec.name)
                    utility.drop_collection(spec.name)
                if utility.has_collection(spec.name):
                    continue
                fields = [
                    FieldSchema(name="pk", dtype=DataType.VARCHAR, is_primary=True, max_length=_PK_MAX, auto_id=False),
                    FieldSchema(
                        name=PARTITION_FIELD,
                        dtype=DataType.VARCHAR,
                        max_length=_PARTITION_MAX,
                        is_partition_key=True,
                    ),
                ]
                native = uses_native_vector(spec)
                for field in spec.fields:
                    if field.name in {PARTITION_FIELD, "rowid"}:
                        continue
                    if field.type == "FLOAT_VECTOR" and native and field.name in spec.vector_fields:
                        fields.append(
                            FieldSchema(
                                name=field.name,
                                dtype=DataType.FLOAT_VECTOR,
                                dim=field.vector_dim or EmbeddingDimensions,
                            )
                        )
                    elif field.type == "INTEGER":
                        fields.append(FieldSchema(name=field.name, dtype=DataType.INT64))
                    else:
                        fields.append(FieldSchema(name=field.name, dtype=DataType.VARCHAR, max_length=_VARCHAR_MAX))
                if needs_dummy_vector(spec):
                    fields.append(
                        FieldSchema(name=DUMMY_VECTOR_FIELD, dtype=DataType.FLOAT_VECTOR, dim=DUMMY_VECTOR_DIM)
                    )
                schema = CollectionSchema(fields, spec.name)
                col = Collection(spec.name, schema)
                index_fields = spec.vector_fields if native else [DUMMY_VECTOR_FIELD]
                for vf in index_fields:
                    try:
                        col.create_index(
                            vf,
                            {"index_type": "IVF_FLAT", "metric_type": "COSINE", "params": {"nlist": 128}},
                        )
                    except Exception:
                        pass
                try:
                    col.load()
                except Exception:
                    pass
            except Exception as exc:
                logger.warning("ensure_schema %s failed: %s", spec.name, exc)

    def upsert(self, collection: str, records: List[Dict[str, Any]]) -> None:
        if not self._connected or not records:
            return
        utility = self._pymilvus["utility"]
        if utility.has_collection(collection) and not self._is_contract_collection(collection):
            logger.warning("replacing legacy collection %s with contract schema", collection)
            try:
                utility.drop_collection(collection)
            except Exception as exc:
                logger.warning("drop legacy %s failed: %s", collection, exc)
                return
        if not utility.has_collection(collection):
            self.ensure_schema()
        if not utility.has_collection(collection):
            raise RuntimeError(f"Milvus collection missing: {collection}")
        Collection = self._pymilvus["Collection"]
        col = Collection(collection)
        try:
            col.load()
        except Exception:
            pass
        spec = COLLECTION_BY_NAME.get(collection)
        rows: List[Dict[str, Any]] = []
        for rec in records:
            prepared = prepare_milvus_row(spec, rec) if spec else dict(rec)
            if not prepared or not prepared.get(PARTITION_FIELD):
                continue
            rows.append(prepared)
        if not rows:
            return
        batch_size = 50
        for start in range(0, len(rows), batch_size):
            batch = rows[start : start + batch_size]
            col.upsert(batch)
        col.flush()
        try:
            col.load()
        except Exception:
            pass

    def search_vector(
        self,
        collection: str,
        data_source_id: str,
        query_vector: Sequence[float],
        top_k: int = 8,
        vector_field: str = "vector",
        extra_where: str = "",
        extra_params: Sequence[Any] = (),
        min_score: Optional[float] = None,
        filter_fn=None,
    ) -> List[Dict[str, Any]]:
        if not self._connected:
            return []
        utility = self._pymilvus["utility"]
        if not utility.has_collection(collection):
            return []
        Collection = self._pymilvus["Collection"]
        col = Collection(collection)
        try:
            col.load()
        except Exception:
            pass
        expr = f'{PARTITION_FIELD} == "{data_source_id}"'
        if extra_where:
            expr += f" && {extra_where}"
        results = col.search(
            data=[list(query_vector)],
            anns_field=vector_field,
            param={"metric_type": "COSINE", "params": {"nprobe": 16}},
            limit=top_k,
            expr=expr,
            output_fields=["*"],
        )
        out = []
        for hits in results:
            for hit in hits:
                dist = milvus_score_to_cosine_distance(hit.score, "COSINE")
                if min_score is not None and dist > min_score:
                    continue
                entity = hit.entity
                row = {field: entity.get(field) for field in entity.fields} if hasattr(entity, "fields") else dict(entity)
                if filter_fn and not filter_fn(row):
                    continue
                row["_distance"] = dist
                out.append(row)
        return out

    def fetch_all(self, collection: str, data_source_id: str) -> List[Dict[str, Any]]:
        if not self._connected:
            return []
        utility = self._pymilvus["utility"]
        if not utility.has_collection(collection):
            return []
        Collection = self._pymilvus["Collection"]
        col = Collection(collection)
        try:
            col.load()
        except Exception:
            pass
        results = col.query(
            expr=f'{PARTITION_FIELD} == "{data_source_id}"',
            output_fields=["*"],
            limit=16384,
            consistency_level="Strong",
        )
        return list(results)

    def fetch_all_rows(self, collection: str) -> List[Dict[str, Any]]:
        if not self._connected:
            return []
        utility = self._pymilvus["utility"]
        if not utility.has_collection(collection):
            return []
        Collection = self._pymilvus["Collection"]
        col = Collection(collection)
        try:
            col.load()
        except Exception:
            pass
        results = col.query(
            expr='pk != ""',
            output_fields=["*"],
            limit=16384,
            consistency_level="Strong",
        )
        return list(results)

    def fetch_one(self, collection: str, data_source_id: str, key_field: str, key: str) -> Optional[Dict[str, Any]]:
        rows = self.fetch_all(collection, data_source_id)
        for row in rows:
            if str(row.get(key_field)) == str(key):
                return row
        return None

    def delete(self, collection: str, data_source_id: str, key_field: str, key: str) -> None:
        if not self._connected:
            return
        utility = self._pymilvus["utility"]
        if not utility.has_collection(collection):
            return
        Collection = self._pymilvus["Collection"]
        col = Collection(collection)
        col.delete(expr=f'{PARTITION_FIELD} == "{data_source_id}" && {key_field} == "{key}"')

    def delete_source(self, collection: str, data_source_id: str) -> None:
        if not self._connected:
            return
        utility = self._pymilvus["utility"]
        Collection = self._pymilvus["Collection"]
        if not utility.has_collection(collection):
            return
        col = Collection(collection)
        try:
            col.load()
        except Exception:
            pass
        try:
            col.delete(expr=f'{PARTITION_FIELD} == "{data_source_id}"')
            col.flush()
        except Exception as exc:
            logger.warning("delete_source %s failed: %s", collection, exc)

    def execute(self, sql: str, params: Sequence[Any] = ()) -> List[Dict[str, Any]]:
        return []
