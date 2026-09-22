# Vector Database Schema

This is the canonical contract for the agent's vector index. The source of truth is `app/services/stores/schema_contracts.py`. Schema version: `VECTOR_SCHEMA_VERSION` = `1.1.0`.

Related documents:

- [AGENT_PROCESS.md](AGENT_PROCESS.md) — how these collections are used at request time
- [DISCOVERY_STRATEGY_IMPLEMENTATION.md](DISCOVERY_STRATEGY_IMPLEMENTATION.md) — ranking and branches
- [VALUE_INDEX_FEATURE.md](VALUE_INDEX_FEATURE.md) — admin upload of categorical values

---

## 1. Design rules

1. **One logical schema, two physical layouts.** Milvus and SQLite implement the same collection names and contract fields. `VECTOR_PROVIDER=milvus` is the default; if Milvus is unreachable the factory falls back to SQLite. Milvus also adds `pk` and, on non-single-vector collections, `_pad_vector` (section 4).
2. **Every row is partitioned by `data_source_id`.** That is the only contract field added versus the built-in desktop engine. SQLite uniqueness is `PRIMARY KEY (data_source_id, …natural key…)`. Milvus uniqueness is the synthetic `pk` string.
3. **Cosine metric.** Vector search uses cosine. Runtime scores are exposed as cosine **distance** (`_distance`) unless a helper converts them to similarity.
4. **Embeddings are 1536-d** (`text-embedding-3-small` by default). The text that is embedded is defined per collection below.
5. **Do not invent collection names.** Legacy names (`schema_index`, `fewshot_index`, `schemas_v2`) are not part of this contract.

---

## 2. Providers and isolation

```
request.source_id
        │
        ▼
build_source_stores(source_id)
        │
        ├── SchemaIndexService
        ├── VectorSearchService      → collection "schemas"
        ├── FewShotVectorService     → "few_shots"
        ├── ValueIndexService        → "value_index"
        ├── PrecomputedQueryStore    → "vec_data_group_queries" (+ cache)
        ├── DataGroupStore           → "data_group_*"
        ├── SemanticModelService     → "semantic_*"
        └── Bm25Service              (in-memory, optional)
```

`get_vector_provider()` (`app/services/stores/provider_factory.py`) returns a cached Milvus or SQLite adapter. Both call `ensure_schema()` from `COLLECTIONS`.

Rebuild / wipe scripts must drop **contract** collections only (`MilvusProvider.drop_all_collections` skips unknown/legacy names).

---

## 3. Collection catalog

| Collection | Kind | Used at query time | Purpose |
|---|---|---|---|
| `schemas` | vector | Yes | Table / view / function **and** column entities |
| `few_shots` | vector | Yes | Knowledge-base Q→SQL examples (vector search **and** deterministic exact-question lookup) |
| `value_index` | vector | Yes (substring on `plain_value`) | Categorical value → table.column |
| `contribution_library` | scalar | Admin | User-submitted examples pending review |
| `data_group_metadata` | scalar | Yes | Business groups, keywords, members |
| `data_group_vectors_cache` | json_vector | Yes | Cached group embeddings (JSON). This is what `DataGroupStore.search` reads |
| `data_group_vectors_map` | scalar | No | SQLite helper: `group_id` → `vec_rowid` |
| `data_group_vectors_vec0` | vector | No | Built-in / SQLite-vec parity (three native vectors). Runtime search does **not** read this table |
| `vec_data_group_queries` | scalar | Yes | Precomputed approved Q→SQL (and optional SMQ) |
| `vec_data_group_query_vectors_cache` | json_vector | Yes | Cached question vectors for precomputed search |
| `embedding_cache` | scalar | Yes | L2 embedding cache keyed by text hash |
| `semantic_models` | scalar | Semantic mode | Active model registry |
| `semantic_measures` | scalar | Semantic mode | Measure name / expression |
| `semantic_dimensions` | scalar | Semantic mode | Dimension → table.column |
| `semantic_joins` | scalar | Semantic mode | Model join graph |
| `semantic_governance_predicates` | scalar | Semantic mode | Row-level predicates |
| `semantic_embeddings` | json_vector | Semantic mode | Model embedding for retrieval |

Runtime connectivity checks require these collections to exist: `schemas`, `few_shots`, `value_index`, `contribution_library` (`RUNTIME_VECTOR_COLLECTIONS`). `few_shots_meta` is retired (`RETIRED_COLLECTIONS`) and is dropped on `ensure_schema` / first few-shot service use.

---

## 4. Field specifications

Source of truth: `COLLECTIONS` in `schema_contracts.py`. Every spec starts with `data_source_id TEXT NOT NULL`. A collection without that column is stale (see [the migration plan](plans/2026-09-12-milvus-data-source-id.md)).

**SQLite physical types**

- Contract `TEXT` → `TEXT`
- Contract `INTEGER` → `INTEGER`
- Contract `FLOAT_VECTOR` → `BLOB`
- Primary key is `PRIMARY KEY (data_source_id, …unique_with_source)` except `data_group_vectors_vec0` (`rowid INTEGER PRIMARY KEY`) and `semantic_governance_predicates` (no declared PK)

**Milvus physical extras** (not in the contract list, added by `MilvusProvider.ensure_schema`)

- `pk` VARCHAR(1024), primary key: `data_source_id|natural_key` (see `row_pk()`)
- `data_source_id` VARCHAR(128), `is_partition_key=True`
- Contract `TEXT` → VARCHAR(65535); `INTEGER` → INT64
- A collection may store **one** native `FLOAT_VECTOR`. That applies only when `kind == "vector"` and there is exactly one vector field (`schemas`, `few_shots`, `value_index`)
- All other collections get `_pad_vector` FLOAT_VECTOR(2). Extra / JSON vectors are stored as VARCHAR (JSON array text)
- `rowid` is omitted on Milvus (`data_group_vectors_vec0`)

Types below are the **contract** types. Constraints match `FieldSpec`.

### 4.1 `schemas`

Unified object **and** column index. SQLite PK: `(data_source_id, key)`.

| Field | Type | Constraints | Notes |
|---|---|---|---|
| `data_source_id` | TEXT | NOT NULL | Partition / source scope |
| `key` | TEXT | unique with source | See keys below |
| `schema_name` | TEXT | | e.g. `dbo` |
| `object_name` | TEXT | | Parent table / view / function |
| `object_type` | TEXT | | `Table`, `View`, or `Function` |
| `entity_type` | TEXT | | Parent: same as `object_type`. Column: `Column` |
| `column_name` | TEXT | | Empty string on parent rows |
| `description` | TEXT | | Embedding source text (not raw markdown) |
| `vector` | FLOAT_VECTOR(1536) | | Embedded `description`. Native vector on Milvus |

**Keys** (`schema_object_key`):

- Parent: `[source_id].[schema].[object]`
- Column: `[source_id].[schema].[object].[column]`

**Embedding text** (written at ingest, `schema_rows.py`):

```
Parent:  Entity: {Table|View|Function} | Name: {object} | Description: {desc}
Column:  Entity: Column | Table: {object} | Name: {column} | Type: {type} | Description: {desc} [| Values: {vals}]
```

Search:

- `VectorSearchService.search_objects()` embeds the user query, searches `schemas`, then **rolls column hits up** to the parent object and records `matched_columns`.
- `search_columns_scored()` filters `entity_type == "Column"`.
- Hits below `OBJECT_SEARCH_VECTOR_SCORE_THRESHOLD` (default 0.50, clamped `[0, 1]`) are dropped.

### 4.2 `few_shots`

SQLite PK: `(data_source_id, key)`. This is the single authoritative KB store. Exact match scans the scalar columns with `question_lookup_key()` (vector-free: no `search_vector` / no `vec0`). Vector search uses the same rows with max cosine distance `KbScoreThreshold` (0.35). Distance ≤ 0.05 is treated as exact.

There is no shadow table. `few_shots_meta` was a duplicate of these scalars and is dropped on first use.

| `few_shots` field | Type | Constraints | Notes |
|---|---|---|---|
| `data_source_id` | TEXT | NOT NULL | Partition |
| `key` | TEXT | unique with source | Identity; edits keep this key |
| `question` | TEXT | | Embedded text; also the exact-match source |
| `sql` | TEXT | | Field name is `sql`, not `sql_query`. Empty SQL is skipped by exact match |
| `created_at_utc` | TEXT | | Preserved across content edits |
| `vector` | FLOAT_VECTOR(1536) | | Native vector on Milvus |

Milvus: `few_shots` has a native `vector`.

### 4.3 `value_index`

SQLite PK: `(data_source_id, key)`.

| Field | Type | Constraints | Notes |
|---|---|---|---|
| `data_source_id` | TEXT | NOT NULL | Partition |
| `key` | TEXT | unique with source | |
| `value` | TEXT | | Original display value (embedded) |
| `plain_value` | TEXT | | Lowercased copy used for lookup |
| `schema_name` | TEXT | | |
| `table_name` | TEXT | | |
| `column_name` | TEXT | | |
| `vector` | FLOAT_VECTOR(1536) | | Native vector on Milvus; stored for parity. **Query-time lookup is substring on `plain_value`**, not a vector search |

Discovery seeds parent tables from those hits (`ColumnDetailValueSeedScore = 0.80`) and injects `value → table.column` mappings into the prompt.

### 4.4 `contribution_library`

Scalar review queue. SQLite PK: `(data_source_id, key)`. Milvus uses `_pad_vector`.

| Field | Type | Constraints | Notes |
|---|---|---|---|
| `data_source_id` | TEXT | NOT NULL | Partition |
| `key` | TEXT | unique with source | |
| `question` | TEXT | NOT NULL | |
| `sql_query` | TEXT | NOT NULL | Field name is `sql_query` (not `sql`) |
| `knowledge_type` | TEXT | NOT NULL | e.g. `sql_query` |
| `user_id` | TEXT | | |
| `submitted_at` | TEXT | | |
| `status` | TEXT | NOT NULL | |

### 4.5 Data groups

Runtime search reads `data_group_metadata` + `data_group_vectors_cache` (top 3). Member object names become the `data_group` RRF list (weight 2.0). `data_group_vectors_vec0` / `data_group_vectors_map` are contract/parity tables; `DataGroupStore` does not read them.

#### `data_group_metadata`

SQLite PK: `(data_source_id, group_id)`.

| Field | Type | Constraints | Notes |
|---|---|---|---|
| `data_source_id` | TEXT | NOT NULL | Partition |
| `group_id` | TEXT | unique with source | Typically `[source_id].[group_name]` |
| `group_name` | TEXT | NOT NULL | |
| `description` | TEXT | NOT NULL | Embedded for the semantic cache vector |
| `keywords_json` | TEXT | NOT NULL | JSON string array |
| `members_json` | TEXT | NOT NULL | JSON string array of `schema.object` names |
| `updated_at_utc` | TEXT | NOT NULL | |

#### `data_group_vectors_cache`

SQLite PK: `(data_source_id, group_id)`. Kind `json_vector`: vectors are JSON text, not native FLOAT_VECTOR. Milvus adds `_pad_vector`.

| Field | Type | Constraints | Notes |
|---|---|---|---|
| `data_source_id` | TEXT | NOT NULL | Partition |
| `group_id` | TEXT | unique with source | |
| `semantic_vector_json` | TEXT | NOT NULL | JSON float array (1536) |
| `functional_vector_json` | TEXT | NOT NULL | From keywords |
| `object_vector_json` | TEXT | NOT NULL | From member names |
| `updated_at_utc` | TEXT | NOT NULL | |

#### `data_group_vectors_map`

SQLite PK: `(data_source_id, group_id)`.

| Field | Type | Constraints | Notes |
|---|---|---|---|
| `data_source_id` | TEXT | NOT NULL | Partition |
| `group_id` | TEXT | unique with source | |
| `vec_rowid` | INTEGER | NOT NULL | Points at `data_group_vectors_vec0.rowid` |

#### `data_group_vectors_vec0`

SQLite PK: `rowid`. No `unique_with_source`. On Milvus, `rowid` is dropped, the three vectors are stored as VARCHAR JSON (standalone can index only one native vector), and `_pad_vector` is added.

| Field | Type | Constraints | Notes |
|---|---|---|---|
| `data_source_id` | TEXT | NOT NULL | Partition |
| `rowid` | INTEGER | SQLite PK | Omitted on Milvus |
| `semantic_vector` | FLOAT_VECTOR(1536) | | Native only on SQLite BLOB |
| `functional_vector` | FLOAT_VECTOR(1536) | | |
| `object_vector` | FLOAT_VECTOR(1536) | | |

### 4.6 Precomputed data-group queries

Thresholds (cosine **similarity**, admin-tunable): direct / exact exit ≥ 0.93; few-shot injection ≥ 0.82 (`precomputed_related/<branch>`); top-K 3.

#### `vec_data_group_queries`

SQLite PK: `(data_source_id, query_id)`.

| Field | Type | Constraints | Notes |
|---|---|---|---|
| `data_source_id` | TEXT | NOT NULL | Partition |
| `query_id` | TEXT | unique with source | |
| `group_name` | TEXT | NOT NULL | |
| `group_file_name` | TEXT | NOT NULL | |
| `question` | TEXT | NOT NULL | Exact path matches canonical question key |
| `sql_query` | TEXT | NOT NULL | |
| `smq_query` | TEXT | DEFAULT `''` | Optional semantic-model JSON |
| `status` | TEXT | NOT NULL | Exact path accepts `Approved` or `Modified`; vector search uses `Approved` |
| `updated_at_utc` | TEXT | NOT NULL | |

#### `vec_data_group_query_vectors_cache`

SQLite PK: `(data_source_id, query_id)`. Kind `json_vector`. Milvus adds `_pad_vector`.

| Field | Type | Constraints | Notes |
|---|---|---|---|
| `data_source_id` | TEXT | NOT NULL | Partition |
| `query_id` | TEXT | unique with source | |
| `question_vector_json` | TEXT | NOT NULL | JSON float array used for cosine similarity |
| `updated_at_utc` | TEXT | NOT NULL | |

### 4.7 `embedding_cache`

SQLite PK: `(data_source_id, text_hash)`. L1 (in-process) size 512; L2 (this table) size 10,000 with batch eviction of 1,000.

| Field | Type | Constraints | Notes |
|---|---|---|---|
| `data_source_id` | TEXT | NOT NULL | Partition |
| `text_hash` | TEXT | unique with source | Hash of the embedded text |
| `text_content` | TEXT | NOT NULL | |
| `embedding_json` | TEXT | NOT NULL | JSON float array |
| `embedding_model` | TEXT | NOT NULL | |
| `created_at_utc` | TEXT | NOT NULL | |
| `last_accessed_utc` | TEXT | NOT NULL | LRU key |
| `access_count` | INTEGER | DEFAULT `1` | |

### 4.8 Semantic layer

Enabled per source via `ENABLE_SEMANTIC_LAYER_PER_DATA_SOURCE` or the request `semantic_mode` flag. Disabled automatically for Python / R / SAS.

Embedding source (`semantic_embedding_source`):

```
{label} | measure({name}:{desc}:{expr}) … | dimension({name}:{desc}:{table}.{column}) … | governance({pred}) …
```

#### `semantic_models`

SQLite PK: `(data_source_id, model_id)`.

| Field | Type | Constraints | Notes |
|---|---|---|---|
| `data_source_id` | TEXT | NOT NULL | Partition |
| `model_id` | TEXT | unique with source | |
| `label` | TEXT | NOT NULL | |
| `is_active` | INTEGER | NOT NULL, DEFAULT `1` | |
| `updated_at_utc` | TEXT | NOT NULL | |

#### `semantic_measures`

SQLite PK: `(data_source_id, model_id, measure_name)`.

| Field | Type | Constraints | Notes |
|---|---|---|---|
| `data_source_id` | TEXT | NOT NULL | Partition |
| `model_id` | TEXT | NOT NULL | |
| `measure_name` | TEXT | NOT NULL | |
| `expression` | TEXT | NOT NULL | |
| `description` | TEXT | NOT NULL | |

#### `semantic_dimensions`

SQLite PK: `(data_source_id, model_id, dimension_name)`.

| Field | Type | Constraints | Notes |
|---|---|---|---|
| `data_source_id` | TEXT | NOT NULL | Partition |
| `model_id` | TEXT | NOT NULL | |
| `dimension_name` | TEXT | NOT NULL | |
| `column_name` | TEXT | NOT NULL | |
| `table_name` | TEXT | NOT NULL | |
| `description` | TEXT | NOT NULL | |

#### `semantic_joins`

SQLite PK: `(data_source_id, model_id, from_table, to_table, join_expression)`.

| Field | Type | Constraints | Notes |
|---|---|---|---|
| `data_source_id` | TEXT | NOT NULL | Partition |
| `model_id` | TEXT | NOT NULL | |
| `from_table` | TEXT | NOT NULL | |
| `to_table` | TEXT | NOT NULL | |
| `join_expression` | TEXT | NOT NULL | |
| `join_type` | TEXT | NOT NULL | e.g. `INNER` |

#### `semantic_governance_predicates`

No `unique_with_source` and no contract primary key. Rows are scoped by `data_source_id` at query time.

| Field | Type | Constraints | Notes |
|---|---|---|---|
| `data_source_id` | TEXT | NOT NULL | Partition |
| `model_id` | TEXT | NOT NULL | |
| `predicate` | TEXT | NOT NULL | |
| `description` | TEXT | DEFAULT `''` | |

#### `semantic_embeddings`

SQLite PK: `(data_source_id, model_id)`. Kind `json_vector`. Milvus adds `_pad_vector`.

| Field | Type | Constraints | Notes |
|---|---|---|---|
| `data_source_id` | TEXT | NOT NULL | Partition |
| `model_id` | TEXT | unique with source | |
| `embedding_json` | TEXT | NOT NULL | JSON float array of `semantic_embedding_source` |
| `updated_at_utc` | TEXT | NOT NULL | |

---

## 5. Ingest path

Parent + column rows are built by `build_schema_object_rows()`:

1. Normalize `object_type` to `Table` / `View` / `Function`.
2. Embed parent text → one `schemas` row with `entity_type` = object type.
3. For each column, embed column text → one `schemas` row with `entity_type=Column`.

Skills-folder markdown (`app/services/stores/skills_folder.py`) is the preferred description source at **hydration** time. The vector `description` field is the embedding payload, not the full markdown file.

Deleting an object removes every `schemas` row with that `(schema_name, object_name)` for the source.

---

## 6. How discovery reads the index

```
User question
    │
    ├─ few_shots / vec_data_group_queries          exact key match → exit
    ├─ few_shots                                   vector KB (distance)
    ├─ schemas (Table/View/Function + Column)      object + column evidence
    ├─ value_index.plain_value                     filter-value seeds
    ├─ data_group_*                                group members (RRF weight 2)
    ├─ vec_data_group_query_vectors_cache          related few-shots
    └─ BM25 (optional)                             lexical rerank of schema hits
```

RRF merge and branch labels are documented in [AGENT_PROCESS.md](AGENT_PROCESS.md#63-discovery-branches).

---

## 7. Configuration

```env
VECTOR_PROVIDER=milvus          # or sqlite / sqlite_vec
VECTOR_HOST=localhost
VECTOR_PORT=19630
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSIONS=1536

MILVUS_COLLECTION_SCHEMA=schemas
MILVUS_COLLECTION_FEWSHOT=few_shots
MILVUS_COLLECTION_VALUES=value_index
MILVUS_COLLECTION_CONTRIBUTIONS=contribution_library

OBJECT_SEARCH_VECTOR_SCORE_THRESHOLD=0.5
PRECOMPUTED_QUERY_DIRECT_MATCH_THRESHOLD=0.93
PRECOMPUTED_QUERY_FEW_SHOT_THRESHOLD=0.82
ENABLE_BM25_RETRIEVAL=false
ENABLE_SEMANTIC_LAYER_PER_DATA_SOURCE={}
```

Changing field lists requires updating `schema_contracts.py`, both providers, ingest (`schema_rows.py` / skills folder), and `tests/unit/test_schema_contract.py`. Do not edit only `vector_store.py` or only `ingest_service.py`.

---

## 8. Legacy names (removed)

| Old name | Current name |
|---|---|
| `schema_index` | `schemas` (parent + column entities) |
| `fewshot_index` | `few_shots` (exact + vector; `few_shots_meta` removed) |
| `schemas_v2` | `schemas` |
| Separate column collection | `schemas.entity_type = Column` |
