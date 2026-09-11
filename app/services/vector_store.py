from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Union
from app.models.schemas import TableSchema, DataObject
from app.core.config import settings
from app.services.settings_service import load_settings
from app.services.embedding_factory import EmbeddingFactory
from app.services.stores.embeddings import embed_text
from app.services.stores.provider_factory import get_vector_provider
from app.services.stores.schema_contracts import object_type_to_table_type, normalize_object_type
from app.services.stores.schema_rows import build_schema_object_rows, delete_schema_object_rows
from app.services.fewshot_vector_service import FewShotVectorService
from app.services.value_index_service import ValueIndexService
from app.services.vector_search_service import VectorSearchService
from datetime import datetime, timezone
from uuid import uuid4
import hashlib
import logging

_vector_store_instance = None


class VectorStoreBase(ABC):
    @abstractmethod
    def search_schemas(self, query: str, top_k: int = 5) -> List[TableSchema]:
        pass
    
    @abstractmethod
    def search_fewshots(self, query: str, top_k: int = 3, knowledge_type: Optional[str] = None) -> List[Dict[str, Any]]:
        pass
    
    @abstractmethod
    def search_values(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        pass

    # --- Admin Methods ---
    @abstractmethod
    def get_all_schemas(self) -> List[TableSchema]:
        pass

    @abstractmethod
    def get_schema_by_name(self, schema_name: str, table_name: str) -> Optional[TableSchema]:
        pass

    @abstractmethod
    def insert_schema_embedding(self, schema: TableSchema, text_for_embedding: str, table_type: str = "table"):
        pass

    @abstractmethod
    def update_schema_description(self, schema_name: str, table_name: str, new_description: str):
        pass

    @abstractmethod
    def delete_schema(self, schema_name: str, table_name: str):
        pass

    @abstractmethod
    def clear_schemas_collection(self, source_id: Optional[str] = None):
        pass

    @abstractmethod
    def get_all_fewshots(self) -> List[Dict[str, Any]]:
        pass
        
    @abstractmethod
    def insert_fewshot_item(self, question: str, sql_query: str, knowledge_type: str = "sql_query", source_guid: str = None):
        pass

    def delete_fewshot_item(self, item_id: Union[int, str]):
        """Delete a few-shot row by contract key. Concrete default so SQL generation can start even if a subclass omits it."""
        return None

    @abstractmethod
    def clear_fewshots_collection(self, source_id: Optional[str] = None):
        pass
    
    # --- Value Index Methods ---
    @abstractmethod
    def get_all_values(self) -> List[Dict[str, Any]]:
        pass
    
    @abstractmethod
    def insert_value_item(self, value: str, schema_name: str, table_name: str, column_name: str, metadata: dict = None, source_guid: str = None):
        pass

    @abstractmethod
    def insert_value_items_batch(self, items: List[Dict[str, Any]], source_guid: str = None):
        """
        Batch insert value items.
        items: List of dicts with keys: value, schema_name, table_name, column_name, metadata (optional)
        """
        pass
    
    @abstractmethod
    def delete_value_item(self, item_id: Union[int, str]):
        pass
    
    @abstractmethod
    def clear_values_collection(self, source_id: Optional[str] = None):
        pass

    # --- Contribution Library Methods ---
    @abstractmethod
    def get_all_contributions(self) -> List[Dict[str, Any]]:
        pass
    
    @abstractmethod
    def insert_contribution(self, question: str, sql_query: str, knowledge_type: str = "sql_query", user_id: str = None, source_guid: str = None) -> Union[int, str]:
        pass
    
    @abstractmethod
    def delete_contribution(self, contribution_id: Union[int, str]):
        pass
    
    @abstractmethod
    def check_similarity(self, question: str, threshold: float = 0.9, knowledge_type: Optional[str] = None) -> tuple:
        """Check if similar item exists in knowledge base. Returns (is_similar, score, similar_item_id)"""
        pass
    
    @abstractmethod
    def move_contribution_to_knowledge_base(self, contribution_id: Union[int, str], edited_question: str = None, edited_sql: str = None, knowledge_type: Optional[str] = None) -> Union[int, str]:
        """Move contribution to knowledge base. Returns new knowledge base item ID.
        
        Args:
            contribution_id: ID of the contribution to approve
            edited_question: Optional edited question text to use instead of original
            edited_sql: Optional edited SQL query to use instead of original
            knowledge_type: Type of knowledge ("general", "sql_query", "r_code", "sas_code")
        """
        pass

    @abstractmethod
    def export_all_data(self) -> Dict[str, Any]:
        """Export all vector store data for backup."""
        pass


class MilvusVectorStore(VectorStoreBase):
    """Compatibility facade over the contract MilvusProvider. Does not create legacy collections."""

    def __init__(self):
        agent_settings = load_settings()
        embedding_config = agent_settings.embedding_config
        self._connected = False
        try:
            self.embedding_client = EmbeddingFactory.create_client(embedding_config)
            self._embedding_dim = embedding_config.dimensions
            self._embedding_ready = True
        except Exception as e:
            print(f"Failed to initialize embedding client: {e}")
            self.embedding_client = None
            self._embedding_dim = embedding_config.dimensions
            self._embedding_ready = False

        self.provider = get_vector_provider()
        self._connected = bool(getattr(self.provider, "_connected", False))

    def _stores(self, source_id: Optional[str] = None):
        sid = source_id or self._resolve_default_source_guid()
        return (
            sid,
            VectorSearchService(self.provider, sid),
            FewShotVectorService(self.provider, sid),
            ValueIndexService(self.provider, sid),
        )

    def _resolve_default_source_guid(self) -> str:
        try:
            from app.services.source_resolver import resolve_or_primary
            return resolve_or_primary(None)
        except Exception:
            pass
        try:
            settings_obj = load_settings()
            if hasattr(settings_obj, "data_sources") and settings_obj.data_sources:
                if settings_obj.primary_source_id:
                    return settings_obj.primary_source_id
                return settings_obj.data_sources[0].source_id
        except Exception:
            pass
        return "legacy"

    def _schema_rows(self, source_id: Optional[str] = None) -> List[Dict[str, Any]]:
        if source_id:
            return self.provider.fetch_all("schemas", source_id)
        if hasattr(self.provider, "fetch_all_rows"):
            return self.provider.fetch_all_rows("schemas")
        return self.provider.fetch_all("schemas", self._resolve_default_source_guid())

    def _parent_rows(self, source_id: Optional[str] = None) -> List[Dict[str, Any]]:
        return [r for r in self._schema_rows(source_id) if (r.get("entity_type") or "Table") != "Column"]

    def _row_to_schema(self, row: Dict[str, Any]) -> TableSchema:
        object_type = row.get("object_type") or row.get("entity_type") or "Table"
        return TableSchema(
            schema_name=row.get("schema_name") or "dbo",
            table_name=row.get("object_name") or row.get("table_name") or "unknown",
            table_type=object_type_to_table_type(object_type),
            description=row.get("description") or "",
            columns=[],
            source_guid=row.get("data_source_id") or row.get("source_guid"),
        )

    def _get_embedding(self, text: str) -> List[float]:
        if not text or not isinstance(text, str):
            return self._fallback_embedding("empty_input_fallback")
        text = text.replace("\n", " ").strip()
        if not text:
            return self._fallback_embedding("empty_text_fallback")
        source_id = self._resolve_default_source_guid()
        try:
            return embed_text(text, self.provider, source_id)
        except Exception:
            return self._fallback_embedding(text)

    def _fallback_embedding(self, text: str) -> List[float]:
        seed = hashlib.sha256(text.encode("utf-8")).digest()
        values: List[float] = []
        counter = 0
        while len(values) < self._embedding_dim:
            block = hashlib.sha256(seed + counter.to_bytes(4, "little")).digest()
            for i in range(0, len(block), 4):
                if len(values) >= self._embedding_dim:
                    break
                chunk = block[i:i + 4]
                val = int.from_bytes(chunk, "little", signed=False) / 2**32
                values.append((val * 2) - 1)
            counter += 1
        return values

    def search_schemas(self, query: str, top_k: int = 5) -> List[TableSchema]:
        if not self._connected:
            return []
        source_id, vector_search, _, _ = self._stores()
        hits = vector_search.search_objects(query, top_k=top_k)
        return [
            TableSchema(
                schema_name=obj.schema_name,
                table_name=obj.object_name,
                table_type=(obj.object_type or "table").lower(),
                description=obj.description or "",
                columns=[],
                source_guid=source_id,
            )
            for obj in hits
        ]

    def search_fewshots(self, query: str, top_k: int = 3, knowledge_type: Optional[str] = None, source_id: Optional[str] = None) -> List[Dict[str, Any]]:
        if not self._connected:
            return []
        _, _, fewshots, _ = self._stores(source_id)
        results = []
        for hit in fewshots.search(query, top_k=top_k):
            entity = {
                "question": hit.question,
                "sql_query": hit.sql,
                "knowledge_type": knowledge_type or "sql_query",
            }
            results.append({
                **entity,
                "entity": entity,
                "score": hit.score,
                "id": None,
            })
        return results

    def search_fewshots_with_threshold(
        self,
        query: str,
        top_k: int = 3,
        knowledge_type: Optional[str] = None,
        score_threshold: float = 0.5,
    ) -> List[Dict[str, Any]]:
        all_results = self.search_fewshots(query, top_k=top_k, knowledge_type=knowledge_type)
        filtered = [r for r in all_results if r.get("score", float("inf")) < score_threshold]
        if filtered:
            logging.info(
                f"[KB Search] {len(filtered)}/{len(all_results)} results passed threshold {score_threshold}. "
                f"Best score: {filtered[0].get('score', 'N/A')}"
            )
        else:
            scores = [r.get("score", "N/A") for r in all_results]
            logging.info(
                f"[KB Search] 0/{len(all_results)} results passed threshold {score_threshold}. "
                f"Scores: {scores}"
            )
        return filtered

    def search_values(self, query: str, top_k: int = 5, source_id: Optional[str] = None) -> List[Dict[str, Any]]:
        if not self._connected:
            return []
        _, _, _, values = self._stores(source_id)
        hits = values.search(query, top_k=top_k)
        results = []
        for hit in hits:
            item = {
                "id": hit.get("key"),
                "value": hit.get("value"),
                "schema_name": hit.get("schema_name"),
                "table_name": hit.get("table_name"),
                "column_name": hit.get("column_name"),
                "source_guid": hit.get("data_source_id"),
            }
            results.append({**item, "entity": item})
        return results

    def get_all_schemas(self) -> List[TableSchema]:
        if not self._connected:
            return []
        return [self._row_to_schema(row) for row in self._parent_rows()]

    def get_schema_by_name(self, schema_name: str, table_name: str) -> Optional[TableSchema]:
        if not self._connected:
            return None
        for row in self._parent_rows():
            if row.get("schema_name") == schema_name and row.get("object_name") == table_name:
                return self._row_to_schema(row)
        return None

    def insert_schema_embedding(self, schema: TableSchema, text_for_embedding: str, table_type: str = "table"):
        if not self._connected:
            raise Exception("Milvus is not connected. Cannot insert schema.")
        source_id = getattr(schema, "source_guid", None) or self._resolve_default_source_guid()
        object_type = normalize_object_type(schema.table_type or table_type)
        description = schema.description or text_for_embedding
        delete_schema_object_rows(self.provider, source_id, schema.schema_name, schema.table_name)
        rows = build_schema_object_rows(
            self.provider,
            source_id,
            schema.schema_name,
            schema.table_name,
            object_type,
            description,
            schema.columns,
        )
        self.provider.upsert("schemas", rows)

    def update_schema_description(self, schema_name: str, table_name: str, new_description: str):
        if not self._connected:
            raise Exception("Milvus is not connected. Cannot update schema.")
        existing = self.get_schema_by_name(schema_name, table_name)
        if not existing:
            raise Exception(f"Schema {schema_name}.{table_name} not found in vector store")
        existing.description = new_description
        self.insert_schema_embedding(existing, new_description, existing.table_type or "table")

    def delete_schema(self, schema_name: str, table_name: str):
        if not self._connected:
            raise Exception("Milvus is not connected. Cannot delete schema.")
        source_id = self._resolve_default_source_guid()
        matched = [
            row for row in self._schema_rows()
            if row.get("schema_name") == schema_name and row.get("object_name") == table_name
        ]
        for row in matched:
            sid = row.get("data_source_id") or source_id
            key = row.get("key")
            if key:
                self.provider.delete("schemas", sid, "key", key)

    def clear_schemas_collection(self, source_id: str = None):
        if not self._connected:
            return
        if source_id:
            self.provider.delete_source("schemas", source_id)
            return
        for row in self._schema_rows():
            sid = row.get("data_source_id")
            key = row.get("key")
            if sid and key:
                self.provider.delete("schemas", sid, "key", key)

    def clear_schemas_v2_collection(self, source_id: str = None):
        self.clear_schemas_collection(source_id)

    def insert_data_object_v2(self, data_object: DataObject, text_for_embedding: str):
        if not self._connected:
            raise Exception("Milvus is not connected. Cannot insert data object.")
        source_id = data_object.source_id or self._resolve_default_source_guid()
        object_type = data_object.object_type.value if hasattr(data_object.object_type, "value") else str(data_object.object_type)
        delete_schema_object_rows(self.provider, source_id, data_object.schema_name, data_object.object_name)
        rows = build_schema_object_rows(
            self.provider,
            source_id,
            data_object.schema_name,
            data_object.object_name,
            object_type,
            data_object.description or text_for_embedding,
            data_object.columns,
        )
        self.provider.upsert("schemas", rows)

    def get_all_objects_v2(self, source_id: Optional[str] = None) -> List[Dict[str, Any]]:
        if not self._connected:
            return []
        results = []
        for row in self._parent_rows(source_id):
            object_type = object_type_to_table_type(row.get("object_type") or "Table")
            results.append({
                "id": row.get("key"),
                "source_guid": row.get("data_source_id"),
                "schema_name": row.get("schema_name"),
                "object_name": row.get("object_name"),
                "object_type": object_type,
                "description": row.get("description") or "",
                "definition": "",
                "return_type": "",
            })
        return results

    def search_objects_v2(
        self,
        query: str,
        top_k: int = 5,
        source_id: Optional[str] = None,
        object_types: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        if not self._connected:
            return []
        sid, vector_search, _, _ = self._stores(source_id)
        wanted = None
        if object_types:
            wanted = {normalize_object_type(t) for t in object_types}
            wanted |= {t.lower() for t in object_types}
        hits = vector_search.search_objects(query, top_k=top_k * 2)
        results = []
        for obj in hits:
            ot = obj.object_type or "Table"
            if wanted and ot not in wanted and ot.lower() not in wanted:
                continue
            results.append({
                "source_guid": sid,
                "schema_name": obj.schema_name,
                "object_name": obj.object_name,
                "object_type": object_type_to_table_type(ot),
                "description": obj.description or "",
                "definition": "",
                "return_type": "",
                "score": obj.vector_score if obj.vector_score is not None else (1.0 - (obj.score or 0)),
            })
            if len(results) >= top_k:
                break
        return results

    def delete_data_object_v2(self, source_id: str, schema_name: str, object_name: str):
        if not self._connected:
            raise Exception("Milvus is not connected. Cannot delete object.")
        delete_schema_object_rows(self.provider, source_id, schema_name, object_name)

    def clear_source_objects_v2(self, source_id: str):
        self.clear_schemas_collection(source_id)

    def get_all_fewshots(self) -> List[Dict[str, Any]]:
        if not self._connected:
            return []
        rows = []
        if hasattr(self.provider, "fetch_all_rows"):
            rows = self.provider.fetch_all_rows("few_shots")
        else:
            rows = self.provider.fetch_all("few_shots", self._resolve_default_source_guid())
        return [
            {
                "id": r.get("key"),
                "question": r.get("question"),
                "sql_query": r.get("sql"),
                "knowledge_type": "sql_query",
                "source_guid": r.get("data_source_id"),
            }
            for r in rows
        ]

    def insert_fewshot_item(self, question: str, sql_query: str, knowledge_type: str = "sql_query", source_guid: str = None):
        if not self._connected:
            raise Exception("Milvus is not connected. Cannot insert fewshot item.")
        _, _, fewshots, _ = self._stores(source_guid)
        return fewshots.upsert(question, sql_query)

    def delete_fewshot_item(self, item_id: Union[int, str]):
        if not self._connected:
            return
        key = str(item_id)
        if hasattr(self.provider, "fetch_all_rows"):
            rows = self.provider.fetch_all_rows("few_shots")
        else:
            rows = self.provider.fetch_all("few_shots", self._resolve_default_source_guid())
        for row in rows:
            if str(row.get("key")) == key:
                sid = row.get("data_source_id") or self._resolve_default_source_guid()
                FewShotVectorService(self.provider, sid).delete(key)
                return
        FewShotVectorService(self.provider, self._resolve_default_source_guid()).delete(key)

    def clear_fewshots_collection(self, source_id: str = None):
        if not self._connected:
            return
        if source_id:
            self.provider.delete_source("few_shots", source_id)
            self.provider.delete_source("few_shots_meta", source_id)
            return
        rows = self.provider.fetch_all_rows("few_shots") if hasattr(self.provider, "fetch_all_rows") else []
        for row in rows:
            sid = row.get("data_source_id")
            if sid:
                self.provider.delete_source("few_shots", sid)
                self.provider.delete_source("few_shots_meta", sid)

    def get_all_values(self) -> List[Dict[str, Any]]:
        if not self._connected:
            return []
        rows = self.provider.fetch_all_rows("value_index") if hasattr(self.provider, "fetch_all_rows") else []
        return [
            {
                "id": r.get("key"),
                "value": r.get("value"),
                "schema_name": r.get("schema_name"),
                "table_name": r.get("table_name"),
                "column_name": r.get("column_name"),
                "source_guid": r.get("data_source_id"),
            }
            for r in rows
        ]

    def insert_value_item(self, value: str, schema_name: str, table_name: str, column_name: str, metadata: dict = None, source_guid: str = None):
        if not self._connected:
            raise Exception("Milvus is not connected. Cannot insert value item.")
        _, _, _, values = self._stores(source_guid)
        values.upsert(value, schema_name, table_name, column_name)

    def insert_value_items_batch(self, items: List[Dict[str, Any]], source_guid: str = None):
        if not items:
            return
        if not self._connected:
            raise Exception("Milvus is not connected. Cannot insert value items.")
        _, _, _, values = self._stores(source_guid)
        for item in items:
            values.upsert(
                str(item.get("value") or ""),
                str(item.get("schema_name") or ""),
                str(item.get("table_name") or ""),
                str(item.get("column_name") or ""),
            )

    def delete_value_item(self, item_id: Union[int, str]):
        if not self._connected:
            return
        key = str(item_id)
        rows = self.provider.fetch_all_rows("value_index") if hasattr(self.provider, "fetch_all_rows") else []
        for row in rows:
            if str(row.get("key")) == key:
                sid = row.get("data_source_id") or self._resolve_default_source_guid()
                ValueIndexService(self.provider, sid).delete(key)
                return

    def clear_values_collection(self, source_id: str = None):
        if not self._connected:
            return
        if source_id:
            self.provider.delete_source("value_index", source_id)
            return
        rows = self.provider.fetch_all_rows("value_index") if hasattr(self.provider, "fetch_all_rows") else []
        seen = set()
        for row in rows:
            sid = row.get("data_source_id")
            if sid and sid not in seen:
                seen.add(sid)
                self.provider.delete_source("value_index", sid)

    def _contribution_rows(self) -> List[Dict[str, Any]]:
        if hasattr(self.provider, "fetch_all_rows"):
            return self.provider.fetch_all_rows("contribution_library")
        return self.provider.fetch_all("contribution_library", self._resolve_default_source_guid())

    def _find_contribution(self, contribution_id: Union[int, str]) -> Optional[Dict[str, Any]]:
        key = str(contribution_id)
        for row in self._contribution_rows():
            if str(row.get("key") or row.get("id") or "") == key:
                return row
        return None

    def get_all_contributions(self) -> List[Dict[str, Any]]:
        if not self._connected:
            return []
        return [
            {
                "id": r.get("key"),
                "question": r.get("question"),
                "sql_query": r.get("sql_query") or r.get("sql"),
                "knowledge_type": r.get("knowledge_type") or "sql_query",
                "user_id": r.get("user_id"),
                "submitted_at": r.get("submitted_at"),
                "status": r.get("status") or "pending",
                "source_guid": r.get("data_source_id"),
            }
            for r in self._contribution_rows()
        ]

    def insert_contribution(self, question: str, sql_query: str, knowledge_type: str = "sql_query", user_id: str = None, source_guid: str = None) -> Union[int, str]:
        if not self._connected:
            raise Exception("Vector store is not connected. Cannot insert contribution.")
        source_id, _, _, _ = self._stores(source_guid)
        key = str(uuid4())
        self.provider.upsert(
            "contribution_library",
            [{
                "data_source_id": source_id,
                "key": key,
                "question": question,
                "sql_query": sql_query,
                "knowledge_type": knowledge_type or "sql_query",
                "user_id": user_id or "anonymous",
                "submitted_at": datetime.now(timezone.utc).isoformat(),
                "status": "pending",
            }],
        )
        return key

    def delete_contribution(self, contribution_id: Union[int, str]):
        if not self._connected:
            return
        row = self._find_contribution(contribution_id)
        if not row:
            return
        sid = row.get("data_source_id") or self._resolve_default_source_guid()
        key = str(row.get("key") or contribution_id)
        self.provider.delete("contribution_library", sid, "key", key)

    def check_similarity(self, question: str, threshold: float = 0.9, knowledge_type: Optional[str] = None) -> tuple:
        if not self._connected:
            return (False, 0.0, None)
        _, _, fewshots, _ = self._stores()
        hits = fewshots.search(question, top_k=1)
        if not hits:
            return (False, 0.0, None)
        hit = hits[0]
        similarity_score = max(0.0, 1.0 - float(hit.score))
        is_similar = similarity_score >= threshold
        similar_item_id = None
        if is_similar:
            exact = fewshots.try_get_exact(hit.question)
            similar_item_id = hit.question if exact else hit.question
        return (is_similar, similarity_score, similar_item_id)

    def export_all_data(self) -> Dict[str, Any]:
        export_data = {
            "schemas": [],
            "fewshots": [],
            "values": [],
            "contributions": []
        }
        if not self._connected:
            return export_data
        try:
            schemas = self.get_all_schemas()
            export_data["schemas"] = [s.model_dump() for s in schemas]
            export_data["fewshots"] = self.get_all_fewshots()
            export_data["values"] = self.get_all_values()
            export_data["contributions"] = self.get_all_contributions()
        except Exception as e:
            print(f"Error during export: {e}")
            raise e
        return export_data

    def move_contribution_to_knowledge_base(self, contribution_id: Union[int, str], edited_question: str = None, edited_sql: str = None, knowledge_type: Optional[str] = None) -> Union[int, str]:
        if not self._connected:
            raise Exception("Vector store is not connected. Cannot move contribution.")

        contribution = self._find_contribution(contribution_id)
        if not contribution:
            raise Exception(f"Contribution {contribution_id} not found")

        source_id = contribution.get("data_source_id") or contribution.get("source_guid") or self._resolve_default_source_guid()
        question = edited_question if edited_question else contribution.get("question")
        sql_query = edited_sql if edited_sql else (contribution.get("sql_query") or contribution.get("sql"))
        stored_type = contribution.get("knowledge_type")
        final_type = knowledge_type or stored_type or "sql_query"

        kb_key = self.insert_fewshot_item(question, sql_query, final_type, source_guid=source_id)
        self.delete_contribution(contribution_id)
        return kb_key or contribution.get("key") or str(contribution_id)


class NullVectorStore(VectorStoreBase):
    """
    Safe no-op vector store for deployments without a vector DB.
    Returns empty results and ignores writes.
    """
    def __init__(self):
        self._disabled_message = "Vector store disabled (VECTOR_DB_ENABLED=false)."

    def search_schemas(self, query: str, top_k: int = 5) -> List[TableSchema]:
        return []

    def search_fewshots(self, query: str, top_k: int = 3, knowledge_type: Optional[str] = None, source_id: Optional[str] = None) -> List[Dict[str, Any]]:
        return []

    def search_values(self, query: str, top_k: int = 5, source_id: Optional[str] = None) -> List[Dict[str, Any]]:
        return []

    def get_all_schemas(self) -> List[TableSchema]:
        return []

    def get_schema_by_name(self, schema_name: str, table_name: str) -> Optional[TableSchema]:
        return None

    def insert_schema_embedding(self, schema: TableSchema, text_for_embedding: str, table_type: str = "table"):
        return None

    def update_schema_description(self, schema_name: str, table_name: str, new_description: str):
        return None

    def delete_schema(self, schema_name: str, table_name: str):
        return None

    def clear_schemas_collection(self, source_id: Optional[str] = None):
        return None

    def get_all_fewshots(self) -> List[Dict[str, Any]]:
        return []

    def insert_fewshot_item(self, question: str, sql_query: str, knowledge_type: str = "sql_query", source_guid: str = None):
        return None

    def delete_fewshot_item(self, item_id: Union[int, str]):
        return None

    def clear_fewshots_collection(self, source_id: Optional[str] = None):
        return None

    def get_all_values(self) -> List[Dict[str, Any]]:
        return []

    def insert_value_item(self, value: str, schema_name: str, table_name: str, column_name: str, metadata: dict = None, source_guid: str = None):
        return None

    def insert_value_items_batch(self, items: List[Dict[str, Any]], source_guid: str = None):
        return None

    def delete_value_item(self, item_id: Union[int, str]):
        return None

    def clear_values_collection(self, source_id: Optional[str] = None):
        return None

    def get_all_contributions(self) -> List[Dict[str, Any]]:
        return []

    def insert_contribution(self, question: str, sql_query: str, knowledge_type: str = "sql_query", user_id: str = None, source_guid: str = None) -> Union[int, str]:
        return -1

    def delete_contribution(self, contribution_id: Union[int, str]):
        return None

    def check_similarity(self, question: str, threshold: float = 0.9, knowledge_type: Optional[str] = None) -> tuple:
        return (False, 0.0, None)

    def move_contribution_to_knowledge_base(self, contribution_id: Union[int, str], edited_question: str = None, edited_sql: str = None, knowledge_type: Optional[str] = None) -> Union[int, str]:
        return -1

    def export_all_data(self) -> Dict[str, Any]:
        return {
            "schemas": [],
            "fewshots": [],
            "values": [],
            "contributions": []
        }


def get_vector_store() -> VectorStoreBase:
    global _vector_store_instance
    if not settings.VECTOR_DB_ENABLED:
        return NullVectorStore()
    if _vector_store_instance is None:
        missing = getattr(MilvusVectorStore, "__abstractmethods__", frozenset()) or frozenset()
        if missing:
            raise TypeError(
                "MilvusVectorStore is missing implementations for: "
                + ", ".join(sorted(missing))
            )
        _vector_store_instance = MilvusVectorStore()
    return _vector_store_instance


def refresh_vector_store() -> VectorStoreBase:
    global _vector_store_instance
    _vector_store_instance = None
    return get_vector_store()
