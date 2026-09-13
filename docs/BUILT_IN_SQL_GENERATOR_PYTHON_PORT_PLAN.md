# BuiltInSqlGenerator → Octofy Agent (Python/FastAPI) Port Plan

## Document Intent

This document is the **authoritative implementation blueprint** for delivering the business logic of the built-in Octofy SQL generator (`Octofy.Agent.AI.BuiltIn.BuiltInSqlGenerator`) to the **Octofy Agent**: the enterprise FastAPI service that Octofy Pro and third-party clients reach **through the backend API** (`octofy-ai-agent-backend-api.md`) for enterprise-level agent access.

The goal is not "similar output." The goal is **process parity in two planes**:

1. **Behavior parity** with the built-in engine — the same routing decisions, short-circuit conditions, discovery branch behavior, retry and recovery semantics, validation ordering, and failure packaging that `BUILT_IN_SQL_GENERATOR.md` documents for `GenerateAsync`.
2. **Transport parity** with the API contract — every pipeline stage surfaces over the documented HTTP/SSE surface (status events, result payload parity fields, structured `failure_report` payloads), and every data-touching operation is scoped by the `source_id` the Octofy Agent uses to select among the many data sources it hosts.

### Why a separate port is needed

- The **built-in agent** runs in-process inside Octofy Pro. One agent instance = one data source; it owns a local `vector-index.db` and a schema-library folder under `SchemaDataDirectory`, so no data-source identifier ever appears in its API.
- The **Octofy Agent** is **one service hosting many data sources**. A single FastAPI deployment serves an arbitrary set of registered sources, each with its own server-side schema library, vector store, few-shot knowledge base, value index, precomputed data-group queries, data groups, and semantic models. Every request must therefore name the target source — this plan threads `source_id` through every layer the way a built-in agent implicitly targets its one source.

Use this file as a machine-executable planning artifact for AI coding tools implementing the Octofy Agent backend.

---

## 1) Source of Truth and Scope

### Behavioral source of truth (read these first)
- `Octofy.Agent/Docs/BUILT_IN_SQL_GENERATOR.md` — the maintained review document describing the current `GenerateAsync` pipeline, discovery subsystem, validation stack, semantic layer, constants, branch taxonomy, and key behavioral changes. **When this plan and that document disagree, that document (and the C# code it reviews) wins.**
- `OctofyPro/Docs/plans/octofy-ai-agent-backend-api.md` — the transport contract this port must serve (routes, `source_id` scoping, SSE envelope, result parity fields, failure report shape).
- `OctofyPro/Docs/VECTOR_DATABASE_RAG_SUMMARY.md` — the storage-layer reference this port's vector schema mirrors (collections, side tables, record fields, embedding pipeline, caches, top-K defaults).

### Primary source files (Octofy.Agent, C#)
- `Octofy.Agent/AI/BuiltIn/BuiltInSqlGenerator.cs` (main orchestration)
- `Octofy.Agent/AI/BuiltIn/BuiltInSqlGenerator.Preprocessing.cs` (preprocess, extraction, hydration)
- `Octofy.Agent/AI/BuiltIn/BuiltInSqlGenerator.Router.cs` (route decisions)
- `Octofy.Agent/AI/BuiltIn/BuiltInSqlGenerator.ColumnDiscovery.cs` (column-level discovery extension)
- `Octofy.Agent/AI/BuiltIn/QueryInterceptor.cs` (safety policy)
- `Octofy.Agent/AI/BuiltIn/SqlErrorClassifier.cs` (error taxonomy)
- `Octofy.Agent/AI/BuiltIn/IDatabaseCatalog.cs` (catalog abstraction)
- `Octofy.Agent/AI/BuiltIn/*VectorService*.cs`, `SchemaIndexService.cs`, `SqlContextHydrator.cs`, `ObjectNameResolver.cs`
- `Octofy.Agent/AI/BuiltIn/ToolFunctionInvoker.cs` (shared MCP/sub-agent tool executor)
- `Octofy.Agent/AI/BuiltIn/SemanticModelService.cs`, `SemanticCompiler.cs`, `SemanticModelExtractionService.cs`, `SemanticDataSourceKeyResolver.cs`
- `Octofy.Agent/AI/BuiltIn/FewShotVectorService.cs`, `DataGroupQueryGenerationService.cs`
- `Octofy.Agent/AI/ConversationHistory.cs`, `Octofy.Agent/AI/LlmRequestConventions.cs`, `Octofy.Agent/AI/AIAgent.cs`
- `Octofy.Agent/AI/OctofyAgentHelper.cs` (the desktop client whose DTOs define the wire contract)

### In scope
- End-to-end SQL-generation behavior: request intake and routing, pre-analysis and fast paths, KB-first discovery, prompt construction, iterative generation/validation/recovery, semantic-layer (SMQ) operation, deterministic fail-fast and structured failure output — implemented as a Python service invoked by the FastAPI routers.
- Per-`source_id` store partitioning and lifecycle (schema library, vector collections, KB few-shots, value index, precomputed queries, data groups, semantic models).
- SSE wiring that maps pipeline milestones to `status` events and a final `result`/`error` payload with the parity fields in the API spec.

### Out of scope
- Octofy Pro desktop UI behavior (Discovery-mode grids, chat rendering, Add-to-KB forms) — these are clients of the API, not ports.
- Vendor-specific SDK details beyond what is needed to preserve orchestration semantics.
- Non-SQL language generators (Python/R/SAS/code-advisor) beyond keeping their route plumbing intact.

---

## 2) Target Architecture

```
                        Octofy Pro (desktop client)
                              |  HTTPS + X-API-Key
                              v
                  FastAPI (Octofy Agent, one process)
        /api/v1/discovery | /api/v1/generation/generate-sql (SSE)
        /api/v1/admin/*   | /api/v1/data-sources/resolve ...
                              |
            +-----------------+------------------+
            v                 v                  v
      Router layer      Orchestrator       Admin/management
      (parses source_id,  (SqlGenerator       routers (few-shots,
       auth, SSE stream)   service = the       values, precomputed,
                           ported GenerateAsync semantic models, ...)
                           business logic)
                              |
        +---------------------+-----------------------+
        v                     v                       v
 Per-source store manager   Catalog / DB adapters    LLM client
 (schema library, vector     (pyodbc per source,      (provider-agnostic
  store, KB, values,          validation executors)    conventions)
  precomputed, data groups,
  semantic models)
```

Key consequence of the multi-source model: every pipeline entry point takes an explicit `source_id` and resolves a **per-source store bundle** (analogous to opening a built-in agent's `vector-index.db` + schema folder). Where the built-in generator constructs `FewShotVectorService`, `VectorSearchService`, `SemanticModelService`, etc., for its single data source, the port constructs them from the source-scoped store bundle for the request's `source_id`.

---

## 3) Non-Negotiable Constants (Must Match)

Preserve these values exactly unless there is a deliberate product change. They are copied from `BUILT_IN_SQL_GENERATOR.md` (2026-09 snapshot).

| Constant | Value | Purpose |
|---|---|---|
| `MaxRetries` | 5 | Maximum generation attempts per request |
| `KbExactMatchThreshold` | 0.05 | Cosine distance below which a KB match is treated as exact |
| `KbConfidenceThreshold` | 0.70 | Confidence above which the `kb_direct` branch is used |
| `KbScoreThreshold` | 0.35 | Maximum cosine distance for a KB result to qualify |
| `DefaultObjectSearchVectorScoreThreshold` | 0.50 | Fallback max raw vector score for object/column discovery (effective value configurable; former constant 0.75 was lowered to 0.50, then made configurable) |
| `DefaultPrecomputedQueryDirectMatchThreshold` | 0.93 | Precomputed direct-match exit threshold |
| `DefaultPrecomputedQueryFewShotThreshold` | 0.82 | Precomputed few-shot injection threshold |
| `PrecomputedQueryTopK` | 3 | Max precomputed results retrieved per search |
| `RrfK` | 60.0 | Reciprocal Rank Fusion constant |
| RRF weights: value-index / few-shot / schema-vector / data-group / BM25-default | 1.0 / 1.0 / 1.0 / 2.0 / 0.5 | Rerank signal weights |
| `MaxRerankTables` | 8 | Upper bound for merged/deduplicated discovery results |
| `ActiveDataGroupTopN` | 3 | Max data groups resolved per request |
| `SchemaContextTokenBudget` | 6 400 | Token cap for supplementary schema context |
| `PromptContextDiscoveryCap` | 8 | Max objects in prompt after capping |
| `MissingObjectBreakThreshold` | 2 | Consecutive failures for one missing object before circuit breaker fires |
| `MissingGroupMemberValidationStatus` | `"MISSING_GROUP_MEMBER"` | Status that triggers broadened group-member recovery |
| `FuzzyMatchMinConfidence` | 0.85 | Min fuzzy-match confidence to auto-substitute an object name |
| `MaxRecoveryExpansion` | 5 | Max objects added per missing-object recovery pass |
| `MaxAutoExtractedObjects` | 5 | Max object names auto-extracted from a prompt with no pins |
| `CatalogCacheTtlSeconds` | 300 | Catalog object list TTL (shared across instances) |
| `MaxGenerationTimeMs` | 120 000 | Total generation time budget (main pipeline) |
| No-discovery path budget | 90 000 ms | Provided-SQL rewrite path budget |
| `MaxDiscoveryCacheEntries` | 256 | Cap of cached discovery result sets |
| `MaxQueryAnalysisCacheEntries` | 100 | Cap of cached query-analysis results |
| `SemanticCompilationTimeoutMs` | 5 000 | Per-call timeout for SMQ → SQL compilation |
| `SemanticSmqParseRetryOnFailure` | `true` | Missing/invalid SMQ payload triggers a retry attempt |
| `SemanticModelDiscoveryTopK` | 3 | Max semantic models surfaced by vector discovery |
| `RelativeColumnScoreThreshold` | 0.85 | Only columns within this fraction of the object's best column score are kept as `MatchedColumns` |
| `ColumnDetailValueSeedScore` | 0.80 | Value-index hit column seed score |
| `KeywordMatchScore` | 1.0 | Full keyword-token column match score (context-noise anchor) |
| `ApplyColumnBoost` | +0.15 (cap 1.0) | Column-evidence object boost |
| Hallucination exit thresholds | 2 (or 1 when the circuit-breaker signal is raised) | Structural-hash repeat count that forces an exit |
| Presence penalty after loop | 0.4 | Applied once a hallucination loop is detected |

### Semantic-layer settings
| Setting | Default | Purpose |
|---|---|---|
| `enable_semantic_layer` (per agent/source) | unset (`null`) | Primary semantic-mode flag; legacy per-source dictionary is the fallback |
| `semantic_compilation_fallback_to_raw_sql` | `true` | Allow SMQ parse/compile failures to fall back to raw SQL output |

### Tunable thresholds (admin settings, same semantics as AI Settings UI)
- `precomputedQueryDirectMatchThreshold` (0.93), `precomputedQueryFewShotThreshold` (0.82), `objectSearchVectorScoreThreshold` (0.50, clamped [0,1]).

These constants define routing thresholds, retrieval ranking behavior, and deterministic breaker outcomes. **Do not change them during the port**; parity tests assert them.

---

## 4) High-Level Behavior Model

The ported generator is a **stateless-over-HTTP, stateful-per-request orchestrator**:

1. deterministic preprocessing (PII masking, object auto-extraction, best-effort schema hydration),
2. route decision (deterministic fast paths + LLM intent classification),
3. fast-path short circuits (KB exact, precomputed exact),
4. parallel heavy pre-analysis (data groups, allowed schemas, query analysis with extracted columns and optional tool calls),
5. retrieval/ranking/hydration (KB-first, column evidence, RRF, token-budgeted prompt contexts),
6. bounded retry loop (≤ 5 attempts, ≤ 120 s, time-budget guarded),
7. layered validation and recovery (safety → sentinels → structural hash → critic → database),
8. structured terminal result (parity fields + `failure_report`).

It is **not** a one-shot text-generation component, and it is **not** allowed to skip validation/recovery to "stream faster."

---

## 5) Required Data Contracts (Pydantic Models)

Implement explicit typed models. Names below follow the C# types; the JSON property names must match the API spec / desktop client wire contract where they cross the HTTP boundary.

### Internal pipeline models
- `AgentRequest` — query (already PII-masked), existing_code, error_message, database_objects (pins), top_k, conversation history, is_user_code, source_id, table_override.
- `AgentContext` — request, schema metadata, intent, generation mode (`fresh_start` | `optimization` | `debugging`), is_error_recovery.
- `RouteDecision` — route enum (`CodeFixing | Optimize | Generate | Conversational`), updated context, immediate result.
- `SchemaMetadata` — hydrated objects, resolved object names, resolution notes.
- `DiscoveryResult` — objects, branch, few-shot examples, value mappings.
- `ScoredObject` — object + score + optional vector score + `matched_columns` + priority/required flags.
- `ActiveDataGroupContext` — top groups, member groups keyed by `schema.object`, summary.
- `QueryAnalysis` — keywords, complexity, entities, date ranges, filter values, `extracted_columns`, resolved tool results.
- `CombinedValidationResult` — requirements satisfied, schema valid, feedback, mismatches, status, missing group members, canonical question.
- `BuiltInAttemptReport` — attempt number, stage, what was tried, why it failed, recovery action, candidate objects.
- `BuiltInFailureReport` — resolution plan, per-attempt reports, final resolution guidance.
- `BuiltInGenerateResult` — success, sql, message, discovery branch, attempts, token usage, processing time ms, hallucination count, agentic retry count, canonical question, context text, failure report, candidates.

### HTTP boundary models (must serialize exactly like the API spec)
- Request: `GenerateSQLRequest` (`query`, `context`, `previousSQL`, `queryHistory`, `forceGeneral`, `queryMode`, `database_objects`, `existing_code`, `error_message`, `is_user_code`, `table_override`, `top_k`, `source_id`, `semantic_mode?`).
- SSE envelope: `{ "type": "status|result|done|error", "payload": {...}, "message": "..." }`.
- Result payload: base `GenerateSQLResponse` (`sql`, `explanation`, `query_type`, `context_text`, `context_history`) plus additive parity fields (`success`, `discovery_branch`, `attempts`, `token_usage`, `processing_time_ms`, `hallucination_count`, `agentic_retry_count`, `canonical_question`, `error_category`, `failure_report`).
- Admin/store models: `FewShotItem`, `DataSourceItem`, `DataSourceResolveResponse`, semantic model + SMQ payloads, precomputed-query records with `sql_query` + `smq_query` + status.

Preserve field semantics even if Python names differ; keep JSON names identical at the API edge.

---

## 6) Service Decomposition (Python Modules)

### Required services (one Python module each)
| Python module | C# source | Responsibility |
|---|---|---|
| `schema_index_service` | `SchemaIndexService` | Object/column keyword discovery, schema filtering, normalization, data-group keyword scoring |
| `vector_search_service` | `VectorSearchService` | Object/column vector retrieval + precomputed exact pre-check + column-row search with `minScore` |
| `fewshot_vector_service` | `FewShotVectorService` | Question→SQL retrieval + deterministic exact pre-check (`few_shots` data table) |
| `value_index_service` | `ValueIndexVectorService` | Value→table/column linkage |
| `bm25_service` | BM25 (feature-flagged) | Lexical rerank signal |
| `sql_context_hydrator` | `SqlContextHydrator` | Object context assembly under token budget, column pruning, `MatchedColumns` propagation |
| `database_catalog` | `IDatabaseCatalog` | Live object listing/existence checks per source |
| `object_name_resolver` | `ObjectNameResolver` | Fuzzy and qualified name normalization |
| `query_interceptor` | `QueryInterceptor` | Safety gate (dangerous operations) |
| `sql_validator` | SQL Server + ODBC validation paths | Compile/dry-run/metadata + driver parse checks |
| `sql_error_classifier` | `SqlErrorClassifier` | Error taxonomy incl. semantic-compilation errors |
| `llm_client` | LLM call layer | Chat completion/Responses API + token accounting, provider-agnostic conventions |
| `tool_function_invoker` | `ToolFunctionInvoker` | MCP (Streamable HTTP) + sub-agent tool execution with argument sanitization |
| `semantic_model_service` | `SemanticModelService` | Per-source model CRUD + embeddings + activation |
| `semantic_compiler` | `SemanticCompiler` | Deterministic SMQ → physical SQL |
| `semantic_extraction_service` | `SemanticModelExtractionService` | LLM-first / SQL-parse fallback model extraction (≥ 1 measure guarantee) |
| `data_group_query_service` | `DataGroupQueryGenerationService` | Precomputed pair generation + statuses (Approved/Modified/Rejected/Pending) |

### Per-source store bundle
Every orchestrator/service that in the built-in world reads "the" vector store or "the" schema library must instead receive a **`SourceStores` bundle** resolved from `source_id`:

```python
@dataclass
class SourceStores:
    source_id: str
    catalog: DatabaseCatalog           # pyodbc adapters for this source's DB
    schema_index: SchemaIndexService
    vector_search: VectorSearchService
    fewshots: FewShotVectorService
    values: ValueIndexService
    precomputed: PrecomputedQueryStore   # vec_data_group_queries analogue
    data_groups: DataGroupStore
    semantic: SemanticModelService
```

Store backends may be Milvus collections filtered by `source_id`, or per-source SQLite sidecars behind one process — the orchestrator must not depend on the choice. See "Vector database backend option."

### Vector database backend option
Keep the provider boundary from the earlier blueprint:

- `VectorProviderType`: `sqlite_vec` (per-source sidecar, mirrors built-in `vector-index.db`) or `milvus` (server collections with the **same collection names as the built-in tables**).
- `VectorProviderFactory` resolves the provider from configuration; adapters normalize score ranges so threshold-sensitive branches remain valid.
- Multi-source partitioning is **never** a collection-name concern: every collection carries the `data_source_id` field from the schema contract below and is filtered/partitioned by it. No per-source prefixes or suffixing.
- Batch upserts; client pooling; timeouts/retries at the provider boundary.
- Default remains per-source SQLite sidecars when `vectorProvider` is unset.

### Vector database table schemas (built-in parity + `data_source_id`)

This subsection is the authoritative table-schema contract. It mirrors **exactly** the built-in per-source `vector-index.db` schema (see `OctofyPro/Docs/VECTOR_DATABASE_RAG_SUMMARY.md`; storage engine `Microsoft.SemanticKernel.Connectors.SqliteVec` 1.74.0-preview over SQLite `vec0`) **with one and only one change**: an extra **`data_source_id`** column/field added to every table. Because the built-in agent keeps one DB file per data source it stores no data-source column anywhere (the legacy partition columns were removed); the Octofy Agent is one store for many sources, so `data_source_id` supplies that partition back.

General rules:

- The Octofy Agent vector database may be **any vector-capable backend** (Milvus, Qdrant, pgvector, Elasticsearch, …). Every table below maps to one collection/index in that backend with the same name and the same scalar fields; only `data_source_id` is added.
- Column names below use the snake_case form of the built-in record property names (`TableSchemaRecord`, `FewShotRecord`, `ValueIndexRecord`) and of the side-table DDL columns. The SQLite columns are case-insensitive and stored verbatim from the property names; pick one canonical casing in the target backend and map 1:1 so a record written through one provider reads back identically through any other.
- `data_source_id` is `TEXT NOT NULL` (VARCHAR up to 128) and should be the **partition key / first filter** of the backend so every read and write is scoped to one source. In Milvus make it a scalar field of type `VARCHAR(128)` used with partition-key or index filtering.
- Vector fields are **1536-dimensional, cosine metric** (the built-in record attributes and vec0 DDL fix 1536; the embedding model *name* is configurable but a different dimension requires a schema change).
- Uniqueness becomes `(data_source_id, <built-in key fields>)`. Key strings that already embed the data source (e.g. `schemas.key = [DataSource].[Schema].[Object]`) are kept verbatim for byte-parity with the built-in; `data_source_id` makes them globally unique again in the shared store.
- The backend must preserve the built-in score conventions: vec0-backed collections return cosine **distance** (lower = more similar); generation thresholds (`KbExactMatchThreshold` 0.05, `KbScoreThreshold` 0.35, `kb_direct` confidence 0.70, vector-score gate 0.50) are expressed against those values and must not be re-interpreted differently per provider.

#### A. Native vector collections (SK vec0-backed in the built-in)

**`schemas`** — hierarchical object discovery rows (one parent row per table/view/function **plus one row per column**; column hits are de-duplicated to their parent at retrieval). Field names mirror `TableSchemaRecord`.

```text
data_source_id   TEXT NOT NULL          -- ADDED; partition key
key              TEXT                   -- PK: [DataSource].[Schema].[Object]
                                        --     column rows: ...[ColumnName]
schema_name      TEXT                   -- e.g. "dbo", "Sales"
object_name      TEXT                   -- e.g. "Customers", "vw_InvoiceSummary"
object_type      TEXT                   -- "Table" | "View" | "Function"
entity_type      TEXT                   -- "Table" | "View" | "Column" (hierarchy level)
column_name      TEXT                   -- populated only for entity_type = "Column"
description      TEXT                   -- the embedded text (see payload formats below)
vector           FLOAT_VECTOR(1536)     -- cosine; 1 vector per row (SK vec0 cosine distance)
```

Embedding payload formats (must match built-in so ranking parity holds):
- Parent: `Entity: Table | Name: <object> | Description: <enriched description>` (View/Function variants likewise).
- Column: `Entity: Column | Table: <object> | Name: <column> | Type: <data type> | Description: <description>[ | Values: <representative values>]`.

`RawSchemaContent` existed in the record for backward compatibility but is **never populated** in the built-in (the on-disk Markdown schema file is the source of truth; the Python service must likewise keep `data_source_id | schema | object → markdown payload` resolution, e.g. in object storage, and store only lightweight rows here).

**`few_shots`** — question→SQL knowledge base (in-context examples + `kb_exact` / `kb_direct` / `kb_gap_fill` branches). Field names mirror `FewShotRecord`.

```text
data_source_id   TEXT NOT NULL          -- ADDED; partition key
key              TEXT                   -- PK (GUID-based)
question         TEXT                   -- natural-language question (embedded text)
sql              TEXT                   -- stored SQL verbatim
created_at_utc   TEXT                   -- ISO-8601 ("o")
vector           FLOAT_VECTOR(1536)     -- cosine distance
```

The exact-question pre-check scans this same table (case-insensitive, whitespace-normalized `question`) **before any vector search**, bypassing `KbExactMatchThreshold`. There is no scalar side store: `few_shots_meta` was retired.

**`value_index`** — representative categorical *data values* (not schema rows), e.g. Status='Active', Country='USA'. Field names mirror `ValueIndexRecord`.

```text
data_source_id   TEXT NOT NULL          -- ADDED; partition key
key              TEXT                   -- PK (GUID-based)
value            TEXT                   -- original value, preserved case
plain_value      TEXT                   -- lowercased copy (case-insensitive substring search)
schema_name      TEXT
table_name       TEXT
column_name      TEXT
vector           FLOAT_VECTOR(1536)     -- populated for parity; today NOT used for search
```

Built-in note: value search is a **case-insensitive substring (`LIKE`) match on `plain_value`** (top-10, fetch cap 16,384), not vector similarity. Keep the same retrieval semantics in the port (the generator calls it per extracted filter value and renders VERIFIED DATA MAPPINGS + an RRF prong).

#### B. Data-group tables (relational side tables in the built-in)

Built-in row-ids for data groups are built as `[DataSource].[GroupName]`; keep the built-in string and add `data_source_id`.

**`data_group_metadata`**

```text
data_source_id   TEXT NOT NULL          -- ADDED; partition key
group_id         TEXT PRIMARY KEY       -- built as [DataSource].[GroupName]
group_name       TEXT NOT NULL
description      TEXT NOT NULL
keywords_json    TEXT NOT NULL          -- JSON array
members_json     TEXT NOT NULL          -- JSON array of schema.object members
updated_at_utc   TEXT NOT NULL
```

**`data_group_vectors_cache`**

```text
data_source_id   TEXT NOT NULL          -- ADDED; partition key
group_id         TEXT PRIMARY KEY       -- FK -> data_group_metadata, cascade
semantic_vector_json    TEXT NOT NULL   -- float[] JSON (AUTHORITATIVE for search)
functional_vector_json  TEXT NOT NULL
object_vector_json      TEXT NOT NULL
updated_at_utc   TEXT NOT NULL
```

**`data_group_vectors_map`**

```text
data_source_id   TEXT NOT NULL          -- ADDED; partition key
group_id         TEXT PRIMARY KEY
vec_rowid        INTEGER NOT NULL
```

**`data_group_vectors_vec0`** — native triple-vector table. Built-in note: this vec0 table is effectively **write-only**; search scores `data_group_metadata ⋈ data_group_vectors_cache` in C# (the built-in later re-creates the vec0 triple as `int8[1536]` via `OptimizeAsync` — a provider-side storage optimization only, with no effect on search results). In Milvus this becomes a collection with **three** `FLOAT_VECTOR(1536)` fields (Milvus 2.4+ supports multiple vector fields) or a single 3×1536 concatenated field if the backend allows one vector per row — the JSON cache above remains authoritative either way.

```text
data_source_id        TEXT NOT NULL     -- ADDED; partition key
rowid                 INTEGER
semantic_vector       FLOAT_VECTOR(1536)
functional_vector     FLOAT_VECTOR(1536)
object_vector         FLOAT_VECTOR(1536)
```

#### C. Precomputed data-group Q&A tables

**`vec_data_group_queries`** — reviewed question→SQL pairs generated by `DataGroupQueryGenerationService` (target ~15 pairs/group). Only `status = 'Approved'` rows participate in vector search; the deterministic exact pre-check additionally reads `Modified` rows.

```text
data_source_id    TEXT NOT NULL         -- ADDED; partition key
query_id          TEXT PRIMARY KEY
group_name        TEXT NOT NULL
group_file_name   TEXT NOT NULL
question          TEXT NOT NULL
sql_query         TEXT NOT NULL
smq_query         TEXT NOT NULL DEFAULT ''   -- SMQ payload; compiled in semantic mode
status            TEXT NOT NULL              -- Pending | Approved | Modified | Rejected | Error
updated_at_utc    TEXT NOT NULL
```

**`vec_data_group_query_vectors_cache`**

```text
data_source_id    TEXT NOT NULL         -- ADDED; partition key
query_id          TEXT PRIMARY KEY      -- FK -> vec_data_group_queries, cascade
question_vector_json  TEXT NOT NULL     -- float[] JSON (question embedding)
updated_at_utc    TEXT NOT NULL
```

#### D. Embedding cache (persistent L2)

```text
data_source_id     TEXT NOT NULL        -- ADDED; partition key
text_hash          TEXT PRIMARY KEY     -- SHA-256 of normalized text
text_content       TEXT NOT NULL
embedding_json     TEXT NOT NULL
embedding_model    TEXT NOT NULL
created_at_utc     TEXT NOT NULL
last_accessed_utc  TEXT NOT NULL        -- index idx_embedding_lru (LRU eviction)
access_count       INTEGER DEFAULT 1
```

Built-in caps: in-memory L1 = 512 (whole-clear when full), persistent L2 = 10,000 rows with LRU eviction in batches of 1,000; invalidated when the embedding model changes. Keep per-`data_source_id` scoping so concurrent sources do not evict each other.

#### E. Semantic-model tables (SMQ semantic layer)

Six plain relational tables (created both by `VectorSearchService.EnsureDataGroupTablesAsync` and idempotently by `SemanticModelService`); model embeddings are JSON text matched by in-service cosine — **not** native vector search.

**`semantic_models`**

```text
data_source_id   TEXT NOT NULL          -- ADDED; partition key
model_id         TEXT PRIMARY KEY
label            TEXT NOT NULL
is_active        INTEGER NOT NULL DEFAULT 1
updated_at_utc   TEXT NOT NULL
```

**`semantic_measures`**

```text
data_source_id   TEXT NOT NULL          -- ADDED
model_id         TEXT NOT NULL          -- FK -> semantic_models, cascade
measure_name     TEXT NOT NULL
expression       TEXT NOT NULL          -- raw SQL expression
description      TEXT NOT NULL
PRIMARY KEY (data_source_id, model_id, measure_name)
```

**`semantic_dimensions`**

```text
data_source_id   TEXT NOT NULL          -- ADDED
model_id         TEXT NOT NULL          -- FK cascade
dimension_name   TEXT NOT NULL
column_name      TEXT NOT NULL
table_name       TEXT NOT NULL
description      TEXT NOT NULL
PRIMARY KEY (data_source_id, model_id, dimension_name)
```

**`semantic_joins`**

```text
data_source_id   TEXT NOT NULL          -- ADDED
model_id         TEXT NOT NULL          -- FK cascade
from_table       TEXT NOT NULL
to_table         TEXT NOT NULL
join_expression  TEXT NOT NULL
join_type        TEXT NOT NULL          -- default INNER
PRIMARY KEY (data_source_id, model_id, from_table, to_table, join_expression)
```

**`semantic_governance_predicates`**

```text
data_source_id   TEXT NOT NULL          -- ADDED
model_id         TEXT NOT NULL          -- FK cascade
predicate        TEXT NOT NULL          -- raw SQL governance predicate
description      TEXT NOT NULL DEFAULT ''
```

**`semantic_embeddings`**

```text
data_source_id   TEXT NOT NULL          -- ADDED
model_id         TEXT PRIMARY KEY       -- FK -> semantic_models, cascade
embedding_json   TEXT NOT NULL          -- float[] JSON of the whole-model embedding
updated_at_utc   TEXT NOT NULL
```

The embedding source string is `label | measure(name:description:expression)... | dimension(name:description:table.column)... | governance(predicate:description)...` (mirrors `SemanticModelService.BuildEmbeddingSource`), so `SearchModelsAsync` ranks identically. Inactive models are excluded from search; "active model for a source" = most recently updated `is_active = 1` row for that `data_source_id`.

#### F. Milvus-specific implementation notes

- One built-in table above → one Milvus collection with the identical name; `data_source_id` is field 0, `VARCHAR(128)`, and is the **partition-key field** (`partition_key_field="data_source_id"`) or drives a `term` filter on every query.
- Vector fields are `FloatVector(dim=1536)`, metric `COSINE` (equivalent cosine-distance semantics after the provider normalizes scores as described in "Vector database backend option").
- SQLite `TEXT PRIMARY KEY` → Milvus `VARCHAR` primary field (enable auto-id only where the built-in used GUIDs and no code depends on the string, e.g. `few_shots.key`, `value_index.key`; otherwise keep the built-in string values).
- The side tables that store vectors as JSON text (data-group caches, query vector cache, semantic embeddings) may either keep a scalar JSON field + in-service cosine (default; exact built-in parity) or be promoted to native Milvus vector fields behind the provider adapter — orchestration must not change either way.
- Schema/index definitions must be centralized in one shared contract module with versioned metadata plus bootstrap/migration scripts, exactly as in the built-in (`EnsureSchemaAsync` / `EnsureDataGroupTablesAsync` idempotent creation) so a fresh source can be provisioned and a new embedding dimension or added column can be migrated without code forks.

### Skills folder structure (built-in parity, no `vector-index.db`)

The Octofy Agent must keep **exactly the same on-disk "skills" folder layout the built-in agent produces for one data source**, with one exception: there is **no `vector-index.db`** (vector collections are stored in the shared vector backend and rebuilt from this folder). The intent is lossless migration: an operator copies a built-in data-source skills folder to the Octofy Agent, registers it under a `source_id`, and the agent rebuilds every vector collection from the copied files.

The layout below is verified against the built-in engine (`SchemaLibraryBuilder`, `SchemaIndexService`, `VectorSearchService`, `LegacyScriptIngestionService`, `MarkdownToolRegistryService`) and `SCHEMA_LIBRARY_BUILD_AND_AGENT_USAGE.md` / `VECTOR_DATABASE_RAG_SUMMARY.md`. Column `Rebuilt?` says whether the vector tables in the schema section can be regenerated from this content alone.

```text
skills/
  data-sources/
    _index.md                                   # data-source registry at the data-sources root
    <data-source-folder>/                       # one folder per source; folder name = source name
                                                #   (e.g. northwind_local, {database}_{server}, {DSN}_ODBC)
      _data-source.md                           # data-source metadata (name, server/database, source_id, ...)
      .schema-index.json                        # schema catalog for stage-1 schema relevance search
      .data-groups                              # plain-text map: "<group name>|<group file name>" per line,
                                                #   sorted; drives group-name resolution
      exclude_objects.txt                       # OPTIONAL: per-source object exclusion list (names to skip
                                                #   during build/sync)
      vector-index.db                           # BUILT-IN ONLY — NOT copied to the Octofy Agent.
                                                #   Rebuilt into the shared vector backend from the files below.
      schemas/
        <schema-name>/
          .object-index.json                    # per-schema object catalog for stage-2 object scoring
          <schema>.<object>.md                  # table/view Markdown (source of truth for schema payload)
          <schema>.fn.<object>.md               # function Markdown
      data-groups/
        .data-group-index.json                  # data-group catalog (+ per-group precomputed Q&A incl. SMQ)
        <group>-group.md                        # data-group Markdown (description, keywords, members,
                                                #   business rules/metrics)
        <group>-group-qas.md                    # data-group precomputed Q&A Markdown mirror (Pending /
                                                #   Approved / Modified / Rejected sections) — optional review surface
      tools/
        *.md                                    # markdown tool definitions (YAML front matter; sub-agent/MCP
                                                #   protocols) registered via MarkdownToolRegistryService
      kb/                                       # created by legacy-script ingestion ("Learn from Past Projects")
        <domain>.skill.md                       # per-domain knowledge skill Markdown
        <domain>.intermediate.skill.md          # per-domain intermediate-step skill Markdown (pipeline trace)
      <domain>.precomputed.json                 # legacy-ingestion precomputed Q&A artifacts (Approved/Pending
                                                #   by confidence), one JSON list per domain
```

Notes on parity and rebuild:

- **Schema objects** — `schemas/*` Markdown plus `.schema-index.json` / `.object-index.json` are the file source of truth. `schemas`, the object+column vector rows, the keyword indexes and data-group membership are all **rebuilt** from them (vector-table groups `schemas`, `data_group_*`, `vec_data_group_queries` and their caches).
- **Data groups** — `.data-group-index.json` carries the group catalog and each group's precomputed Q&A payloads (including `smq_query`); `<group>-group.md` / `<group>-group-qas.md` are the human-reviewable mirrors. Rebuildable from `.data-group-index.json`; the Q&A Markdown files exist for review/edit and are resynced on approval.
- **Tools** — `tools/*.md` are read directly at runtime by `MarkdownToolRegistryService`; they need no vector index. The Octofy Agent must register the same files (per `source_id`) so tool-calling analysis behaves identically.
- **Legacy-ingestion artifacts** — `kb/*` Markdown and `<domain>.precomputed.json` are produced by `LegacyScriptIngestionService` and are inputs, not vector tables; copy them as-is.
- **Files that are NOT in the folder** — few-shot KB rows added through "Add to Knowledge Base", `value_index` entries, semantic models and the `embedding_cache` live **only** inside `vector-index.db` in the built-in. For those, "copy the folder + rebuild" cannot reconstruct them from files; the Octofy Agent's equivalent content is the `few_shots`, `value_index`, `semantic_*` tables keyed by `data_source_id` (see schema section), which must be migrated through the Octofy Agent's own stores / admin endpoints or re-created server-side. Everything else migrates by folder copy.
- **Migration procedure** — copy the whole `<data-source-folder>` (minus `vector-index.db`) into the Octofy Agent's source storage, resolve/register a `source_id` for it, then run the per-source rebuild (equivalent of `SchemaLibraryBuilder.RebuildVectorIndexFromDiskAsync` + `SyncDataGroupsFromIndexAsync` + `SyncPrecomputedQueriesFromIndexAsync`) which re-embeds and repopulates all vector tables. The `_index.md` registry is updated to list the new source.

### Caches that must exist
- **Static catalog cache** per source (TTL 300 s).
- **Per-request discovery cache** (256 entries; cleared wholesale at cap) keyed by sorted entities + complexity band + topK (+ `cols:<sha256>` fingerprint when `extracted_columns` present); entries are deep-cloned before return so downstream score mutation never corrupts cached results.
- **Per-request query-analysis cache** (100 entries; cleared at the start of each generate call) keyed by trimmed `(combined_query, existing_code)` or its SHA-256 when > 512 chars.
- **Semantic discovery cache** bounded by `MaxDiscoveryCacheEntries`.

### Data-group integration
Active data groups influence allowed schemas, ranked candidates, and protected context objects — same as built-in.

---

## 7) Deterministic Pipeline Specification

Mirrors `BUILT_IN_SQL_GENERATOR.md`'s six top-level steps. Each stage emits a `status` SSE event (stage name in parentheses) before doing work so clients see pipeline progress.

### Stage A — Request intake and routing (`routing`)

**A.1 Validate and sanitize** — reject empty/whitespace query (HTTP 400 at the API edge). Apply PII masking (email/SSN/US phone/credit card → `[EMAIL]`, `[SSN]`, `[PHONE]`, `[CARD]`). All downstream work uses the masked query.

**A.2 Preprocess and route.**
1. Build the immutable `AgentRequest` (masked prompt, existing code, error, pins, top-K, history, `is_user_code`).
2. Preprocess: deterministic object auto-extraction (up to `MaxAutoExtractedObjects` when no pins) + best-effort schema hydration for routing.
3. Route with deterministic fast paths first:
   - error-recovery turn (`errorMessage` + `existingCode`) → `CodeFixing` (debugging mode; **not** a no-discovery exit — existing code becomes the discovery anchor),
   - explicit pins → `Generate` or `Optimize` depending on editor code presence,
   - simple/clear SQL-data request meeting `ShouldUseSimplePreAnalysisFastPath` (route `Generate`, no code/error, ≤ 180 collapsed chars, strong language-agnostic DB signal, `simple` complexity, none of join/group by/having/union/except/intersect/compare/versus/vs, ≤ 40 words) → `Generate` without LLM analysis,
   - likely DB query (≤ 50 words + the same DB signal) → bypass intent classification.
   - The single shared signal test is `HasStrongLanguageAgnosticDbSignal` (SQL-shaped text only): begins like a real statement (`SELECT/INSERT/UPDATE/DELETE/MERGE/SET NOCOUNT/SET TRANSACTION/SET ANSI`, `WITH … AS … SELECT`), contains an extractable inline SQL block, or matches the `select…from` / `insert into` / `update … set` / `delete from` / `merge into` clause-pair regex. Conversational phrasing alone never short-circuits routing — it goes to the LLM classifier.
4. Otherwise one LLM call classifies `db_query | optimize_code | app_feature | off_topic`.
5. `app_feature` / `off_topic` → immediate conversational result (branch = intent name). `Optimize` with existing code, and `Generate` with inline SQL in the request (no editor SQL, code-operation request), → **no-discovery path** via `GenerateFromProvidedSql` with its own 90 s budget and DB-only validation (no critic).
6. When no pins: copy preprocess `ResolutionNotes`; convert `ResolvedObjectNames` into discovery hints.

### Stage B — Priority-object validation (`validate_pins`)
When `database_objects` is non-empty:
1. Validate pins against the live per-source catalog (`ObjectNameResolver`): exact match | fuzzy substitution (confidence ≥ 0.85) | missing.
2. Replace pins with validated qualified names; append substitution notes.
3. Any remaining missing pins → immediate failure with discovery branch `priority_validation_failed`, closest-match candidates, resolution guidance.
4. Resolve which pins are PostgreSQL functions (for `()` call-syntax normalization later).
Then build the combined conversational query: masked query + `Q: … | A: …` history (newest answer verbatim; older answers truncated to 200 chars; failed/canceled turns become explicit placeholders).

### Stage C — Two-phase pre-analysis (`preanalysis`)
**Phase 1 (parallel, can short-circuit the whole pipeline):**
- KB exact pre-check: deterministic case-insensitive, whitespace-normalized question match over the plain `few_shots` data table → return stored SQL immediately (`kb_exact`, 0 attempts, no vector search and no cosine threshold involved). Only on a deterministic miss does the top-1 few-shot vector search run; its `KbExactMatchThreshold` (0.05) check applies only to that vector path.
- Precomputed exact pre-check: same normalization over Approved/Modified rows of the precomputed metadata table → single result `Score = 1.0`, `IsExactMatch = true`; deterministic hit always clears the 0.93 direct-match threshold (`precomputed_exact`, 0 attempts; SMQ-compiled in semantic mode). On miss, vector search (top 3) with 0.93 direct-match / 0.82 few-shot thresholds.

If neither fast path fires, **Phase 2 (parallel):**
- `ResolveActiveDataGroups` (vector first, keyword-overlap fallback; top 3),
- `DetermineAllowedSchemas` (single-schema files accepted; multi-schema heuristic → LLM schema selection → keyword fallback; per-file LLM calls concurrent),
- `AnalyzeQuery` (LLM: keywords, complexity, entities, date ranges, `filter_values`, `extracted_columns` JSON array — normalized: trim, strip brackets/quotes/schema.table prefixes, de-dupe, cap 20). Skipped entirely on the simple fast path (empty analysis). May execute markdown-registered tools (sub-agent or MCP with schema-sanitized arguments); resolved tool results prepend to `filter_values`. In semantic mode, matching measure/dimension names are prepended to `filter_values`.

After Phase 2: merge active-group schemas into the allowed set, build the active business context summary, promote qualifying precomputed matches (SMQ payload in semantic mode) to few-shot examples.

### Stage D — Discovery, ranking, hydration (`discovery`)
1. Anchor: existing code (for fix/optimize turns) else the combined query.
2. Append inferred data-requirement keywords, then inferred object hints (bare names), to form the discovery query.
3. **KB-first discovery** with **column evidence**: parallel prefetch prong runs `DiscoverObjectsWithColumnEvidence` → `DiscoverObjectsWithColumnDetail` (question-based, or the column-list overload when `extracted_columns` is non-empty). Objects are enriched with `MatchedColumns` (value-index seeds at 0.80, column-vector rows gated by the effective `ObjectSearchVectorScoreThreshold` inside the service, keyword-token matches scoring 1.0) and column-only objects are synthesized; KB branches inherit the enriched prefetch when merged (`kb_gap_fill`, `dual_prong`).
4. Branch decision follows the built-in taxonomy exactly: `kb_direct` (KB confidence ≥ 0.70, tables from best KB example only) | `kb_gap_fill` (KB hit below threshold merged with schema/value expansion) | `dual_prong` (no KB hit, RRF of schema/vector + value-index + few-shot + data-group + optional BM25 signals with fixed weights and `RrfK = 60`); `group_anchored` when active-group members are in the final object set; `table_override` when the result is driven by user-pinned objects rather than open discovery.
5. Post-discovery: prioritize pins; boost FK-connected objects; force active-context priority objects; set value mappings on the hydrator; cap prompt context to `PromptContextDiscoveryCap` (8) with a 5% relative score floor — objects carrying `MatchedColumns` are treated as required, and `SemanticModel` objects are always required.
6. Build the four contexts: `selected_object_context` (full schema for pins/high-priority), `supplementary_objects` (token-budget-pruned views/functions, excluded from critic), `schema_context` (protected + prunable, for generation), `schema_context_for_validation` (annotated with `-- Matched column evidence: [schema].[object].[column]` per object|column so the critic sees grounding even when full schema was pruned).

### Stage E — Iterative generation and validation loop (`attempt`, `critic`, `db_validation`, `recovery`)

Initialize loop state: attempt history, last error/prompt/failed SQL, pending recovery objects, per-object + per-(object, category) missing-object counters, structural-hash history, loop-breaker flag, previous error category, previous critic-passed flag, time budget (120 s), circuit-breaker signal, broadened-group-member flag.

Per attempt (1..`MaxRetries`):
1. **Time guard** — if elapsed > 120 s, return `timeout` failure.
2. **Loop-breaker hints** — if loop-breaker active and no explicit extra objects, derive fallback terms from extracted entities.
3. **Merge recovery objects** — when pending recovery objects or loop-breaker active: expand `topK`, optionally re-discover broader context, merge/dedup, re-apply prioritization, rebuild contexts, reset loop-breaker, force critic to rerun.
4. **Compact attempt history** — all but the newest full entry become one-line summaries.
5. **Build prompts** — system prompt: DBMS/dialect, generation mode, query analysis, active business context, KB examples (complexity-matched, up to 3; precomputed examples prepended, de-duped by question, capped at 5 total), verified value mappings, available schemas (selected + supplementary), attempt history, output format (fenced SQL with reasoning comment header). In **semantic mode** the system prompt is the semantic variant (DBMS CONTEXT SEMANTIC MODE, AVAILABLE SEMANTIC MODELS JSON, SEMANTIC OUTPUT FORMAT STRICT — reply with a fenced ` ```smq ```` block containing `{"metrics":[...],"dimensions":[...],"filters":[...],"timeframes":[...]}`, only model names; no reasoning/view/scripting sections).
6. **Call the LLM** — apply `presence_penalty = 0.4` once a hallucination loop is detected; accumulate token usage (thread-safe). Post-process: strip markdown fences, normalize dialect qualifiers, normalize pinned PostgreSQL function invocations to `()` call syntax. In semantic mode: extract SMQ (```` ```smq ```` fence or bare `{"metrics":` object), deserialize, compile against the active model under the 5 s timeout; missing payload / compile failure → `semantic_compilation` failure retried per `SemanticSmqParseRetryOnFailure` (or raw-SQL fallback per policy). Empty response → `generation` failure.

**Validation order is fixed (do not reorder):**
1. Safety gate (`QueryInterceptor`) — dangerous DML/DDL blocked unless explicitly requested; temp-object exceptions; comment/string stripping.
2. Sentinel parse — `TABLE_VALIDATION_ERROR` / `COLUMN_VALIDATION_ERROR` → expand missing objects (`COLUMN_VALIDATION_ERROR` uses exact-column recovery with `extracted_columns`), merge into pending recovery objects, protect them, retry; circuit breaker exits early at threshold.
3. Structural-hash loop detection — whitespace-collapsed, comment-stripped, literal/alias-normalized SHA-256; repeat → `hallucination_loop` report, loop-breaker on, `ANTI-REPEAT DIRECTIVE` injected; exit at threshold 2 (or 1 with circuit-breaker signal raised) listing candidate objects.
4. **Attempt-1 DB pre-check runs before the critic** — DB validation first on attempt 1; if it passes, skip the critic and return success immediately; if it fails, reuse the result after the critic.
5. LLM critic (`ValidateSqlWithLlm`) — requirements satisfaction + schema adherence in one call over a filtered validator schema; in semantic mode the critic receives the serialized model and checks semantic entities instead of physical schema. Returns `canonical_question` (≤ 25 words, same natural language, only when both flags true) which flows to the result. Requirement failure → `requirement` failure + recovery. Schema failure → `MISSING_GROUP_MEMBER` triggers one broadened no-restriction recovery pass; otherwise extract missing objects, expand, protect, retry (circuit breaker respected).
6. DB validation (`ValidateSql`) — SQL Server path: compile via `SET NOEXEC ON`, transaction dry-run, result-set metadata via `sys.dm_exec_describe_first_result_set`; ODBC path: driver parse (`SET NOEXEC` SQL Server / `EXPLAIN PLAN FOR` Oracle / `EXPLAIN` MySQL·MariaDB·PostgreSQL / `PREPARE` fallback). On failure also run out-of-scope reference checks → structured `TABLE_VALIDATION_ERROR` feedback. Classify the error, extract missing object, update counters, trip breaker at threshold, expand, retry.

**Success** → stopwatch stop, analytics, return result with sql, attempt count, prompt text, branch, business context, token usage, processing time, hallucination count, agentic retry count, canonical question.

### Stage F — Terminal fallback (`done`/`error`)
Unexpected loop exit → structured failure via `BuildDetailedFailureResult`: final resolution guidance, resolution plan + per-attempt reports packaged into `BuiltInFailureReport`, multi-section user-facing error wrapped in a `/* ... */` SQL comment, full `BuiltInGenerateResult { success: false }`.

---

## 8) Discovery Subsystem Details (parity checklist)

- `DiscoverWithDataGroups` — vector path (embed + search local store; prioritized objects embedded and boosted to near-forced scores; cache hit deep-cloned, cache key includes the `cols:` fingerprint) with keyword/data-group fallback path (term-overlap group scoring → member expansion → keyword discovery merge).
- `DiscoverObjectsWithColumnEvidence` / `DiscoverObjectsWithColumnDetail` — three evidence passes (value-index hits seed columns at 0.80; `SearchColumnsScored(topK=100, minScore=effective threshold)` keeps only `EntityType == "Column"` rows; keyword-token pass with full-token match = 1.0 anchor); per-object columns filtered within `RelativeColumnScoreThreshold` (0.85); +0.15 column boost; column-only objects synthesized and merged to top-K. Column embeddings built name-first (`"first name | <description> | Values: ..."`). Column-list overloads skip value-index, run column vector search per candidate, and keyword-match column tokens against candidates.
- `DiscoverVectorFirstWithFallback` — vector first, keyword fallback; optional `dataSource`/`maxVectorScore` filters; column list forwarded (cache key only at this level).
- `ExpandObjectsFromActiveGroups` — per active-group member (groups < 20% query overlap filtered out), keyword first then batched vector fallback with group-score boost.
- `FilterObjectsByAllowedSchemas` — keep objects whose `dataSource|schemaName` key is in the allowed set; no-op when set empty.
- `MergeAndDedup` — unique key `dataSource|schemaName|strippedObjectName`; strip ` (Segment N/M)` suffixes for dedup while retaining segments for the hydrator.
- `RrfMerge` — positional `weight × 1/(RrfK + rank + 1)` over the five ranked lists.
- Deterministic exact pre-checks for KB and precomputed fast paths (KB reads the `few_shots` data table; case/whitespace-insensitive). No KB side store.
- Cache semantics and keys as in "Caches that must exist."

---

## 9) Semantic Layer Integration (SMQ)

- **Enablement (per source):** semantic mode requires both (1) the source's semantic flag — explicit per-agent/`source_id` flag wins, else the legacy per-source dictionary — and (2) an active `SemanticModel` for that source. Legacy deployments seed `enable = true` when the folder/source was enabled in the legacy dictionary. The `semantic_mode` request field may force on/off for one call.
- **Storage:** per-source model tables (models, measures, dimensions, joins, governance predicates, embeddings) with idempotent `CREATE TABLE IF NOT EXISTS`; full-model text embedding stored at save; retrieval by cosine similarity; "most recently updated active model" as the compile target.
- **Model shape:** `SemanticModel { model_id, data_source_key, label, is_active, measures[], dimensions[], joins[] }` — measure `{name, expression (raw SQL), description}`; dimension `{name, column, table, description}`; join `{from_table, to_table, join_expression, join_type (default INNER)}`.
- **Extraction:** LLM-first prompt requires a non-empty `measures` array and instructs the model to infer defaults (`row_count = COUNT(*)`, `COUNT(DISTINCT …)`, `SUM`/`AVG` over numeric columns) using full `schema.table.column` references (aliases are not resolvable); SQL-parse fallback; deterministic last resort injects `row_count = COUNT(*)` because the editor refuses zero-measure models and compilation requires ≥ 1 metric.
- **Compiler (deterministic, synchronous, wrapped in the 5 s budget):** resolve metrics/dimensions by name (case-insensitive; `UNKNOWN_METRIC`/`UNKNOWN_DIMENSION`), determine required tables (dimension `Table` → first dimension table → first join `FromTable`), build a BFS join plan connecting all required tables (`INCOMPATIBLE_DIMENSIONS` no path / `MISSING_JOIN_PATH` no source), emit `SELECT` dimensions (`table.column AS name`) + measures (`expression AS name`), `FROM` anchor, join plan, `WHERE` from filters (`eq/ne/neq/gt/gte/lt/lte/like`) + timeframes (`field BETWEEN start AND end`) + optional governance predicates, `GROUP BY` dimensions. Quote identifiers per dialect (`[x]` SQL Server, `` `x` `` MySQL/MariaDB, `"x"` otherwise; `N'…'` string literals on SQL Server).
- **Integration points to preserve:** precomputed fast path compiles stored `smq_query`; few-shot injection uses the SMQ payload; semantic candidates appended to discovery as scored semantic-model objects; semantic-mode system prompt; SMQ extraction + compile in the attempt loop; semantic critic variant; missing-object expansion surfaces matching models first; `SqlErrorClassifier` recognizes `SemanticCompilationError` (`UnknownMetric`, `UnknownDimension`, `IncompatibleDimensions`, `MissingJoinPath`).

---

## 10) Prompting Contracts That Must Be Preserved

- **Output format:** model output may include a `/* reasoning */` block and fenced SQL; normalization must extract the SQL body while tolerating wrappers (also strips the reasoning header when the client saves to KB).
- **Dialect strictness:** inject effective DBMS type, dialect-specific syntax rules, identifier quoting, prohibited cross-dialect syntax; PostgreSQL strict guidance (LIMIT not TOP, CASE not IF(), explicit casts, schema qualification).
- **System prompt sections (normal mode):** DBMS CONTEXT (STRICT), GENERATION MODE, QUERY ANALYSIS, ACTIVE BUSINESS CONTEXT, KNOWLEDGE BASE EXAMPLES, VERIFIED DATA MAPPINGS, AVAILABLE SCHEMAS, SUPPLEMENTARY SCHEMAS, ATTEMPT HISTORY, OUTPUT FORMAT.
- **Semantic mode sections:** DBMS CONTEXT (SEMANTIC MODE), AVAILABLE SEMANTIC MODELS (JSON), SEMANTIC OUTPUT FORMAT (STRICT) — prompt returns immediately after that section.
- **Complexity tiers** for few-shot matching: "complex" ≥ 2 complex keywords; "moderate" = 1; "simple" = 0.
- **Conversation folding:** newest answer verbatim; older ≤ 200 chars; failed/canceled turns → placeholders.

---

## 11) Concurrency and Performance Semantics

- `asyncio.gather` where the C# code uses `Task.WhenAll`: Phase-1 fast-path checks; Phase-2 heavy tasks (data groups, allowed schemas, query analysis); per-group member expansion; per-index-file multi-schema LLM selection.
- Token-usage accumulation must be thread/async-safe across parallel LLM calls.
- Request-local caches with bounded memory: discovery cache cap, history compaction, token-budget pruning. A request-local `source_id` never leaks across concurrent requests.
- Long-running admin jobs (precomputed generation, schema sync/scan, model extraction, ingest) run as background tasks with per-source status endpoints; generation itself stays within the single SSE request.
- Vector provider (Milvus): client/channel pooling, batch upserts, provider-boundary timeouts/retries, normalized scores compatible with thresholds.
- SSE backpressure: status events are small; result payload may be large but is a single final event.

---

## 12) Error Taxonomy and Failure Reporting

### Categories to preserve
`safety` | `generation` | `requirement` | `schema` | `validation` | `syntax` | `timeout` | `deterministic_missing_object` | `priority_validation_failed` | `semantic_compilation` (+ LLM intent exits `app_feature` / `off_topic`).

### Failure payload requirements
Each failure includes: summary error message, resolution plan, per-attempt diagnostics, candidate objects when applicable, final resolution guidance. Never return opaque errors when structured information can be produced. Over HTTP, failures stream an `error` SSE event and/or a `result` payload with `success: false`, `error_category`, and `failure_report`.

---

## 13) Branch Names and Observability Contract

Preserve these discovery branch labels — tests and analytics depend on them:

`kb_exact`, `precomputed_exact`, `precomputed_related/<base_branch>`, `table_override`, `kb_direct`, `kb_gap_fill`, `dual_prong`, `group_anchored`, `no_discovery`, `priority_validation_failed`, plus conversational exits `app_feature` / `off_topic`.

Emit per request: branch, attempts, token usage, processing time, hallucination count, agentic retry count, error category, `source_id`.

---

## 14) Implementation Plan (Executable by AI Tools)

## Phase 1 — Foundation & scaffolding
1. Create the FastAPI app package with routers, per-source store bundle resolution from `source_id`, and auth (X-API-Key user/admin) as in the API spec.
2. Implement typed Pydantic contracts and enums; add constants exactly matching Section 3.
3. Add telemetry scaffolding (structured logs with `source_id`, timing).

## Phase 2 — Deterministic utilities
1. Port regex utilities (PII masking, inline-SQL extraction, validation-sentinel parsing, markdown fence stripping, structural SQL hash normalization).
2. Port dialect/identifier helpers (quoting, qualifier normalization, pinned-function `()` normalization).

## Phase 3 — Per-source stores & catalog
1. Implement the **schema contract** (`stores/schema_contracts.py`) exactly as specified under "Vector database table schemas" (Section 6): every table/collection with built-in field names plus `data_source_id` as the partition field, versioned DDL/bootstrap for both SQLite and Milvus.
2. Implement `SourceStores` resolution and the store adapters (schema library, vector, KB, values, precomputed, data groups, semantic).
3. Implement catalog adapters per DBMS + fuzzy/qualified-name resolver.
4. Implement pinned-object fail-fast response path (`priority_validation_failed`).

## Phase 4 — Preprocess + Router
1. Preprocessing with deterministic object auto-extraction and hydration.
2. Router with immutable context transitions, deterministic fast paths (shared `HasStrongLanguageAgnosticDbSignal`), conversational short-circuit, no-discovery rewrite/optimize path.

## Phase 5 — Retrieval and discovery engine
1. Deterministic exact pre-checks + KB-first + precomputed fast paths with thresholds.
2. Active data-group resolution and allowed-schema selection (LLM + deterministic fallback).
3. Column-evidence discovery (value seeds, column rows with minScore, keyword passes, column-only synthesis, column-list overloads).
4. RRF merge with fixed weights; discovery cache with `cols:` fingerprint keys.

## Phase 6 — Hydration and prompt builders
1. Context hydrator with token budget + pruning + `MatchedColumns`; value mappings + active business context.
2. Generation and validation schema contexts (with `-- Matched column evidence:` annotations).
3. Dialect-specific system/user prompt builders incl. semantic-mode variant.

## Phase 7 — Attempt loop and recovery
1. Bounded retry loop with time guard, history compaction, loop-breaker divergence.
2. Validation ordering contract (safety → sentinels → structural hash → critic → DB with attempt-1 pre-check + skip rules).
3. Recovery expansion/protection/counters/circuit breaker, broadened group-member pass, exact-column recovery, agentic retry counter.

## Phase 8 — Validation adapters
1. Safety interceptor; LLM critic integration + mismatch parsing + `canonical_question`.
2. DB validators: SQL Server (NOEXEC compile, dry-run, result metadata) and ODBC/other dialect paths via pyodbc; schema-scope cross-check → `TABLE_VALIDATION_ERROR`.

## Phase 9 — Semantic layer
1. Per-source semantic settings, model CRUD + embedding, activation.
2. Extraction service (LLM-first + SQL-parse fallback + ≥1 measure guarantee).
3. Deterministic SMQ compiler with BFS join planning and dialect quoting under the 5 s budget; integration into precomputed path, few-shot payloads, discovery, prompt, critic, recovery, error classification.

## Phase 10 — HTTP/SSE integration & reporting
1. Wire the orchestrator into `/api/v1/generation/generate-sql` (and legacy alias), emitting `status` events per stage and a parity `result`/`error` payload.
2. Wire `/api/v1/discovery` to the discovery subsystem with `relevant_tables` (+ similarity scores).
3. Implement admin surfaces: few-shots (KB), values, precomputed data-group queries, semantic models/compile, data sources + resolve, settings thresholds, backup.
4. Implement the **skills-folder import/migration surface**: register a copied built-in data-source folder under a `source_id`, then rebuild all vector collections from the folder content (per "Skills folder structure (built-in parity, no `vector-index.db`)"); expose a per-source rebuild-status endpoint.
5. Structured success/failure packaging; branch analytics + diagnostics fields; golden parity + API-contract tests.

---

## 15) Test Matrix (Parity Acceptance)

### Behavior parity (must mirror built-in outcomes)
1. Empty query rejected (HTTP 400).
2. Conversational route short-circuits with intent branch.
3. Optimize route with existing code (no error) takes the no-discovery provided-SQL path; error-recovery turns (`CodeFixing`) run normal discovery anchored on the existing SQL; inline-SQL rewrite requests take no-discovery.
4. Pinned-object validation fail-fast (`priority_validation_failed`) with candidates.
5. `kb_exact` early return (deterministic exact pre-check first, then vector path) with 0 attempts.
6. `precomputed_exact` early return; SMQ-compiled in semantic mode.
7. Phase-1 short-circuit prevents Phase-2 LLM analysis.
8. Simple fast path skips LLM analysis (≤ 180 chars, DB signal).
9. Active data-group schema merge behavior.
10. `kb_direct` / `kb_gap_fill` branch selection.
11. `dual_prong` / `group_anchored` RRF ranking behavior with fixed weights.
12. Column-evidence discovery: value seeds, column rows, keyword matches, synthesized column-only objects, `MatchedColumns` propagated and treated as required.
13. Safety gate blocks dangerous SQL; explicit-write and temp-object exceptions honored.
14. Sentinel recovery path (`TABLE_VALIDATION_ERROR`, `COLUMN_VALIDATION_ERROR` exact-column pass).
15. Structural-hash hallucination loop detection; exit at 2 (or 1 with breaker signal); presence penalty applied.
16. Critic requirement mismatch path.
17. Critic schema mismatch path; `MISSING_GROUP_MEMBER` broadened recovery once.
18. Attempt-1 DB pre-check passes → critic skipped.
19. DB syntax/compile/runtime recovery path; error classification drives recovery.
20. Deterministic missing-object breaker trips at threshold 2.
21. Recovery-protected objects not pruned across attempts.
22. Timeout failure after 120 s (90 s no-discovery).
23. Success result includes metrics and diagnostics fields incl. canonical question.
24. Semantic mode: SMQ-only prompt, compile success, semantic critic, compile-failure retry/fallback policy, unknown metric/dimension expansion.

### Transport parity (API contract)
25. `/api/v1/generation/generate-sql` streams `status` events for each stage then one `result` (or `error`) + `done`.
26. Result payload base fields (`sql`, `explanation`, `query_type`, ...) parse with the desktop `OctofyAgentHelper` DTOs.
27. Additive parity fields present on success and failure (`success`, `discovery_branch`, `attempts`, `token_usage`, `processing_time_ms`, `hallucination_count`, `agentic_retry_count`, `canonical_question`, `error_category`, `failure_report`).
28. Legacy flat route `/api/v1/generate-sql` returns the same payload (404-free fallback path).
29. `source_id` scoping: concurrent requests for different sources never share caches/stores; unknown source → 404.
30. Admin store endpoints (few-shots, values, precomputed, semantic models, settings) round-trip with the API spec field names.
31. `/discovery` response shape parses with `DiscoveryResponse`/`DiscoveryContext` DTOs.
32. Milvus and SQLite providers produce identical orchestrator decisions (golden fixtures per provider).

### Schema parity (vector store)
33. Every collection/table in the schema contract carries `data_source_id` as the partition field, and only that field is added to the built-in schema (golden schema diff test vs. `VECTOR_DATABASE_RAG_SUMMARY.md`).
34. Field names, types, vector dimensions (1536) and cosine semantics match the built-in records (`TableSchemaRecord`, `FewShotRecord`, `ValueIndexRecord`) and side-table DDL.
35. Records from two `data_source_id` values can coexist in one collection with no cross-source leakage in search, delete, or upsert by key.
36. No `few_shots_meta` side table: the deterministic exact pre-check scans the `few_shots` data table.
37. Only `status = 'Approved'` precomputed rows are vector-searchable; the deterministic exact pre-check additionally reads `Modified` rows (matching built-in commit `eeb19de9` semantics).

### Skills folder parity (migration by copy)
38. A golden built-in data-source skills folder (fixture produced by the built-in `SchemaLibraryBuilder`/legacy ingestion) imports byte-identically (minus `vector-index.db`) via the Octofy Agent import surface.
39. Folder-copy migration then rebuild: vector collections regenerated from the copied files match the source's rebuilt vectors (same embedded texts → same nearest neighbors; golden fixture comparison), for `schemas`, data-group vectors, and precomputed-query vectors.
40. The importer rejects uploads containing `vector-index.db` and reports every schema/object/group/Q&A/tool entry imported; data groups and precomputed Q&A (incl. `smq_query`) round-trip through `.data-group-index.json` / `<group>-group-qas.md`.
41. No cross-source leakage after import: content imported for source A never answers source B (see also item 35).
42. Few-shot KB / value-index / semantic models, which the built-in stores only in `vector-index.db`, are explicitly *not* claimed by folder copy; their migration path is the Octofy Agent store/admin endpoints (documented gap, verified by test).

---

## 16) Parity Risks and Mitigations

### Risk: retrieval behavior drift
Mitigation: freeze constants; assert branch decisions in tests; use golden fixtures captured from the C# engine.

### Risk: score-scale mismatch between SQLite and Milvus (or per-source partitions)
Mitigation: provider-level score normalization policy; backend-specific golden tests for threshold-sensitive branches (`kb_exact`, `precomputed_exact`, `kb_direct`); calibration tests comparing ranked-order stability.

### Risk: vector schema/index incompatibility across providers
Mitigation: centralize collection/index schema definitions in a shared contract; version collection metadata; migration/bootstrap scripts that partition by `source_id`.

### Risk: DB validator semantics differ per driver/dialect
Mitigation: adapter abstraction; DBMS-specific integration tests; normalized error extraction feeding `SqlErrorClassifier`.

### Risk: LLM provider payload differences (the Octofy Agent must stay provider-agnostic)
Mitigation: follow `LlmRequestConventions` (memory/doc `LlmRequestConventions`): `max_tokens` vs `max_completion_tokens` per model family, reasoning-effort values, temperature omission rules (OpenAI reasoning family, DeepSeek reasoner, Moonshot fixed temperature), DeepSeek having no `thinking.budget_tokens`, `reasoning_content` fallback for empty content, question-generation token budgets, MiniMax OpenAI-compat host, Responses-API vs chat-completions tool shapes, Google OpenAI-compat Bearer auth.

### Risk: prompt/token budget drift
Mitigation: explicit token-accounting hooks; snapshot tests for prompt sections; bounded history/context pruning.

### Risk: SSE contract drift vs desktop client
Mitigation: contract tests parse `GenerateSQLResponse`/`SseEventEnvelope` with the exact `OctofyAgentHelper` DTOs; additive-only field changes.

### Risk: multi-source data leakage
Mitigation: `source_id`-scoped store bundles and caches; integration test asserting isolation under concurrency; never embed `source_id` into object context (built-in schema keys are `dataSource|schema` only server-internally).

---

## 17) Definition of Done (Port Complete)

A target Python port inside the Octofy Agent is complete only when:
1. All required constants and branch labels are preserved (Section 3, Section 13).
2. All validation stages execute in the same order with the same skip rules.
3. Deterministic circuit-break, loop-breaker, and protected-recovery semantics match.
4. Semantic-layer behavior (SMQ prompt, compile, critic, expansion, error taxonomy) matches the built-in integration points.
5. Every data-touching call is `source_id`-scoped and isolation is proven under concurrency.
6. Test matrix passes with equivalent outcomes, including the transport-parity tests against the desktop client DTOs.
7. Telemetry fields are populated and comparable; SSE status events fire per stage.
8. Human review confirms SQL generation, error handling, and retry behavior parity on representative workloads against a built-in agent on the same data source.

---

## 18) Recommended Repository Layout (Octofy Agent service)

```text
octofy-agent/                      # FastAPI service (one process, many sources)
  app/
    main.py                        # app factory, health, OpenAPI
    routers/
      discovery.py                 # POST /api/v1/discovery
      generation.py                # POST /api/v1/generation/generate-sql (+ legacy alias)
      admin_schema.py              # schema/object admin routes
      admin_kb.py                  # few-shots + precomputed queries
      admin_values.py
      admin_semantic.py            # models, extract, compile, settings
      data_sources.py              # CRUD + resolve
      users.py, conversations.py, contributions.py
    schemas/                       # Pydantic contracts (Section 5)
      requests.py, responses.py, sse.py, stores.py
  core/
    orchestrator/                  # builtin_sql_generator.py (Stage A–F)
      preprocessing.py, router.py, attempts.py
    constants.py                   # Section 3 values, single source of truth
    branch_taxonomy.py
    errors.py                      # taxonomy + failure report builders
  services/
    stores/                        # SourceStores resolution + adapters
      bundle.py                    # resolve SourceStores from data_source_id
      schema_contracts.py          # vector-index schema DDL + versions (single source
                                   #   of truth for every table/collection; Section 6)
      skills_folder.py             # built-in-parity skills folder layout + import/migration
                                   #   (Section 6: "Skills folder structure")
      sqlite_vec_provider.py       # per-source SQLite sidecar adapter
      milvus_provider.py           # Milvus adapter (data_source_id partition key)
    schema_index_service.py
    vector_search_service.py
    fewshot_vector_service.py
    value_index_service.py
    bm25_service.py
    sql_context_hydrator.py
    database_catalog.py            # pyodbc adapters per DBMS
    object_name_resolver.py
    query_interceptor.py
    sql_validator.py               # SQL Server + ODBC/dialect paths
    sql_error_classifier.py
    llm_client.py                  # provider-agnostic conventions
    tool_function_invoker.py       # MCP + sub-agent tools
    semantic_model_service.py
    semantic_compiler.py
    semantic_extraction_service.py
    data_group_query_service.py
    skills_importer.py             # copy-in + rebuild (skills folder -> source_id -> vector store)
  utils/
    regexes.py, dialect.py, sql_normalization.py, rrf.py, hashing.py, pii.py
  tests/
    unit/ integration/ parity/ contract/
```

Keep module boundaries clean so AI tools can regenerate individual services independently without changing orchestrator semantics.

---

## 19) Final Guidance for AI Implementers

When using this plan to implement the Octofy Agent backend:
- implement contracts first,
- implement deterministic paths before LLM-dependent paths,
- lock branch names, constants, and JSON field names early,
- add parity tests as each phase completes,
- treat every request as `source_id`-scoped; treat stores as per-source bundles,
- avoid "prompt-only shortcuts" that bypass validation/recovery contracts,
- keep LLM behavior provider-agnostic per `LlmRequestConventions`.

If behavior differs from this blueprint, treat it as a defect, not a style variation. For multi-backend vector support (SQLite + Milvus), treat the backend as an infrastructure concern only: retrieval outputs may come from different stores, but orchestration decisions, branch names, thresholds, retry behavior, semantic compilation, and validation order must remain identical — exactly as the built-in agent behaves for its one data source.
