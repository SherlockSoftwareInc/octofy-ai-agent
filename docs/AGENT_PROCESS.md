# Agent Process

This is the canonical description of how the Octofy AI Agent turns a natural-language request into validated SQL (or Python / R / SAS). It matches the built-in generator port in `app/core/orchestrator/`.

Related documents:

- [VECTOR_SCHEMA.md](VECTOR_SCHEMA.md) — vector collections, fields, embeddings, and `source_id` partitioning
- [REQUEST_TO_CODE_FLOW.md](REQUEST_TO_CODE_FLOW.md) — HTTP/SSE path from the client into this process
- [GENERATE_SQL.md](GENERATE_SQL.md) — generation plus execute / profile / insight workflow
- [DISCOVERY_STRATEGY_IMPLEMENTATION.md](DISCOVERY_STRATEGY_IMPLEMENTATION.md) — discovery branches and ranking

---

## 1. Entry and ownership

`POST /api/v1/generate-sql` streams Server-Sent Events. The HTTP wrapper is `app/services/generation_service.py` → `generate_sql_for_request()`. That wrapper still owns **non-generate** modes. The data-query generate path hands off to the orchestrator.

| Mode / intent | Owner | Produces SQL? |
|---|---|---|
| `queryMode` is `plan` or `ask` | `discuss_service.discuss_conversation()` | No — conversational reply |
| `queryMode` is `search` | `search_data_objects()` | No — object list |
| `forceGeneral=true` | `_handle_general_query()` | No |
| Intent `off_topic` | `_handle_general_query()` | No |
| Intent `system_metadata` | `build_system_catalog_prompt()` + 2 validation attempts | Yes, catalog views |
| Multiple matching `source_id`s | Wrapper returns a disambiguation message | No |
| `queryMode` is `generate` and `BUILTIN_SQL_GENERATOR=true` (default) | `generate_sql_builtin()` | Yes |

`source_id` is required for every store read. The wrapper resolves it from the request, the classifier's related sources, or the primary data source, then `build_source_stores(source_id)` constructs the per-source bundle (catalog, schema index, vectors, few-shots, values, precomputed queries, data groups, semantic models, BM25).

Python / R / SAS generation reuse the same orchestrator with `target_language` set. Semantic-model (SMQ) mode is SQL-only.

---

## 2. Pipeline stages

```
HTTP request
    │
    ▼
Wrapper: history fold, source resolve, intent gate
    │  (plan / ask / search / off-topic / system_catalog exit here)
    ▼
A  Preprocess → coreference rewrite + session filter inheritance → route (scenario)
B  Validate pinned objects
C  Fast paths (KB exact, precomputed exact, KB vector exact)
D  Query analysis + data groups + discovery (refinement: base-object anchor) + hydrate
E  Attempt loop (≤ 5 attempts, ≤ 120 s)
F  SSE result + done
```

SSE stage names come from `PipelineStage`: `routing`, `validate_pins`, `preanalysis`, `discovery`, `attempt`, `critic`, `db_validation`, `recovery`.

---

## 3. Stage A — Preprocess, context resolution, and route

**Files:** `preprocessing.py`, `coreference.py`, `session_context.py`, `scenario.py`, `router.py`

### 3.1 Preprocess

1. Mask PII in the user query.
2. Parse `queryHistory` into `Q:` / `A:` turns and fold them into `combined_query`. Older answers are truncated to 200 characters.
3. If the request has no pinned `database_objects`, auto-extract up to 5 qualified names (`schema.object`) from the query.
4. Set the provisional generation mode:
   - `debugging` when `existing_code` and `error_message` are both present
   - `optimization` when only `existing_code` is present
   - `fresh_start` otherwise

   `route()` replaces this with the classified **scenario** (Section 3.3).

### 3.2 Conversational context resolution (coreference + session filters)

Runs before intent classification and metadata retrieval.

1. **Session state** — `SessionSemanticContext` (keyed by the request's `session_id`, i.e. the chat section) holds `active_filters`, `active_domains`, `target_grain`, `turn_index` and `last_sql`. Without a `session_id` the same rules still run against the filters parsed out of the caller's own editor SQL, so filter preservation never depends on the client opting in.
2. **Filter extraction** — `extract_filters_from_sql()` collects literal predicates only (`col LIKE '%x%'`, `col = 'y'`, numeric/date bounds), resolving the owning table through FROM/JOIN aliases. Join predicates (`o.CustomerID = c.CustomerID`) are ignored.
3. **Lifecycle rules** (Phase 2.2):
   - *inheritance* — filters carry forward;
   - *negation / clear* — `for all products`, `clear filters`, `no filters`, `start over` empties the state;
   - *replacement* — `now do this for coffee` rewrites the established value `'%chocolate%'` → `'%coffee%'`, keeping attribute and structure.
4. **Coreference rewrite** — `resolve_coreference()` rewrites a short/elided turn against the last ≤3 turns and the active filters:

   | Input | Rewritten |
   |---|---|
   | `I need all order details` | `I need all order details for chocolate Products` |

   The LLM path returns `{rewritten_query, carried_filters, changed}` and is validated (non-empty, ≤ 400 chars, actually different). A deterministic fallback folds the session's own quoted `=`/`LIKE` filters back into the sentence, so the rewrite survives an unreachable LLM. Directed optimization edits (`format this`, `make it faster`) are **not** rewritten — their subject is the editor SQL.
5. **Prompt injection** — the resolved filters become `ACTIVE SESSION FILTERS` plus the `SCOPE GUARD` block on refinement turns.
6. The generated SQL's own filters are recorded back into the session (`record_generation_outcome`) so the next turn inherits what the query actually filtered on.

### 3.3 Route

Deterministic checks run before any LLM call:

| Condition | Route | Notes |
|---|---|---|
| `force_general` | Conversational | Immediate general result |
| `error_message` + `existing_code` | CodeFixing | Debugging; discovery still runs |
| Scenario `fresh_start` + `existing_code` | Generate | Explicit reset; discovery runs, editor SQL context dropped |
| Pinned `database_objects` + existing code, no error | Optimize / Refine | Refine when the scenario is refinement/drill_down |
| Pinned objects, no existing code | Generate | Pins validated in Stage B |
| Short query with a strong SQL signal | Generate | May skip LLM query analysis |
| Existing code, scenario `optimization` | Optimize | Skip discovery (provided-code path) |
| Existing code, scenario `refinement` / `drill_down` | Refine | Discovery kept (schema lookup + join resolution) |
| Inline SQL, no existing code | Generate | Skip discovery |
| LLM intent `app_feature` / `off_topic` | Conversational | Immediate result |
| LLM intent `optimize_code` + existing code | Optimize | Skip discovery |
| LLM intent `refine_query` + existing code | Refine | Discovery kept |
| Otherwise | Generate | Full discovery |

Intent labels: `db_query`, `optimize_code`, `refine_query`, `app_feature`, `off_topic`. If the classifier fails, the request is treated as `db_query`.

**Scenarios** (`scenario.py`) replace the old binary "SQL exists ⇒ optimization" check:

| Scenario | Meaning | Examples |
|---|---|---|
| `fresh_start` | No editor SQL, or the user explicitly resets | `start over`, `new query`, `forget the previous one` |
| `optimization` | Semantics-, filter-, entity- and grain-preserving edits | `format this`, `add indexing`, `convert to a CTE`, `tune performance`, `remove unused joins` |
| `refinement` | Output grain / attribute changes, filter replacement or negation | `I need all order details`, `add shipping date`, `now do this for coffee`, `for all products` |
| `drill_down` | Deeper grain or a new grouping dimension | `break this down by customer`, `per employee`, `group by country` |
| `debugging` | Error repair on the editor code | error message present |

Ordering is reset > drill_down > refinement > optimization > default. Structural additions (`add an index`, `add a comment`) stay optimization. When the deterministic signals are silent and the turn is short, the LLM classifies the scenario (16 tokens); with no LLM the historical default (optimization) is kept.

---

## 4. Stage B — Pin validation

If the user pinned objects, `ObjectNameResolver` resolves each name against the live catalog:

- Exact match → keep
- Fuzzy match with confidence ≥ 0.85 → substitute and record a note
- Missing → fail immediately with `priority_validation_failed` and a structured `failure_report` listing candidates

No generation runs when a pin cannot be resolved.

---

## 5. Stage C — Fast paths (no attempt loop)

These exit before discovery when a stored answer is exact enough.

```
KB exact (few_shots, canonical question key)
    │ miss
    ▼
Precomputed exact (vec_data_group_queries, Approved/Modified)
    │ miss
    ▼
KB vector top-1 (few_shots, cosine distance ≤ 0.05)
    │ miss
    ▼
Continue to Stage D
```

- **KB exact** (`kb_exact`): normalized question matches a few-shot row. SQL is returned as-is (or materialized into Python / R / SAS).
- **Precomputed exact** (`precomputed_exact`): same lookup against approved/modified data-group questions. In semantic mode the stored SMQ is compiled when present.
- **KB vector exact** (`kb_exact`): nearest few-shot with cosine distance ≤ `KbExactMatchThreshold` (0.05).

All three lookups use the coreference-rewritten query. A refinement/drill-down turn that carries active filters **bypasses** them: a stored answer authored without `ProductName LIKE '%chocolate%'` must not satisfy a turn that still filters on chocolate.

The provided-code optimize/rewrite path also skips discovery. It validates the supplied SQL (or script) and, on failure, allows one rewrite inside a 90-second budget (`no_discovery`). For the `optimization` scenario the model is called even when the editor code already validates — a modification request must produce a modification — under the strict *editor-code-only* rules of Section 7.1. If the rewrite does not validate, the original editor code is returned unchanged rather than failing the turn. Every other provided-code turn keeps the historical short-circuit.

---

## 6. Stage D — Discovery and context hydration

**Files:** `discovery_engine.py`, `sql_context_hydrator.py`

### 6.1 Query analysis

Unless the router skipped pre-analysis, the LLM returns JSON:

- `keywords`, `complexity` (`simple` / `moderate` / `complex`)
- `entities`, `date_ranges`, `filter_values`
- `extracted_columns` (bare column names, max 20)

Results are cached (100 entries). Complexity falls back to a regex heuristic when the LLM is skipped or fails.

### 6.2 Active data groups

Top 3 data groups are resolved by vector search, then keyword overlap if needed. Member tables become a later RRF signal and set the `group_anchored` branch when they appear in the merged result.

### 6.3 Discovery branches

`table_override` short-circuits to those objects only.

Otherwise discovery is **KB-first**:

1. Search few-shots (`top_k=3`, max cosine distance 0.35).
2. Collect column evidence (value-index seeds + column-entity vector hits).
3. Search precomputed questions for few-shot injection.

| Condition | Branch | Objects used |
|---|---|---|
| Best KB hit confidence ≥ 0.70 | `kb_direct` | Tables extracted from the matched SQL (fallback: column evidence) |
| KB hit below that threshold | `kb_gap_fill` | SQL tables ∪ column evidence |
| No KB hit | `dual_prong` | RRF merge of schema vectors, value index, few-shots, data groups, optional BM25 |
| Merged objects sit in an active data group | `group_anchored` | Same merge, labeled for analytics |
| Precomputed similarity ≥ 0.82 and not exact | `precomputed_related/<base>` | Same objects; precomputed examples injected into the prompt |

RRF (`k=60`) weights:

| Signal | Weight |
|---|---|
| Data group | 2.0 |
| Value index | 1.0 |
| Few-shot | 1.0 |
| Schema vector | 1.0 |
| BM25 | 0.5 (off unless `ENABLE_BM25_RETRIEVAL=true`) |

Merged list is capped at 8 objects. Pins are prepended as required. Discovery results are cached (256 entries).

Column evidence details:

- Filter values seed parent tables from `value_index` (`plain_value` substring match, seed score 0.80).
- Extracted columns (or the raw query) search `schemas` rows with `entity_type=Column`.
- Columns below 85% of the parent object's best column score are dropped.
- Objects with matched columns get +0.15 score (cap 1.0) and are marked required.

See [DISCOVERY_STRATEGY_IMPLEMENTATION.md](DISCOVERY_STRATEGY_IMPLEMENTATION.md) and [VECTOR_SCHEMA.md](VECTOR_SCHEMA.md).

### 6.4 Refinement scope expansion

For `refinement` / `drill_down` turns with editor SQL:

- the tables referenced by the editor SQL are promoted to **required** objects (`_base_objects_from_sql`) and merged ahead of the discovered list, so the established domain context is never dropped;
- discovery still runs, so the base tables and foreign-key joins (e.g. `[dbo].[Order Details]` ↔ `dbo.Orders` ↔ `dbo.Products`) needed by the deeper grain can be added;
- the branch label is prefixed (`refinement/<base>`, `drill_down/<base>`) for analytics;
- the prompt-context cap is widened to `RefinementPromptContextCap` (12) so base + newly discovered objects both fit.

The prompt itself then carries `REFINEMENT INSTRUCTIONS` (Section 7.1).

### 6.5 Hydration

`SqlContextHydrator` builds four prompt slices from skills-folder markdown (fallback: short description + matched columns):

| Field | Contents |
|---|---|
| `selected_object_context` | Required / priority objects |
| `supplementary_objects` | Remaining objects that fit the 6,400-token budget |
| `schema_context` | Combined selected + supplementary |
| `schema_context_for_validation` | Same blocks plus `-- Matched column evidence` lines |

Required objects always win a slot. Other objects below 5% of the best remaining score are dropped. The prompt cap is 8 objects. Over-budget markdown is column-pruned to matched columns.

---

## 7. Stage E — Attempt loop

**File:** `attempts.py`

Budgets: **5 attempts**, **120 seconds**. Semantic compilation has a 5-second timeout per compile.

Each attempt:

1. Build dialect-specific system + user prompts (`prompts.py`). Semantic mode asks for a fenced ` ```smq ` JSON payload instead of SQL.
2. Call the LLM. After a hallucination loop is detected, a presence penalty of 0.4 is applied.
3. Extract SQL (or Python / R / SAS body). Embedded SQL in scripts is schema-qualified against discovered objects.
4. Semantic mode: parse SMQ → `SemanticCompiler.compile()`. One parse retry, then optional raw-SQL fallback (`SEMANTIC_COMPILATION_FALLBACK_TO_RAW_SQL`).
5. Validate in a **frozen order** (do not reorder):

```
Safety interceptor
    → validation sentinels in the model output
    → structural hash (hallucination loop)
    → attempt-1 DB pre-check (skip critic if it already passes)
    → LLM critic (requirements + schema)
    → database validation (SET NOEXEC ON / dialect EXPLAIN)
```

### 7.1 Scenario rules in the system prompt

Every SQL / Python / R / SAS prompt carries a `GENERATION MODE` block plus the scenario's rules (`prompts.py`):

- **`optimization`** — `OPTIMIZATION INSTRUCTIONS`: *work exclusively from the SQL shown; do not consult any catalog, schema, or knowledge base; do not invent, add, or remove tables or columns; preserve filters, joins, entities and output grain; change only syntax, structure, formatting or performance.* The provided-code optimizer prompt (`build_optimization_system_prompt`) embeds the editor code as the only permitted source.
- **`refinement` / `drill_down`** — `REFINEMENT INSTRUCTIONS`: (1) base context on the editor SQL and conversation history, (2) scope expansion is authorized — query base tables and establish the foreign-key joins the requested granularity needs, (3) filter preservation — established domain filters must survive into the new query structure.
- **active filters** — `ACTIVE SESSION FILTERS` lists the inherited filters; when any exist, `SCOPE GUARD` states: *preserve all active filters from preceding turns unless the user explicitly requests their removal.*
- **`fresh_start` / `debugging`** — no scenario rule block.

### 7.2 Safety

`QueryInterceptor` (and language-specific interceptors) block writes unless the user explicitly asked for INSERT / UPDATE / DELETE / DROP in user-code mode. A safety failure is terminal (`error_category=safety`).

### 7.3 Sentinels and missing-object recovery

If the model emits table/column validation sentinels, or the database reports a missing object, discovery expands by up to 5 extra objects from schema search (and semantic models). The same missing object twice trips the circuit breaker (`deterministic_missing_object`).

The critic status `MISSING_GROUP_MEMBER` triggers one broadened recovery pass.

### 7.4 Hallucination loop

A structural hash of the candidate is recorded. A repeated hash increments `hallucination_count`. Exit after 2 repeats, or 1 repeat once the missing-object breaker has fired.

### 7.5 Critic

The critic returns JSON: `requirements_satisfied`, `schema_valid`, `feedback`, `missing_objects`, optional `canonical_question`. Failed requirements retry the attempt. Failed schema expands missing objects and retries.

### 7.6 Database validation

`SqlValidator` parse-checks SQL against the target source. SQL Server uses `SET NOEXEC ON`. Other dialects use `EXPLAIN` / `PREPARE`. Generated SQL that references objects outside the discovered allow-list fails as out of scope.

Scripts (Python / R / SAS) are syntax-checked first; each embedded SQL statement is then validated.

On success the loop returns `BuiltInGenerateResult` with SQL, `discovery_branch`, attempt count, token usage, processing time, hallucination / agentic-retry counts, and the prompt as `context_text`.

On exhaustion it returns a structured `failure_report` (summary, resolution plan, per-attempt notes, candidates).

---

## 8. Stage F — HTTP result

`BuiltInGenerateResult` is mapped to `GenerateSQLResponse`:

| Field | Meaning |
|---|---|
| `sql` | Generated statement or script |
| `explanation` / `message` | Status or failure summary |
| `query_type` | `database`, `general`, `python_code`, `r_code`, `sas_code` |
| `discovery_branch` | Branch label from Section 6.3 |
| `success` | Whether validation passed |
| `attempts` | Attempt count |
| `token_usage` | Prompt / completion / total |
| `processing_time_ms` | End-to-end time |
| `hallucination_count` | Repeated-structure count |
| `agentic_retry_count` | Recovery expansions |
| `canonical_question` | Critic-normalized question when present |
| `error_category` | See `ErrorCategory` |
| `failure_report` | Structured failure payload |
| `context_text` | Prompt used on the last attempt |
| `source_id` | Data source that was queried |

The stream then emits `{ "type": "done" }`.

---

## 9. Execution (after generation)

Execution is a separate `POST /api/v1/execute-sql` call. It is **not** part of the generate attempt loop.

1. Run the SQL with timeout and row limit.
2. On error, regenerate with the error message (up to 5 times).
3. If `ENABLE_AI_DATA_ANALYSIS` is true: profile the result, generate insights, recommend a chart.

See [GENERATE_SQL.md](GENERATE_SQL.md#sql-execution--analysis).

---

## 10. Key files

| Area | Path |
|---|---|
| HTTP generate / execute | `app/api/endpoints/generation.py` |
| Wrapper + non-generate modes | `app/services/generation_service.py` |
| Orchestrator entry | `app/core/orchestrator/builtin_sql_generator.py` |
| Preprocess | `app/core/orchestrator/preprocessing.py` |
| Scenario classification | `app/core/orchestrator/scenario.py` |
| Coreference rewrite | `app/core/orchestrator/coreference.py` |
| Session filter state | `app/core/orchestrator/session_context.py` |
| Router | `app/core/orchestrator/router.py` |
| Discovery | `app/core/orchestrator/discovery_engine.py` |
| Prompts | `app/core/orchestrator/prompts.py` |
| Attempt loop | `app/core/orchestrator/attempts.py` |
| Constants / thresholds | `app/core/constants.py` |
| Branch labels | `app/core/branch_taxonomy.py` |
| Pipeline models | `app/models/pipeline.py` |
| Per-source stores | `app/services/stores/bundle.py` |
| Discuss / ask | `app/services/discuss_service.py` |

---

## 11. Constants (must match the built-in engine)

Do not retune these unless there is a deliberate product change. Values live in `app/core/constants.py`.

| Constant | Value |
|---|---|
| `MaxRetries` | 5 |
| `MaxGenerationTimeMs` | 120 000 |
| `NoDiscoveryTimeBudgetMs` | 90 000 |
| `KbExactMatchThreshold` | 0.05 (cosine distance) |
| `KbConfidenceThreshold` | 0.70 |
| `KbScoreThreshold` | 0.35 |
| `DefaultObjectSearchVectorScoreThreshold` | 0.50 (admin-overridable) |
| `DefaultPrecomputedQueryDirectMatchThreshold` | 0.93 (cosine similarity) |
| `DefaultPrecomputedQueryFewShotThreshold` | 0.82 |
| `PrecomputedQueryTopK` | 3 |
| `RrfK` | 60 |
| `MaxRerankTables` | 8 |
| `ActiveDataGroupTopN` | 3 |
| `SchemaContextTokenBudget` | 6 400 |
| `PromptContextDiscoveryCap` | 8 |
| `RefinementPromptContextCap` | 12 (refinement/drill_down only) |
| `MissingObjectBreakThreshold` | 2 |
| `FuzzyMatchMinConfidence` | 0.85 |
| `MaxRecoveryExpansion` | 5 |
| `HallucinationExitThreshold` | 2 (1 after breaker) |
| `VECTOR_SCHEMA_VERSION` | `1.1.0` |

Admin-tunable: `PRECOMPUTED_QUERY_DIRECT_MATCH_THRESHOLD`, `PRECOMPUTED_QUERY_FEW_SHOT_THRESHOLD`, `OBJECT_SEARCH_VECTOR_SCORE_THRESHOLD`, `ENABLE_BM25_RETRIEVAL`, `ENABLE_SEMANTIC_LAYER_PER_DATA_SOURCE`.
