# Fixing "SMQ JSON executed as SQL" in a Semantic-Layer Pipeline

**Audience:** whoever is porting or maintaining the semantic-layer SQL generation path in `octofy-ai-agent` (the Python/FastAPI service) — and anyone debugging the same class of failure in the built-in C# generator.

**Status of this document.** The C# reference implementation landed on 2026-09-28 and is described authoritatively in `Octofy.Agent/Docs/BUILT_IN_SQL_GENERATOR.md` item 39. The bug diagnosis and every rule below come from that work. The Python code in §8 was executed and is verified by the test matrix in §10; the Python-side *integration* points (module names, router signatures, where the compile call lives) are described as required behaviour rather than as claims about the current `octofy-ai-agent` source, which this document does not have access to.

> **Ported into `octofy-ai-agent` on 2026-09-28.** This is a copy of the plan that lived in
> `OctofyPro/Docs/plans/`; the port is complete and the rules below are now the implemented contract:
>
> | Plan rule | Where it landed |
> |---|---|
> | §8 module (`extract_smq_json`, `looks_like_smq`, `parse_smq`, `valid_names_hint`) | `app/services/semantic_smq.py` — the payload-class guard additionally detects truncated payloads through a depth-1 JSON-key scan, so a `{"metrics": ...` cut off mid-array is refused rather than executed |
> | §4 Steps 1–4 (guarded control flow, retry feedback, terminal classification) | `app/core/orchestrator/attempts.py:241-322` and `:496-508`; the guard precedes the fallback policy, and every semantic failure carries the offending item plus the model's valid names |
> | §5 Steps 5–7 (compiler rules, timeout) | `app/services/semantic_compiler.py` — ordered required tables, deterministic anchor, aggregate-aware `GROUP BY`, traversal-only tables never emitted, `EMPTY_REQUEST` for an empty request, `compile_guarded` enforcing the 5 s budget |
> | §4 Step 6 (keep the real database error) | `app/core/orchestrator/attempts.py:600-631` + `app/services/sql_validator.py:17-34` (`skip_object_scope`) |
> | §4 Step 7 (retrieval robustness) | `app/services/semantic_model_service.py:129-141` — `get_active_model()` returns `None` when the store is absent or predates the tables |
> | §10 test matrix | `tests/unit/test_semantic_smq.py` (61 tests), including the acceptance test that asserts the SQL validator is called **zero** times across four malformed payload shapes × fallback on/off |
>
> Two deliberate deviations from the letter of the plan: an empty payload (`{}`) is rejected with
> `EMPTY_REQUEST` rather than defaulting to the model's first measure, and a structurally SMQ payload whose
> value type is wrong is an explicit semantic retry rather than a fallback. The full behaviour record is
> blueprint §9.10 in `docs/SQL_GENERATION_BACKEND_BLUEPRINT.md`.

---

## 1. The symptom

A chat/generation request fails after every retry, and the last error is a **database syntax error pointing at a JSON key**:

```
Incorrect syntax near 'metrics'.
```

(or the driver equivalent — `syntax error at or near "metrics"`, `You have an error in your SQL syntax ... near '"metrics"'`).

The tell-tale sign is that the offending token is a **JSON key name** (`metrics`, `dimensions`, `filters`, `timeframes`), not a SQL keyword, table, or column. That means the database parser was handed the model's *semantic request*, never SQL.

## 2. Why it happens

The semantic path has three stages:

```
[LLM] --SMQ JSON--> [extract] --SemanticModelQuery--> [compiler] --physical SQL--> [validator] --> [DB]
                        ^^^                                 |
                   fails here                             +--- success
```

When extraction fails, the pipeline still holds the model's raw text. If a "be tolerant, fall back to raw SQL" switch is on — and it usually defaults to **on**, because it looks like graceful degradation — that raw text is treated as the SQL answer and continues down the normal path:

```
[LLM] --SMQ JSON--> [extract: ""] --???--> [validator] --> "Incorrect syntax near 'metrics'"
```

The failure is therefore **not** a missing compiler and **not** a schema-selection problem. It is a **payload-classification problem**: the pipeline could not recognise, and therefore could not refuse, a semantic payload.

Root causes observed in the C# implementation, in the order they were found:

| # | Root cause | Consequence |
|---|---|---|
| 1 | Extraction recognised only two shapes: a ```` ```smq ```` fence, or text that literally started with `{"metrics"` | A ```` ```json ````-fenced or prose-prefixed SMQ returned empty |
| 2 | The raw-SQL fallback was keyed on "extraction returned empty", not on "the payload is not SMQ" | Any unrecognised SMQ was silently executed as SQL |
| 3 | Compile failures wrote a bare error string and `continue`d | The retry loop never learned which metric/dimension was wrong or what the valid names were |
| 4 | Payload-class detection re-used the strict deserializer | A malformed-but-clearly-SMQ payload deserialized to `None`, which also looked like "no payload" |
| 5 | The compiler's FROM anchor came from an unordered set; `GROUP BY` was emitted whenever dimensions existed | Identical input compiled to different SQL across runs; detail queries were silently collapsed to distinct tuples |

Cause **2** is the dangerous one. Cause 1 is what triggers it. Fix 1 without 2 and the bug becomes rarer instead of impossible.

## 3. The one rule that must hold

> **A response that carries an SMQ payload is never executed as SQL — regardless of any fallback setting.**

The fallback setting keeps a legitimate meaning, but a narrower one:

- **Reply carries an SMQ payload** → it is compiled. If it cannot be compiled, it is a *semantic* failure that is retried, then reported. Never executed.
- **Reply carries no SMQ payload at all** (the model genuinely answered in SQL) → the fallback decides: with it on, use the raw SQL; with it off, fail.

Write that as a single explicit decision in code. Do not let "extraction returned nothing" imply "therefore it is SQL" — those are different questions.

### Shape decision table

| Reply shape | Extract? | Compiled? | Executed as SQL? |
|---|---|---|---|
| ```` ```smq ```` fence | yes | yes | no |
| ```` ```json ```` fence containing an SMQ object | yes | yes | no |
| Bare fence containing an SMQ object | yes | yes | no |
| Bare JSON | yes | yes | no |
| JSON embedded in prose | yes | yes | no |
| SMQ-shaped but malformed JSON | no | no | **no** — semantic retry, then semantic failure |
| JSON object with none of `metrics` / `dimensions` | no | no | fallback decides |
| Plain SQL (`SELECT ...`) | no | no | fallback decides |
| Prose / empty | no | no | fallback decides (and an empty reply is a generation failure) |

## 4. Implementation recipe

### Step 1 — Tolerant extraction

Accept all five payload shapes in the table above. Build the candidate list in this order and take the first that validates:

1. ```` ```smq ```` fenced block body.
2. Any other fenced block body (covers ```` ```json ````, ```` ```JSON ````, bare ```` ``` ````).
3. The first brace-balanced `{...}` region anywhere in the text (covers bare JSON and prose-prefixed JSON).
4. The whole response.

**Validation** of a candidate: it parses as a JSON **object** and carries a `metrics` **or** `dimensions` **array**. Accepting either key keeps a dimension-only request recognisable — it is still an SMQ and must not be run as SQL.

Two details that will otherwise cost you a debugging session:

- **Strip a leading fence language tag from the body.** A generic fence regex captures the tag (`json`) as the body's first line when it does not know the tag.
- **The brace scanner must honour string literals *and* escapes.** Skip braces inside strings, and treat `\"` as an escaped quote. Getting this wrong returns a truncated region for values like `"a \" b {c"`, the parse fails, and a perfectly good SMQ falls through to the SQL path — the exact bug. See §9.1.

### Step 2 — Payload-class detection (the guard)

Implement a second, **independent** predicate that answers only "does this look like an SMQ payload?", using JSON *parsing* for structure but not the strict SMQ model. It must be true for a malformed SMQ attempt (a `metrics` array that fails full validation), because that is precisely the case you must refuse to execute.

Do not implement this with a substring test such as `"metrics" in text` — a legitimate query such as `SELECT [metrics] FROM [dbo].[audit]` would be misclassified and refused.

### Step 3 — Guarded control flow

Structure the semantic branch as an explicit three-way decision, not a chain of fall-throughs:

```
smq_json = extract(cleaned_output)
if not smq_json:
    if looks_like_smq(raw_output) or looks_like_smq(cleaned_output) or not fallback_enabled:
        record_semantic_retry(reason, attachment=valid_names_hint(model))
        continue                                  # never reaches validation
    return raw_sql(cleaned_output)                # genuine SQL answer + fallback on

smq = parse_smq(smq_json)
if smq is None:
    record_semantic_retry("payload could not be parsed", attachment=valid_names_hint(model))
    continue

result = compile(smq, model, dialect)             # with a timeout
if not result.success:
    record_semantic_retry(result.detail + classifier_hint(result.detail),
                          attachment=valid_names_hint(model))
    continue

generated_sql = result.sql
mark_compiled_from_semantic_model()               # consumed in Step 4
```

Note the order: the guard is evaluated **before** the fallback policy, so `fallback_enabled` cannot resurrect the payload.

### Step 4 — Retry feedback that can actually succeed

Every semantic failure must append an attachment naming:

- the offending item (the unknown metric or dimension, or the unparsable payload text, truncated), and
- **the model's valid names** — the metrics from `measures[].name` and the dimensions from `dimensions[].name`, enumerated.

A retry that is told "unknown metric: gross_margin" and nothing else cannot converge. A retry that is told "unknown metric: gross_margin. Valid metrics: row_count, avg_response_minutes. Valid dimensions: bctr_number, arrival_date, transport_mode. Return only a fenced `smq` block; do not return SQL." usually can.

Also add an explicit statement that the reply must be an SMQ block and not SQL, because the retry prompt is now the main corrective signal.

**Terminal failure classification.** When the retry budget is exhausted while every attempt ended in a semantic retry, end the turn as a *semantic* failure (`error_category = "semantic_compilation"`) carrying the recorded detail. Guard this deliberately: if the last attempt was a semantic retry, do not fall through to the generic "unexpected loop exit" or to validation. This is what makes the symptom impossible rather than merely rare.

### Step 5 — Compiler rules

These are correctness rules for the SQL you generate, independent of the payload bug:

1. **Deterministic ordering.** Collect required tables in *request order* — dimensions first, then the tables named by measure expressions, then a join's `from_table` — into an ordered list, with a separate set for membership. Never derive the FROM anchor or the join order from set iteration.
2. **Deterministic anchor.** The anchor is: the first requested dimension's table → else the table a measure expression reads from (parse its `FROM`) → else the first required table.
3. **`GROUP BY` only when it is needed.** Emit `GROUP BY` over every projected dimension **only if** at least one resolved measure expression is an aggregate (`COUNT|SUM|AVG|MIN|MAX|STDEV|STDEVP|VAR|VARP|STRING_AGG|GROUP_CONCAT|LISTAGG|ARRAY_AGG|MEDIAN|APPROX_COUNT_DISTINCT`, delimiter-aware). Emitting it for a dimensions-only request silently collapses the result to distinct tuples — a wrong answer that validation will happily accept, which is worse than an error.
4. **Join plan.** BFS over the model's joins to connect all required tables (treating joins as traversable in both directions); no path → `INCOMPATIBLE_DIMENSIONS`; no source table at all → `MISSING_JOIN_PATH`.
5. **Accept a dimensions-only request.** Reject a payload that requests neither metrics nor dimensions. Do not reject one that requests only dimensions, and do not let a "measure required" editor rule leak into the compiler — extraction guarantees ≥ 1 measure on the model, not on the request.
6. **Dialect quoting.** `[x]` for SQL Server, `` `x` `` for MySQL/MariaDB, `"x"` otherwise; `N'...'` string literals on SQL Server.
7. **Timeout.** Wrap compilation with a per-call timeout (the reference uses 5 s) and treat expiry as a semantic retry.

### Step 6 — Keep the real database error

If the generated SQL came from the semantic compiler, **skip the client-side object-scope check** that rewrites database errors into "missing object" feedback.

Rationale: that check assumes the SQL was written against the retrieved schema context. Semantic SQL is not — the model may legitimately own tables the discovery step never selected (the reference case: a model rooted in schema `BCTR` while schema selection chose `TSBC`). Rewriting the error then buries the real cause and sends the retry loop off to search for objects that were never missing.

In the reference implementation this is a `compiled_from_semantic_model` flag set at compile time and passed to `ValidateSql(...)`.

### Step 7 — Retrieval robustness

Make the active-model lookup return `None` rather than raise when the store is absent or predates the semantic tables. A data source whose vector index was never built must degrade to "no active model" (semantic mode off for that turn), not fail the whole generation request.

## 5. Acknowledge the misleading paths (post-mortem notes)

These made the real cause harder to see. Recognise them so the port does not reproduce them:

- **The symptom names the wrong layer.** `Incorrect syntax near 'metrics'` looks like a SQL-generation bug or a schema problem. It is a payload-classification bug. If the offending token is a JSON key, stop looking at schema selection and prompts.
- **A candidate "fix" is to pin the semantic model's schemas into the prompt or the schema selector.** In the reference architecture the retrieved schema block is *not sent to the model at all* in semantic mode (the prompt carries the semantic model JSON instead and returns early), so such a change is dead code. Verify where the payload actually leaks before changing retrieval.
- **A "valid T-SQL" repair prompt looks like the bug.** In the semantic path the model is not asked for SQL. The instruction that mattered was the retry feedback, not the dialect reminder.
- **`SemanticCompilationError`-style taxonomy can be dead code.** If compile failures are handled before they reach the error classifier, the classifier's semantic branches only ever supply a recovery hint. That is fine, but do not assume the classification path is doing the work.

## 6. Do not

- Do not treat "extraction returned nothing" as "the payload is SQL".
- Do not let the raw-SQL fallback run before the payload-class guard.
- Do not implement the guard as a substring search for `metrics`.
- Do not use set/`dict` iteration order for the FROM anchor or join emission order.
- Do not emit `GROUP BY` merely because dimensions are present.
- Do not swallow compile failures with a bare message and no valid-name attachment.
- Do not let a semantic retry budget exhaust into a generic failure, and do not let an exhausted semantic turn reach the SQL validator.
- Do not gate the guard on a configuration flag that defaults to permissive.

## 7. Language notes

- **Regex `.` and newlines.** The C# patterns use single-line mode so `.` matches newlines inside a fence body. Python's `re.DOTALL` is the equivalent; without it a multi-line fenced body will not match.
- **Fence pattern.** ```` r"```(?:sql)?\s*\n?(?P<body>.*?)```" ```` with `re.I | re.S` mirrors the reference behaviour, including that it captures an unknown language tag as the body's first line — which is why `_drop_fence_tag` exists.
- **Idempotent parsing.** Doing tolerant extraction, then a *second* tolerant parse to produce the strongly typed query, is intentional: the first pass answers "is there something SMQ-shaped here?", the second answers "can I use it?". Keep them separate.
- **Pydantic.** If the SMQ model is a Pydantic model, do **not** rely on construction failing as the guard — `ValidationError` on a missing/renamed field also fires for a merely-malformed payload. Build the guard on raw `json.loads` structure.
- **Serialization round-tripping.** If extraction re-serializes the parsed object before the typed parse (as the reference does), verify that `None` values survive the round trip, or skip the round trip.

## 8. Python reference module

Verified by the test matrix in §10 (15/15 extraction cases, zero false positives from the guard).

```python
"""SMQ (Semantic Model Query) payload handling.

The contract with the model is a fenced ```smq block, but models answer with
```json, bare fences, bare JSON, and JSON wrapped in prose. Extraction is
therefore shape-tolerant.

Two independent questions are answered here, and keeping them independent is the
whole point:

* extract_smq()        -- is there a usable SMQ payload in this response?
* looks_like_smq()     -- does this response carry SMQ-shaped JSON, usable or not?

The second question is what keeps an unusable semantic payload out of the SQL
validator.
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional

# Preferred contract: a ```smq fenced block.
_SMQ_FENCE_RE = re.compile(r"```smq\s*\n?(?P<body>.*?)```", re.IGNORECASE | re.DOTALL)

# Any fenced block. The optional tag group deliberately does not enumerate tags:
# an unrecognised tag ends up as the body's first line and _drop_fence_tag removes it.
_ANY_FENCE_RE = re.compile(r"```(?:sql)?\s*\n?(?P<body>.*?)```", re.IGNORECASE | re.DOTALL)


def _parse_object(text: Optional[str]) -> Optional[dict]:
    """Parse text as a JSON object, or return None."""
    if not text or not text.strip():
        return None
    try:
        parsed = json.loads(text)
    except (ValueError, TypeError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _is_smq_object(obj: Optional[dict]) -> bool:
    """An SMQ object carries a `metrics` or `dimensions` array.

    Either key alone is enough: a dimensions-only request is a valid detail query
    and must still be recognised, so that it is never executed as SQL.
    """
    if obj is None:
        return False
    return isinstance(obj.get("metrics"), list) or isinstance(obj.get("dimensions"), list)


def _drop_fence_tag(body: str) -> str:
    """Remove a leading markdown language tag line left inside a fence body."""
    first, sep, rest = body.partition("\n")
    if not sep:
        return body
    tag = first.strip()
    if tag and not tag.startswith("{") and "://" not in tag:
        candidate = rest.strip()
        if candidate.startswith("{"):
            return candidate
    return body


def _find_balanced_object(text: str) -> Optional[str]:
    """Return the first brace-balanced {...} region, ignoring braces in strings.

    String literals and backslash escapes must both be honoured. A scanner that
    ignores escapes closes the string early on a value such as "a \\" b {c"},
    mis-counts the brace, and returns a truncated region -- which then fails to
    parse and lets a valid SMQ fall through to the SQL path.
    """
    start = text.find("{")
    while start >= 0:
        depth = 0
        in_string = False
        escaped = False
        for i in range(start, len(text)):
            ch = text[i]
            if in_string:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == '"':
                    in_string = False
                continue
            if ch == '"':
                in_string = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start : i + 1]
        start = text.find("{", start + 1)
    return None


def extract_smq_json(raw: Optional[str]) -> Optional[str]:
    """Extract the SMQ JSON object text from a raw model response."""
    if not raw or not raw.strip():
        return None
    text = raw.strip()

    for pattern in (_SMQ_FENCE_RE, _ANY_FENCE_RE):
        for match in pattern.finditer(text):
            body = _drop_fence_tag(match.group("body").strip())
            obj = _parse_object(body)
            if _is_smq_object(obj):
                return body

    region = _find_balanced_object(text)
    if region is not None and _is_smq_object(_parse_object(region)):
        return region

    if _is_smq_object(_parse_object(text)):
        return text

    return None


def looks_like_smq(raw: Optional[str]) -> bool:
    """True when the response carries SMQ-shaped JSON, applicable or not.

    Used to refuse to execute a semantic payload as SQL. Implemented by parsing
    structure -- never by searching for the substring "metrics", which would
    misclassify a query such as SELECT [metrics] FROM [dbo].[audit].
    """
    if not raw or not raw.strip():
        return False
    text = raw.strip()

    if _is_smq_object(_parse_object(text)):
        return True

    region = _find_balanced_object(text)
    if region is not None and _is_smq_object(_parse_object(region)):
        return True

    for match in _ANY_FENCE_RE.finditer(text):
        body = _drop_fence_tag(match.group("body").strip())
        if _is_smq_object(_parse_object(body)):
            return True

    return False


def _field(source: Any, key: str) -> Any:
    """Read `key` from a dict-shaped or attribute-shaped object."""
    if source is None:
        return None
    if isinstance(source, dict):
        return source.get(key)
    return getattr(source, key, None)


def valid_names_hint(model: Any) -> str:
    """Retry attachment enumerating the model's valid metric/dimension names.

    A semantic retry that is not told the valid vocabulary cannot converge.
    Accepts either a dict-shaped model (the shape the API transports) or an
    attribute-shaped one (a Pydantic/ORM instance), because both occur.
    """
    if isinstance(model, str):
        return model

    def names(collection: Any) -> list[str]:
        out: list[str] = []
        for item in collection or []:
            value = _field(item, "name")
            if isinstance(value, str) and value.strip() and value.strip() not in out:
                out.append(value.strip())
        return out

    measures = names(_field(model, "measures"))
    dimensions = names(_field(model, "dimensions"))

    parts = [" Return only a fenced smq code block with JSON of the shape "
             '{"metrics":[...],"dimensions":[...],"filters":[...],"timeframes":[...]}.'
             " Do not return SQL."]
    if measures:
        parts.append(" Valid metrics: " + ", ".join(measures) + ".")
    if dimensions:
        parts.append(" Valid dimensions: " + ", ".join(dimensions) + ".")
    return "".join(parts)
```

### Wiring it into the attempt loop

```python
smq_json = extract_smq_json(cleaned_output)

if not smq_json:
    # A payload that carries SMQ JSON must never be executed as SQL, whatever the
    # fallback policy says: the fallback exists for a model that answered in SQL.
    if looks_like_smq(raw_output) or looks_like_smq(cleaned_output) or not FALLBACK_TO_RAW_SQL:
        last_error = "Semantic mode requires an SMQ JSON payload, but the response could not be read as one."
        attempt_history.append(f"Attempt semantic compilation failure: {last_error}{valid_names_hint(model)}")
        semantic_retry = True
        continue
    generated_sql = cleaned_output          # genuine SQL answer + fallback enabled
else:
    smq = parse_smq(smq_json)               # strict, typed
    if smq is None:
        last_error = f"The SMQ payload could not be parsed. Received: {smq_json[:400]}"
        attempt_history.append(f"Attempt semantic compilation failure: {last_error}{valid_names_hint(model)}")
        semantic_retry = True
        continue

    result = compile_smq(smq, model, dialect, timeout=5)
    if not result.success:
        last_error = build_semantic_compile_error_feedback(result.detail)
        attempt_history.append(f"Attempt semantic compilation failure: {last_error}{valid_names_hint(model)}")
        semantic_retry = True
        continue

    generated_sql = result.sql
    compiled_from_semantic_model = True

# After the loop: an exhausted semantic budget is a semantic failure, not a parse error.
if last_attempt_was_semantic_retry:
    return semantic_failure(error_category="semantic_compilation", detail=last_error)
```

## 9. Gotchas

### 9.1 The escaped-quote brace scan (verified)

Payload value containing an escaped quote followed by a brace:

```
{"metrics":["row_count"],"filters":[{"field":"note","op":"eq","value":"a \" b {c"}]}
```

| Scanner | Region returned | Parses? |
|---|---|---|
| Honours string state **and** escapes | the whole payload | ✅ yes |
| Ignores escapes | `None` (truncated / unbalanced) | ❌ no |

When it fails, a valid SMQ is not recognised and — with the fallback on — is executed as SQL. That is the original bug, reproduced by a one-character omission.

### 9.2 The substring trap (verified)

`"metrics" in text` is true for `SELECT [metrics] FROM [dbo].[audit] WHERE [metrics] IS NOT NULL;`. Classifying that as SMQ would refuse a legitimate SQL answer. Parse structure instead: the guard returns `False` for that input.

### 9.3 Ordering is the fix

The guard must be evaluated before the fallback, and semantic failures must `continue` before the payload reaches safety scan, critic, or `ValidateSql`. If any refinement moves validation earlier, the bug returns regardless of how good extraction is.

## 10. Test matrix

Port these. The C# suite lives in `MyTestProject/BuiltInSqlGeneratorSmqExtractionTests.cs`; the Python equivalents were executed while writing §8 and pass as shown.

### Extraction (must return a payload)

| Case | Input |
|---|---|
| smq fence | ```` ```smq\n{...}\n``` ```` |
| json fence | ```` ```json\n{...}\n``` ```` |
| bare fence | ```` ```\n{...}\n``` ```` |
| bare JSON | `{...}` |
| prose + JSON | `Here you go:\n\n{...}` |
| prose + json fence | `Working:\n\n```json\n{...}\n```\nAny questions?` |
| bold marker | `**smq**\n{...}` |
| dimensions only | `{"dimensions":["bctr_number"]}` |
| nested filters + timeframes | object with `filters[]` / `timeframes[]` |

### Rejection (must return nothing, and the guard must be false)

| Case | Input |
|---|---|
| plain SQL | `SELECT COUNT(*) AS c FROM bctr.trauma_scene;` |
| sql fence | ```` ```sql\nSELECT 1 AS v;\n``` ```` |
| JSON without SMQ keys | `{"name":"r","columns":["a"]}` |
| SQL mentioning the word metrics | `SELECT [metrics] FROM [dbo].[audit]` |
| empty / whitespace | `""`, `"   "` |
| prose only | `I could not find a matching semantic model.` |

### Behavioural

1. **Guard precedence** — with the fallback **enabled**, an SMQ-shaped payload that fails to parse produces a `semantic_compilation` retry and the JSON is never the value passed to SQL execution.
2. **Fallback still works for SQL** — with the fallback enabled, a plain-SQL reply with no SMQ still proceeds as SQL (no regression).
3. **Fallback off** — a missing SMQ is an error; semantic retries still occur.
4. **Retry feedback** — an unknown metric/dimension produces an attempt-history entry containing the model's valid names.
5. **Terminal classification** — exhausting the budget with only semantic retries yields `semantic_compilation`, and the reported detail contains no `Incorrect syntax` text.
6. **Compiler determinism** — the same model+SMQ compiles to byte-identical SQL over ≥ 20 runs (this is what catches set-iteration ordering).
7. **GROUP BY matrix** — dimensions + aggregate → `GROUP BY` listing every dimension; dimensions only → no `GROUP BY`; aggregate only → no `GROUP BY`.
8. **Anchor** — with dimensions spanning three tables, `FROM` is the first requested dimension's table.
9. **Missing store** — a data source with no semantic store returns "no active model" instead of raising.
10. **Compiled-SQL error preservation** — with `compiled_from_semantic_model` set, a server rejection returns the server error, not a rewritten missing-object error.

## 11. Acceptance criteria

- No configuration of the fallback setting can cause a JSON payload containing `metrics` to be sent to a database. Prove it by test, not by inspection.
- An unusable semantic payload terminates as `semantic_compilation` with actionable detail.
- A genuine SQL reply with no SMQ still works under the fallback.
- Repeated compilation of the same input is byte-identical.
- Detail queries (dimensions without aggregates) are not grouped.

## 12. Related documents

- `Octofy.Agent/Docs/BUILT_IN_SQL_GENERATOR.md` — item 39 is the authoritative C# change record; the Semantic Layer Integration section documents the compiler and payload rules.
- `OctofyPro/Docs/plans/BUILT_IN_SQL_GENERATOR_PYTHON_PORT_PLAN.md` — the overall porting contract, including parity tests 24a–24c that correspond to this document.
- `OctofyPro/Docs/VECTOR_DATABASE_RAG_SUMMARY.md` — §7, semantic model layer.
- `OctofyPro/Docs/User Manual/octofy-ai-agent-backend-api.md` — the client-visible guarantee that a semantic payload is never executed as SQL.
