# SQL Generation and Execution

How Octofy turns a natural-language question into validated SQL, then optionally executes it.

- **Generate** (`POST /api/v1/generate-sql`) — parse-check only. Owned by the built-in orchestrator. Details: [AGENT_PROCESS.md](AGENT_PROCESS.md).
- **Execute** (`POST /api/v1/execute-sql`) — run the statement, retry on runtime errors, profile, insights, chart hint.

---

## Generate workflow

```
User query
    │
    ▼
generation_service (mode + intent gate)
    │  plan/ask → discuss
    │  search → object list
    │  off_topic / forceGeneral → chat
    │  system_metadata → catalog SQL (2 attempts)
    │  generate →
    ▼
generate_sql_builtin
    │
    ├─ Route (and pin validation)
    ├─ Fast path: KB / precomputed exact
    ├─ Discover + hydrate
    └─ Attempt loop (≤ 5, ≤ 120 s)
           safety → sentinels → hash → critic → SET NOEXEC ON
    │
    ▼
GenerateSQLResponse (SSE result + done)
```

### Request fields that change the path

| Field | Effect |
|---|---|
| `queryMode` | `generate` enters the orchestrator; `plan`/`ask`/`search` do not |
| `source_id` | Selects the store bundle |
| `database_objects` | Pins; catalog-validated; fail-fast if missing |
| `table_override` | Exclusive object set; skips retrieval |
| `existing_code` / `previousSQL` | Optimization or debug mode |
| `error_message` | Debugging route |
| `forceGeneral` | Skip SQL entirely |
| `semantic_mode` | SMQ compile path (SQL only) |
| `queryHistory` | Folded into `combined_query` |

### Discovery (short)

KB-first. Strong few-shot → `kb_direct`. Weaker hit → `kb_gap_fill`. Otherwise RRF of schema vectors, value-index seeds, few-shot tables, data groups, optional BM25 → `dual_prong` or `group_anchored`.

See [DISCOVERY_STRATEGY_IMPLEMENTATION.md](DISCOVERY_STRATEGY_IMPLEMENTATION.md).

### Prompt

Built in `app/core/orchestrator/prompts.py`: dialect rules, mode, query analysis, data groups, examples, value mappings, selected + supplementary schemas, attempt history.

### Validation order (do not reorder)

1. Safety interceptor (writes blocked unless the user asked for them)
2. Model validation sentinels
3. Structural hash (hallucination loop)
4. Attempt-1 database pre-check (can skip the critic)
5. LLM critic (requirements + schema)
6. Database parse (`SET NOEXEC ON` on SQL Server; `EXPLAIN` / `PREPARE` elsewhere)

Missing objects expand discovery (max 5 per pass). The same miss twice trips a circuit breaker.

### Result fields

`sql`, `explanation`, `query_type`, `discovery_branch`, `success`, `attempts`, `token_usage`, `processing_time_ms`, `hallucination_count`, `agentic_retry_count`, `canonical_question`, `error_category`, `failure_report`, `context_text`, `source_id`.

### Other languages

`generate_python_builtin` / `generate_r_builtin` / `generate_sas_builtin` call the same pipeline. Scripts are syntax-checked; embedded SQL is validated. Semantic mode is disabled.

---

## SQL execution and analysis

Execution is a separate request. It does not reuse the generate attempt loop.

```
POST /api/v1/execute-sql
    │
    ▼
execute_sql_query (timeout, max_rows, multi-result-set)
    │
    ├─ error → regenerate_sql_with_error_feedback (up to 5)
    │
    ▼
If ENABLE_AI_DATA_ANALYSIS:
    ProfilingService → InsightService → VisualizationService
    │
    ▼
ExecuteSQLResponse
```

### Execute request

```http
POST /api/v1/execute-sql
Content-Type: application/json

{
  "sql": "SELECT TOP 10 * FROM dbo.Customers",
  "source_id": "northwind",
  "context": {
    "user_query": "Show customers",
    "schema_context": "..."
  },
  "timeout_seconds": 30,
  "max_rows": 10000,
  "chart_type_override": "column"
}
```

### Runtime retry

`execute_sql_endpoint` runs the statement. On failure it calls `regenerate_sql_with_error_feedback()` and retries, up to 5 times. The response sets `auto_fixed`, `fix_attempt`, and `original_error` when a retry succeeded.

### Execution service

`validation_service.execute_sql_query()`:

- Configurable timeout (default 30s) and row cap (default 10,000)
- Fetches every result set
- Serializes datetime → ISO 8601, Decimal → float, bytes → base64

Profiling is skipped when `ENABLE_AI_DATA_ANALYSIS=false`.

### Profiling

`ProfilingService.profile_dataframe()`:

| Level | When | Contents |
|---|---|---|
| Basic | Always | Row/column counts, types, null % |
| Distribution | < 10k rows | Min/max/mean/median/std, quartiles, outliers, top values |
| Relationship | < 5k rows and < 10 columns | Correlation matrix, \|r\| > 0.7 pairs |

### Insights and charts

`InsightService` mixes rules (outliers, trends, missing data, correlations) with an LLM pass for ranking.

`VisualizationService.get_chart_recommendation()` picks a chart type and axes. `chart_type_override` wins when the user named a chart in chat.

---

## API sketches

### Generate (SSE)

```http
POST /api/v1/generate-sql
X-API-Key: ...

{
  "query": "Show monthly revenue for 2024",
  "queryMode": "generate",
  "source_id": "northwind"
}
```

```
data: {"type":"status","step":"discovery","message":"Discovering relevant objects"}

data: {"type":"result","payload":{"sql":"SELECT ...","discovery_branch":"dual_prong","success":true}}

data: {"type":"done"}
```

### Execute

```json
{
  "success": true,
  "output": { "columns": ["Month", "Revenue"], "data": [...] },
  "results": [...],
  "recommendation": { "chart_type": "column", "x_axis": "Month", "y_axis": ["Revenue"] },
  "execution_time": 0.42,
  "rows_affected": 12,
  "data_profile": {},
  "insights": [],
  "auto_fixed": false,
  "fix_attempt": 1
}
```

Standalone discovery: `POST /api/v1/discovery` → `discover_for_api()` (same engine, no generation).

---

## Configuration

```env
BUILTIN_SQL_GENERATOR=true
OBJECT_SEARCH_VECTOR_SCORE_THRESHOLD=0.5
PRECOMPUTED_QUERY_DIRECT_MATCH_THRESHOLD=0.93
PRECOMPUTED_QUERY_FEW_SHOT_THRESHOLD=0.82
ENABLE_BM25_RETRIEVAL=false
ENABLE_SEMANTIC_LAYER_PER_DATA_SOURCE={}
SEMANTIC_COMPILATION_FALLBACK_TO_RAW_SQL=true
ENABLE_AI_DATA_ANALYSIS=true
ENABLE_JOIN_PATH_VALIDATION=true
```

`ENABLE_JOIN_PATH_VALIDATION` applies only to the **legacy** wrapper path (`BUILTIN_SQL_GENERATOR=false`). The built-in loop uses the critic + database validator instead.

Thresholds and retry budgets: [AGENT_PROCESS.md](AGENT_PROCESS.md#11-constants-must-match-the-built-in-engine).

---

## Key files

| Role | File |
|---|---|
| HTTP generate / execute | `app/api/endpoints/generation.py` |
| Wrapper / discuss / catalog | `app/services/generation_service.py` |
| Orchestrator | `app/core/orchestrator/builtin_sql_generator.py` |
| Discovery | `app/core/orchestrator/discovery_engine.py` |
| Attempts | `app/core/orchestrator/attempts.py` |
| Parse-check + execute | `app/services/validation_service.py`, `app/services/sql_validator.py` |
| Profile / insight / chart | `app/services/profiling_service.py`, `insight_service.py`, `visualization_service.py` |

---

## Related docs

- [AGENT_PROCESS.md](AGENT_PROCESS.md)
- [VECTOR_SCHEMA.md](VECTOR_SCHEMA.md)
- [REQUEST_TO_CODE_FLOW.md](REQUEST_TO_CODE_FLOW.md)
- [SQL_EXECUTION_AUTO_RETRY_FEATURE.md](SQL_EXECUTION_AUTO_RETRY_FEATURE.md)
- [PYTHON_CODE_AUTO_RETRY_FEATURE.md](PYTHON_CODE_AUTO_RETRY_FEATURE.md)
