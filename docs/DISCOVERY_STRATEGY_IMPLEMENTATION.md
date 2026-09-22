# Discovery Strategy

How the built-in generator finds tables, views, functions, and columns for a request. This replaces the older three-pronged / user-selection write-up.

Canonical process: [AGENT_PROCESS.md](AGENT_PROCESS.md). Index layout: [VECTOR_SCHEMA.md](VECTOR_SCHEMA.md).

**Implementation:** `app/core/orchestrator/discovery_engine.py`, `app/utils/rrf.py`, `app/services/vector_search_service.py`.

---

## Goals

1. Prefer a known-good SQL example (knowledge base or precomputed question) over a cold schema search.
2. Use column-level evidence so filter values and mentioned column names pull in the right parents.
3. Merge competing signals with Reciprocal Rank Fusion instead of ad-hoc integer scores.
4. Keep the prompt small: 8 objects, 6,400-token markdown budget.

---

## Inputs

`DiscoveryEngine.discover(query, analysis, pins, table_override, top_k)`:

- `query` — combined / masked user text (or existing SQL when recovering)
- `analysis` — `QueryAnalysis` (keywords, entities, filter values, extracted columns, complexity)
- `pins` — user-selected objects (required after catalog resolve)
- `table_override` — exclusive set; skips retrieval
- `top_k` — default 8 (`MaxRerankTables`)

Stores (all scoped by `source_id`): few-shots, `schemas` vectors, `value_index`, data groups, precomputed questions, optional BM25.

---

## Decision tree

```
table_override present?
    yes → branch table_override (those objects only)
    no
      KB search (few_shots, top_k=3, max distance 0.35)
          best confidence ≥ 0.70 → kb_direct
              objects = tables parsed from the matched SQL
              fallback = column-evidence objects
          KB hit, lower confidence → kb_gap_fill
              objects = SQL tables ∪ column evidence
          no KB hit → dual_prong (RRF)
              lists: schema_vector, value_index, few_shot, data_group, bm25
              if any merged object is a member of an active data group
                  → group_anchored
      if a precomputed question scores ≥ 0.82 and is not exact
          → precomputed_related/<base-branch>
      pins, if any, are prepended as required
```

Exact KB / precomputed exits happen **before** this function (Stage C in the orchestrator). Those branches are `kb_exact` and `precomputed_exact`.

---

## Branch reference

| Branch | When | Typical objects |
|---|---|---|
| `kb_exact` | Canonical question or vector distance ≤ 0.05 | Not discovery — SQL returned immediately |
| `precomputed_exact` | Approved/modified precomputed question key match | Immediate SQL / compiled SMQ |
| `table_override` | Request listed exclusive tables | Those names only |
| `kb_direct` | Strong KB example | Tables referenced in that SQL |
| `kb_gap_fill` | Weaker KB example | SQL tables plus column evidence |
| `dual_prong` | No usable KB hit | RRF merge, cap 8 |
| `group_anchored` | RRF result intersects an active data group | Same merge, analytics label |
| `precomputed_related/<base>` | Related approved question ≥ 0.82 similarity | Same objects; examples injected |
| `no_discovery` | Provided-code optimize/rewrite | None |
| `priority_validation_failed` | A pin could not be resolved | Failure candidates only |

---

## Column evidence

`discover_with_column_evidence()`:

1. For each `analysis.filter_values`, search `value_index` by lowercase substring on `plain_value`. Each hit seeds the parent table (score 0.80) and records the column as matched / required.
2. If `extracted_columns` is non-empty, search `schemas` for each column name (`entity_type=Column`). Otherwise search once with the full query (`top_k=100`).
3. Hits below `OBJECT_SEARCH_VECTOR_SCORE_THRESHOLD` (default 0.50) are dropped.
4. Per parent object, keep columns whose score is at least 85% of that object's best column (`RelativeColumnScoreThreshold`).
5. Objects with any matched column receive +0.15 (cap 1.0) and `required=true`.

`VectorSearchService.search_objects()` also rolls column hits up to parents, so the schema-vector RRF list already carries `matched_columns`.

---

## Reciprocal Rank Fusion

```
score(object) = Σ  weight(list) / (60 + rank + 1)
```

| List | Weight | Source |
|---|---|---|
| `data_group` | 2.0 | Top 3 data-group members |
| `value_index` | 1.0 | Filter-value seeds |
| `few_shot` | 1.0 | Tables extracted from KB SQL |
| `schema_vector` | 1.0 | `schemas` collection search |
| `bm25` | 0.5 | Optional lexical rank of schema + column objects |

Dedup key: `data_source|schema|object` (segment suffix stripped). Matched columns, `priority`, and `required` are unioned. Result length ≤ 8.

BM25 is off unless `ENABLE_BM25_RETRIEVAL=true`. Weight follows `BM25_WEIGHT`.

---

## Data groups

`resolve_active_data_groups(query)`:

1. Vector search of group embeddings, top 3.
2. If empty, score group keywords against the query and keep overlapping groups.
3. Build `member_groups` (object name → group names) and a one-line summary for the prompt.

If any RRF object is a member, the branch becomes `group_anchored`.

---

## Precomputed questions

After merge, `search_precomputed()` ranks approved questions by cosine **similarity** of cached question vectors.

- ≥ 0.93 and exact key match already exited in Stage C.
- ≥ 0.82 and not exact → inject up to 3 examples and prefix the branch with `precomputed_related/`.

---

## Hydration (after ranking)

`SqlContextHydrator`:

1. Keep required / priority / matched-column / semantic-model objects.
2. Drop other objects below 5% of the best remaining score.
3. Cap at 8.
4. Load skills-folder markdown per object.
5. Fill `selected_object_context`, `supplementary_objects`, `schema_context`, and `schema_context_for_validation` under a 6,400-token budget. Over-budget files are pruned to matched columns.

---

## Recovery expansion

The attempt loop calls `_expand_missing()` when validation names a missing object: schema search (`top_k=5`) plus optional column searches and semantic-model hits. New objects are merged with `merge_and_dedup`. The same missing name twice trips `deterministic_missing_object`.

---

## Caches

| Cache | Cap | Key |
|---|---|---|
| Query analysis | 100 | Combined query + existing code |
| Discovery result | 256 | Entities + complexity + top_k + extracted columns |

The orchestrator clears the analysis cache at the start of each request.

---

## What was removed

The previous sequential flow (KB exact → skills score ≥ 15 → user-selection of 20 candidates → value-index merge) is no longer the generate path. User table choice is now **pins** / `table_override` on the request, not an in-pipeline selection prompt. The old helpers in `discovery_service.py` remain only for the legacy wrapper when `BUILTIN_SQL_GENERATOR=false`.
