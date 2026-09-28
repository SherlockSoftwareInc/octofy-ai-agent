# Octofy AI Agent backend API

**Octofy AI Agent is an open-source project.** You can find the source code, report issues, and read the license on GitHub: [github.com/SherlockSoftwareInc/octofy-ai-agent](https://github.com/SherlockSoftwareInc/octofy-ai-agent) (MIT License).

Octofy Professional can use any **AI agent backend** that implements the contract described here. The [Octofy AI Agent](/products/octofy-ai-agent) product ships a FastAPI server that follows this API; third-party or in-house services can integrate with Octofy Pro by matching these routes, headers, request bodies, and streaming behavior. Only the HTTP surface matters: a backend that reproduces the routes below is a valid agent backend regardless of how it is implemented internally.

This page is the integration reference: base URL, authentication, data-source scoping, Server-Sent Events (SSE) for generation, discovery, execution and summarization, schema lookup, users and conversations, contributions, and admin endpoints.

## Blueprint: rebuild the agent with vibe coding

Octofy AI Agent is also a **build blueprint**, not just a running service. [`docs/SQL_GENERATION_BACKEND_BLUEPRINT.md`](https://github.com/SherlockSoftwareInc/octofy-ai-agent/blob/main/docs/SQL_GENERATION_BACKEND_BLUEPRINT.md) is a code-derived specification (§01–§16) that a developer — or an AI coding agent — can execute to build an equivalent natural-language-to-code agent from an empty repository:

- **Written to be executed, not skimmed.** Exact constants, a frozen validation order, verbatim prompt contracts (§08), algorithms given as pseudocode, field-by-field data contracts, and an acceptance test matrix (§14).
- **Verifiable.** Non-obvious claims cite `path/file.py:LINE`, so every statement can be cross-checked against the working service in the same repository.
- **Consumed one section at a time.** Each `## NN` section is self-contained and ends with its own checklist. §16.1 maps a target repository layout to the section that specifies each module, and §13 gives the build plan and milestones, including a reduced SQL-only vertical slice when the full pipeline is more than you need.
- **Made for AI-assisted rebuilds.** §02, *How to Build This With an AI Coding Agent*, documents the workflow the project calls **vibe coding**: point an AI coding assistant at the specification and have it implement the blueprint section by section, rather than pasting the whole document at once. §15 lists the invariants and non-obvious rules to insist on, and the repository's README carries the copy-paste prompts and a deviations log.

Because the blueprint is paired with the reference implementation in the same repository, you can read a section, then confirm the behaviour in code. The React app under `frontend/` is a demonstration harness for exercising this API — not a product — and is not required to run or rebuild the service.

---

## Backend feature summary

- Query discovery and context synthesis from the data source's schema library, vector store, value index, and knowledge base.
- Streaming generation for SQL, Python, R, SAS, and code-advisor responses (SSE) with staged progress events.
- Optional per-data-source semantic layer: a generation request can ask for a semantic model query (SMQ) that the server compiles against the source's active semantic model into physical SQL.
- SQL and Python execution endpoints with auto-fix retry loops, profiling, insights, and chart recommendations.
- Admin schema, few-shot (knowledge base), value-index, precomputed-query, semantic-model, settings, and vector-store backup operations.
- Multi-source data-source and schema-tree management APIs, including data-source resolution and a persistent source-id registry.
- Skills-library import plus vector rebuild endpoints for migrating a data source's knowledge files.
- Contribution submission plus admin approval workflow.
- User authentication, user management, user activity analytics, and conversation persistence.

---

## Technology stack (reference implementation)

| Technology | Purpose |
|------------|---------|
| FastAPI | Web framework |
| SQLAlchemy + pyodbc | SQL Server connectivity |
| Milvus | Vector search / indexing |
| OpenAI + LiteLLM | LLM + embeddings |
| Pydantic | Validation and response schemas |

Compatible backends may use different internals; callers depend on the HTTP API surface below, not on these libraries.

---

## Base URL, OpenAPI, and health

| Item | Value |
|------|-------|
| Base URL | `/api/v1` |
| Health check | `GET /` → `{"message":"Database AI Agent API is running"}` |
| OpenAPI spec | `GET /api/v1/openapi.json` |
| Swagger UI | `http://localhost:8000/docs` (typical dev URL) |

The health check is mounted at the server root, outside the `/api/v1` prefix. Octofy Pro reads `GET /` for the health message and `GET /api/v1/openapi.json` for the machine-readable spec, so both must be reachable on a host that Octofy Pro is configured to use.

---

## Authentication model

The API uses API-key authentication via the `X-API-Key` header.

```http
X-API-Key: <user-or-admin-api-key>
```

Keys are issued per user. `POST /api/v1/auth/login` returns the caller's key as `access_token`, and an administrator can create users or regenerate any user's key.

### Auth rules

- `POST /api/v1/auth/login` is public (username/password login).
- Most endpoints require a valid API key belonging to an **active** user; a missing key, an unknown key, or a deactivated user's key is rejected with `401`.
- Admin endpoints additionally require the key's user to have the `admin` role; a valid non-admin key gets `403`.
- A few routes verify only "any valid user key", so both admin and user keys work there: `/api/v1/discovery`, `/api/v1/test`, the generation and execution endpoints, `/api/v1/planning-summary`, `/api/v1/contributions`, and `GET /api/v1/admin/data-sources`.
- Regenerating a key invalidates the previous one immediately.

### Routes without an auth dependency (reference server)

The reference server mounts the following routes without an authentication dependency. They are documented here so integrators can decide whether to mirror that behaviour or protect them:

| Endpoint | Method | Notes |
|----------|--------|-------|
| `/` | GET | Health check |
| `/api/v1/auth/login` | POST | Username/password login |
| `/api/v1/schema/{object_name}` | GET | Schema lookup for one object |
| `/api/v1/summarize-results` | POST | Natural-language summary of a result preview |
| `/api/v1/admin/ingest-progress` | GET | SSE ingest progress |

Harden these routes in production if you mirror the API.

### Common error responses

| Status | Response |
|--------|----------|
| 400 | `{"detail": "Bad request"}` |
| 401 | `{"detail": "Invalid or missing API key"}` |
| 403 | `{"detail": "Insufficient permissions"}` |
| 404 | `{"detail": "Resource not found"}` |
| 409 | `{"detail": "<reason>"}` — a conflicting state, such as a rebuild already running or an env API key that is already set |
| 429 | `{"detail": "Rate limit exceeded. Try again in <n> seconds."}` — code advisor only |
| 500 | `{"detail": "Internal server error"}` |

Validation failures use the same `{"detail": ...}` shape with a specific message; for example a data-touching request without a data source returns `400` with `{"detail": "source_id is required"}`.

---

## Data-source scoping

The agent service is designed as **one server for many data sources**, so data-touching calls are scoped by a data source id.

| Item | Value |
|------|-------|
| Identifier | `source_id` (string GUID) |
| Placement | JSON body for discovery, generation, and execution; body, query, or multipart form parameters on admin store routes (see each section) |
| Discover ids | `GET /api/v1/admin/data-sources` (`data_sources[*].source_id`) |
| Resolve from connection details | `GET /api/v1/admin/data-sources/resolve` |

Rules:

- `POST /api/v1/discovery`, `POST /api/v1/generate-sql` (and `/api/v1/generation/generate-sql`), `POST /api/v1/generate-python`, `POST /api/v1/generate-r`, `POST /api/v1/generate-sas`, `POST /api/v1/execute-sql`, and `POST /api/v1/execute-python` require a resolved `source_id`. Omitting it returns `400` with `{"detail": "source_id is required"}`, and an id that is not in the registry returns `404`. The server does not fall back to a primary or first-listed source for these routes.
- Admin store routes take `source_id` in different ways: the precomputed-query routes, the semantic-model routes, and `/skills/rebuild/{source_id}` require it and answer `404` for an id that is not registered; `GET /admin/schema/status` accepts it as an optional filter; and routes such as `GET /admin/fewshots` and `GET /admin/values` are not source-scoped in the reference server.
- `POST /api/v1/admin/skills/import` is the exception: when the body's `source_id` is missing or unknown it falls back to the server's configured primary source.
- Data sources are soft-deleted, and deleted ids stay in the registry so they can be reused; the data-source list and the resolve route return active (non-deleted) sources only, while `/admin/data-sources/registry?include_deleted=true` can include deleted entries.
- The result payload of a successful SQL generation echoes the `source_id` the client should use when executing that SQL.

---

## Core endpoints

### Discovery

| Endpoint | Method | Notes |
|----------|--------|-------|
| `/api/v1/discovery` | POST | Semantic discovery (relevant tables, similar queries, glossary terms) |
| `/api/v1/test` | POST | Simple authenticated test endpoint; returns `{"message": "Test endpoint works"}` |

`POST /api/v1/discovery` accepts:

| Field | Type | Notes |
|-------|------|-------|
| `query` | string | Required. Natural-language search text |
| `top_k` | int | Optional. Result cap; default 5 |
| `source_id` | string | Required |

The response is `{"query", "reasoning", "context"}` where `context` contains `relevant_tables`, `similar_queries`, and `glossary_terms`. Each entry in `relevant_tables` carries `schema_name`, `table_name`, `description`, and `columns` entries with `name`, `data_type`, and `description`; the reference server's built-in generator path also returns `similarity_score` and `matched_columns`.

---

### Generation (streaming SSE)

All generation endpoints stream `text/event-stream`. Octofy Pro tries the canonical `/api/v1/generation/...` path first and falls back to the legacy top-level path when the canonical one answers `404`, so a backend may mount either or both:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/generation/generate-sql` (legacy alias: `/api/v1/generate-sql`) | POST | Generate, fix, or optimize T-SQL |
| `/api/v1/generate-python` (canonical: `/api/v1/generation/generate-python`) | POST | Generate Python code |
| `/api/v1/generate-r` (canonical: `/api/v1/generation/generate-r`) | POST | Generate R code |
| `/api/v1/generate-sas` (canonical: `/api/v1/generation/generate-sas`) | POST | Generate SAS code |
| `/api/v1/code-advisor` | POST | Streaming code advisor (rate-limited) |

The reference server mounts the `/api/v1/generation/` alias for SQL only and the legacy path for all four languages; the desktop client's fallback sequence therefore succeeds against it.

#### SSE event envelope

Every streamed line is `data: <json>` where the JSON is:

```json
{ "type": "status|result|done|error", "payload": { }, "message": "..." }
```

| `type` | Payload | Meaning |
|--------|---------|---------|
| `status` | `stage`, `step_id`, `source_id`, stage-specific extras | Step update |
| `result` | Generation result payload | Final answer |
| `done` | `{}` | Stream completion |
| `error` | `{"detail": ...}` | Failure; surface `message` |

`payload.stage` names the pipeline stage: `routing`, `validate_pins`, `preanalysis`, `discovery`, `attempt`, `critic`, `db_validation`, or `recovery`. Events for the `attempt` stage also carry `attempt` and `max_attempts` so a client can render progress such as "attempt 2 of 5". A backend that emits no `status` events at all is still valid; the client then shows a static progress label for the whole wait.

Reference-server generation behaviour:

- An empty `query` is rejected with `400`.
- The server runs up to **5** generation attempts under a **120 s** budget; the no-discovery rewrite path uses a **90 s** budget.
- When the request fails, the failure is reported through the `error` event and through the structured `failure_report` field of the result payload where available.

#### Result payload

The `result` payload uses these fields (extra fields are additive and may be ignored):

| Field | Type | Notes |
|-------|------|-------|
| `sql` | string | Generated code; may carry a failure message when the request failed |
| `explanation` | string | Conversational explanation when no code applies |
| `query_type` | string | `"database"` by default |
| `context_text` | string | Context used to produce the answer |
| `context_history` | string[] | Context list per attempt |
| `objects` | object[] | Discovered objects (`schema`, `name`, `type`, `auto_checked`) |
| `discovery_branch` | string | Discovery branch used, for diagnostics |
| `source_id` | string | Data source to use when executing this code |
| `is_code_edit` | bool | When true, the previous code box should be updated in place |
| `success` | bool | Pipeline outcome |
| `attempts` | int | Generation attempts used |
| `token_usage` | object | `prompt_tokens`, `completion_tokens`, `total_tokens` |
| `processing_time_ms` | int | Total processing time |
| `hallucination_count` | int | Repeated-output loop detections |
| `agentic_retry_count` | int | Validation-error recovery cycles |
| `canonical_question` | string | Self-contained restatement of the question |
| `error_category` | string | Failure category, for example `safety`, `requirement`, `schema`, `validation`, `timeout` |
| `failure_report` | object | Structured failure detail (`resolution_plan`, `attempts`, `final_resolution_guidance`) |
| `tool_event` | string | Tool chip name when a lookup ran |

#### Code advisor

`POST /api/v1/code-advisor` also streams `text/event-stream` but uses a slightly different envelope: `status` events are raw agent-status objects (`step_id`, `message`, `type`, `details`, `timestamp`), the final result is `{"type": "result", "payload": { ... }}`, completion is `{"type": "done"}`, and failures are `{"type": "error", "message": "..."}`.

It is rate limited to **10 requests per minute per API key**. Exceeding the limit returns `429` with a message stating how many seconds to wait, and allowed responses carry an `X-RateLimit-Info` header.

---

### Execution and summarization

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/execute-sql` | POST | Execute SQL with retry/auto-fix support |
| `/api/v1/execute-python` | POST | Execute Python with retry/auto-fix support |
| `/api/v1/planning-summary` | POST | Generate planning context summary |
| `/api/v1/summarize-results` | POST | Natural-language summary of result preview |

`/execute-sql` and `/execute-python` require a resolved `source_id` and return a single JSON document (they do not stream). Their responses include `success`, `output`, `error`, `results`, `recommendation` (chart type, axes, title), `execution_time`, `data_profile`, `insights`, `sql` or `code` for the final working statement, and the auto-fix metadata `auto_fixed`, `fix_attempt`, and `original_error`. `/execute-sql` additionally reports `rows_affected`.

`POST /api/v1/planning-summary` takes `{"planning_context": { ... }}` and returns `{"summary": "<markdown>"}`. It does not require a `source_id`.

`POST /api/v1/summarize-results` takes `user_request`, `result_data`, and an optional `chart_type`, and returns `{"summary": "<markdown>"}`. In the reference server this route has no auth dependency.

---

### Schema lookup

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/schema/{object_name}` | GET | Schema details for a specific object |

Notes:

- `object_name` must be a `schema.table` pair (brackets are tolerated); anything else returns `400`.
- An object that is not in the index returns `404`.
- The reference server mounts this route without an auth dependency, and it reads the vector store rather than a `source_id`-scoped store.

---

## User and conversation APIs

### Authentication and profile

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/auth/login` | POST | Login; returns API key as `access_token` (public) |
| `/api/v1/auth/me` | GET | Current user details |
| `/api/v1/users/me` | PUT | Update current user profile (email, full name, password) |
| `/api/v1/users/me/regenerate-api-key` | POST | Regenerate current user API key; the old key stops working |

### Admin user management

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/admin/users` | GET | List users (`skip`, `limit`) |
| `/api/v1/admin/users/{user_id}` | GET | User details |
| `/api/v1/admin/users` | POST | Create user (returns `201`) |
| `/api/v1/admin/users/{user_id}` | PUT | Update user |
| `/api/v1/admin/users/{user_id}` | DELETE | Delete user (returns `204`) |
| `/api/v1/admin/users/{user_id}/regenerate-api-key` | POST | Regenerate user API key |
| `/api/v1/admin/users/{user_id}/stats` | GET | User statistics (`days`, default 30) |
| `/api/v1/admin/users/{user_id}/activities` | GET | User activity log (`skip`, `limit`, `activity_type`, `success_only`, `start_date`, `end_date`) |
| `/api/v1/admin/users/overview` | GET | System-wide user overview (`days`, default 7) |

### Conversations

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/conversations` | GET | List current user conversations (`skip`, `limit`) |
| `/api/v1/conversations/{conversation_id}` | GET | Get conversation |
| `/api/v1/conversations` | POST | Create conversation (returns `201`) |
| `/api/v1/conversations/{conversation_id}` | PUT | Update conversation |
| `/api/v1/conversations/{conversation_id}` | DELETE | Delete conversation (returns `204`) |

Conversations are always scoped to the authenticated user; they do not take a `source_id`.

---

## Contributions

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/contributions` | POST | Submit contribution (any valid user key) |
| `/api/v1/admin/contributions` | GET | List pending contributions (admin) |
| `/api/v1/admin/contributions/approve` | POST | Approve contribution (admin) |
| `/api/v1/admin/contributions/{contribution_id}` | DELETE | Reject contribution (admin) |

Submission accepts `question` and `sql_query` (both required), plus optional `knowledge_type`, `user_id`, and `source_id`; the response reports `contribution_id` and a `similarity_warning` when the question is close to an existing knowledge-base entry. Approval takes `contribution_id` with optional `edited_question`, `edited_sql`, and `knowledge_type`, and returns the new `knowledge_base_id`. Approved contributions land in the target source's few-shot knowledge base.

---

## Admin APIs

All routes in this section are prefixed with `/api/v1/admin`. They require an admin key unless a note says otherwise.

### Schema management

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/schema/status` | GET | Indexed schema status |
| `/schema/sync` | POST | Sync one table |
| `/schema/sync-full` | POST | Full schema sync |
| `/schema/batch-sync` | POST | Batch table sync |
| `/schema/description` | PUT | Update description |
| `/schema` | DELETE | Delete schema |
| `/schema/export` | GET | Export schema index |
| `/schema/template` | GET | Download schema template |
| `/schema/clear` | POST | Clear schema index |
| `/ingest-schemas` | POST | Ingest schema Excel |

Notes:

- `/schema/status` accepts optional `include_db_inspection` and `source_id`; `/schema/sync` and `/schema/description` take `schema` and `table` query parameters; `/schema/clear` accepts an optional `source_id`.
- `/schema/export` and `/schema/template` return files (Excel); `/schema/batch-sync` takes `table_names` and an optional `source_id`.
- `/ingest-schemas` is a multipart upload with a `file`, a `mode` form field (default `append`), and an optional `source_id`.
- Octofy Pro also calls `POST /api/v1/admin/schema/sync-all`. The reference server does not mount that path (it returns `404`) and implements all-schema sync as `/schema/sync-full`; mount the alias if you want the client's all-schema call to succeed on the first attempt.

### Object-level schema library

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/object` | POST | Add object metadata |
| `/object/sync` | POST | Sync specific object |
| `/object` | DELETE | Delete object metadata |
| `/object/discover` | POST | Discover objects |
| `/enhance-schema` | POST | AI-assisted schema enhancement |

Notes: `/object`, `/object/sync`, and `/object/discover` take `source_id`, `schema_name`, and `object_name` (plus `object_type`) in the body; `DELETE /object` takes `source_id`, `schema`, and `object_name` as query parameters; `/enhance-schema` takes `file_path` and `current_content`.

### Few-shot (knowledge base)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/fewshots` | GET | List few-shots |
| `/fewshots` | POST | Add few-shot |
| `/fewshots/{item_id}` | DELETE | Delete few-shot |
| `/fewshots/export` | GET | Export few-shots |
| `/ingest-fewshots` | POST | Ingest few-shots from file |

An item carries `question`, `sql_query`, `knowledge_type` (default `sql_query`), `verified`, and an optional `source_id`. `/ingest-fewshots` is a multipart upload with `file`, `mode`, and an optional `source_id`.

### Value index

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/values` | GET | List value-index items |
| `/values/search` | GET | Search values |
| `/values/{item_id}` | DELETE | Delete value item |
| `/values/clear` | POST | Clear values |
| `/values/template` | GET | Download values template |
| `/values/export` | GET | Export values |
| `/ingest-values` | POST | Ingest values file (Excel/CSV) |
| `/ingest-progress` | GET | SSE ingest progress |

Notes:

- `/values/search` takes `query` and optional `top_k` (default 50).
- `/values/clear` accepts an optional `source_id`.
- `/ingest-values` is a multipart upload with `file`, `mode`, and an optional `source_id`.
- `/ingest-progress` streams `data:` events shaped `{"current", "total", "percentage", "status"}`, emitting every half second and stopping once the status is `complete` or `error`. In the reference server it has no auth dependency.

### Precomputed data-group queries

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/precomputed-queries` | GET | List precomputed queries for a source (`source_id` required, optional `status`) |
| `/precomputed-queries` | POST | Create or update a precomputed query; returns `{"query_id"}` |
| `/precomputed-queries/{query_id}/status` | POST | Set the review status of a query |

A precomputed item carries `question`, `sql_query`, `group_name`, an optional `group_file_name`, an optional `smq_query`, `status`, and an optional `query_id`; `status` is a free-form string that defaults to `Pending`, and Octofy Pro's review workflow uses `Approved`, `Modified`, and `Rejected` as reviewed states.

### Semantic models

The semantic layer is per data source. A generation request enables it with `semantic_mode` (or leaves it to the server's configured enablement for that source), and generation then returns SMQ-compiled physical SQL. Python, R, and SAS generation always run without the semantic layer.

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/semantic-models` | GET | List semantic models for a source |
| `/semantic-models` | POST | Save (upsert) a semantic model |
| `/semantic-models/extract` | POST | Extract a model from schema text and/or SQL |
| `/semantic-models/compile` | POST | Compile an SMQ payload into physical SQL |

Details:

- `source_id` is required on all four routes.
- A model carries `model_id`, `label`, `is_active`, `measures`, `dimensions`, `joins`, and optional `governance_predicates`.
- `/semantic-models/extract` takes `schema_text`, an optional `sql`, and an optional `label`, and returns the saved model.
- `/semantic-models/compile` takes an `smq` payload (`metrics`, `dimensions`, `filters`, `timeframes`) with an optional `dbms` (default `SQL Server`) and returns `{"sql": ...}`. It returns `404` when the source has no active model and `400` when compilation fails.

### Settings and connectivity

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/settings` | GET | Get settings (sensitive values masked) |
| `/settings` | PUT | Update settings |
| `/api-key` | GET | Read env API key |
| `/api-key` | POST | Set env API key |
| `/test-connection` | POST | Test DB connection |
| `/verify-settings` | POST | Verify DB/LLM/vector store |
| `/models` | GET | List available models |
| `/fetch-models` | POST | Fetch models from endpoint |
| `/build-connection-string` | POST | Build DB connection string |
| `/generator-thresholds` | GET | Read generation thresholds |
| `/generator-thresholds` | PUT | Update generation thresholds |

Notes:

- `/api-key` returns `{"api_key", "exists"}`; setting it returns `400` for an empty value and `409` when a key is already present.
- `/verify-settings` returns separate `db_connected`/`db_message`, `llm_connected`/`llm_message`, and `milvus_connected`/`milvus_message` results.
- `/generator-thresholds` exposes `precomputedQueryDirectMatchThreshold`, `precomputedQueryFewShotThreshold`, and `objectSearchVectorScoreThreshold`; the object-search threshold is clamped to the `0`–`1` range on update.

### Multi-source management

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/data-sources` | GET | List data sources |
| `/data-sources` | POST | Add data source |
| `/data-sources/{source_id}` | GET | Get data source |
| `/data-sources/{source_id}` | PUT | Update data source |
| `/data-sources/{source_id}` | DELETE | Delete data source |
| `/data-sources/{source_id}/scan` | POST | Trigger source scan |
| `/data-sources/{source_id}/scan-status` | GET | Scan status |
| `/data-sources/{source_id}/test` | POST | Connection test wrapper |
| `/data-sources/{source_id}/enable` | POST | Enable/disable source |
| `/data-sources/{source_id}/set-primary` | POST | Set primary source |
| `/data-sources/{source_id}/exclude-objects` | POST | Upload exclusion list |
| `/data-sources/{source_id}/exclude-objects` | GET | Get exclusion list |
| `/data-sources/{source_id}/exclude-objects` | DELETE | Delete exclusion list |
| `/data-sources/registry` | GET | List every registered source, including soft-deleted ones |
| `/data-sources/resolve` | GET | Resolve connection details to `source_id` |

Notes:

- `GET /api/v1/admin/data-sources` accepts any valid user `X-API-Key` in the reference implementation; the other routes in this table require an admin key.
- Use `data_sources[*].source_id` as the data source id and `data_sources[*].friendly_name` as the data source name.
- `POST /data-sources/{source_id}/enable` takes an `enabled` query parameter (default `true`), and `POST /data-sources/{source_id}/scan` accepts an optional body with connection details.
- `POST /data-sources/{source_id}/exclude-objects` is a multipart file upload.
- `GET /data-sources/registry` accepts `include_deleted` (default `false`) and returns the persistent id registry used for troubleshooting conversations that reference deleted sources.

#### Data source resolution

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/data-sources/resolve` | GET | Resolve connection details to `source_id` |

The full path is `/api/v1/admin/data-sources/resolve`; Octofy Pro also probes the un-prefixed `/api/v1/data-sources/resolve` first and falls back to the admin path on `404`.

**Query parameters**

For SQL Server sources:

- `server` — server name (required with `database`)
- `database` — database name (required with `server`)

For Excel/file sources:

- `file_path` — full path to file

**Example request (SQL Server):**

```bash
GET /api/v1/admin/data-sources/resolve?server=SQLSERVER01&database=Northwind
```

**Example response:**

```json
{
  "source_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "name": "Northwind Production",
  "type": "SQL Server",
  "server": "SQLSERVER01",
  "database": "Northwind",
  "file_path": null,
  "status": "active",
  "object_count": 245
}
```

**Example request (Excel):**

```bash
GET /api/v1/admin/data-sources/resolve?file_path=/data/sales.xlsx
```

**Example response:**

```json
{
  "source_id": "e5f6a7b8-c9d0-1234-abcd-ef1234567890",
  "name": "Sales Data",
  "type": "Excel",
  "server": null,
  "database": null,
  "file_path": "/data/sales.xlsx",
  "status": "active",
  "object_count": 12
}
```

**Error responses**

- `400` — invalid parameter combination: only `server` without `database`, mixed SQL Server and file parameters, or no parameters at all.
- `404` — data source not found.

**Usage pattern:**

```bash
# Step 1: Resolve SQL Server data source to ID
RESOLVED=$(curl -s "http://localhost:8000/api/v1/admin/data-sources/resolve?server=MyServer&database=MyDB" \
  -H "X-API-Key: admin-key" | jq -r '.source_id')

# Step 2: Use source_id in discovery
curl -X POST http://localhost:8000/api/v1/discovery \
  -H "X-API-Key: user-key" \
  -H "Content-Type: application/json" \
  -d "{\"query\": \"show customers\", \"source_id\": \"$RESOLVED\"}"

# Step 3: Use source_id in generate-sql
curl -N -X POST http://localhost:8000/api/v1/generation/generate-sql \
  -H "X-API-Key: user-key" \
  -H "Content-Type: application/json" \
  -d "{\"query\": \"show top 10 customers\", \"source_id\": \"$RESOLVED\"}"
```

**Notes**

- The route requires admin authentication.
- For SQL Server sources both `server` and `database` must be supplied, but the lookup matches on the **database name**, which is compared case-insensitively; the `server` value is accepted and echoed back, but is not used to select the match.
- File-path matching is exact (case-sensitive on case-sensitive filesystems).
- Only active (non-deleted) data sources are matched; a soft-deleted source returns `404` rather than a `deleted` status.
- Object count reflects tables/views/procedures indexed in the vector store for that source.

### Schema tree navigation

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/schema-tree` | GET | Full tree across sources |
| `/schema-tree/{source_id}` | GET | Tree for one source (`include_db_inspection` optional) |
| `/schema-tree/{source_id}/schemas` | GET | List source schemas |
| `/schema-tree/{source_id}/objects` | GET | List objects with filters (`schema_name`, `object_type`) |
| `/schema-tree/{source_id}/discover` | POST | DB introspection discovery (`schema_name` optional) |

### Skills admin utilities

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/skills/data-sources` | GET/POST | List or create skill data sources |
| `/skills/data-sources/{data_source_name}` | PUT/DELETE | Update/delete skill data source |
| `/skills/data-groups` | GET/POST/PUT/DELETE | Manage data groups |
| `/skills/tables` | GET/POST/PUT/DELETE | Manage tables |
| `/skills/tables/by-path` | GET | Fetch table by path |
| `/skills/raw-markdown` | GET/PUT | Read/update raw markdown |
| `/skills/sync-schema-markdown` | POST | Sync schema markdown |
| `/skills/folder-tree` | GET | Skills folder tree |
| `/skills/search` | GET | Skills search |
| `/skills/objects` | GET | List skill objects |
| `/skills/objects/by-name` | GET | Get object by name |
| `/skills/statistics` | GET | Skills statistics |
| `/skills/regenerate-indices` | POST | Rebuild skill indexes |
| `/skills/import` | POST | Import a skills folder and rebuild its vectors |
| `/skills/rebuild/{source_id}` | POST | Rebuild a source's vector collections (background) |
| `/skills/rebuild-status/{source_id}` | GET | Rebuild progress per collection |

Notes:

- Several skills routes identify their target with a `file_path` query parameter (`GET /skills/tables/by-path`, `DELETE /skills/tables`, `DELETE /skills/data-groups`, `GET /skills/raw-markdown`).
- `/skills/data-groups` and `/skills/tables` accept optional `data_source`/`data_group` filters; `/skills/search` accepts `query` plus optional `data_source`, `object_type`, `top_k`, and `domain`; `/skills/objects` accepts optional `data_source` and `schema_name`; `/skills/objects/by-name` takes `object_name` with optional `schema_name` (default `dbo`) and `data_source`; `/skills/statistics` accepts optional `data_source` and `query`.
- `/skills/import` takes `folder_path` and `source_id` and returns an import report; when files are rejected it returns `400` with the rejected file list.
- `/skills/rebuild/{source_id}` accepts an optional `folder_path`, returns the initial rebuild status, and continues in the background; it returns `404` when the folder is missing and `409` when a rebuild for that source is already running.

### Backup

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/vector-store/backup` | GET | Download vector-store backup JSON |

---

## Notes on request models

### `GenerateSQLRequest`

Sent to all four generation endpoints (`generate-sql`, `generate-python`, `generate-r`, `generate-sas`) and to `code-advisor`:

| Field | Type | Notes |
|-------|------|-------|
| `query` | string | Required |
| `source_id` | string | Required by the HTTP layer on the generation endpoints |
| `context` | object | Optional prior discovery context |
| `previousSQL` | string | Previous SQL from the conversation |
| `queryHistory` | string | Compacted conversation history |
| `database_objects` | string[] | User-pinned objects, boosted ahead of general discovery |
| `existing_code` | string | Base code for optimization or expansion |
| `error_message` | string | Error or stack trace for debugging |
| `is_user_code` | bool | Default `false`; whether `existing_code` came from the user |
| `forceGeneral` | bool | Default `false`; bypass source-specific tuning |
| `queryMode` | string | Default `generate`; also accepts `search`, `plan`, `ask`, `code_advisor` |
| `table_override` | string[] | Force discovery to these tables |
| `chart_type_override` | string | `line`, `pie`, `scatter`, `column`, `stackedColumn`, `clusteredColumn`, `area`, `radar`, `treemap`, `funnel`, or `none` |
| `user_selected_tables` | string[] | Checkbox selections from a threshold prompt |
| `planning_context` | object | Structured planning state for conversational exploration |
| `top_k` | int | Discovery cap override |
| `semantic_mode` | bool | Force the semantic layer on or off for this request |
| `session_id` | string | Conversation/session id for cross-turn filter state |

#### Unified generation scenarios

Generation endpoints route behavior based on these fields:

- **Debugging:** `error_message` present → fix `existing_code` using error feedback.
- **Optimization:** `existing_code` present with no error → improve or extend code.
- **Fresh start:** neither present → standard natural-language-to-code generation.

`database_objects` are high-priority context and are boosted ahead of general discovery. Omitting `source_id` on discovery, generate-sql/python/r/sas, execute-sql, or execute-python returns `400` with `{"detail": "source_id is required"}`. The server does not fall back to a primary or first-listed source.

### `ExecuteSQLRequest`

Supports execution controls such as:

- `sql` (required)
- `context`
- `source_id` (required; selects which data source to execute against)
- `timeout_seconds` (default 60), `max_rows` (default 10000)
- `enable_profiling`
- `chart_type_override`, `preserved_x_axis`, `preserved_y_axis`

### `ExecutePythonRequest`

Supports:

- `code` (required)
- `source_id` (required; same connection SQL execution uses)
- optional `context`
- `enable_profiling`
- `chart_type_override`, `preserved_x_axis`, `preserved_y_axis`

---

## Development and testing (reference server)

```bash
# Run backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run tests
python -m pytest tests/
```

---

## See also

- [AI Agent Manager Window](ai-agent-manager-window.md) — assigning an agent in Octofy Pro.
- [How to Use the AI Assistant](how-to-use-ai-assistant.md) — client-side chat and context.
- OpenAPI: `GET /api/v1/openapi.json` on your deployed agent host for the authoritative machine-readable schema.
