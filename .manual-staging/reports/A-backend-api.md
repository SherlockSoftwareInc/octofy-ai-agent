# Report A — `octofy-ai-agent-backend-api.md`

**Status: rewritten.** The endpoint inventory, auth model, SSE section, request-model notes, and data-source resolution were rebuilt from the reference-server code. No endpoints were removed; 14 were added and several claims were corrected.

- Output page: `.manual-staging/new/octofy-ai-agent-backend-api.md` (658 lines)
- Baseline: 113 documented method+path entries → new page: 127 (matches `app/api/endpoints/*.py` exactly)
- Coverage check: every one of the 127 `@router.<method>("<path>")` decorators in the reference server appears in the new page (scripted check, 0 missing); no route appears in the page that does not exist in code (only the client-side `/admin/schema/sync-all` probe is mentioned, and it is explicitly described as not mounted by the reference server).

## Endpoints added (14)

| Endpoint | Evidence |
|---|---|
| `POST /api/v1/generation/generate-sql` (canonical alias of `/api/v1/generate-sql`) | `app/api/endpoints/generation.py:51-52` |
| `GET /api/v1/admin/generator-thresholds` | `app/api/endpoints/settings.py:353` |
| `PUT /api/v1/admin/generator-thresholds` | `app/api/endpoints/settings.py:362` |
| `GET /api/v1/admin/precomputed-queries` | `app/api/endpoints/admin_precomputed.py:23` |
| `POST /api/v1/admin/precomputed-queries` | `app/api/endpoints/admin_precomputed.py:30` |
| `POST /api/v1/admin/precomputed-queries/{query_id}/status` | `app/api/endpoints/admin_precomputed.py:46` |
| `GET /api/v1/admin/semantic-models` | `app/api/endpoints/admin_semantic.py:14` |
| `POST /api/v1/admin/semantic-models` | `app/api/endpoints/admin_semantic.py:21` |
| `POST /api/v1/admin/semantic-models/extract` | `app/api/endpoints/admin_semantic.py:29` |
| `POST /api/v1/admin/semantic-models/compile` | `app/api/endpoints/admin_semantic.py:43` |
| `POST /api/v1/admin/skills/import` | `app/api/endpoints/admin_skills_import.py:27` |
| `POST /api/v1/admin/skills/rebuild/{source_id}` | `app/api/endpoints/admin_skills_import.py:36` |
| `GET /api/v1/admin/skills/rebuild-status/{source_id}` | `app/api/endpoints/admin_skills_import.py:58` |
| `GET /api/v1/admin/data-sources/registry` | `app/api/endpoints/data_sources.py:680` |

Pre-existing rows were kept, and methods in combined cells (`GET/POST`, `GET/POST/PUT/DELETE`) still expand to the same method+path pairs as before.

## Endpoints removed

**None.** Every entry documented in the baseline page still exists in code; the reverse arithmetic closes exactly (113 + 14 = 127), and the scripted reverse check found no orphan paths. Details that changed are corrections, not removals:

- `/api/v1/admin/skills/*`, `/api/v1/admin/schema*`, `/api/v1/admin/fewshots*`, `/api/v1/admin/values*`, `/api/v1/admin/data-sources*`, `/api/v1/admin/schema-tree*`, `/api/v1/admin/contributions*`, `/api/v1/admin/vector-store/backup` — all still present (`app/api/endpoints/admin.py`, `data_sources.py`, `schema_tree.py`).
- The health check, `X-API-Key` header, error table, `GET /api/v1/openapi.json`, Swagger URL, and the end-to-end `data-sources/resolve` example were preserved.

## Changes with evidence

### Corrections to inherited claims

- **`data-sources/resolve` path corrected.** The baseline examples used `/api/v1/data-sources/resolve`; the router is mounted at `/api/v1/admin` (`app/main.py:52`), so the only server path is `/api/v1/admin/data-sources/resolve` (`app/api/endpoints/data_sources.py:354`). Octofy Pro tries the un-prefixed path first and falls back on `404` (`OctofyPro/Octofy.Agent/AI/OctofyAgentHelper.cs:473-481`); the page now documents the real path and the client's fallback, and the usage example was updated (the rest of the example is unchanged).
- **"Server and database matching is case-insensitive" corrected.** `find_by_connection_info` matches on the **database name only**, case-insensitively; the `server` argument is "accepted but ignored for matching" (`app/services/data_source_registry_service.py:225-260`, quote at line 239). File-path matching is an exact string compare (`...:303-308`). The page now says so.
- **File-path case sensitivity** kept but stated as an exact match, per the same code.
- **Soft-deleted sources**: the resolve route filters `deleted_at IS NULL` (line 258) and returns `404`; the page now says a soft-deleted source returns `404` (the baseline's wording about `status: "deleted"` was misleading for this route).
- **Open (unauthenticated) routes expanded.** Baseline listed only `/admin/ingest-progress` (`app/api/endpoints/admin.py:667`, no dependency). Code also has `GET /api/v1/schema/{object_name}` (`app/api/endpoints/schema.py:18-19`, no dependency) and `POST /api/v1/summarize-results` (`app/api/endpoints/summarize.py:18-19`, no dependency), plus `GET /` (`app/main.py:128`) and `POST /api/v1/auth/login` (public by design). A new table lists all of them with the "harden in production" caveat.
- **Auth rules sharpened**: `verify_api_key` accepts any active user (`app/core/auth.py:87-117`) with detail `"Invalid or missing API key"`; admin routes require role `admin` and return `403` (`app/core/auth.py:63-84`). The page now names the routes that accept either key: discovery, test, generation, execution, planning-summary, contributions, and `GET /admin/data-sources` (`app/api/endpoints/discovery.py:10`, `generation.py:56`, `contributions.py:23`, `data_sources.py:35`).
- **Error table extended** with `409` (`settings.py:82` "API key is already set in .env."; `admin_skills_import.py:45-48` rebuild already running) and `429` (`generation.py:718-722`). The 400/401/403/404/500 rows were left as they were.
- **`source_id` requirements made explicit.** `require_source_id` returns `400 {"detail": "source_id is required"}` when missing and `404` when unknown, and its docstring states the server must not fall back to a first folder (`app/services/source_resolver.py:43-53`, quote lines 46-47). Call sites: `discovery.py:20`; `generation.py:61, 118, 174, 230, 296, 506`. `POST /admin/skills/import` is the documented exception (falls back to primary, `admin_skills_import.py:29` + `source_resolver.py:56-70`).
- **Request-model notes**: `GenerateSQLRequest` now carries the full field list from `app/models/schemas.py:102-120`, including `source_id`, `top_k`, `semantic_mode`, `session_id`, `user_selected_tables`, `planning_context`, and the real `queryMode` enum (`generate`, `search`, `plan`, `ask`, `code_advisor`). `ExecuteSQLRequest` (`schemas.py:201-210`) now lists `preserved_x_axis`/`preserved_y_axis`, `timeout_seconds` (60) and `max_rows` (10000) instead of the vague "axis preservation fields". `ExecutePythonRequest` (`schemas.py:191-198`) lists the real controls and required `source_id`.
- **Execution endpoints do not stream.** Both are `response_model` JSON handlers (`generation.py:284, 494`; models `schemas.py:304-333`), while the baseline implied nothing about the transport. The page now states this and lists the response fields (`auto_fixed`, `fix_attempt`, `original_error`, `rows_affected`, profiling, insights).
- **Schema lookup notes added**: `schema.table` required (400), not indexed (404), no auth, reads the vector store (`schema.py:7-28`).
- **Feature summary and technology table**: bullets updated for the semantic layer, precomputed queries, thresholds, registry, and skills import/rebuild; the technology table is unchanged.

### SSE section (new detail)

- Envelope `{ "type": "status|result|done|error", "payload", "message" }` and `data: <json>` framing (`app/utils/sse.py:7-35`).
- Stage values `routing, validate_pins, preanalysis, discovery, attempt, critic, db_validation, recovery` (`app/core/branch_taxonomy.py:67-75`), emitted with `step_id` and `source_id` (`app/core/orchestrator/builtin_sql_generator.py:77-81`), and `attempt`/`max_attempts` on attempt events (`app/core/orchestrator/attempts.py:162-167`).
- 5 attempts, 120 s budget, 90 s no-discovery budget (`app/core/constants.py:6-8`); empty `query` → 400 (`generation.py:59, 116, 172, 228`).
- Result payload field table from `GenerateSQLResponse` (`app/models/schemas.py:163-182`; `source_id` echoed at `builtin_sql_generator.py:539`).
- Code advisor's different envelope (`generation.py:727-749`), 10 requests/minute per API key (`app/core/rate_limiter.py:84-87`), `429` + `X-RateLimit-Info` (`generation.py:718-722, 754-758`).
- A backend that emits no `status` events is still valid; the client then shows a static progress label — from the product-team doc (line 200), not contradicted by code.

### New admin/behaviour notes

- Precomputed item shape and status default (`admin_precomputed.py:13-20`); semantic model shape, extract inputs, compile errors 404/400 (`admin_semantic.py:14-55`, `app/models/pipeline.py:305-322`).
- Semantic layer per request via `semantic_mode`, forced off for Python/R/SAS (`builtin_sql_generator.py:170`), source enablement in config (`app/core/config.py:63`).
- `generator-thresholds` fields and the 0–1 clamp (`settings.py:340-347, 362-370`).
- Settings notes: `/api-key` returns `{"api_key","exists"}`, 400 empty, 409 already set (`settings.py:69-85`); `/verify-settings` flag set (`settings.py:245-330`).
- Multi-source notes: `enabled` query default `true` (`data_sources.py:562`), scan optional body (`data_sources.py:170-173`), exclude-objects multipart (`data_sources.py:592`), registry `include_deleted` (`data_sources.py:680-708`).
- Schema management parameter notes and the `sync-all` client probe (`admin.py:34-53, 55-64, 96-104, 161-162, 231`; client `OctofyAgentHelper.cs:374`).
- Skills file_path/filter parameters (`admin.py:910, 950, 961, 987, 1024, 1035, 1073, 1179, 1216, 1243, 1274`); rebuild 404/409 (`admin_skills_import.py:45-48`).
- Conversation and user status codes (201/204) from `conversations.py:77, 111` and `users.py:155, 184`.

## Product-team doc vs. code (code preferred, as instructed)

The newest product-team doc (`OctofyPro/OctofyPro/Docs/plans/octofy-ai-agent-backend-api.md`) lists routes the reference server does not mount. The page follows the code; the divergences are:

- Doc line 313 lists `/schema/sync-all`. Not in code. The page documents `/schema/sync-full` and notes the client probe (`OctofyAgentHelper.cs:374`).
- Doc lines 375-381 list `/semantic/settings` (GET/PUT) and `/semantic/models*`. Code has `/admin/semantic-models`, `/semantic-models/extract`, `/semantic-models/compile` (`admin_semantic.py`) and no semantic settings route; enablement is configuration plus the per-request `semantic_mode` (`config.py:63`, `schemas.py:119`).
- Doc lines 364-367 list `/precomputed-queries/generate`, `PUT /precomputed-queries/{item_id}`, `GET /precomputed-queries/status`. Code has `GET/POST /precomputed-queries` and `POST /precomputed-queries/{query_id}/status` only.
- Doc lines 423-425 list `/data-sources/{source_id}/import-skills`, `/rebuild-vectors`, `/rebuild-status`. Code implements these as `/admin/skills/import`, `/admin/skills/rebuild/{source_id}`, `/admin/skills/rebuild-status/{source_id}`.
- Doc lines 151-153 imply `/generation/generate-python|r|sas` exist. Only `/generation/generate-sql` is mounted (`generation.py:51-52`); the client falls back to the legacy paths (`OctofyAgentHelper.cs:264-293`). The page describes both sides.
- Doc line 77 claims API keys are bound to the data sources their owner may access. No such binding exists in code: `User` has no source-access field (`app/models/user_models.py:20-57`) and the data-source list returns everything for any valid user key (`data_sources.py:34-93`). The claim was omitted.
- Doc line 404 puts `semanticCompilationFallbackToRawSql` in the thresholds payload. `GeneratorThresholds` exposes only three fields (`settings.py:340-347`); the fallback exists as a constant/config (`app/core/constants.py:60`). The page lists only the three real fields.
- Doc line 167 says `queryMode` is `"generate" | "search"`. Code allows `generate`, `search`, `plan`, `ask`, `code_advisor` (`schemas.py:112`). Code wins.
- Doc lines 194-201 describe a removed closing `attempt` status and immediate flushing. Stage names are verifiable (`branch_taxonomy.py:67-75`) and were documented; the historical claim about a removed status was left out.
- Doc line 437 says resolve has a fallback at `/admin/data-sources/resolve`. That is in fact the only server path (see corrections above).

## Could not verify / open questions

- **Who calls the new admin APIs.** A repo-wide grep over `OctofyPro/**/*.cs` found no callers for `precomputed-queries`, `semantic-models`, `generator-thresholds`, `skills/import`, or `skills/rebuild*`; they are presumably consumed by server-side tooling or tests. The manual documents them as contract surface because they exist in the reference server.
- **Threshold semantics beyond the field names.** The effect of each threshold on ranking/generation was not traced end to end; only the defaults and the clamp are documented.
- **`/data-sources/{source_id}/scan` and `/skills/rebuild*` runtime behaviour.** Both start background work (`background_tasks`, daemon thread); progress is reported through `scan-status` / `rebuild-status`, but the exact status payloads were not enumerated.
- **Skills folder layout.** `import-skills`/`rebuild` accept a `folder_path`; the expected file tree is only defined in the product-team plan documents, which I did not treat as authoritative for the page.
- **Reference-server quirk not documented:** on `GET /admin/schema/status`, an unknown `source_id` is converted from the resolver's `404` into a `500` because the resolver call sits inside a broad `except Exception` (`admin.py:47-53`). True in code, deliberately left out of the page.
- **Client rendering of SSE stages.** The client requests `text/event-stream` (`OctofyAgentHelper.cs:307`); how it displays stage/attempt payloads was not verified, so the page only states what the server emits and that stages are optional.
- **Health-check claim.** The page says Octofy Pro reads `GET /` and `GET /api/v1/openapi.json`; verified as client capabilities (`OctofyAgentHelper.cs:41-56`), not as a startup preflight requirement.
