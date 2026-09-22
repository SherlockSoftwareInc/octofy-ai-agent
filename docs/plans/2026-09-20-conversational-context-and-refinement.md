# Conversational Context & Refinement Routing (Built-in Agent Port)

> **Status:** implemented 2026-09-20. Ports the OctofyPro built-in-agent enhancement plan
> ("address conversational context drift and mode misrouting") into this repository's Python
> orchestrator (`app/core/orchestrator/`).
>
> **Canonical process doc:** [AGENT_PROCESS.md](../AGENT_PROCESS.md) (updated in the same change).

---

## Problem

The Python port inherited the C# engine's **binary mode check**: *any* SQL in the editor
(`existing_code`) selected `optimization`, which routes to the schema-free provided-code
path. Two failures followed:

1. **Mode misrouting** — a granularity change (*"I need all order details"*) was treated as a
   syntax/performance tweak, so it could never add the base tables (`[dbo].[Order Details]`,
   `dbo].[Orders]`) or the joins the new grain needs.
2. **Context drift** — the pipeline had no memory of the active filter set. `ProductName LIKE
   '%chocolate%'` lived only inside the editor SQL text, and a follow-up turn was folded with
   raw history concatenation (`Q: … | A: …`) instead of being rewritten into a self-contained
   question, so the semantic analyzer saw an unbounded "all order details" request.

A third, latent gap: on the provided-code path a *validating* editor query short-circuited the
LLM entirely, so even genuine optimization requests were a no-op.

---

## What changed

### Phase 1 — Intent & routing

| Piece | Where |
|---|---|
| Scenario taxonomy (`fresh_start` / `optimization` / `refinement` / `drill_down` / `debugging`) | `app/core/branch_taxonomy.py` (`GenerationMode`, `REFINEMENT_SCENARIOS`, `is_refinement_scenario`, `scenario_branch`), `RouteKind.REFINE` |
| Deterministic multi-scenario classifier (ordered: reset > drill-down > refinement > optimization > default; structural additions stay optimization; short ambiguous turns fall back to a 16-token LLM label) | `app/core/orchestrator/scenario.py` |
| Route wiring — only `optimization` keeps `skip_discovery`; `refinement`/`drill_down` return `RouteKind.REFINE` with discovery enabled; explicit reset returns `Generate` with discovery | `app/core/orchestrator/router.py` |
| Intent labels widened to `db_query` / `optimize_code` / `refine_query` / `app_feature` / `off_topic` | `router.classify_intent` (`INTENT_LABELS`) |

### Phase 2 — Conversational context resolution

| Piece | Where |
|---|---|
| Coreference rewrite of vague follow-ups, LLM-first with a deterministic filter-carry fallback and validation (non-empty, ≤ 400 chars, actually different) | `app/core/orchestrator/coreference.py` |
| Session state `{session_id, active_filters, active_domains, target_grain, turn_index, last_sql}`, bounded thread-safe store, filter extraction from editor SQL (literal predicates only; join predicates ignored), inheritance / replacement / clear lifecycle, generation-outcome write-back | `app/core/orchestrator/session_context.py`, models in `app/models/pipeline.py` |
| Optional `session_id` on `GenerateSQLRequest` → `AgentRequest` | `app/models/schemas.py`, `preprocessing.build_agent_request` |
| Status events for observability (`Resolved follow-up context: …`, `Carried N active filter(s)`) | `builtin_sql_generator.generate_sql_builtin` |

Directed optimization edits are **not** rewritten — their subject is the editor SQL, not the
sentence.

### Phase 3 — Prompt & rule refactoring

| Piece | Where |
|---|---|
| `OPTIMIZATION_INSTRUCTIONS` (editor SQL only; no catalog/schema; no added/removed tables or columns; filters, joins, entities and grain preserved) | `app/core/orchestrator/prompts.py` |
| `REFINEMENT_INSTRUCTIONS` (base context, authorized scope expansion to base tables + FK joins, filter preservation) | same |
| `SCOPE GUARD` + `ACTIVE SESSION FILTERS` blocks, injected into SQL / Python / R / SAS / semantic prompts | `scenario_rules`, `_filter_block`, `_scenario_section` |
| Dedicated editor-code-only prompt for the no-discovery optimizer, and the optimizer now runs even when the editor code validates (falling back to the original code if the rewrite does not validate) | `build_optimization_system_prompt` / `build_optimization_user_prompt`, `_generate_from_provided_sql` |

### Phase 4 — Discovery & verification

- Refinement seeds the editor SQL's tables as **required** objects (`_base_objects_from_sql`)
  and merges them ahead of the discovered list, keeps discovery enabled, prefixes the branch
  (`refinement/<base>`), and widens the prompt-context cap to `RefinementPromptContextCap` (12).
- Refinement turns with active filters bypass the KB-exact / precomputed-exact / KB-vector
  fast paths, because a stored answer authored without the active filter must not satisfy them.

### Tests

| File | Contract |
|---|---|
| `tests/unit/test_scenario_routing.py` | optimization keeps editor-SQL-only routing; refinement/drill-down enable discovery; reset drops the editor context; filter negation ≠ full reset; LLM scenario + intent label fallbacks |
| `tests/unit/test_coreference_resolution.py` | self-contained turns are untouched; deterministic filter carry-forward; LLM rewrite validation + fallback; dates/numeric bounds are not folded into sentences |
| `tests/unit/test_session_filters.py` | predicate extraction (join conditions ignored, alias → table, verbatim values); inheritance / replacement / clear; session continuity; bounded store |
| `tests/unit/test_scenario_prompts.py` | strict optimization rules (no schema section); refinement instructions + scope guard + inherited filters; fresh start has no scenario rules |
| `tests/parity/test_refinement_scope_expansion.py` | end-to-end: optimization never fetches schema; refinement runs discovery, keeps base objects, adds the new grain object, and carries the inherited filter into the prompt; active filters bypass stored exact answers |

Run:

```bash
python -m pytest tests/unit tests/parity tests/contract -q
```

---

## Verification matrix (plan §Phase 4 step 4)

| # | Request (with editor SQL) | Scenario | Route | Discovery | Prompt rules |
|---|---|---|---|---|---|
| 1 | `make it faster` / `format this` / `add indexing` / `convert this to a CTE` / `remove unused joins` | optimization | Optimize (`skip_discovery=True`) | none | editor-code-only, no schema |
| 2 | `I need all order details` | refinement | Refine | yes (base + new tables, joins) | refinement + scope guard + filters |
| 3 | `break this down by customer` / `per employee` | drill_down | Refine | yes | refinement + scope guard + filters |
| 4 | `now do this for coffee` | refinement | Refine | yes | filter value replaced, structure kept |
| 5 | `for all products` / `clear filters` | refinement | Refine | yes | filters cleared, structure kept |
| 6 | `start over` / `new query` | fresh_start | Generate | yes (full) | none |

---

## Scope notes / deliberate limits

- The **HTTP wrapper** (`generation_service.generate_sql_for_request`) still performs its coarse
  3-way gate (`data_query` / `system_metadata` / `off_topic`) on the history-folded query before
  handing off to the orchestrator; the coreference pass runs inside the orchestrator, immediately
  before scenario classification, so no turn is rewritten twice.
- `plan` / `ask` (discuss) and `search` modes are unchanged — they never reach the generate path.
- `app/services/refinement_service.py` (`RefinementDetector`, `RefinementIntent`,
  `AnalysisContext`) is the older *data-analysis* refinement detector and remains unused by the
  orchestrator; it is unrelated to the routing scenario introduced here.
- `session_id` is optional and additive; clients that do not send it still get filter
  inheritance derived from their own `existing_code`.
