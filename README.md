# Octofy AI Agent

**Octofy AI Agent** is the backend API service for [Octofy Pro](https://sherlocksoftwareinc.com/). It turns natural-language questions into validated T-SQL (and Python, R, or SAS) using retrieval-augmented generation, semantic search, and an iterative attempt loop.

**Octofy AI Agent is also a blueprint** for building agents capable of generating SQL, SAS, R, and Python code from natural-language requests. It is a reusable build specification paired with the working service that proves it out:

| Deliverable | What it is |
|---|---|
| **The blueprint** | [`docs/SQL_GENERATION_BACKEND_BLUEPRINT.md`](docs/SQL_GENERATION_BACKEND_BLUEPRINT.md) — a code-derived build specification (§01–§16) that a developer *or an AI coding agent* can execute to build an equivalent agent from an empty repository: transport, storage, retrieval, prompts, validation loop, semantic layer, script targets. |
| **The reference implementation** | The running service itself, with the full pipeline exercised end to end: ingestion, discovery, generation, validation, execution and analysis. |

The service is designed as a copilot: users ask questions in chat, the agent discovers the relevant schema and examples, generates dialect-correct code, parse-checks it against the warehouse, and optionally executes the statement with profiling and insights. The same pipeline serves four output targets — `sql` (T-SQL today), `python`, `r`, and `sas` — chosen per request with `target_language`.

The blueprint is written to be *executed*, not skimmed: exact constants, a frozen validation order, verbatim prompts, field-by-field data contracts, and an acceptance test matrix. It is derived from this repository's code, so non-obvious claims cite `path/file.py:LINE` and can be cross-checked against the running implementation. The rule in both directions: change pipeline behaviour here, update the corresponding blueprint section in the same change.

> **Note on the frontend.** The React app in [`frontend/`](frontend/) is **not a formal product** — it is a
> demonstration harness used to showcase and exercise the backend (chat thread, streaming status steps,
> result grids, admin screens). The backend is the deliverable; the UI is a convenience for trying it out.
> It carries no product guarantees, and you do **not** need it to run, test, or rebuild the service.

> **Rebuilding this agent (or an equivalent one) with an AI coding agent?**
> Everything you need is in **[docs/SQL_GENERATION_BACKEND_BLUEPRINT.md](docs/SQL_GENERATION_BACKEND_BLUEPRINT.md)**.
> Jump to **[Vibe-coding the agent](#vibe-coding-the-agent)** for the workflow, the section map, and the copy-paste prompts.

---

## Contents

- [Technologies employed](#technologies-employed) — RAG, semantic layers, prompt contracts, precomputed Q&A
- [Why this approach](#why-this-approach) — the rationale and the problems this design solves
- [Vibe-coding the agent](#vibe-coding-the-agent) — build a working agent from the blueprint
- [Overview](#overview) — how a request flows
- [Main features](#main-features)
- [Technology stack](#technology-stack)
- [Prerequisites](#prerequisites)
- [Quick start](#quick-start)
- [Usage examples](#usage-examples)
- [Admin workflows](#admin-workflows)
- [API surface](#api-surface)
- [Project structure](#project-structure)
- [Configuration notes](#configuration-notes)
- [Testing](#testing)
- [Docker](#docker)
- [Security](#security)
- [Documentation](#documentation)

---

## Technologies employed

These are the techniques that make generation reliable, as opposed to a single "ask the model for SQL" prompt. The libraries and services they run on are listed under [Technology stack](#technology-stack).

| Technology | How it is used here |
|---|---|
| **Retrieval-augmented generation (RAG)** | Evidence is retrieved *before* the model writes anything: schema objects and columns, few-shot examples, real stored values, and business data groups. Rankings from the knowledge base, value index, schema vectors, data groups and optional BM25 are combined with reciprocal rank fusion (k = 60) so no single signal dominates, and the retrieved evidence is hydrated into the prompt under a token budget. |
| **Semantic layers** | For governed metrics, the model emits **SMQ** (Semantic Model Query) JSON — logical metrics, dimensions, filters and timeframes — and a deterministic `SemanticCompiler` translates it into physical SQL against the active `SemanticModel`. Business definitions live in the model, not in the prompt, and compilation errors (`UNKNOWN_METRIC`, `UNKNOWN_DIMENSION`, `INCOMPATIBLE_DIMENSIONS`, `MISSING_JOIN_PATH`) are structured and recoverable. |
| **Prompt engineering as a contract** | Prompts are versioned artifacts, not ad-hoc strings. Assembly order, example payloads, dialect rules, scope guards and output formats are specified verbatim in §08 of the blueprint and locked by snapshot tests; the same scenario and guard text is injected into the SQL, Python, R and SAS prompts. Editing a prompt is a behaviour change, not a tweak. |
| **Precomputed Q&A pairs** | Curated question → code pairs (few-shot knowledge base, precomputed data-group queries, and their SMQ form) answer recurring questions deterministically. An exact match short-circuits generation entirely; a near match (cosine similarity ≥ 0.82) is injected into the prompt as a worked example instead of being returned blindly. |
| **Value index** | Maps everyday terms — "North America", a product line, a status word — to the exact literal stored in `schema.table.column`, so generated predicates use real values rather than plausible-looking guesses. |
| **Iterative validation loop** | Up to 5 attempts / 120 s with a safety interceptor, structural-hash hallucination detection, an advisory LLM critic, and authoritative database parse validation (`SET NOEXEC ON`, dry run, `sys.dm_exec_describe_first_result_set`). Missing objects trigger discovery expansion; terminal failures return a structured report. |
| **Deterministic front half** | Preprocessing, PII masking, history folding, conversational-context resolution, scenario classification, routing, pin validation and the fast paths all run in code before any model call, so routing and cache hits are reproducible. |
| **Provider-agnostic model layer** | Any OpenAI-compatible endpoint (OpenAI, Azure, Anthropic, Google, DeepSeek, Ollama, local servers, …) via LiteLLM, with parameter naming, temperature omission and reasoning budgets decided centrally by the request-conventions module — never hardcoded per call site. |
| **Per-source partitioning** | Every store read and write is partitioned by `source_id`, so one service can host many warehouses without cross-leakage of schemas, examples, values, data groups, semantic models or cached embeddings. |
| **Multi-target code generation** | One pipeline, four outputs (`sql`, `python`, `r`, `sas`). Non-SQL targets reuse the same discovery, attempt loop and validation, and materialize stored SQL into runnable script code when a fast path answers the question. |

---

## Why this approach

A capable language model given a bare question and a database connection will produce code that *looks* right and fails in specific, repeatable ways. This project's answer is to treat the model as one component in a pipeline — retrieval-first, deterministic where it can be, and validation-bound where it cannot — rather than as the whole system.

| Problem it addresses | How this approach solves it |
|---|---|
| **Hallucinated schema** — invented tables, columns and joins that read plausibly but do not exist | Generation is grounded in the real catalog: object and column discovery, KB-first lookup, and database validation that rejects unknown identifiers before a result is ever reported as success. |
| **Business language vs. physical schema** — "top customers in North America" names nothing that exists in the warehouse | The semantic layer and data groups translate business vocabulary into governed metrics and dimensions; the value index resolves terms to the literals actually stored in the data. |
| **Dialect and target correctness** — T-SQL specifics such as `TOP`, `N'…'` literals and `SET NOEXEC ON`, plus Python/R/SAS targets | Dialect rules live in the prompt contracts and the compiler's quoting layer, and every statement is validated against the engine that will run it; script targets are executed the same way. |
| **Cost and latency of generating every answer from scratch** | Precomputed Q&A and exact few-shot matches return a verified answer with zero generation attempts, while near matches become few-shot context instead of open-ended invention. |
| **Non-determinism and answers nobody can audit** | The deterministic front half and the SMQ compiler produce reproducible plans: a governed metric is defined by a stored semantic model, not by sampling. |
| **The model grading its own work** | The LLM critic is advisory; the database is authoritative. Success is a passed parse check (and, optionally, a real execution), and failure yields a structured report rather than a confident guess. |
| **Follow-up turns that lose the thread** — "now just the ones from last quarter" | Coreference rewriting plus session filter inheritance, replacement and clearing keep multi-turn conversations coherent, including explicit "start over" resets. |
| **Provider and model churn** | A provider-agnostic request layer keeps the agent working across OpenAI-compatible endpoints and reasoning vs. non-reasoning models without per-endpoint special cases. |
| **Multi-tenant safety** | `source_id` partitioning of every store prevents one warehouse's schema, examples, values or semantic definitions from leaking into another's answers. |
| **Knowledge that is hard to hand over or rebuild** | The blueprint captures thresholds, orderings, prompts and contracts so the system can be rebuilt, reviewed or ported without reverse-engineering it, and the human-curated knowledge (few-shots, data groups, value index, semantic models) lives in stores rather than in someone's head. |

The trade-off is deliberate: more ingestion and curation up front — schema metadata, values, example pairs, semantic models — in exchange for answers that are repeatable, explainable and verified against a real database. A reduced build is possible when that trade is not worth it: [§13 of the blueprint](docs/SQL_GENERATION_BACKEND_BLUEPRINT.md) describes a SQL-only vertical slice, and semantic mode and non-SQL targets are optional modes of the same pipeline.

---

## Vibe-coding the agent

This section explains how to use the implementation blueprint to have an AI coding agent (Claude Code, Codex, Cursor, DSH, …) build — or rebuild — a fully operational natural-language → SQL agent.

### What the blueprint is

| | |
|---|---|
| **File** | [`docs/SQL_GENERATION_BACKEND_BLUEPRINT.md`](docs/SQL_GENERATION_BACKEND_BLUEPRINT.md) |
| **Size** | ~16,600 lines / ~1.1 MB, 17 sections (§00–§16) |
| **Nature** | Build specification, not an overview: exact constants, orderings, data contracts, verbatim prompts, algorithms as pseudocode, acceptance tests |
| **Grounding** | Derived from this repository's code; non-obvious claims cite `path/file.py:LINE` so your agent can cross-check against the running implementation |

The document is written to be *executed* by a coding agent, not skimmed by a human:

- constants carry their exact values (do not retune them),
- the pipeline is specified stage by stage in execution order,
- prompts are reproduced verbatim, with assembly order,
- the validation order is marked as a frozen invariant,
- every section ends with an **Implementation checklist**,
- reference defects are listed so you can decide to fix or reproduce them.

### What you can build with it

- **The full service** — FastAPI transport, PostgreSQL user/conversation store, a vector store (Milvus or sqlite-vec), ingestion/admin surfaces, the generation pipeline, the semantic layer, execution and analysis.
- **A scoped subsystem** — for example the discovery engine (§06), the attempt loop (§07), or the semantic compiler (§09) on their own.
- **A reduced build** — SQL-only (skip §09 semantics and §12 script targets), single-source (drop multi-tenant partitioning), or sqlite-vec only (defer Milvus).
- **A migration** — port the pipeline to another language/runtime; §12 and §04 give the utility and storage contracts to reproduce.

If you only need a demo quickly, follow the vertical slice in §13: transport stub → sqlite-vec + in-memory schema → one table ingested → routing → minimal discovery → attempt loop with database validation. Add knowledge-base discovery, column evidence, refinement, and semantic mode afterwards.

### The workflow

| Step | Do this | Read |
|---|---|---|
| **1. Prepare the substrate** | Stand up PostgreSQL, the vector store, a SQL Server target and an LLM/embedding endpoint. Decide the scope (full / reduced). | §01, §04 |
| **2. Brief the agent** | Open your coding agent in an empty target repo and paste the [standing instructions](#standing-instructions-for-your-coding-agent). Keep them in every session. | §02.3 |
| **3. Build phase by phase** | Follow the phase plan; attach *only* the sections for the current phase and paste the matching [phase prompt](#phase-prompts). | §13 + [section map](#section-map--what-to-paste-when) |
| **4. Test as you go** | Require the tests from the acceptance matrix with each phase. Do not carry a red phase forward. | §14 |
| **5. Verify per section** | Walk the section's **Implementation checklist**; have the agent report files created, tests run, output, and deviations. | each § |
| **6. Prove parity** | Run the full acceptance matrix end-to-end against a real data source, then walk the invariants and pitfalls. Record fix-or-reproduce decisions. | §14, §15 |

**Feeding a 1.1 MB specification.** Do not paste the whole document — an agent will summarise instead of implement. Copy **one section at a time** (each is self-contained, numbered `## NN — …`, and ends with its own checklist). Attach the section plus the target repo layout from §16.1.

### Section map — what to paste when

| Build step | Sections | Why |
|---|---|---|
| Orientation | §01, §16 | Capability contract, file map, glossary, `.env` template |
| Transport first | §03 | Routes, request/response models, SSE envelope, auth, error taxonomy — your test harness |
| Substrate | §04 | Every setting and constant, Postgres DDL, vector collections, embedding caches, per-source store bundle |
| Ingestion | §11 | Schema scan, skills-folder markdown, few-shots, value index, data groups, precomputed questions, admin API |
| Deterministic front half | §05 | Preprocess, conversational context, scenario, routing, pin validation, fast paths |
| Retrieval | §06 | Query analysis, data groups, KB-first discovery, column evidence, RRF, hydration, caps |
| Prompting | §08 | Every prompt builder, verbatim, with assembly order and model parameters |
| Reliability core | §07 | Attempt loop, frozen validation order, breakers, critic, database validation, failure reports |
| Semantic layer | §09 | SMQ contract, compiler algorithm, error codes, governance, extraction |
| Execution & chat | §10 | execute-sql + retry, profiling, insights, charts, discuss/ask, catalog mode |
| Script targets | §12 | Python/R/SAS extraction, qualification, materialization, interceptors, utilities |
| Planning & verification | §13, §14, §15 | Phase plan, acceptance tests, invariants and pitfalls |

### Standing instructions for your coding agent

Paste this at the start of every session:

```text
You are implementing a natural-language → SQL agent backend from a written specification
(the "Backend SQL Generation — Implementation Blueprint"). Follow it literally.

HARD RULES
1. Do not invent numeric thresholds, weights, caps, timeouts or retry counts. Every value
   comes from the specification. If a value you need is not specified, stop and ask.
2. Do not reorder the validation sequence or the pipeline stages. The specification marks
   ordering invariants explicitly; reproduce them in the same order and add a comment at
   each enforcement point naming the invariant.
3. Do not "improve" prompt text. Prompts are contracts: reproduce them verbatim, including
   section headings, capitalization and blank lines.
4. Preserve every failure path and its error category. Every terminal vs retryable decision
   in the specification must exist in the code.
5. Keep all retrieval and storage partitioned by source_id. No read may ignore the partition.
6. Keep the LLM layer provider-agnostic: parameter naming, temperature omission and reasoning
   budgets are decided by the request-conventions module, never hardcoded per call site.
7. Every generated statement must be validated against the target database before it is
   reported as a success. The LLM critic is advisory; the database is authoritative.
8. Write the tests from the acceptance matrix alongside the code.
9. Never modify the reference repository; it is read-only evidence. Build in the new tree.
10. When you cannot verify something from the specification, say so instead of guessing.
```

### Phase prompts

Each prompt is deliberately short: attach the referenced sections with it.

```text
PHASE 0 — Transport skeleton
Implement the HTTP boundary exactly as specified in §03: app/main.py, the routers, auth
dependencies, Pydantic request/response models with the documented field names and aliases,
and the SSE helpers. The generate endpoint may return a canned stub result for now.
Exit criteria: the endpoint list in §03 answers with the documented status codes; an SSE
smoke test shows status → result → done frames with the documented envelope fields.
Do not implement the pipeline yet.
```

```text
PHASE 1 — Configuration and storage substrate
Implement §04: settings (env-driven, exact defaults), the frozen constants module, the
PostgreSQL schema and access layer, the vector-store abstraction with both providers, the
schema-contract module, the embedding service with its two-level cache, and
build_source_stores(source_id) returning the documented bundle.
Exit criteria: a test that builds a bundle for one source and exercises every store's read
method against empty collections; no hardcoded values that are not in §04.
```

```text
PHASE 2 — Ingestion
Implement §11 so that a real data source can be onboarded: connection handling, catalog
scan, skills-folder markdown, schema/column vector rows, value index, few-shots, data groups,
precomputed questions, semantic models, plus the admin endpoints listed there.
Exit criteria: point it at a SQL Server instance, run the ingestion, and show the
collections/folders populated with the documented fields.
```

```text
PHASE 3 — Deterministic front half
Implement §05 exactly: preprocessing, PII masking, history folding, object auto-extraction,
conversational context (filter lifecycle + coreference), scenario classification, routing,
pin validation and the exact fast paths. Unit-test each decision table row by row.
Exit criteria: the scenario/route tables in §05 are reproduced as parameterized tests, and
the fast-path ordering test passes.
```

```text
PHASE 4 — Discovery and hydration
Implement §06: query analysis with caching, active data groups, KB-first discovery with all
branch labels, column evidence, RRF fusion with the documented k and weights, the object
caps and score floor, and the hydrator's four context slices with the token budget.
Exit criteria: with the ingested fixture source, a discovery call returns the documented
branch label and the expected tables for the fixture questions.
```

```text
PHASE 5 — Prompts
Create the prompt module from §08 verbatim. Do not paraphrase. Add a test that renders each
prompt for a fixed fixture context and diffs it against the expected text from §08
(snapshot test).
```

```text
PHASE 6 — Attempt loop and validation
Implement §07: the bounded attempt loop, the frozen validation order with a comment at each
step, the sentinel parser, the structural-hash hallucination breaker, the missing-object
circuit breaker, the critic call and parsing, the database validator for every supported
dialect, and the structured failure result.
Exit criteria: simulate 1) a clean first-try success, 2) a schema failure repaired by
expansion, 3) a repeated-structure hallucination loop, 4) a missing object twice, 5) a
safety refusal, 6) budget exhaustion — each producing the documented result and category.
```

```text
PHASE 7 — Semantic layer, execution, scripts
Implement §09 (semantic compiler + storage + prompts), §10 (execute/analysis/discuss/catalog)
and §12 (python/r/sas targets and utilities).
Exit criteria: the §14 tests for these sections pass, including SMQ error codes and the
execute-sql retry loop.
```

### Definition of done

The build is complete when the §14 acceptance matrix passes end-to-end against at least one real data source, including:

- a fresh question that needs retrieval (not an exact match),
- a follow-up that inherits a filter,
- an optimization turn that preserves semantics,
- a refinement turn that adds a table,
- a question whose first attempt fails schema validation and is repaired,
- a question that must fail honestly (unknown object) with a structured report,
- a semantic-mode question compiled from SMQ,
- a Python target turn whose embedded SQL is validated.

### Prompting patterns that work

| Instead of | Ask for |
|---|---|
| "Build the SQL generator" | "Implement §07 only. Do not change behaviour specified in §05 or §06." |
| "Use sensible thresholds" | "Transcribe every constant in §04 and assert them in a test." |
| "Write good prompts" | "Copy the prompt templates in §08 verbatim; show a diff against §08." |
| "Make it robust" | "Implement invariant I1–I14 from §15.1 as comments at the enforcement points and as tests where observable." |
| "Add error handling" | "Preserve every early-exit and terminal condition in the §07 matrix with its error category." |
| "Improve performance later" | "Implement the caps, floors and token budget from §06 before optimising anything." |

Also useful:

- Ask the agent to cite `docs/SQL_GENERATION_BACKEND_BLUEPRINT.md §NN` (or `app/...:LINE` in this repo) next to any decision it makes.
- Require a per-phase self-report: files created, tests run, observed output, deviations and why.
- Keep a `DEVIATIONS.md` — every intentional difference from the blueprint, with rationale.

### Traps that break parity

These are the mistakes that produce a plausible but incompatible agent (full list: §15.3):

1. **Reordering validation** — the attempt-1 database pre-check exists to skip an expensive critic call; moving the critic earlier changes latency and outcomes.
2. **Treating the critic as authoritative** — it can be wrong or unparsable; a parse failure defaults to "pass" and the database still decides.
3. **Retuning constants** — every threshold, weight, cap and budget is part of the product contract.
4. **Mixing score scales** — stores return cosine *distance* (KB exact ≤ 0.05) or *similarity* (precomputed ≥ 0.93); normalising them disables the fast paths.
5. **Dropping required/pinned objects** — pins, required objects and matched-column objects must survive caps, floors and pruning.
6. **Dropping the refinement widening** — refinement/drill-down raises the context cap (8 → 12) and promotes the editor SQL's tables to required.
7. **Inventing prompt wording** — prompts are contracts; paraphrase breaks the snapshot tests and model behaviour.
8. **Letting a stored exact answer override an active filter** — refinement turns carrying filters bypass exact matches by design.
9. **Ignoring token-budget accounting** — the schema budget (6 400) is measured, and over-budget markdown is column-pruned, not dropped.
10. **Assuming one data source** — every store read must be partitioned by `source_id`.

### Known reference defects — decide, don't copy

§15.5 documents verified defects in this repository. The blueprint tells you to fix or deliberately reproduce each one. The highest-impact ones:

| Defect | Consequence | Recommendation |
|---|---|---|
| `mode="replace"` ingest clears the collection for **all** sources | Cross-tenant data loss | Scope every clear/delete by `source_id` |
| Skills-folder rebuild writes corrupt column rows (bad tuple unpacking) | Garbage schema rows | Use the deterministic schema-row builder as the only producer |
| `/admin/schema/sync-full` picks the first data source found on disk | Wrong source scanned | Require `source_id` on every ingestion entry point |
| `/execute-sql` bypasses the safety interceptor and commits | Execute path is not read-only | Decide explicitly; add the interceptor and read-only transaction if needed |
| Default LLM client path drops `max_tokens` / `presence_penalty` and records zero tokens | Silent quality and cost blind spots | Forward shaped parameters and record usage on every path |
| Session filter state is a process-local LRU with no TTL | Lost context across workers | Use a shared store, or pin sessions to a worker |
| `config/agent_settings.json` is dead code containing live secrets | Credential exposure | Do not port or commit it; rotate what it contains |

### Keeping the blueprint in sync

If you change pipeline behaviour **in this repository**, update the corresponding blueprint section in the same change (the same rule that applies to [`docs/AGENT_PROCESS.md`](docs/AGENT_PROCESS.md)). Prompt edits must update §08; threshold edits must update §04; validation-order edits must update §07 and §15.1.

---

## Overview

A typical request flows through a FastAPI wrapper, then into a built-in orchestrator:

1. **Mode gate** — `plan` / `ask` stay conversational; `search` returns objects; `generate` produces code.
2. **Conversational context** — vague follow-ups are rewritten against recent turns, and active filters carry forward across a chat session.
3. **Route** — the request is classified as a fresh start, optimization, refinement, drill-down, or debugging turn.
4. **Discovery** — knowledge-base first, then reciprocal-rank fusion of schema vectors, value-index hits, data groups, and optional BM25.
5. **Attempt loop** — up to 5 attempts / 120 seconds: safety checks, critic, and database parse validation (`SET NOEXEC ON` on SQL Server).
6. **Optional execute** — a separate endpoint runs the SQL, retries on runtime errors, and can attach a data profile, insights, and a chart recommendation.

```
┌─────────────────────────────────────────────────────────────────┐
│              Frontend (React + Auth) — demo harness              │
│  Chat  ·  Admin panel  ·  Conversations  ·  User profile        │
└──────────────────────────────┬──────────────────────────────────┘
                               │ HTTP / SSE  (X-API-Key)
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Backend (FastAPI :8000)                    │
│  /api/v1/generate-sql  ·  /execute-sql  ·  /discovery           │
│  /api/v1/auth/*  ·  /users/*  ·  /conversations/*  ·  /admin/*  │
└───────┬──────────────────────┬──────────────────────┬───────────┘
        ▼                      ▼                      ▼
 PostgreSQL 15          Vector store              SQL Server
 users & convos         Milvus or sqlite-vec      warehouse
                        partitioned by            (or Excel files)
                        data_source_id
                               │
                               ▼
                         LLM + embeddings
                    (OpenAI-compatible / LiteLLM)
```

---

## Main features

| Feature | What it does |
|---------|----------------|
| **Natural language → SQL** | Converts questions into validated T-SQL for Microsoft SQL Server. |
| **Multi-language codegen** | Same pipeline for Python, R, and SAS (`target_language`). |
| **Query modes** | `generate`, `search`, `plan`, `ask`, and `code_advisor`. Planning/ask modes explore intent without emitting SQL. |
| **Conversational refinement** | Coreference rewrite of short follow-ups (`I need all order details` → `… for chocolate Products`) plus session filter inheritance, replacement, and clear. |
| **KB-first discovery** | Exact few-shot / precomputed hits short-circuit generation; otherwise RRF ranks schema, values, and data groups. |
| **Value index** | Maps everyday terms (for example “North America”) to exact `schema.table.column` values so generated SQL uses real literals. |
| **Iterative validation** | Safety interceptor, structural hash, LLM critic, and database parse-check; missing objects expand discovery. |
| **Execute + analyze** | Run SQL or Python with auto-retry, optional profiling, insights, and chart hints. |
| **Multi-source** | Each warehouse is a `source_id`. Vector collections and catalog lookups are partitioned by that id. |
| **Admin governance** | Schema index, knowledge base (few-shots), value index, data sources, contributions, and users. |
| **Skills / markdown catalog** | Schema objects and business groups stored as markdown and hydrated into the generation prompt under a token budget. |
| **Auth** | Per-user API keys (`X-API-Key`) with admin/user roles. Login is public; most other routes require a key. |
| **Streaming** | Generation endpoints stream Server-Sent Events (`status`, `result`, `done`, `error`). |

---

## Technology stack

| Layer | Technology |
|-------|------------|
| Backend | FastAPI, Pydantic v2, SQLAlchemy, pyodbc, LiteLLM |
| Frontend | React 19, TypeScript, Vite, Tailwind CSS — **showcase harness only, not a product** (see the note above) |
| User store | PostgreSQL 15 |
| Vector store | Milvus 2.3 (default) or sqlite-vec; same contract (`VECTOR_SCHEMA_VERSION` 1.1.0) |
| Warehouse | Microsoft SQL Server (ODBC Driver 17) |
| LLM | Any OpenAI-compatible API (OpenAI, Azure, Ollama, …) via LiteLLM |
| Embeddings | `text-embedding-3-small` (1536-d cosine) by default |

---

## Prerequisites

- **Python 3.11+** (the backend Docker image is `python:3.11-slim`)
- **Node.js 20+** (frontend Docker image is `node:20`)
- **Docker** for Milvus, etcd, MinIO, and PostgreSQL
- **Microsoft SQL Server** plus **ODBC Driver 17 for SQL Server**
- An **OpenAI-compatible LLM API key** (and embedding access if separate)

The same prerequisites apply when rebuilding the agent from the blueprint — start the substrate first (see [Vibe-coding the agent](#vibe-coding-the-agent)).

---

## Quick start

### 1. Clone and install

```bash
git clone https://github.com/SherlockSoftwareInc/octofy-ai-agent.git
cd octofy-ai-agent

pip install -r requirements.txt
pip install -r requirements-dev.txt   # tests

cd frontend
npm install
cd ..
```

### 2. Start infrastructure

```bash
docker-compose up -d
```

This starts:

| Service | Host port | Role |
|---------|-----------|------|
| PostgreSQL 15 | `5432` | Users and conversation history |
| Milvus standalone | `19630` | Vector search (`19530` inside the network) |
| etcd | internal | Milvus metadata |
| MinIO | `9100` / `9101` | Milvus object storage |

### 3. Configure environment

Copy `.env.example` to `.env` and fill in secrets:

```bash
cp .env.example .env
```

Minimum required values:

```env
# Auth
API_KEY=change-this-to-a-secure-key
JWT_SECRET_KEY=***REMOVED***

# PostgreSQL (matches docker-compose defaults)
POSTGRES_USER=octofy
POSTGRES_PASSWORD=***REMOVED***
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=octofy_users

# LLM
LLM_API_KEY=your_llm_api_key
LLM_MODEL=gpt-4o
# LLM_ENDPOINT=https://api.openai.com/v1   # optional; any OpenAI-compatible base URL

# Warehouse
SQL_SERVER_CONNECTION_STRING=DRIVER={ODBC Driver 17 for SQL Server};SERVER=localhost;DATABASE=Northwind;Trusted_Connection=yes

# Vector store
VECTOR_DB_ENABLED=true
VECTOR_PROVIDER=milvus
MILVUS_HOST=localhost
MILVUS_PORT=19630
```

SQL authentication example:

```env
SQL_SERVER_CONNECTION_STRING=DRIVER={ODBC Driver 17 for SQL Server};SERVER=localhost;DATABASE=Northwind;UID=sa;PWD=your_password
```

### 4. Initialize users and schema

User tables are created on backend startup. You can also seed them explicitly:

```bash
python scripts/init_user_db.py
```

If no users exist, a default admin is created:

| Field | Value |
|-------|--------|
| Username | `admin` |
| Password | `admin123` |

Change this password immediately after first login.

Ingest warehouse metadata into the vector index:

```bash
python scripts/ingest_metadata.py
```

Alternatively, register a data source in **Admin → Data Sources** and sync the schema from the UI.

### 5. Run the apps

Backend (port **8000**):

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Frontend (port **45678**, proxies `/api` to the backend) — **optional**; this is the showcase harness described at the top of this README and is not required to use or test the backend:

```bash
cd frontend
npm run dev
```

| Surface | URL |
|---------|-----|
| Chat UI | http://localhost:45678 |
| Admin | http://localhost:45678/admin |
| Health | http://localhost:8000/ → `{"message": "Database AI Agent API is running"}` |
| Swagger | http://localhost:8000/docs |
| ReDoc | http://localhost:8000/redoc |
| OpenAPI | http://localhost:8000/api/v1/openapi.json |

---

## Usage examples

All authenticated requests send the user’s API key:

```http
X-API-Key: <access_token from login>
```

Login returns that key as `access_token` (`token_type` is `api-key`).

### Login

```bash
curl -s http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'
```

```json
{
  "access_token": "oct_...",
  "token_type": "api-key",
  "user": { "username": "admin", "role": "admin" }
}
```

### Generate SQL (SSE)

`source_id` is required. Resolve it from Admin → Data Sources, or:

```bash
curl -s "http://localhost:8000/api/v1/admin/data-sources" \
  -H "X-API-Key: $API_KEY"
```

```bash
curl -N http://localhost:8000/api/v1/generate-sql \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{
    "query": "Show the top 10 customers by order count",
    "queryMode": "generate",
    "source_id": "northwind"
  }'
```

Typical stream:

```
data: {"type":"status","step":"discovery","message":"Discovering relevant objects"}

data: {"type":"result","payload":{"sql":"SELECT TOP 10 ...","success":true,"discovery_branch":"dual_prong"}}

data: {"type":"done"}
```

### Follow-up with session filters

Pass `session_id` (the chat/conversation id) so filters inherit, replace, or clear across turns. Also send the previous SQL as `existing_code` / `previousSQL` when the user is refining the editor query.

```bash
curl -N http://localhost:8000/api/v1/generate-sql \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{
    "query": "I need all order details",
    "queryMode": "generate",
    "source_id": "northwind",
    "session_id": "conv-123",
    "existing_code": "SELECT ProductName FROM dbo.Products WHERE ProductName LIKE '\''%chocolate%'\''",
    "queryHistory": "Q: Show chocolate products\nA: SELECT ProductName FROM dbo.Products WHERE ProductName LIKE '\''%chocolate%'\''"
  }'
```

The orchestrator rewrites the follow-up against active filters (for example, keep the chocolate product constraint) and treats the turn as **refinement** rather than a full rewrite. Phrases like `start over`, `new query`, or `clear filters` reset that state.

### Plan / ask (no SQL)

```bash
curl -N http://localhost:8000/api/v1/generate-sql \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{
    "query": "What tables would I use to analyze freight costs by ship country?",
    "queryMode": "ask",
    "source_id": "northwind"
  }'
```

### Execute SQL

Generation parse-checks only. Execution is a second call:

```bash
curl -s http://localhost:8000/api/v1/execute-sql \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{
    "sql": "SELECT TOP 10 CustomerID, COUNT(*) AS OrderCount FROM dbo.Orders GROUP BY CustomerID ORDER BY OrderCount DESC",
    "source_id": "northwind",
    "timeout_seconds": 30,
    "max_rows": 10000
  }'
```

When `ENABLE_AI_DATA_ANALYSIS=true`, the response can include `data_profile`, `insights`, and a `recommendation` chart. Runtime errors trigger up to five regenerate-and-retry attempts.

### Other languages

```bash
# Python
curl -N http://localhost:8000/api/v1/generate-python \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"query":"Load orders into a pandas DataFrame and plot monthly counts","source_id":"northwind"}'

# R
curl -N http://localhost:8000/api/v1/generate-r ...

# SAS
curl -N http://localhost:8000/api/v1/generate-sas ...
```

### Chat UI

The bundled UI is the demo harness from the note at the top of this README — a way to see the backend work, not a supported product surface.

1. Open http://localhost:45678 and sign in.
2. Pick a data source in the sidebar.
3. Choose a mode: Ask, Generate SQL, Python, R, SAS, or Code Advisor.
4. Ask a question. Status steps stream into the thread; SQL/code appears with an explanation.
5. Run the statement to see a result grid, optional insights, and a chart suggestion.
6. Continue in the same conversation to refine filters, add columns, or drill down.

---

## Admin workflows

Open **Admin** from the chat UI (`/admin`). Pages:

| Page | Purpose |
|------|---------|
| **Data Sources** | Register warehouses, test connections, scan objects, set primary source. |
| **Schema Index** | Sync tables/views/functions from the database, Excel bulk import, descriptions. |
| **Knowledge Base** | Few-shot question/SQL pairs that enable exact-match fast paths. |
| **Contributions** | User-submitted examples pending admin approval. |
| **Value Index** | Categorical value map used at generation time. |
| **User Management** | Create users, roles, regenerate API keys. |
| **Settings** | LLM, embeddings, and connectivity checks. |

### Value index (Excel)

1. Admin → **Value Index** → download the template.
2. Fill `value`, `schema_name`, `table_name`, `column_name`.
3. Upload in append or replace mode.

That mapping is what lets “North America” become the literal stored in `dbo.Region.RegionDescription` instead of a guessed string. Details: [docs/VALUE_INDEX_QUICKSTART.md](docs/VALUE_INDEX_QUICKSTART.md).

### Schema sync

Use **Sync** / **Sync Full** in Schema Index, or:

```bash
python scripts/ingest_metadata.py
```

> Rebuilding a service from the blueprint? §11 specifies the ingestion contract end to end, including the minimum dataset that makes generation possible (Tier 0: a single few-shot row; Tier 1: a concrete six-step set).

---

## API surface

Base path: `/api/v1`. Full reference: [docs/BACKEND_API.md](docs/BACKEND_API.md), and §03 of the blueprint for the contract-level detail (models, aliases, SSE envelope, status codes).

| Area | Examples |
|------|----------|
| Discovery | `POST /discovery` |
| Generation (SSE) | `POST /generate-sql`, `/generate-python`, `/generate-r`, `/generate-sas`, `/code-advisor` |
| Execution | `POST /execute-sql`, `/execute-python` |
| Summaries | `POST /planning-summary`, `/summarize-results` |
| Auth / users | `POST /auth/login`, `GET /auth/me`, admin `/admin/users` |
| Conversations | `GET/POST /conversations` |
| Admin | schema, few-shots, values, data sources, schema tree, skills, contributions |

`GenerateSQLRequest` fields that change the path:

| Field | Effect |
|-------|--------|
| `queryMode` | `generate` enters the orchestrator; `plan` / `ask` / `search` do not |
| `source_id` | Selects the per-source store bundle (required on generate HTTP) |
| `database_objects` | Pins; catalog-validated; fail-fast if missing |
| `existing_code` / `previousSQL` | Optimization, refinement, or debug |
| `error_message` | Debugging route (fix the provided code) |
| `session_id` | Cross-turn filter state |
| `semantic_mode` | Semantic-model compile path (SQL only) |
| `forceGeneral` | Skip SQL and chat instead |

---

## Project structure

```
octofy-ai-agent/
├── app/
│   ├── api/endpoints/          # FastAPI routers
│   ├── core/
│   │   ├── orchestrator/       # Route → discover → attempt loop
│   │   ├── auth.py
│   │   ├── config.py
│   │   └── constants.py        # Built-in thresholds (do not retune)
│   ├── models/                 # Pydantic + SQLAlchemy
│   ├── services/               # Generation wrapper, execute, stores
│   │   └── stores/             # Milvus / sqlite-vec contract
│   └── utils/
├── frontend/                   # Vite + React showcase harness for the backend (demo only, not a product)
├── scripts/                    # Ingest, user DB init, migrations
├── tests/                      # unit / contract / parity
├── docs/                       # Design and API docs
│   └── SQL_GENERATION_BACKEND_BLUEPRINT.md   # Build spec for the generation backend
├── docker-compose.yml          # etcd, MinIO, Milvus, PostgreSQL
└── .env.example
```

Orchestrator modules:

| File | Role |
|------|------|
| `app/services/generation_service.py` | Mode gate, discuss, catalog SQL |
| `app/core/orchestrator/builtin_sql_generator.py` | Generate path |
| `preprocessing.py`, `coreference.py`, `session_context.py` | History fold, rewrite, filters |
| `scenario.py`, `router.py` | Fresh start / optimize / refine / drill-down / debug |
| `discovery_engine.py` | KB-first + RRF |
| `attempts.py`, `prompts.py` | Attempt loop and dialect prompts |

The blueprint's §16.1 maps every module in this tree to the section that specifies its behaviour.

---

## Configuration notes

| Variable | Default | Notes |
|----------|---------|--------|
| `BUILTIN_SQL_GENERATOR` | `true` | Built-in orchestrator (recommended) |
| `VECTOR_PROVIDER` | `milvus` | Falls back to sqlite-vec if Milvus is unreachable |
| `ENABLE_AI_DATA_ANALYSIS` | `true` | Profiling, insights, chart after execute |
| `ENABLE_BM25_RETRIEVAL` | `false` | Optional lexical rerank |
| `ENABLE_SEMANTIC_LAYER_PER_DATA_SOURCE` | `{}` | JSON map of `source_id` → enabled |
| `OBJECT_SEARCH_VECTOR_SCORE_THRESHOLD` | `0.5` | Clamped to `[0, 1]` |

Retry budgets live in `app/core/constants.py` (`MaxRetries = 5`, `MaxGenerationTimeMs = 120000`) and should stay aligned with the desktop engine. §04 of the blueprint lists every setting and constant with its exact value and effect.

Vector collections (all partitioned by `data_source_id`): `schemas`, `few_shots`, `value_index`, `data_group_*`, `vec_data_group_queries`, `semantic_*`, `contribution_library`. See [docs/VECTOR_SCHEMA.md](docs/VECTOR_SCHEMA.md).

---

## Testing

```bash
pip install -r requirements-dev.txt
python -m pytest
python -m pytest tests/unit -v
```

Frontend:

```bash
cd frontend
npm test
```

Tests mock OpenAI and Milvus. Layout: `tests/unit`, `tests/contract`, `tests/parity`, plus module-level files. More detail: [tests/README.md](tests/README.md).

Building from the blueprint? Use §14 as the test plan: transport, constants/storage, routing/context, discovery, attempt loop, semantic layer, execution, script targets, ingestion, and cross-cutting suites (prompt snapshots, two-source isolation, provider-agnostic request shaping).

---

## Docker

Infrastructure only (typical local workflow):

```bash
docker-compose up -d
```

Backend and frontend also have their own images (`app/Dockerfile`, `frontend/Dockerfile`). The backend image installs ODBC Driver 17 and serves uvicorn on port 8000. The frontend image is a multi-stage Vite build served by nginx; it packages the demo UI only (not a product build).

Volume root defaults to `./volumes` (etcd, MinIO, Milvus, PostgreSQL). Override with `DOCKER_VOLUME_DIRECTORY`.

---

## Security

- Send `X-API-Key` on every authenticated route.
- Login (`POST /api/v1/auth/login`) is public.
- Admin routes require an active admin key.
- Change `API_KEY`, `JWT_SECRET_KEY`, the default admin password, and warehouse credentials before any shared deployment.
- Generation blocks write statements unless the user explicitly asked for them.
- `config/agent_settings.json` is dead code that contains live credentials — do not commit or port it (§15.5 D11).

### Never commit these

`.env` (and any `.env.*` other than `.env.example`), `config/agent_settings.json`, `*.pem` / `*.key` / `*.pfx` / `*.p12`, `credentials*.json`, `service-account*.json`, deployment archives (`*.tar.gz`), and generated dumps such as `repomix-output.xml`. All of them are covered by `.gitignore` — keep them out of `git add .`, and store runtime secrets in the environment or a secret manager.

Before pushing, verify what git will actually upload:

```bash
git ls-files | grep -Ei '\.env|agent_settings|\.pem$|\.key$|credential'
git grep --cached -n -I -E 'sk-[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{30,}|-----BEGIN [A-Z ]*PRIVATE KEY'
```

The second command prints nothing when the staged tree is clean.

### If a credential is ever committed

Rotate the credential first — assume it is compromised the moment it reaches a remote, a fork, or a CI log. Then remove it from history (`git filter-repo` or BFG), force-push the rewritten branch, ask collaborators to re-clone, and note that GitHub may retain unreachable objects and pull-request references for a while. Deleting the file in a new commit is not enough: the old commit still contains it.

---

## Documentation

**Building or re-implementing the backend?**

1. [docs/SQL_GENERATION_BACKEND_BLUEPRINT.md](docs/SQL_GENERATION_BACKEND_BLUEPRINT.md) — the build specification (§01–§16)

**Understanding the running service:**

1. [docs/AGENT_PROCESS.md](docs/AGENT_PROCESS.md) — stages, branches, attempt loop
2. [docs/VECTOR_SCHEMA.md](docs/VECTOR_SCHEMA.md) — collections and `source_id` partitioning
3. [docs/REQUEST_TO_CODE_FLOW.md](docs/REQUEST_TO_CODE_FLOW.md) — HTTP/SSE path
4. [docs/DISCOVERY_STRATEGY_IMPLEMENTATION.md](docs/DISCOVERY_STRATEGY_IMPLEMENTATION.md) — KB-first + RRF
5. [docs/BACKEND_API.md](docs/BACKEND_API.md) — endpoint reference

Also useful:

| Doc | Topic |
|-----|--------|
| [docs/CHATBOT.md](docs/CHATBOT.md) | Chat UI capabilities (demo harness) |
| [docs/GENERATE_SQL.md](docs/GENERATE_SQL.md) | Generate vs execute |
| [docs/PLANNING_MODE_FLOW.md](docs/PLANNING_MODE_FLOW.md) | Plan / ask modes |
| [docs/plans/2026-09-20-conversational-context-and-refinement.md](docs/plans/2026-09-20-conversational-context-and-refinement.md) | Scenarios, coreference, session filters |
| [docs/VALUE_INDEX_QUICKSTART.md](docs/VALUE_INDEX_QUICKSTART.md) | Value index setup |
| [docs/INDEX.md](docs/INDEX.md) | Full doc index |
| [CONTEXT.md](CONTEXT.md) | Project overview for contributors |
