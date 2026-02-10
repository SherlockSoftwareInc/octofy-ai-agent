from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from app.models.schemas import TableSchema, ColumnInfo, DataObject, ObjectType
from app.core.config import settings
from pymilvus import connections, Collection, utility, FieldSchema, CollectionSchema, DataType
from openai import OpenAI, NotFoundError
from app.services.settings_service import load_settings
from app.services.embedding_factory import EmbeddingFactory
import json
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
    def clear_schemas_collection(self):
        pass

    @abstractmethod
    def get_all_fewshots(self) -> List[Dict[str, Any]]:
        pass
        
    @abstractmethod
    def insert_fewshot_item(self, question: str, sql_query: str, knowledge_type: str = "sql_query", source_guid: str = None):
        pass
        
    @abstractmethod
    def delete_fewshot_item(self, item_id: int):
        pass

    @abstractmethod
    def clear_fewshots_collection(self):
        pass
    
    # --- Value Index Methods ---
    @abstractmethod
    def search_values(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        pass
    
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
    def delete_value_item(self, item_id: int):
        pass
    
    @abstractmethod
    def clear_values_collection(self):
        pass

    # --- Contribution Library Methods ---
    @abstractmethod
    def get_all_contributions(self) -> List[Dict[str, Any]]:
        pass
    
    @abstractmethod
    def insert_contribution(self, question: str, sql_query: str, knowledge_type: str = "sql_query", user_id: str = None) -> int:
        pass
    
    @abstractmethod
    def delete_contribution(self, contribution_id: int):
        pass
    
    @abstractmethod
    def check_similarity(self, question: str, threshold: float = 0.9, knowledge_type: Optional[str] = None) -> tuple:
        """Check if similar item exists in knowledge base. Returns (is_similar, score, similar_item_id)"""
        pass
    
    @abstractmethod
    def move_contribution_to_knowledge_base(self, contribution_id: int, edited_question: str = None, edited_sql: str = None, knowledge_type: Optional[str] = None) -> int:
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
    def __init__(self):
        # Load configurations and resolve embedding client settings.
        agent_settings = load_settings()
        embedding_config = agent_settings.embedding_config
        
        # Track connection state
        self._connected = False
        
        # Initialize Embedding Client via Factory
        try:
            self.embedding_client = EmbeddingFactory.create_client(embedding_config)
            self._embedding_dim = embedding_config.dimensions
            self._embedding_ready = True
        except Exception as e:
            print(f"Failed to initialize embedding client: {e}")
            self.embedding_client = None
            self._embedding_dim = embedding_config.dimensions # Keep config dim
            self._embedding_ready = False

        # Connect to the vector database.
        self._connect_milvus()
        
    def _connect_milvus(self):
        try:
            agent_settings = load_settings()
            vector_config = agent_settings.vector_config
            connections.connect(
                alias="default", 
                host=vector_config.host, 
                port=vector_config.port
            )
            print(f"Connected to Milvus at {vector_config.host}:{vector_config.port}")
            self._connected = True
            self._ensure_values_collection()
            self._ensure_schema_collection()
            self._ensure_schema_v2_collection()  # NEW: Multi-source collection
            self._ensure_fewshot_collection()
        except Exception as e:
            print(f"Failed to connect to Milvus: {e}")
            self._connected = False

    def _ensure_values_collection(self):
        """
        Ensure the value index collection exists with source_guid partitioning.
        If the collection exists but lacks required fields, it is dropped and recreated.
        """
        try:
            if utility.has_collection(settings.MILVUS_COLLECTION_VALUES):
                existing = Collection(settings.MILVUS_COLLECTION_VALUES)
                
                # Check Dimensions
                fields = {f.name: f for f in existing.schema.fields}
                if "embedding" in fields:
                    dim = fields["embedding"].params.get("dim")
                    if dim and int(dim) != self._embedding_dim:
                        print(f"WARNING: Dimension mismatch for {settings.MILVUS_COLLECTION_VALUES}. Expected {self._embedding_dim}, found {dim}. Recreating collection.")
                        utility.drop_collection(settings.MILVUS_COLLECTION_VALUES)
                        # Fall through to recreate
                    else:
                        # Check schema fields - must have both plain_value and source_guid
                        required_fields = ["plain_value", "source_guid"]
                        if all(field in fields for field in required_fields):
                            return
                        print(f"Value collection missing required fields. Recreating.")
                        utility.drop_collection(settings.MILVUS_COLLECTION_VALUES)
                else:
                    utility.drop_collection(settings.MILVUS_COLLECTION_VALUES)
            
            val_fields = [
                FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
                FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self._embedding_dim),
                FieldSchema(name="source_guid", dtype=DataType.VARCHAR, max_length=128, is_partition_key=True),
                FieldSchema(name="value", dtype=DataType.VARCHAR, max_length=256),
                FieldSchema(name="plain_value", dtype=DataType.VARCHAR, max_length=256),  # Plain text for search
                FieldSchema(name="schema_name", dtype=DataType.VARCHAR, max_length=128),
                FieldSchema(name="table_name", dtype=DataType.VARCHAR, max_length=128),
                FieldSchema(name="column_name", dtype=DataType.VARCHAR, max_length=128)
            ]
            val_schema = CollectionSchema(fields=val_fields, description="Lookup Value Index")
            coll = Collection(name=settings.MILVUS_COLLECTION_VALUES, schema=val_schema)
            index_params = {
                "metric_type": "L2",
                "index_type": "IVF_FLAT",
                "params": {"nlist": 1024}
            }
            coll.create_index(field_name="embedding", index_params=index_params)
            coll.flush()
            print(f"Created/updated value collection: {settings.MILVUS_COLLECTION_VALUES}")
        except Exception as e:
            print(f"Failed to ensure value collection: {e}")

    def _ensure_schema_collection(self):
        """
        Ensure the schema index collection exists and has the expected fields.
        If the collection exists but lacks new fields (table_type),
        it is dropped and recreated.
        """
        try:
            if utility.has_collection(settings.MILVUS_COLLECTION_SCHEMA):
                existing = Collection(settings.MILVUS_COLLECTION_SCHEMA)
                
                # Check Dimensions
                fields = {f.name: f for f in existing.schema.fields}
                if "embedding" in fields:
                    dim = fields["embedding"].params.get("dim")
                    if dim and int(dim) != self._embedding_dim:
                        print(f"WARNING: Dimension mismatch for {settings.MILVUS_COLLECTION_SCHEMA}. Expected {self._embedding_dim}, found {dim}. Recreating collection.")
                        utility.drop_collection(settings.MILVUS_COLLECTION_SCHEMA)
                    else:
                        # Check fields
                        required_fields = ["table_type", "source_guid"]
                        if all(field in fields for field in required_fields):
                            return
                        utility.drop_collection(settings.MILVUS_COLLECTION_SCHEMA)
                else:
                    utility.drop_collection(settings.MILVUS_COLLECTION_SCHEMA)
            
            schema_fields = [
                FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
                FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self._embedding_dim),
                FieldSchema(name="source_guid", dtype=DataType.VARCHAR, max_length=128, is_partition_key=True),
                FieldSchema(name="schema_name", dtype=DataType.VARCHAR, max_length=128),
                FieldSchema(name="table_name", dtype=DataType.VARCHAR, max_length=128),
                FieldSchema(name="table_type", dtype=DataType.VARCHAR, max_length=32),  # 'table' or 'view'
                FieldSchema(name="description", dtype=DataType.VARCHAR, max_length=65535)  # Rich Markdown description (also used for embedding)
            ]
            schema_schema = CollectionSchema(fields=schema_fields, description="Database Schema Index")
            coll = Collection(name=settings.MILVUS_COLLECTION_SCHEMA, schema=schema_schema)
            index_params = {
                "metric_type": "L2",
                "index_type": "IVF_FLAT",
                "params": {"nlist": 1024}
            }
            coll.create_index(field_name="embedding", index_params=index_params)
            coll.flush()
            print(f"Created/updated schema collection: {settings.MILVUS_COLLECTION_SCHEMA}")
        except Exception as e:
            print(f"Failed to ensure schema collection: {e}")

    def _ensure_schema_v2_collection(self):
        """
        Ensure the schema_index_v2 collection exists with multi-source support and SP/Function fields.
        This collection supports: tables, views, stored procedures, and functions across multiple data sources.
        """
        try:
            if utility.has_collection(settings.MILVUS_COLLECTION_SCHEMA_V2):
                existing = Collection(settings.MILVUS_COLLECTION_SCHEMA_V2)
                
                # Check Dimensions
                fields = {f.name: f for f in existing.schema.fields}
                if "embedding" in fields:
                    dim = fields["embedding"].params.get("dim")
                    if dim and int(dim) != self._embedding_dim:
                        print(f"WARNING: Dimension mismatch for {settings.MILVUS_COLLECTION_SCHEMA_V2}. Expected {self._embedding_dim}, found {dim}. Recreating collection.")
                        utility.drop_collection(settings.MILVUS_COLLECTION_SCHEMA_V2)
                    else:
                        # Check required fields for v2 schema
                        required_fields = ["source_guid", "object_name", "object_type", "definition"]
                        if all(field in fields for field in required_fields):
                            return
                        print(f"Schema v2 collection missing required fields. Recreating.")
                        utility.drop_collection(settings.MILVUS_COLLECTION_SCHEMA_V2)
                else:
                    utility.drop_collection(settings.MILVUS_COLLECTION_SCHEMA_V2)
            
            schema_v2_fields = [
                FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
                FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self._embedding_dim),
                FieldSchema(name="source_guid", dtype=DataType.VARCHAR, max_length=128, is_partition_key=True),  # Links to data source GUID
                FieldSchema(name="schema_name", dtype=DataType.VARCHAR, max_length=128),
                FieldSchema(name="object_name", dtype=DataType.VARCHAR, max_length=128),  # Renamed from table_name
                FieldSchema(name="object_type", dtype=DataType.VARCHAR, max_length=32),  # 'table', 'view', 'stored_procedure', 'function'
                FieldSchema(name="description", dtype=DataType.VARCHAR, max_length=65535),  # Rich Markdown description
                FieldSchema(name="definition", dtype=DataType.VARCHAR, max_length=65535),  # SP/Function code
                FieldSchema(name="return_type", dtype=DataType.VARCHAR, max_length=256),  # Function return type
            ]
            schema_v2_schema = CollectionSchema(fields=schema_v2_fields, description="Multi-Source Database Schema Index (v2)")
            coll = Collection(name=settings.MILVUS_COLLECTION_SCHEMA_V2, schema=schema_v2_schema)
            index_params = {
                "metric_type": "L2",
                "index_type": "IVF_FLAT",
                "params": {"nlist": 1024}
            }
            coll.create_index(field_name="embedding", index_params=index_params)
            coll.flush()
            print(f"Created/updated schema_v2 collection: {settings.MILVUS_COLLECTION_SCHEMA_V2}")
        except Exception as e:
            print(f"Failed to ensure schema_v2 collection: {e}")

    def _ensure_fewshot_collection(self):
        """
        Ensure the few-shot collection exists with source_guid partitioning.
        If the collection exists but lacks required fields, it is dropped and recreated.
        """
        try:
            if utility.has_collection(settings.MILVUS_COLLECTION_FEWSHOT):
                existing = Collection(settings.MILVUS_COLLECTION_FEWSHOT)
                
                # Check Dimensions
                fields = {f.name: f for f in existing.schema.fields}
                if "embedding" in fields:
                    dim = fields["embedding"].params.get("dim")
                    if dim and int(dim) != self._embedding_dim:
                        print(f"WARNING: Dimension mismatch for {settings.MILVUS_COLLECTION_FEWSHOT}. Expected {self._embedding_dim}, found {dim}. Recreating collection.")
                        utility.drop_collection(settings.MILVUS_COLLECTION_FEWSHOT)
                    else:
                        required_fields = ["knowledge_type", "source_guid"]
                        if all(field in fields for field in required_fields):
                            return
                        # Recreate if schema is outdated
                        print(f"Fewshot collection missing required fields. Recreating.")
                        utility.drop_collection(settings.MILVUS_COLLECTION_FEWSHOT)
                else:
                    utility.drop_collection(settings.MILVUS_COLLECTION_FEWSHOT)
            
            fewshot_fields = [
                FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
                FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self._embedding_dim),
                FieldSchema(name="source_guid", dtype=DataType.VARCHAR, max_length=128, is_partition_key=True),
                FieldSchema(name="question", dtype=DataType.VARCHAR, max_length=512),
                FieldSchema(name="sql_query", dtype=DataType.VARCHAR, max_length=8192),  # Also used for R/SAS code
                FieldSchema(name="knowledge_type", dtype=DataType.VARCHAR, max_length=32)  # "general", "sql_query", "r_code", "sas_code"
            ]
            fewshot_schema = CollectionSchema(fields=fewshot_fields, description="Few-Shot Examples / Knowledge Base")
            coll = Collection(name=settings.MILVUS_COLLECTION_FEWSHOT, schema=fewshot_schema)
            index_params = {
                "metric_type": "L2",
                "index_type": "IVF_FLAT",
                "params": {"nlist": 1024}
            }
            coll.create_index(field_name="embedding", index_params=index_params)
            coll.flush()
            print(f"Created/updated few-shot collection: {settings.MILVUS_COLLECTION_FEWSHOT}")
        except Exception as e:
            print(f"Failed to ensure few-shot collection: {e}")

    def _resolve_default_source_guid(self) -> str:
        """
        Resolve a default source GUID for partitioning when not explicitly provided.
        """
        try:
            settings_obj = load_settings()
            if hasattr(settings_obj, "data_sources") and settings_obj.data_sources:
                if settings_obj.primary_source_id:
                    return settings_obj.primary_source_id
                return settings_obj.data_sources[0].source_id
        except Exception:
            pass
        try:
            from app.services.skills_service import SkillsService
            skills_service = SkillsService()
            primary = skills_service.load_primary_data_source()
            if primary and getattr(primary, "source_id", None):
                return primary.source_id
            sources = skills_service.load_data_sources_index()
            for source in sources:
                if getattr(source, "source_id", None):
                    return source.source_id
        except Exception:
            pass
        return "legacy"

    def _get_embedding(self, text: str) -> List[float]:
        # Validate input before processing
        if not text or not isinstance(text, str):
            print(f"Warning: Invalid embedding input (type: {type(text).__name__}), using fallback")
            return self._fallback_embedding("empty_input_fallback")
        
        text = text.replace("\n", " ").strip()
        
        # Check if text is empty after cleaning
        if not text:
            print("Warning: Empty text after cleaning, using fallback")
            return self._fallback_embedding("empty_text_fallback")
        
        if not self._embedding_ready or self.embedding_client is None:
            # Try to re-init if ready (maybe key was added)
            # For now just fall back
            print("Embedding client not ready, using fallback.")
            return self._fallback_embedding(text)
            
        try:
            return self.embedding_client.embed_query(text)
        except Exception as e:
            print(f"Embedding request failed: {e}")
            # Fall back to deterministic embeddings so dev flows (like seed_fewshot) can proceed.
            print(
                "Embedding request failed. Falling back to deterministic embeddings. "
                "Check Settings > Embedding Configuration."
            )
            return self._fallback_embedding(text)

    def _get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        # Validate and clean inputs
        if not texts:
            return []
        
        # Filter out invalid texts and clean valid ones
        clean_texts = []
        for i, t in enumerate(texts):
            if not t or not isinstance(t, str):
                print(f"Warning: Invalid text at index {i} (type: {type(t).__name__}), using fallback")
                clean_texts.append("empty_input_fallback")
            else:
                cleaned = t.replace("\n", " ").strip()
                clean_texts.append(cleaned if cleaned else "empty_text_fallback")
        
        if not self._embedding_ready or self.embedding_client is None:
            print("Embedding client not ready, using fallback batch.")
            return [self._fallback_embedding(t) for t in clean_texts]
            
        try:
            return self.embedding_client.embed_documents(texts)
        except Exception as e:
            print(f"Batch embedding request failed: {e}")
            print("Falling back to deterministic embeddings.")
            return [self._fallback_embedding(t) for t in texts]

    def _fallback_embedding(self, text: str) -> List[float]:
        """
        Generate a deterministic embedding when the embedding API is unavailable.
        This is a dev-friendly fallback and is not semantically meaningful.
        """
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

    def _search_collection(self, collection_name: str, query_vector: List[float], output_fields: List[str], top_k: int = 5, score_threshold: Optional[float] = None):
        """
        Search a Milvus collection with high relevance settings.
        
        Args:
            collection_name: Name of the collection to search
            query_vector: Embedding vector for the query
            output_fields: Fields to return from matching documents
            top_k: Maximum number of results to return
            score_threshold: Maximum L2 distance to include (lower = more similar). 
                            If None, uses default threshold of 1.0 for high relevance.
        
        Returns:
            List of matching items with their scores
        """
        if not self._connected:
            return []
        if not utility.has_collection(collection_name):
            print(f"Collection {collection_name} does not exist.")
            return []
            
        collection = Collection(collection_name)
        collection.load()
        
        # High relevance search parameters:
        # - nprobe=64: Search more clusters for higher accuracy (default was 10)
        # - For IVF_FLAT with nlist=1024, nprobe=64 provides ~6% cluster coverage
        search_params = {
            "metric_type": "L2", 
            "params": {"nprobe": 64}, 
        }
        
        results = collection.search(
            data=[query_vector], 
            anns_field="embedding", 
            param=search_params, 
            limit=top_k, 
            output_fields=output_fields
        )
        
        # Default score threshold for high relevance (L2 distance: lower = more similar)
        # For normalized embeddings: 0-0.5 = very similar, 0.5-1.0 = similar, 1.0-1.5 = somewhat similar
        if score_threshold is None:
            score_threshold = 1.0  # High relevance: only include similar results
        
        retrieved_items = []
        for hits in results:
            for hit in hits:
                # Filter out low-relevance results based on L2 distance
                if hit.score <= score_threshold:
                    item = hit.entity.to_dict()
                    item['score'] = hit.score
                    retrieved_items.append(item)
                
        return retrieved_items

    def search_schemas(self, query: str, top_k: int = 5) -> List[TableSchema]:
        # Check if connected and collection exists
        if not self._connected:
            return []
        if not utility.has_collection(settings.MILVUS_COLLECTION_SCHEMA):
            return []

        embedding = self._get_embedding(query)
        # Moderate relevance for schema search (L2 threshold 1.5)
        results = self._search_collection(
            settings.MILVUS_COLLECTION_SCHEMA,
            embedding,
            ['schema_name', 'table_name', 'table_type', 'description'],
            top_k,
            score_threshold=1.5  # Moderate relevance
        )

        schemas = []
        for res in results:
            try:
                # The actual data is nested under 'entity' key
                entity = res.get('entity', {})
                if not entity:
                    continue

                schemas.append(TableSchema(
                    schema_name=entity.get('schema_name', 'dbo'),
                    table_name=entity.get('table_name', 'unknown'),
                    table_type=entity.get('table_type', 'table'),
                    description=entity.get('description', ''),
                    columns=[]
                ))
            except Exception as e:
                continue

        return schemas
    
    def search_fewshots(self, query: str, top_k: int = 3, knowledge_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Search few-shot examples, optionally filtered by knowledge_type."""
        if not self._connected:
            return []
        if not utility.has_collection(settings.MILVUS_COLLECTION_FEWSHOT):
            return []
        
        embedding = self._get_embedding(query)
        collection = Collection(settings.MILVUS_COLLECTION_FEWSHOT)
        collection.load()
        
        search_params = {
            "metric_type": "L2",
            "params": {"nprobe": 64}
        }
        
        # Build filter expression if knowledge_type is specified
        filter_expr = None
        if knowledge_type:
            filter_expr = f'knowledge_type == "{knowledge_type}"'
        
        results = collection.search(
            data=[embedding],
            anns_field="embedding",
            param=search_params,
            limit=top_k,
            expr=filter_expr,
            output_fields=['question', 'sql_query', 'knowledge_type']
        )
        
        retrieved_items = []
        for hits in results:
            for hit in hits:
                item = hit.entity.to_dict()
                item['score'] = hit.score
                retrieved_items.append(item)
        
        return retrieved_items

    def search_fewshots_with_threshold(
        self, 
        query: str, 
        top_k: int = 3, 
        knowledge_type: Optional[str] = None,
        score_threshold: float = 0.5
    ) -> List[Dict[str, Any]]:
        """
        Search few-shot examples with L2 distance threshold filtering.
        Only returns results with L2 distance < score_threshold.
        
        Args:
            query: Search query text
            top_k: Maximum results to return
            knowledge_type: Optional filter (e.g., "sql_query")
            score_threshold: Maximum L2 distance to include (lower = more similar)
            
        Returns:
            List of matching fewshot items with score < threshold
        """
        # Use existing search
        all_results = self.search_fewshots(query, top_k=top_k, knowledge_type=knowledge_type)
        
        # Filter by threshold
        filtered = [r for r in all_results if r.get('score', float('inf')) < score_threshold]
        
        if filtered:
            logging.info(
                f"[KB Search] {len(filtered)}/{len(all_results)} results passed threshold {score_threshold}. "
                f"Best score: {filtered[0].get('score', 'N/A')}"
            )
        else:
            scores = [r.get('score', 'N/A') for r in all_results]
            logging.info(
                f"[KB Search] 0/{len(all_results)} results passed threshold {score_threshold}. "
                f"Scores: {scores}"
            )
        
        return filtered
    
    def search_values(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Search for values using plain text matching.
        Retrieves all values and filters in Python for accurate substring matching.
        
        Args:
            query: Search term to match against values (case-insensitive)
            top_k: Maximum number of results to return
            
        Returns:
            List of matching value items
        """
        if not self._connected:
            return []
        if not utility.has_collection(settings.MILVUS_COLLECTION_VALUES):
            return []
        
        collection = Collection(settings.MILVUS_COLLECTION_VALUES)
        collection.load()
        
        # Retrieve all values (Milvus LIKE doesn't support wildcards properly)
        # We'll filter in Python for accurate substring matching
        try:
            all_results = collection.query(
                expr="id >= 0",  # Get all records
                output_fields=['id', 'value', 'plain_value', 'schema_name', 'table_name', 'column_name'],
                limit=16384  # Milvus default max limit
            )
        except Exception as e:
            print(f"Error querying values: {e}")
            return []
        
        # Filter results in Python for substring matching
        query_lower = query.lower()
        matched_results = []
        
        for item in all_results:
            plain_value = item.get('plain_value', '')
            if query_lower in plain_value:
                # Remove plain_value from result (not needed in response)
                result_item = {
                    'id': item.get('id'),
                    'value': item.get('value'),
                    'schema_name': item.get('schema_name'),
                    'table_name': item.get('table_name'),
                    'column_name': item.get('column_name')
                }
                matched_results.append(result_item)
                
                # Stop if we've reached the limit
                if len(matched_results) >= top_k:
                    break
        
        return matched_results

    # --- Admin Implementation ---
    
    def get_all_schemas(self) -> List[TableSchema]:
        # Optimized Milvus query for all schemas
        if not self._connected:
             return []
        if not utility.has_collection(settings.MILVUS_COLLECTION_SCHEMA):
             return []
        
        collection = Collection(settings.MILVUS_COLLECTION_SCHEMA)
        collection.load()
        
        # Use empty expr for better performance (no filter scan)
        # Increase limit to handle larger schema collections
        res = collection.query(
            expr="",  # Empty expr is faster than "id > 0" or "id >= 0"
            output_fields=["schema_name", "table_name", "table_type", "description"],
            limit=16384  # Milvus max limit for better coverage
        )
        
        schemas = []
        for r in res:
             try:
                schemas.append(TableSchema(
                    schema_name=r.get('schema_name'),
                    table_name=r.get('table_name'),
                    table_type=r.get('table_type', 'table'),
                    description=r.get('description'),
                    columns=[]
                ))
             except: pass
        return schemas

    def get_schema_by_name(self, schema_name: str, table_name: str) -> Optional[TableSchema]:
        if not self._connected:
            return None
        if not utility.has_collection(settings.MILVUS_COLLECTION_SCHEMA):
            return None

        collection = Collection(settings.MILVUS_COLLECTION_SCHEMA)
        collection.load()

        safe_schema = schema_name.replace('"', '\\"')
        safe_table = table_name.replace('"', '\\"')
        res = collection.query(
            expr=f'schema_name == "{safe_schema}" && table_name == "{safe_table}"',
            output_fields=["schema_name", "table_name", "table_type", "description"],
            limit=1,
            consistency_level="Strong"
        )

        if not res:
            return None

        record = res[0]
        return TableSchema(
            schema_name=record.get('schema_name'),
            table_name=record.get('table_name'),
            table_type=record.get('table_type', 'table'),
            description=record.get('description'),
            columns=[]
        )

    def insert_schema_embedding(self, schema: TableSchema, text_for_embedding: str, table_type: str = "table"):
        if not self._connected:
            raise Exception("Milvus is not connected. Cannot insert schema.")
        self._ensure_schema_collection()
        collection = Collection(settings.MILVUS_COLLECTION_SCHEMA)
        try:
            collection.load()
        except Exception:
            pass
        
        # 1. Delete existing for this table to avoid dups
        collection.delete(f'table_name == "{schema.table_name}" && schema_name == "{schema.schema_name}"')
        
        # 2. Embed
        embedding = self._get_embedding(text_for_embedding)
        
        # 3. Insert
        # Milvus Collection structure:
        # [embedding], [source_guid], [schema_name], [table_name], [table_type], [description]
        # Use schema.table_type if available, otherwise use the parameter
        actual_table_type = schema.table_type or table_type
        source_guid = getattr(schema, "source_guid", None) or self._resolve_default_source_guid()
        data = [
            [embedding],
            [source_guid],
            [schema.schema_name],
            [schema.table_name],
            [actual_table_type],
            [schema.description]
        ]
        
        collection.insert(data)
        collection.flush()

    def update_schema_description(self, schema_name: str, table_name: str, new_description: str):
        if not self._connected:
            raise Exception("Milvus is not connected. Cannot update schema.")
        if not utility.has_collection(settings.MILVUS_COLLECTION_SCHEMA):
            raise Exception(f"Collection {settings.MILVUS_COLLECTION_SCHEMA} does not exist")

        self._ensure_schema_collection()
        collection = Collection(settings.MILVUS_COLLECTION_SCHEMA)
        collection.load()

        # Find the existing record
        res = collection.query(
            expr=f'schema_name == "{schema_name}" && table_name == "{table_name}"',
            output_fields=["id", "schema_name", "table_name", "table_type", "description", "source_guid"],
            limit=1
        )

        if not res:
            raise Exception(f"Schema {schema_name}.{table_name} not found in vector store")

        # Get the existing data
        existing = res[0]
        existing_id = existing['id']

        # Create new embedding for the updated description
        embedding = self._get_embedding(new_description)

        # Update the record
        collection.delete(f'id == {existing_id}')
        collection.flush()

        # Re-insert with updated description
        # Milvus Collection structure:
        # [embedding], [source_guid], [schema_name], [table_name], [table_type], [description]
        data = [
            [embedding],
            [existing.get('source_guid', '')],
            [schema_name],
            [table_name],
            [existing.get('table_type', 'table')],  # Keep existing table_type
            [new_description]  # Update description (also used for embedding)
        ]

        collection.insert(data)
        collection.flush()

    def delete_schema(self, schema_name: str, table_name: str):
        if not self._connected:
            raise Exception("Milvus is not connected. Cannot delete schema.")
        if not utility.has_collection(settings.MILVUS_COLLECTION_SCHEMA):
            raise Exception(f"Collection {settings.MILVUS_COLLECTION_SCHEMA} does not exist")

        collection = Collection(settings.MILVUS_COLLECTION_SCHEMA)
        collection.load()

        # Delete the record
        collection.delete(f'schema_name == "{schema_name}" && table_name == "{table_name}"')
        collection.flush()

    def clear_schemas_collection(self):
        if not self._connected:
            return
        self._ensure_schema_collection()
        if not utility.has_collection(settings.MILVUS_COLLECTION_SCHEMA):
            return
        collection = Collection(settings.MILVUS_COLLECTION_SCHEMA)
        # Ensure collection is loaded before delete
        try:
            collection.load()
        except Exception:
            pass
        collection.delete("id >= 0")
        collection.flush()

    def clear_schemas_v2_collection(self):
        if not self._connected:
            return
        self._ensure_schema_v2_collection()
        if not utility.has_collection(settings.MILVUS_COLLECTION_SCHEMA_V2):
            return
        collection = Collection(settings.MILVUS_COLLECTION_SCHEMA_V2)
        try:
            collection.load()
        except Exception:
            pass
        collection.delete("id >= 0")
        collection.flush()

    # --- Schema V2 (Multi-Source) Methods ---

    def insert_data_object_v2(self, data_object: DataObject, text_for_embedding: str):
        """
        Insert a data object (table, view, SP, function) into schema_index_v2.
        
        Args:
            data_object: DataObject with all metadata
            text_for_embedding: Text to generate embedding from (usually description + object name)
        """
        if not self._connected:
            raise Exception("Milvus is not connected. Cannot insert data object.")
        self._ensure_schema_v2_collection()
        collection = Collection(settings.MILVUS_COLLECTION_SCHEMA_V2)
        try:
            collection.load()
        except Exception:
            pass
        
        # Delete existing object to avoid duplicates
        if data_object.source_id:
            collection.delete(
                f'object_name == "{data_object.object_name}" && '
                f'schema_name == "{data_object.schema_name}" && '
                f'source_guid == "{data_object.source_id}"'
            )
        
        # Generate embedding
        embedding = self._get_embedding(text_for_embedding)
        
        # Prepare data for insertion
        # Schema: [embedding], [source_guid], [schema_name], [object_name], [object_type], [description], [definition], [return_type]
        data = [
            [embedding],
            [data_object.source_id or ""],
            [data_object.schema_name],
            [data_object.object_name],
            [data_object.object_type.value],
            [data_object.description or ""],
            [data_object.definition or ""],
            [data_object.return_type or ""]
        ]
        
        collection.insert(data)
        collection.flush()

    def get_all_objects_v2(self, source_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Retrieve all objects from schema_index_v2, optionally filtered by source_id.
        
        Args:
            source_id: Optional source ID to filter by
            
        Returns:
            List of data objects with metadata
        """
        if not self._connected:
            return []
        if not utility.has_collection(settings.MILVUS_COLLECTION_SCHEMA_V2):
            return []
        
        collection = Collection(settings.MILVUS_COLLECTION_SCHEMA_V2)
        collection.load()
        
        # Build filter expression
        expr = "id >= 0"
        if source_id:
            expr = f'source_guid == "{source_id}"'
        
        res = collection.query(
            expr=expr,
            output_fields=["id", "source_guid", "schema_name", "object_name", "object_type", "description", "definition", "return_type"],
            limit=10000,
            consistency_level="Strong"
        )
        return res

    def search_objects_v2(self, query: str, top_k: int = 5, source_id: Optional[str] = None, object_types: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Semantic search for data objects in schema_index_v2.
        
        Args:
            query: Natural language query
            top_k: Number of results to return
            source_id: Optional source filter
            object_types: Optional list of object types to filter by
            
        Returns:
            List of matching data objects with similarity scores
        """
        if not self._connected:
            return []
        if not utility.has_collection(settings.MILVUS_COLLECTION_SCHEMA_V2):
            return []
        
        embedding = self._get_embedding(query)
        collection = Collection(settings.MILVUS_COLLECTION_SCHEMA_V2)
        collection.load()
        
        search_params = {
            "metric_type": "L2",
            "params": {"nprobe": 64}
        }
        
        # Build filter expression
        filter_parts = []
        if source_id:
            filter_parts.append(f'source_guid == "{source_id}"')
        if object_types:
            types_str = ', '.join([f'"{t}"' for t in object_types])
            filter_parts.append(f'object_type in [{types_str}]')
        
        filter_expr = " && ".join(filter_parts) if filter_parts else None
        
        results = collection.search(
            data=[embedding],
            anns_field="embedding",
            param=search_params,
            limit=top_k,
            expr=filter_expr,
            output_fields=["source_guid", "schema_name", "object_name", "object_type", "description", "definition", "return_type"]
        )
        
        retrieved_items = []
        for hits in results:
            for hit in hits:
                if hit.score <= 1.5:  # Moderate relevance threshold
                    item = hit.entity.to_dict()
                    item['score'] = hit.score
                    retrieved_items.append(item)
        
        return retrieved_items

    def delete_data_object_v2(self, source_id: str, schema_name: str, object_name: str):
        """Delete a specific data object from schema_index_v2."""
        if not self._connected:
            raise Exception("Milvus is not connected. Cannot delete object.")
        if not utility.has_collection(settings.MILVUS_COLLECTION_SCHEMA_V2):
            raise Exception(f"Collection {settings.MILVUS_COLLECTION_SCHEMA_V2} does not exist")
        
        collection = Collection(settings.MILVUS_COLLECTION_SCHEMA_V2)
        collection.load()
        
        collection.delete(
            f'source_guid == "{source_id}" && '
            f'schema_name == "{schema_name}" && '
            f'object_name == "{object_name}"'
        )
        collection.flush()

    def clear_source_objects_v2(self, source_id: str):
        """Remove all objects for a specific data source from schema_index_v2."""
        if not self._connected:
            return
        if not utility.has_collection(settings.MILVUS_COLLECTION_SCHEMA_V2):
            return
        
        collection = Collection(settings.MILVUS_COLLECTION_SCHEMA_V2)
        try:
            collection.load()
        except Exception:
            pass
        
        collection.delete(f'source_guid == "{source_id}"')
        collection.flush()

    def get_all_fewshots(self) -> List[Dict[str, Any]]:
        if not self._connected:
            return []
        if not utility.has_collection(settings.MILVUS_COLLECTION_FEWSHOT):
            return []
        collection = Collection(settings.MILVUS_COLLECTION_FEWSHOT)
        collection.load()
        
        res = collection.query(
            expr="id >= 0",
            output_fields=["id", "question", "sql_query", "knowledge_type", "source_guid"],
            limit=1000,
            consistency_level="Strong"
        )
        return res

    def insert_fewshot_item(self, question: str, sql_query: str, knowledge_type: str = "sql_query", source_guid: str = None):
        if not self._connected:
            raise Exception("Milvus is not connected. Cannot insert fewshot item.")
        self._ensure_fewshot_collection()
        collection = Collection(settings.MILVUS_COLLECTION_FEWSHOT)
        
        embedding = self._get_embedding(question)
        
        resolved_source_guid = source_guid or self._resolve_default_source_guid()
        
        # Schema: [embedding], [source_guid], [question], [sql_query], [knowledge_type]
        data = [
            [embedding],
            [resolved_source_guid],
            [question],
            [sql_query],
            [knowledge_type]
        ]
        
        collection.insert(data)
        collection.flush()
        
    def delete_fewshot_item(self, item_id: int):
        if not self._connected:
            return
        if not utility.has_collection(settings.MILVUS_COLLECTION_FEWSHOT):
            return
        collection = Collection(settings.MILVUS_COLLECTION_FEWSHOT)
        collection.load()
        # Use string expression for deletion
        expr = f"id in [{item_id}]"
        collection.delete(expr)
        collection.flush()
        # Release and reload to ensure consistency
        collection.release()
        collection.load()

    # --- Value Index Implementation ---
    
    def get_all_values(self) -> List[Dict[str, Any]]:
        if not self._connected:
            return []
        self._ensure_values_collection()
        if not utility.has_collection(settings.MILVUS_COLLECTION_VALUES):
            return []
        collection = Collection(settings.MILVUS_COLLECTION_VALUES)
        collection.load()
        
        res = collection.query(
            expr="id >= 0",
            output_fields=["id", "value", "schema_name", "table_name", "column_name", "source_guid"],
            limit=10000,
            consistency_level="Strong"
        )
        return res
    
    def insert_value_item(self, value: str, schema_name: str, table_name: str, column_name: str, metadata: dict = None, source_guid: str = None):
        if not self._connected:
            raise Exception("Milvus is not connected. Cannot insert value item.")
        self._ensure_values_collection()
        collection = Collection(settings.MILVUS_COLLECTION_VALUES)
        
        embedding = self._get_embedding(value)
        
        if metadata is None:
            metadata = {}
        
        resolved_source_guid = source_guid or self._resolve_default_source_guid()
        
        # Schema: [embedding], [source_guid], [value], [plain_value], [schema_name], [table_name], [column_name]
        data = [
            [embedding],
            [resolved_source_guid],
            [value],
            [value.lower()],  # Store lowercase for case-insensitive search
            [schema_name],
            [table_name],
            [column_name]
        ]
        
        collection.insert(data)
        collection.flush()
    
    def insert_value_items_batch(self, items: List[Dict[str, Any]], source_guid: str = None):
        if not items:
            return
        if not self._connected:
            raise Exception("Milvus is not connected. Cannot insert value items.")

        self._ensure_values_collection()
        collection = Collection(settings.MILVUS_COLLECTION_VALUES)
        
        # Extract values for embedding
        values = [str(item['value']) for item in items]
        
        # Get embeddings in batch
        embeddings = self._get_embeddings_batch(values)
        
        # Prepare data columns
        # Schema: [embedding], [source_guid], [value], [plain_value], [schema_name], [table_name], [column_name]
        resolved_source_guid = source_guid or self._resolve_default_source_guid()
        col_embeddings = embeddings
        col_source_guids = [resolved_source_guid] * len(items)
        col_values = values
        col_plain_values = [v.lower() for v in values]
        col_schema_names = [str(item['schema_name']) for item in items]
        col_table_names = [str(item['table_name']) for item in items]
        col_column_names = [str(item['column_name']) for item in items]
        
        data = [
            col_embeddings,
            col_source_guids,
            col_values,
            col_plain_values,
            col_schema_names,
            col_table_names,
            col_column_names
        ]
        
        collection.insert(data)
        collection.flush()
    
    def delete_value_item(self, item_id: int):
        if not self._connected:
            return
        self._ensure_values_collection()
        if not utility.has_collection(settings.MILVUS_COLLECTION_VALUES):
            return
        collection = Collection(settings.MILVUS_COLLECTION_VALUES)
        collection.delete(f"id == {item_id}")
        collection.flush()
    
    def clear_values_collection(self):
        if not self._connected:
            return
        self._ensure_values_collection()
        if not utility.has_collection(settings.MILVUS_COLLECTION_VALUES):
            return
        collection = Collection(settings.MILVUS_COLLECTION_VALUES)
        # Ensure collection is loaded before delete
        try:
            collection.load()
        except Exception:
            pass
        collection.delete("id >= 0")
        collection.flush()

    def clear_fewshots_collection(self):
        if not self._connected:
            return
        self._ensure_fewshot_collection()
        if not utility.has_collection(settings.MILVUS_COLLECTION_FEWSHOT):
            return
        collection = Collection(settings.MILVUS_COLLECTION_FEWSHOT)
        try:
            collection.load()
        except Exception:
            pass
        collection.delete("id >= 0")
        collection.flush()

    # --- Contribution Library Implementation ---
    
    def _ensure_contributions_collection(self):
        """Ensure the contributions collection exists with proper schema."""
        if not self._connected:
            return
        try:
            if utility.has_collection(settings.MILVUS_COLLECTION_CONTRIBUTIONS):
                existing = Collection(settings.MILVUS_COLLECTION_CONTRIBUTIONS)
                field_names = [f.name for f in existing.schema.fields]
                if "knowledge_type" in field_names:
                    return
                # Recreate if schema is outdated
                utility.drop_collection(settings.MILVUS_COLLECTION_CONTRIBUTIONS)
            
            contrib_fields = [
                FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
                FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self._embedding_dim),
                FieldSchema(name="question", dtype=DataType.VARCHAR, max_length=2048),
                FieldSchema(name="sql_query", dtype=DataType.VARCHAR, max_length=4096),
                FieldSchema(name="knowledge_type", dtype=DataType.VARCHAR, max_length=32),
                FieldSchema(name="user_id", dtype=DataType.VARCHAR, max_length=128),
                FieldSchema(name="submitted_at", dtype=DataType.VARCHAR, max_length=64),
                FieldSchema(name="status", dtype=DataType.VARCHAR, max_length=32)
            ]
            contrib_schema = CollectionSchema(fields=contrib_fields, description="Contribution Library - Staging Area")
            coll = Collection(name=settings.MILVUS_COLLECTION_CONTRIBUTIONS, schema=contrib_schema)
            index_params = {
                "metric_type": "L2",
                "index_type": "IVF_FLAT",
                "params": {"nlist": 1024}
            }
            coll.create_index(field_name="embedding", index_params=index_params)
            coll.flush()
            print(f"Created/updated collection: {settings.MILVUS_COLLECTION_CONTRIBUTIONS}")
        except Exception as e:
            print(f"Failed to ensure contributions collection: {e}")
    
    def get_all_contributions(self) -> List[Dict[str, Any]]:
        if not self._connected:
            return []
        self._ensure_contributions_collection()
        if not utility.has_collection(settings.MILVUS_COLLECTION_CONTRIBUTIONS):
            return []
        collection = Collection(settings.MILVUS_COLLECTION_CONTRIBUTIONS)
        collection.load()
        
        res = collection.query(
            expr="id >= 0",
            output_fields=["id", "question", "sql_query", "knowledge_type", "user_id", "submitted_at", "status"],
            limit=1000,
            consistency_level="Strong"
        )
        return res
    
    def insert_contribution(self, question: str, sql_query: str, knowledge_type: str = "sql_query", user_id: str = None) -> int:
        from datetime import datetime
        
        if not self._connected:
            raise Exception("Milvus is not connected. Cannot insert contribution.")
        self._ensure_contributions_collection()
        collection = Collection(settings.MILVUS_COLLECTION_CONTRIBUTIONS)
        
        embedding = self._get_embedding(question)
        submitted_at = datetime.now().isoformat()
        
        data = [
            [embedding],
            [question],
            [sql_query],
            [knowledge_type],
            [user_id or "anonymous"],
            [submitted_at],
            ["pending"]
        ]
        
        result = collection.insert(data)
        collection.flush()
        
        # Return the inserted ID
        if result.primary_keys:
            return result.primary_keys[0]
        return -1
    
    def delete_contribution(self, contribution_id: int):
        if not self._connected:
            return
        self._ensure_contributions_collection()
        if not utility.has_collection(settings.MILVUS_COLLECTION_CONTRIBUTIONS):
            return
        collection = Collection(settings.MILVUS_COLLECTION_CONTRIBUTIONS)
        collection.load()
        expr = f"id in [{contribution_id}]"
        collection.delete(expr)
        collection.flush()
        # Release and reload to ensure consistency
        collection.release()
        collection.load()
    

    def check_similarity(self, question: str, threshold: float = 0.9, knowledge_type: Optional[str] = None) -> tuple:
        """
        Check if similar item exists in knowledge base.
        Returns (is_similar, similarity_score, similar_item_id)
        
        Uses L2 distance - lower values mean more similar.
        For normalized embeddings: 0 = identical, 0.5 = very similar, 1.0 = similar
        """
        if not self._connected:
            return (False, 0.0, None)
        if not utility.has_collection(settings.MILVUS_COLLECTION_FEWSHOT):
            return (False, 0.0, None)
        
        embedding = self._get_embedding(question)
        collection = Collection(settings.MILVUS_COLLECTION_FEWSHOT)
        collection.load()
        
        search_params = {
            "metric_type": "L2",
            "params": {"nprobe": 64}
        }
        
        # Build filter expression if knowledge_type is specified
        filter_expr = None
        if knowledge_type:
            filter_expr = f'knowledge_type == "{knowledge_type}"'

        results = collection.search(
            data=[embedding],
            anns_field="embedding",
            param=search_params,
            limit=1,
            expr=filter_expr,
            output_fields=["id", "question", "sql_query", "knowledge_type"]
        )
        
        if not results or not results[0]:
            return (False, 0.0, None)
        
        hit = results[0][0]
        l2_distance = hit.score
        
        # Convert L2 distance to similarity score (0-1, higher = more similar)
        # For normalized embeddings, L2 distance ranges from 0 to 2
        # similarity = 1 - (distance / 2)
        similarity_score = max(0, 1 - (l2_distance / 2))
        
        is_similar = similarity_score >= threshold
        similar_item_id = hit.entity.get('id') if is_similar else None
        
        return (is_similar, similarity_score, similar_item_id)

    def export_all_data(self) -> Dict[str, Any]:
        """Export all vector store data for backup."""
        export_data = {
            "schemas": [],
            "fewshots": [],
            "values": [],
            "contributions": []
        }
        
        if not self._connected:
            return export_data
        
        try:
            # Schemas
            schemas = self.get_all_schemas()
            export_data["schemas"] = [s.model_dump() for s in schemas]
            
            # FewShots
            export_data["fewshots"] = self.get_all_fewshots()
            
            # Values
            export_data["values"] = self.get_all_values()
            
            # Contributions
            export_data["contributions"] = self.get_all_contributions()
            
        except Exception as e:
            print(f"Error during export: {e}")
            raise e
            
        return export_data
    
    def move_contribution_to_knowledge_base(self, contribution_id: int, edited_question: str = None, edited_sql: str = None, knowledge_type: Optional[str] = None) -> int:
        """Move a contribution to the knowledge base and delete from contributions.
        
        Args:
            contribution_id: ID of the contribution to approve
            edited_question: Optional edited question text to use instead of original
            edited_sql: Optional edited SQL query to use instead of original
            knowledge_type: Type of knowledge ("general", "sql_query", "r_code", "sas_code")
        """
        if not self._connected:
            raise Exception("Milvus is not connected. Cannot move contribution.")
        self._ensure_contributions_collection()
        
        # Get the contribution
        contrib_collection = Collection(settings.MILVUS_COLLECTION_CONTRIBUTIONS)
        contrib_collection.load()
        
        res = contrib_collection.query(
            expr=f"id == {contribution_id}",
            output_fields=["question", "sql_query", "knowledge_type"],
            limit=1
        )
        
        if not res:
            raise Exception(f"Contribution {contribution_id} not found")
        
        contribution = res[0]
        # Use edited question/SQL if provided, otherwise use original
        question = edited_question if edited_question else contribution['question']
        sql_query = edited_sql if edited_sql else contribution['sql_query']
        # Prefer explicit knowledge_type, then stored type, then default.
        stored_type = contribution.get('knowledge_type')
        final_type = knowledge_type or stored_type or "sql_query"
        
        # Insert into knowledge base (fewshot collection) with knowledge_type
        self.insert_fewshot_item(question, sql_query, final_type)
        
        # Delete from contributions
        self.delete_contribution(contribution_id)
        
        # Return a placeholder ID (Milvus auto-generates IDs)
        return -1  # We can't easily get the new ID without querying again

class NullVectorStore(VectorStoreBase):
    """
    Safe no-op vector store for deployments without a vector DB.
    Returns empty results and ignores writes.
    """
    def __init__(self):
        self._disabled_message = "Vector store disabled (VECTOR_DB_ENABLED=false)."

    def search_schemas(self, query: str, top_k: int = 5) -> List[TableSchema]:
        return []

    def search_fewshots(self, query: str, top_k: int = 3, knowledge_type: Optional[str] = None) -> List[Dict[str, Any]]:
        return []

    def search_values(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
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

    def clear_schemas_collection(self):
        return None

    def get_all_fewshots(self) -> List[Dict[str, Any]]:
        return []

    def insert_fewshot_item(self, question: str, sql_query: str, knowledge_type: str = "sql_query", source_guid: str = None):
        return None

    def delete_fewshot_item(self, item_id: int):
        return None

    def clear_fewshots_collection(self):
        return None

    def get_all_values(self) -> List[Dict[str, Any]]:
        return []

    def insert_value_item(self, value: str, schema_name: str, table_name: str, column_name: str, metadata: dict = None, source_guid: str = None):
        return None

    def insert_value_items_batch(self, items: List[Dict[str, Any]], source_guid: str = None):
        return None

    def delete_value_item(self, item_id: int):
        return None

    def clear_values_collection(self):
        return None

    def get_all_contributions(self) -> List[Dict[str, Any]]:
        return []

    def insert_contribution(self, question: str, sql_query: str, knowledge_type: str = "sql_query", user_id: str = None) -> int:
        return -1

    def delete_contribution(self, contribution_id: int):
        return None

    def check_similarity(self, question: str, threshold: float = 0.9, knowledge_type: Optional[str] = None) -> tuple:
        return (False, 0.0, None)

    def move_contribution_to_knowledge_base(self, contribution_id: int, edited_question: str = None, edited_sql: str = None, knowledge_type: Optional[str] = None) -> int:
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
        _vector_store_instance = MilvusVectorStore()
    return _vector_store_instance


def refresh_vector_store() -> VectorStoreBase:
    global _vector_store_instance
    _vector_store_instance = None
    return get_vector_store()
