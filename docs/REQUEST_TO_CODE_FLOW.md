# Request to Code Generation Flow

End-to-end path from a chat request to validated code. Process internals live in [AGENT_PROCESS.md](AGENT_PROCESS.md). Storage internals live in [VECTOR_SCHEMA.md](VECTOR_SCHEMA.md).

---

## Architecture

```
┌─────────────────────────────┐
│  Frontend (React chat)      │
│  queryMode, source_id, SSE  │
└──────────────┬──────────────┘
               │ POST /api/v1/generate-sql
               ▼
┌─────────────────────────────┐
│  generation.py              │
│  Auth, activity log, SSE    │
└──────────────┬──────────────┘
               ▼
┌─────────────────────────────┐
│  generation_service         │
│  Modes + intent gate        │
└──────────────┬──────────────┘
               │ queryMode=generate
               ▼
┌─────────────────────────────┐
│  generate_sql_builtin       │
│  Route → Discover → Attempt │
└──────────────┬──────────────┘
               │
     ┌─────────┼──────────┐
     ▼         ▼          ▼
 PostgreSQL  Vector     SQL Server
 (users)     store      (validate)
```

**Key components**

- Frontend: `frontend/src/App.tsx` — conversation, mode, EventSource
- API: `app/api/endpoints/generation.py`
- Wrapper: `app/services/generation_service.py`
- Orchestrator: `app/core/orchestrator/`
- Stores: `app/services/stores/bundle.py` (per `source_id`)
- Vector contract: `app/services/stores/schema_contracts.py`

---

## 1. Client request

The user submits a query and a mode:

| `queryMode` | Meaning |
|---|---|
| `generate` | SQL generation (default orchestrator path) |
| `generate-python` / `generate-r` / `generate-sas` | Same orchestrator, different language |
| `plan` / `ask` | Discuss pipeline — no SQL |
| `search` | Object search — no SQL |
| `code-advisor` | Separate advisor endpoint |

Typical payload:

```json
{
  "query": "Show top customers by revenue",
  "queryMode": "generate",
  "source_id": "northwind",
  "database_objects": [],
  "table_override": [],
  "existing_code": null,
  "error_message": null,
  "previousSQL": null,
  "queryHistory": "Q: ... | A: ...",
  "forceGeneral": false,
  "semantic_mode": null,
  "top_k": 8
}
```

---

## 2. API and streaming

`POST /api/v1/generate-sql` authenticates (API key or JWT), logs the request, and streams SSE:

```
data: {"type":"status","step":"routing","message":"Validating and routing request",...}

data: {"type":"result","payload":{ "sql":"...", "discovery_branch":"kb_direct", "success":true, ... }}

data: {"type":"done"}
```

Status step names: `routing`, `validate_pins`, `preanalysis`, `discovery`, `attempt`, `critic`, `db_validation`, `recovery`.

---

## 3. Wrapper gate (before the orchestrator)

`generate_sql_for_request()` folds conversation history, loads data-source metadata, and classifies intent.

| Exit | Result |
|---|---|
| `plan` / `ask` | `discuss_conversation()` |
| `search` | `search_data_objects()` |
| `forceGeneral` or intent `off_topic` | Conversational answer |
| Multiple related `source_id`s | Ask the user to pick one |
| Intent `system_metadata` | Catalog-view SQL, 2 validate attempts, branch `system_catalog` |
| `generate` + `BUILTIN_SQL_GENERATOR` | Hand off to `generate_sql_builtin()` |

The leftover path in `generation_service.py` (three-pronged discovery, join-path sufficiency) is the pre-port implementation. It is not used when the built-in generator flag is on (the default).

---

## 4. Orchestrator (generate)

See [AGENT_PROCESS.md](AGENT_PROCESS.md) for the full stage list. Summary:

1. **Preprocess** — PII mask, fold history, auto-extract object names, set `fresh_start` / `optimization` / `debugging`.
2. **Route** — deterministic fast paths, then LLM intent (`db_query` / `optimize_code` / `app_feature` / `off_topic`).
3. **Validate pins** — catalog resolve; fuzzy ≥ 0.85; fail-fast if missing.
4. **Fast paths** — KB exact → precomputed exact → KB vector exact (distance ≤ 0.05).
5. **Discover** — KB-first, then RRF (`dual_prong` / `group_anchored` / `kb_direct` / `kb_gap_fill`).
6. **Hydrate** — markdown under a 6,400-token budget, cap 8 objects.
7. **Attempt loop** — up to 5 tries / 120 s. Frozen validation: safety → sentinels → structural hash → critic → `SET NOEXEC ON`.
8. **Result** — `GenerateSQLResponse` plus optional `failure_report`.

Python / R / SAS call the same function with `target_language` set. Semantic mode compiles SMQ JSON instead of asking the LLM for raw SQL.

---

## 5. Discovery in one page

```
table_override? ──yes──► those objects only
        │ no
        ▼
KB few-shot (distance ≤ 0.35)
        │
   confidence ≥ 0.70 ──► kb_direct (tables from matched SQL)
        │ below
        ├── hit ──► kb_gap_fill (SQL tables ∪ column evidence)
        └── miss ─► RRF: schema vectors + value index + few-shots
                     + data groups (+ BM25 if enabled)
                     → dual_prong or group_anchored
```

Column evidence: `value_index` substring seeds + `schemas` column-entity vector hits. Details: [DISCOVERY_STRATEGY_IMPLEMENTATION.md](DISCOVERY_STRATEGY_IMPLEMENTATION.md).

---

## 6. Prompt shape

The system prompt (SQL mode) includes:

- Target dialect rules
- Generation mode
- Query analysis (complexity, keywords, entities)
- Active data groups
- Knowledge-base / precomputed examples
- Verified value mappings (`value → table.column`)
- Selected and supplementary schemas
- Compact attempt history

Output: optional `/* reasoning */` plus a single fenced SQL statement. Semantic mode: a ` ```smq ` JSON block (`metrics`, `dimensions`, `filters`, `timeframes`).

---

## 7. Validation and recovery

| Layer | On failure |
|---|---|
| Safety interceptor | Terminal `safety` error |
| Model sentinels / missing object | Expand up to 5 objects; breaker after 2 repeats of the same miss |
| Structural hash repeat | Hallucination counter; exit after 2 (or 1 after breaker) |
| Critic requirements | Retry with feedback |
| Critic schema / `MISSING_GROUP_MEMBER` | Expand or one broadened group pass |
| Database parse (`SET NOEXEC ON`) | Classify error, expand, retry |

Success returns the SQL. Exhaustion returns the last error and a `failure_report` (summary, resolution plan, per-attempt notes, candidates).

---

## 8. Frontend display and optional execute

The client appends status steps, then renders `payload.sql` and `explanation`. Execute is a **second** call: `POST /api/v1/execute-sql` (timeout, row limit, optional auto-retry, profiling, insights). That path is not the generate attempt loop.

---

## 9. Planning / ask vs generate

`plan` and `ask` do **not** enter the orchestrator. They use `discuss_service` (tool lookup + conversational reply). When the user later clicks generate, the client sends `queryMode=generate` (optionally with pinned objects or a planning summary) and this flow starts at Section 4.

---

## Related docs

- [AGENT_PROCESS.md](AGENT_PROCESS.md) — stages, branches, constants
- [VECTOR_SCHEMA.md](VECTOR_SCHEMA.md) — collections and fields
- [GENERATE_SQL.md](GENERATE_SQL.md) — generate + execute
- [PLANNING_MODE_FLOW.md](PLANNING_MODE_FLOW.md) — discuss / plan UI
- [BACKEND_API.md](BACKEND_API.md) — HTTP contract
