# Plan: Require `data_source_id` on every Milvus collection

**Date:** 2026-09-12  
**Status:** Proposed  
**Goal:** Every vector-store collection is partitioned by `data_source_id`, and every read/write used for generation or discovery is filtered by that field so results cannot leak across data sources.

---

## Problem

The agent hosts many data sources in one process. A few-shot, value, or data-group hit from the wrong source can pull the wrong tables and produce invalid SQL.

Review of the live Milvus instance shows **`schemas` has `data_source_id`, but the other collections do not**. Those collections cannot be filtered at query time. A search on `few_shots` or `value_index` either fails the `data_source_id == "..."` expression or (worse) returns rows from every source.

Milvus cannot `ALTER` a collection to add a partition-key field. The only repair is **drop → recreate with the contract schema → reload data**.

---

## What is already correct in code

The Python contract already requires the column. Do not invent a second schema.

| Layer | Current behavior |
|---|---|
| `schema_contracts.py` | Every `CollectionSpec` starts with `data_source_id` (`PARTITION_FIELD`). Version `1.0.0`. |
| SQLite provider | `sqlite_ddl()` creates the column on all tables. `fetch_all` / `search_vector` / `delete` all `WHERE data_source_id = ?`. |
| New Milvus create path | `ensure_schema()` adds `data_source_id` as `is_partition_key=True` **when it creates a collection**. |
| New Milvus query path | `search_vector`, `fetch_all`, `delete`, `delete_source` all use `data_source_id == "..."`. |
| Service writes | Few-shots, values, data groups, precomputed queries, semantic models, and embeddings already set `data_source_id` on upsert. |

The defect is **live collection shape + recreate policy + a few unscoped list paths**, not a missing field in the contract.

---

## Root cause

`MilvusProvider.ensure_schema()` skips any collection that already exists unless `_collection_needs_recreate()` is true.

```
if has_collection and needs_recreate → drop
if has_collection → continue   # leave as-is
else → create with data_source_id
```

`_collection_needs_recreate()` only rebuilds collections that already have a `pk` field and are missing `data_source_id` or a vector. **Legacy collections without `pk` are left alone.**

That matches the observed state:

- `schemas` was dropped/recreated during ingest or a contract rewrite, so it has the field.
- `few_shots`, `few_shots_meta` (later retired; exact lookup now reads `few_shots`), `value_index`, `contribution_library`, data-group tables, precomputed-query tables, semantic tables, and `embedding_cache` kept their pre-contract schema.

Secondary leaks (even after the column exists):

1. `vector_store.py` admin lists use `fetch_all_rows()` (no source filter) for few-shots, values, and contributions.
2. Settings “Milvus OK” only checks that collection **names** exist, not that `data_source_id` is present.
3. `search_vector` / `fetch_all` have no guard: if the field is missing they throw at query time instead of failing closed with a clear “rebuild required” error.

---

## Non-negotiable rules

1. **`data_source_id` is required on every contract collection.** No collection is considered healthy without it.
2. **Every generate/discovery read is scoped.** `search_vector` and `fetch_all` must always take a `source_id` and apply the filter. Unscoped `fetch_all_rows` is admin/replication only.
3. **Writes without `data_source_id` are dropped.** `prepare_milvus_row()` already returns `None`; keep that and log a warning.
4. **Do not retune retrieval constants** while doing this. This is a storage-isolation fix.
5. **No silent cross-source fallback.** If the filter cannot be applied, return empty and raise a rebuild error — do not query the whole collection.

---

## Target Milvus shape

Every collection (vector and scalar) must be created as:

```
pk                 VARCHAR  primary key (composite: data_source_id|natural_key)
data_source_id     VARCHAR  is_partition_key=True
…contract fields…
[+ _pad_vector     FLOAT_VECTOR(2)  for scalar collections — Milvus requires one vector field]
```

Natural keys stay as today (`key`, `query_id`, `group_id`, `model_id`, `text_hash`). Uniqueness is `(data_source_id, natural key)` via `pk`.

Collections in scope (all of `COLLECTIONS`):

- Vector: `schemas`, `few_shots`, `value_index`, `data_group_vectors_vec0`
- Scalar / json-vector: `contribution_library`, `data_group_metadata`, `data_group_vectors_cache`, `data_group_vectors_map`, `vec_data_group_queries`, `vec_data_group_query_vectors_cache`, `embedding_cache`, `semantic_models`, `semantic_measures`, `semantic_dimensions`, `semantic_joins`, `semantic_governance_predicates`, `semantic_embeddings` (`few_shots_meta` was in this set at the time; it has since been retired)

---

## Work plan

### Task 0 — Diagnose the live instance (do this first)

Add `scripts/inspect_vector_schema.py` (or a pytest-skippable admin check) that, for each contract collection, prints:

- exists / missing
- field names
- whether `data_source_id` is present and is a partition key
- row count
- distinct `data_source_id` values (if the field exists)

Run it against the running Milvus and attach the output to the PR. This confirms which collections are stale and whether SQLite already has good copies.

**Success:** a table of collection → `has_data_source_id` before any drop.

### Task 1 — Recreate policy: treat missing `data_source_id` as fatal

**File:** `app/services/stores/milvus_provider.py`

Change `_collection_needs_recreate()` to:

1. Missing collection → create (existing path).
2. Existing collection **without** `data_source_id` → recreate.
3. Existing collection **without** `pk` → recreate (legacy).
4. Existing collection without a FLOAT_VECTOR field → recreate (Milvus requirement).
5. Only keep a collection when `{pk, data_source_id}` ⊆ fields and a vector field exists.

Remove the “leave legacy collections alone” branch for **contract names**. Unknown/legacy *names* (`schema_index`, `fewshot_index`) can still be skipped by `_is_contract_collection` / name allow-list so we do not drop unrelated collections.

On recreate, log: `recreating {name}: missing data_source_id (fields={...})`.

**Do not auto-drop on every process start if data would be lost.** Pair this with Task 2: recreate only after a snapshot exists, **or** recreate only when `OCTOFY_RECREATE_STALE_COLLECTIONS=1` / an explicit admin “Rebuild vector store” action. Recommended default for this fix: **admin rebuild is the one-shot migration**; `ensure_schema` on boot **refuses to serve** stale collections (Task 3) rather than silently dropping production data.

### Task 2 — One-shot migration / rebuild

Milvus cannot migrate in place. Use this order:

```
1. Snapshot SQLite sidecar (data/vector-index.sqlite) if present
2. For each stale contract collection:
     if SQLite has rows for that table → keep SQLite as source of truth
     else export Milvus rows (best-effort) into SQLite, stamping
          data_source_id = row.source_guid OR primary source_id
3. Drop stale Milvus collections
4. ensure_schema() (creates data_source_id partition key)
5. replicate_sqlite_to_milvus()
6. Re-run inspect script — every collection has the field
7. Smoke: discover + few-shot search for source A must not return source B rows
```

Reuse existing tools; do not add a second rebuild stack:

- `scripts/rebuild_northwind_vectors.py` (skills folder → SQLite → optional Milvus)
- `milvus_replicate.replicate_sqlite_to_milvus()`
- `MilvusProvider.drop_all_collections()` (already limited to contract names)

Add a dedicated script, e.g. `scripts/migrate_milvus_data_source_id.py`, that:

1. Inspects and prints the before table.
2. Copies any Milvus-only rows into SQLite with a resolved `data_source_id` (refuse rows that cannot be attributed — write them to a reject log).
3. Drops stale collections.
4. Recreates + replicates.
5. Prints the after table and exits non-zero if any collection still lacks the field.

**Attribution rule for orphan rows** (old collections with no source column):

- If the deployment has exactly one registered data source → stamp that `source_id`.
- If multiple sources → do **not** guess. Export to `data/milvus-orphan-{collection}.json` and skip those rows. Operator re-ingests per source from skills / admin upload.

### Task 3 — Fail closed in the provider

**File:** `app/services/stores/milvus_provider.py`

Add `_require_partition_field(collection)` used by `search_vector`, `fetch_all`, `delete`, `upsert`:

- If the live schema has no `data_source_id`, raise a dedicated error (`VectorSchemaStaleError`) with message: collection X is missing data_source_id; run the rebuild script.
- Do not fall back to an unfiltered query.

`upsert` already drops non-contract collections. After Task 1, keep that, but still refuse upsert if `prepare_milvus_row` cannot resolve `data_source_id`.

### Task 4 — Scope every search path

Audit and fix any read that can return another source’s rows.

| Path | Required change |
|---|---|
| `MilvusProvider.search_vector` / `fetch_all` | Already filtered; add Task 3 guard |
| `FewShotVectorService.search` / `try_get_exact` | Already passes `self.source_id` — keep |
| `ValueIndexService.search` | Already `fetch_all(..., self.source_id)` — keep |
| `VectorSearchService.search_objects` / `search_precomputed` | Already scoped — keep |
| `DataGroupStore` / `PrecomputedQueryStore` / `SemanticModelService` | Already scoped — keep |
| `vector_store.py` `get_all_fewshots` / `get_all_values` / `get_all_contributions` | Today uses `fetch_all_rows()`. Change default to `fetch_all(source_id)`. Add optional `source_id=None` only for an explicit admin “all sources” view that **groups by** `data_source_id` and never feeds the generate prompt |
| `_schema_rows()` without `source_id` | Same: default to resolved source, not global scan |
| `admin_service` schema list | Keep a filtered path when `source_id` is in the request (already does). Global list must still display `data_source_id` per row |
| Legacy `discovery_service.py` | If `BUILTIN_SQL_GENERATOR` is off, pass `source_id` into every vector_store search |

Generate/discovery must never call `fetch_all_rows`.

### Task 5 — Health check

**Files:** `app/services/settings_service.py`, `app/api/endpoints/settings.py`

Extend Milvus validation:

1. Each name in `COLLECTIONS` (or at least `RUNTIME_VECTOR_COLLECTIONS` plus data-group / precomputed / semantic tables used at runtime) exists.
2. Each has field `data_source_id`.
3. Prefer: field is a partition key.

Return a structured payload, e.g. `missing_collections`, `collections_missing_data_source_id`. The settings UI should say “rebuild vector store” instead of “connected”.

### Task 6 — Tests

| Test | Asserts |
|---|---|
| `test_schema_contract.py` (existing) | Keep: every spec starts with `data_source_id` |
| New `test_milvus_ensure_recreates_missing_partition` | Mock an existing collection whose fields omit `data_source_id` → `_collection_needs_recreate` is True |
| New `test_search_vector_always_includes_partition_expr` | Captured `expr` contains `data_source_id ==` |
| New `test_fetch_all_requires_source_id` | Calling fetch without a source is a TypeError (already the signature); no new unscoped method on the generate path |
| New `test_two_sources_fewshot_isolation` | Insert few-shots for A and B; search A does not return B (SQLite provider is enough; Milvus optional) |
| New `test_two_sources_value_index_isolation` | Same for `value_index` |
| Extend `test_milvus_contract_facade.py` | `insert_fewshot_item` / `insert_value_item` / contribution rows always persist `data_source_id` |
| Health-check unit | Mock collection missing the field → validation error, not success |

### Task 7 — Docs

Update [VECTOR_SCHEMA.md](../VECTOR_SCHEMA.md):

- Add a **Migration** section: live collections without `data_source_id` are stale; run `scripts/migrate_milvus_data_source_id.py`; generate will fail closed until rebuild.
- State explicitly that **all** collections, not only `schemas`, use the partition field.
- Point settings health check at field presence.

Update [AGENT_PROCESS.md](../AGENT_PROCESS.md) with one line: every store read is `source_id`-scoped; a stale Milvus schema is a hard error.

---

## Suggested implementation order

```
Task 0  inspect live Milvus (no writes)
Task 6  tests first (recreate policy, filter expr, two-source isolation)
Task 1  recreate predicate
Task 3  fail closed
Task 4  unscoped list paths
Task 5  health check
Task 2  migration script + run on the review instance
Task 7  docs
```

Task 2 is the only destructive step. Run it after the code refuses to query stale collections, so a half-migrated process cannot serve mixed results.

---

## Risk and rollback

| Risk | Mitigation |
|---|---|
| Drop loses Milvus-only rows | Snapshot SQLite; export orphans to JSON before drop |
| Multi-source orphans stamped with the wrong id | Refuse to guess when >1 source; operator re-ingests |
| Downtime during drop/reload | Rebuild is an admin action; health check shows “rebuilding” |
| Embeddings must be recomputed | SQLite already stores vectors; replicate copies them — no re-embed if SQLite is complete |
| Rollback | Restore the SQLite file; `drop_all_collections` + replicate again. Old Milvus collections without the field must not be restored |

---

## Out of scope

- Changing embedding models or RRF weights.
- Renaming collections.
- Making `fetch_all_rows` the generate-path API.
- Automatic boot-time drop of production collections without an explicit rebuild flag.

---

## Acceptance criteria

1. Inspect script: **every** contract collection in Milvus lists `data_source_id` as a partition key.
2. Insert a few-shot and a value for source A and source B; generate/discover for A never returns B’s objects, questions, or values.
3. Settings validation fails if any runtime collection is missing the field.
4. `search_vector` / `fetch_all` raise `VectorSchemaStaleError` (or equivalent) instead of querying unfiltered when the field is absent.
5. Admin lists default to the current `source_id`; an all-sources view is labeled and grouped.
6. Unit tests in Task 6 pass without a live Milvus; isolation tests pass on SQLite.
