"""SMQ payload handling test matrix (plan §10).

Extraction and rejection share one table each; the behavioural tests drive the real
attempt loop with doubles so the *ordering* guarantees (guard before fallback, semantic
failures before validation) are proven by execution rather than by inspection.
"""

import json
from types import SimpleNamespace

import pytest

from app.core.constants import MaxRetries
from app.core.errors import ErrorCategory
from app.core.orchestrator.attempts import run_attempt_loop
from app.models.pipeline import (
    AgentContext,
    AgentRequest,
    DiscoveryResult,
    SemanticDimension,
    SemanticJoin,
    SemanticMeasure,
    SemanticModel,
    SmqPayload,
)
from app.services.semantic_compiler import (
    SemanticCompiler,
    SemanticCompilationError,
    expression_has_aggregate,
)
from app.services.semantic_smq import (
    extract_smq_json,
    looks_like_smq,
    parse_smq,
    valid_names_hint,
)

# --------------------------------------------------------------------------------------
# Payload fixtures
# --------------------------------------------------------------------------------------

PAYLOAD = {"metrics": ["row_count"], "dimensions": ["bctr_number"]}
PAYLOAD_JSON = json.dumps(PAYLOAD)

# §9.1: an escaped quote followed by a brace. A scanner that ignores escapes truncates here.
ESCAPED = (
    '{"metrics":["row_count"],"filters":[{"field":"note","op":"eq","value":"a \\" b {c"}]}'
)

EXTRACTION_CASES = [
    ("smq fence", f"```smq\n{PAYLOAD_JSON}\n```"),
    ("json fence", f"```json\n{PAYLOAD_JSON}\n```"),
    ("JSON fenced with a capital tag", f"```JSON\n{PAYLOAD_JSON}\n```"),
    ("bare fence", f"```\n{PAYLOAD_JSON}\n```"),
    ("bare JSON", PAYLOAD_JSON),
    ("prose + JSON", f"Here you go:\n\n{PAYLOAD_JSON}"),
    ("prose + json fence", f"Working:\n\n```json\n{PAYLOAD_JSON}\n```\nAny questions?"),
    ("bold marker", f"**smq**\n{PAYLOAD_JSON}"),
    ("dimensions only", '{"dimensions":["bctr_number"]}'),
    ("nested filters + timeframes", json.dumps({
        "metrics": ["avg_response_minutes"],
        "dimensions": ["transport_mode"],
        "filters": [{"field": "bctr_number", "op": "eq", "value": "1"}],
        "timeframes": [{"field": "arrival_date", "start": "2024-01-01", "end": "2024-12-31"}],
    })),
    ("escaped quote before a brace", ESCAPED),
]

REJECTION_CASES = [
    ("plain SQL", "SELECT COUNT(*) AS c FROM bctr.trauma_scene;"),
    ("sql fence", "```sql\nSELECT 1 AS v;\n```"),
    ("JSON without SMQ keys", '{"name":"r","columns":["a"]}'),
    ("SQL mentioning the word metrics", "SELECT [metrics] FROM [dbo].[audit]"),
    ("empty", ""),
    ("whitespace", "   "),
    ("prose only", "I could not find a matching semantic model."),
]


@pytest.mark.parametrize("label,text", EXTRACTION_CASES, ids=[c[0] for c in EXTRACTION_CASES])
def test_extraction_returns_payload(label, text):
    extracted = extract_smq_json(text)
    assert extracted is not None, label
    parsed = parse_smq(text)
    assert parsed is not None, label
    assert parsed.metrics or parsed.dimensions, label


@pytest.mark.parametrize("label,text", REJECTION_CASES, ids=[c[0] for c in REJECTION_CASES])
def test_rejection_returns_nothing(label, text):
    assert extract_smq_json(text) is None, label
    assert parse_smq(text) is None, label
    assert looks_like_smq(text) is False, label


def test_guard_true_for_malformed_smq():
    """An unusable semantic payload is exactly what must never reach the SQL validator."""
    malformed = '{"metrics":["row_count"],'  # truncated
    assert extract_smq_json(malformed) is None
    assert looks_like_smq(malformed) is True


def test_guard_is_not_a_substring_search():
    """§9.2: `"metrics" in text` would refuse this legitimate SQL answer."""
    sql = "SELECT [metrics] FROM [dbo].[audit] WHERE [metrics] IS NOT NULL;"
    assert "metrics" in sql
    assert looks_like_smq(sql) is False
    assert extract_smq_json(sql) is None


def test_guard_ignores_a_quoted_word_that_only_looks_like_a_key():
    """A quoted literal followed by a colon inside SQL is not a JSON key."""
    sql = "SELECT 'dimensions': FROM [dbo].[audit]"
    assert looks_like_smq(sql) is False


def test_guard_detects_a_truncated_payload_before_its_first_value():
    assert looks_like_smq('{"metrics":') is True
    assert looks_like_smq('```json\n{"metrics":') is True


def test_escaped_quote_brace_scan_returns_whole_payload():
    """§9.1: ignoring escapes returns a truncated region, which parses as nothing."""
    region = extract_smq_json(ESCAPED)
    assert region is not None
    assert json.loads(region) == json.loads(ESCAPED)


def test_extraction_prefers_smq_fence_over_later_text():
    text = f"```smq\n{PAYLOAD_JSON}\n```\n\nand also:\n```json\n{{\"metrics\":[\"other\"]}}\n```"
    assert json.loads(extract_smq_json(text))["metrics"] == ["row_count"]


# --------------------------------------------------------------------------------------
# Compiler rules (§5)
# --------------------------------------------------------------------------------------


def _model():
    return SemanticModel(
        model_id="m1",
        label="BCTR",
        measures=[
            SemanticMeasure(name="row_count", expression="COUNT(*)", description="rows"),
            SemanticMeasure(
                name="avg_response_minutes", expression="AVG(trauma.response_min)", description="avg"
            ),
        ],
        dimensions=[
            SemanticDimension(name="bctr_number", column="bctr_number", table="bctr.trauma_scene"),
            SemanticDimension(name="transport_mode", column="mode", table="bctr.transport"),
            SemanticDimension(name="arrival_date", column="arrival_date", table="bctr.trauma_scene"),
        ],
        joins=[
            SemanticJoin(
                from_table="bctr.trauma_scene",
                to_table="bctr.transport",
                join_expression="bctr.trauma_scene.transport_id = bctr.transport.id",
                join_type="INNER",
            )
        ],
    )


def test_group_by_matrix():
    compiler = SemanticCompiler()
    model = _model()

    grouped = compiler.compile(
        SmqPayload(metrics=["row_count"], dimensions=["bctr_number"]), model
    )
    assert "GROUP BY" in grouped
    assert grouped.count("GROUP BY") == 1

    detail = compiler.compile(SmqPayload(dimensions=["bctr_number"]), model)
    assert "GROUP BY" not in detail

    aggregate_only = compiler.compile(SmqPayload(metrics=["row_count"]), model)
    assert "GROUP BY" not in aggregate_only


def test_group_by_needs_a_real_aggregate():
    """A non-aggregate measure must not make a detail query grouped."""
    model = _model()
    model.measures.append(
        SemanticMeasure(name="plain", expression="bctr.trauma_scene.arrival_date", description="d")
    )
    sql = SemanticCompiler().compile(
        SmqPayload(metrics=["plain"], dimensions=["bctr_number"]), model
    )
    assert "GROUP BY" not in sql


def test_aggregate_detection_is_delimiter_aware():
    assert expression_has_aggregate("COUNT(*)") is True
    assert expression_has_aggregate("AVG(x.y)") is True
    assert expression_has_aggregate("approx_count_distinct(x.y)") is True
    # a column whose *name* starts with an aggregate name is not an aggregate call
    assert expression_has_aggregate("t.avg_cost") is False
    assert expression_has_aggregate("t.county_name") is False
    assert expression_has_aggregate("t.maximum_load") is False


def test_determinism_is_byte_identical():
    compiler = SemanticCompiler()
    model = _model()
    payload = SmqPayload(metrics=["row_count"], dimensions=["transport_mode", "bctr_number"])
    first = compiler.compile(payload, model)
    for _ in range(20):
        assert compiler.compile(payload, model) == first


def test_from_anchor_is_first_requested_dimension():
    model = _model()
    # transport_mode is requested first and lives in bctr.transport, not the measure's table
    sql = SemanticCompiler().compile(
        SmqPayload(metrics=["row_count"], dimensions=["transport_mode", "bctr_number"]), model
    )
    assert sql.split("FROM ")[1].splitlines()[0].strip().startswith("[bctr].[transport]")


def test_anchor_declines_a_measure_table_the_model_does_not_declare():
    """A name inside an expression may not silently choose the FROM clause."""
    model = _model()
    model.measures.append(
        SemanticMeasure(
            name="orphan_rows",
            expression="(SELECT COUNT(*) FROM staging.orphan_feed)",
            description="n",
        )
    )
    sql = SemanticCompiler().compile(SmqPayload(metrics=["orphan_rows"]), model)
    # staging.orphan_feed is not part of the model, so the model's own anchor stands.
    assert "[bctr].[trauma_scene]" in sql.split("\nFROM ")[1]
    assert '"staging"' not in sql.split("\nFROM ")[1]


def test_anchor_falls_back_to_measure_source_table():
    """A measure's explicit FROM names the anchor when the model declares that table."""
    model = _model()
    model.measures.append(
        SemanticMeasure(
            name="remote_rows",
            expression="(SELECT COUNT(*) FROM bctr.transport)",
            description="n",
        )
    )
    sql = SemanticCompiler().compile(SmqPayload(metrics=["remote_rows"]), model)
    assert sql.split("\nFROM ")[1].splitlines()[0].strip().startswith("[bctr].[transport]")


def test_dimensions_only_request_is_accepted():
    sql = SemanticCompiler().compile(SmqPayload(dimensions=["bctr_number"]), _model())
    assert "SELECT" in sql
    assert "COUNT(*)" not in sql


def test_empty_request_is_rejected():
    with pytest.raises(SemanticCompilationError) as exc:
        SemanticCompiler().compile(SmqPayload(), _model())
    assert exc.value.code == "EMPTY_REQUEST"


def test_incompatible_dimensions_raise():
    model = _model()
    model.joins = []
    with pytest.raises(SemanticCompilationError) as exc:
        SemanticCompiler().compile(
            SmqPayload(dimensions=["bctr_number", "transport_mode"]), model
        )
    assert exc.value.code == "INCOMPATIBLE_DIMENSIONS"


def test_join_plan_skips_traversal_only_tables():
    """arrival_date and bctr_number share a table; transport_mode is joined once."""
    sql = SemanticCompiler().compile(
        SmqPayload(dimensions=["bctr_number", "arrival_date", "transport_mode"]), _model()
    )
    assert sql.count("JOIN") == 1
    assert "[bctr].[transport]" in sql


def test_guarded_compile_reports_failure_instead_of_raising():
    result = SemanticCompiler().compile_guarded(
        SmqPayload(metrics=["nope"]), _model()
    )
    assert result.success is False
    assert "UNKNOWN_METRIC" in result.detail


def test_guarded_compile_times_out():
    class SlowCompiler(SemanticCompiler):
        def _render(self, payload, model, dbms, include_governance):
            import time

            time.sleep(0.5)
            return "SELECT 1"

    result = SlowCompiler().compile_guarded(SmqPayload(metrics=["row_count"]), _model(), timeout_ms=10)
    assert result.success is False
    assert "COMPILATION_TIMEOUT" in result.detail


def test_dialect_quoting():
    model = _model()
    payload = SmqPayload(metrics=["row_count"], dimensions=["bctr_number"])
    assert "[bctr].[trauma_scene]" in SemanticCompiler().compile(payload, model, "SQL Server")
    assert "`bctr`.`trauma_scene`" in SemanticCompiler().compile(payload, model, "MySQL")
    assert '"bctr"."trauma_scene"' in SemanticCompiler().compile(payload, model, "PostgreSQL")


# --------------------------------------------------------------------------------------
# valid_names_hint (§4 Step 4)
# --------------------------------------------------------------------------------------


def test_valid_names_hint_enumerates_model_vocabulary():
    hint = valid_names_hint(_model())
    assert "Valid metrics: row_count, avg_response_minutes." in hint
    assert "Valid dimensions: bctr_number, transport_mode, arrival_date." in hint
    assert "Do not return SQL" in hint


def test_valid_names_hint_accepts_dict_shaped_model():
    hint = valid_names_hint({"measures": [{"name": "row_count"}], "dimensions": [{"name": "d1"}]})
    assert "Valid metrics: row_count." in hint
    assert "Valid dimensions: d1." in hint


def test_valid_names_hint_on_missing_model_still_forbids_sql():
    hint = valid_names_hint(None)
    assert "Do not return SQL" in hint


# --------------------------------------------------------------------------------------
# Behavioural matrix (§10) — drive the real attempt loop
# --------------------------------------------------------------------------------------


class FakeLlm:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = 0
        self.token_usage = SimpleNamespace(as_dict=lambda: {})

    def complete(self, messages, **kwargs):
        self.calls += 1
        index = min(self.calls - 1, len(self.replies) - 1)
        return self.replies[index]

    def complete_json(self, messages, **kwargs):
        return {}


class FakeSemanticService:
    def __init__(self, model=None, raises=False):
        self.model = model
        self.raises = raises

    def get_active_model(self):
        if self.raises:
            raise RuntimeError("table semantic_models does not exist")
        return self.model

    def search_models(self, query, top_k=3):
        return []


class FakeStores:
    def __init__(self, model=None, raises=False):
        self.semantic = FakeSemanticService(model=model, raises=raises)


def _context():
    return AgentContext(
        request=AgentRequest(query="how many trauma scenes", source_id="src-1"),
        combined_query="how many trauma scenes",
        dbms_type="SQL Server",
    )


def _discovery():
    return DiscoveryResult(objects=[], branch="fresh_start")


def _validate_calls(monkeypatch):
    """Record every SQL string handed to the validator and accept all of them."""
    seen = []

    def fake_validate(self, sql, allowed_objects=None, skip_object_scope=False):
        seen.append({"sql": sql, "skip_object_scope": skip_object_scope})
        return True, "", []

    monkeypatch.setattr("app.services.sql_validator.SqlValidator.validate", fake_validate)
    return seen


def _drive(loop):
    """Exhaust a generator, returning the value it returns through StopIteration."""
    while True:
        try:
            next(loop)
        except StopIteration as done:
            return done.value


def _run(replies, model=None, raises=False, monkeypatch=None):
    seen = _validate_calls(monkeypatch)
    llm = FakeLlm(replies)
    result = _drive(
        run_attempt_loop(
            _context(),
            _discovery(),
            FakeStores(model=model, raises=raises),
            llm,
            lambda *a, **k: None,
            semantic_mode=True,
        )
    )
    return result, seen, llm


@pytest.mark.parametrize("fallback_enabled", [True, False], ids=["fallback-on", "fallback-off"])
@pytest.mark.parametrize(
    "reply",
    [
        '```json\n{"metrics":["row_count"], "dimensions":[\n```',  # truncated inside a fence
        '{"metrics":["row_count"],',                                  # truncated bare JSON
        '{"dimensions":"bctr_number"}',                               # SMQ key, wrong value type
        "Here is the query:\n\n```json\n{\"metrics\": [\"row_count\"],\n\nAny questions?",
    ],
    ids=["truncated-fence", "truncated-bare", "wrong-value-type", "prose-truncated"],
)
def test_no_fallback_setting_can_execute_a_payload(reply, fallback_enabled, monkeypatch):
    """Acceptance criterion: no configuration of the fallback lets a payload reach the DB.

    Proven by execution: the smuggled SQL validator is asserted to have been called zero
    times, with the fallback both on and off.
    """
    monkeypatch.setattr(
        "app.core.orchestrator.attempts.semantic_compilation_fallback_to_raw_sql",
        lambda: fallback_enabled,
    )
    result, seen, llm = _run([reply], model=_model(), monkeypatch=monkeypatch)

    assert seen == [], f"payload reached the SQL validator: {seen}"
    assert result.success is False
    assert result.error_category == ErrorCategory.SEMANTIC_COMPILATION
    assert llm.calls == MaxRetries
    for report in result.failure_report.attempts:
        assert report.stage == "semantic_compilation"


def test_guard_precedence_malformed_smq_never_reaches_validation(monkeypatch):
    """Behavioural 1: with the fallback enabled, an SMQ-shaped payload is never executed."""
    malformed = '{"metrics":["row_count"], "dimensions":['
    result, seen, llm = _run([malformed], model=_model(), monkeypatch=monkeypatch)

    assert llm.calls == MaxRetries
    assert result.success is False
    assert result.error_category == ErrorCategory.SEMANTIC_COMPILATION
    assert seen == [], "no candidate should ever reach the SQL validator"
    assert "Incorrect syntax" not in (result.message or "")


def test_guard_precedence_json_object_with_smq_keys(monkeypatch):
    """A payload carrying an SMQ key is never executed as SQL, even when unusable.

    ``{"metrics": "row_count"}`` is not a *valid* SMQ, which is the weak spot: it must be
    caught by the payload-class guard rather than fall through to the SQL path.
    """
    unusable = '{"metrics": "row_count"}'
    result, seen, llm = _run([unusable], model=_model(), monkeypatch=monkeypatch)

    assert looks_like_smq(unusable) is True
    assert llm.calls == MaxRetries
    assert result.success is False
    assert result.error_category == ErrorCategory.SEMANTIC_COMPILATION
    assert seen == [], "no candidate should ever reach the SQL validator"


def test_json_object_without_smq_keys_is_not_refused(monkeypatch):
    """A JSON reply that never mentions SMQ keys is not a semantic payload."""
    notebook = '{"name":"report","columns":["a","b"]}'
    result, seen, _ = _run([notebook], model=_model(), monkeypatch=monkeypatch)
    assert looks_like_smq(notebook) is False
    assert seen and seen[0]["sql"] == notebook


def test_fallback_still_works_for_plain_sql(monkeypatch):
    """Behavioural 2: a genuine SQL reply with no SMQ proceeds as SQL."""
    sql = "SELECT COUNT(*) AS c FROM bctr.trauma_scene;"
    result, seen, llm = _run([f"```sql\n{sql}\n```"], model=_model(), monkeypatch=monkeypatch)

    assert result.success is True
    assert result.sql == sql
    assert seen and seen[0]["sql"] == sql
    assert llm.calls == 1


def test_fallback_off_makes_a_missing_smq_an_error(monkeypatch):
    """Behavioural 3: with the fallback off, a SQL reply is a semantic failure."""
    monkeypatch.setattr(
        "app.core.orchestrator.attempts.semantic_compilation_fallback_to_raw_sql",
        lambda: False,
    )
    result, seen, _ = _run(
        ["SELECT COUNT(*) AS c FROM bctr.trauma_scene;"], model=_model(), monkeypatch=monkeypatch
    )
    assert result.success is False
    assert result.error_category == ErrorCategory.SEMANTIC_COMPILATION
    assert seen == []


def test_unknown_metric_retry_names_the_valid_vocabulary(monkeypatch):
    """Behavioural 4: the retry feedback carries the model's valid names."""
    result, seen, _ = _run(
        ['{"metrics":["gross_margin"]}'], model=_model(), monkeypatch=monkeypatch
    )
    history = "\n".join(r.why_it_failed or "" for r in result.failure_report.attempts)
    assert "gross_margin" in history
    assert "Valid metrics: row_count, avg_response_minutes." in history
    assert "Valid dimensions: bctr_number, transport_mode, arrival_date." in history
    assert seen == []


def test_compiled_semantic_sql_reaches_validation_with_scope_check_skipped(monkeypatch):
    """§5 Step 6: the compiled flag must reach the validator."""
    payload = json.dumps({"metrics": ["row_count"], "dimensions": ["transport_mode"]})
    result, seen, llm = _run([f"```smq\n{payload}\n```"], model=_model(), monkeypatch=monkeypatch)

    assert result.success is True
    assert seen and seen[0]["skip_object_scope"] is True
    assert llm.calls == 1


def test_sql_reply_keeps_the_scope_check(monkeypatch):
    sql = "SELECT COUNT(*) AS c FROM bctr.trauma_scene;"
    _, seen, _ = _run([f"```sql\n{sql}\n```"], model=_model(), monkeypatch=monkeypatch)
    assert seen and seen[0]["skip_object_scope"] is False


def test_terminal_classification_is_semantic_not_generic(monkeypatch):
    """Behavioural 5: an exhausted semantic budget ends as semantic_compilation."""
    result, seen, _ = _run(
        ['{"metrics":["gross_margin"]}'], model=_model(), monkeypatch=monkeypatch
    )
    assert result.error_category == ErrorCategory.SEMANTIC_COMPILATION
    assert result.failure_report is not None
    assert all(a.stage == "semantic_compilation" for a in result.failure_report.attempts)
    assert "Incorrect syntax" not in (result.message or "")
    assert seen == []


def test_semantic_retry_then_success(monkeypatch):
    """The retry loop can actually converge when the model corrects itself."""
    payload = json.dumps({"metrics": ["row_count"]})
    result, _, llm = _run(
        ['{"metrics":["gross_margin"]}', f"```smq\n{payload}\n```"],
        model=_model(),
        monkeypatch=monkeypatch,
    )
    assert result.success is True
    assert result.attempts == 2
    assert llm.calls == 2


def test_missing_store_degrades_to_semantic_failure_not_a_crash(monkeypatch):
    """Behavioural 9: a data source with no semantic store yields 'no active model'."""
    _validate_calls(monkeypatch)
    llm = FakeLlm(['{"metrics":["row_count"]}'])
    result = _drive(
        run_attempt_loop(
            _context(),
            _discovery(),
            FakeStores(raises=True),
            llm,
            lambda *a, **k: None,
            semantic_mode=True,
        )
    )
    assert result.success is False
    assert result.error_category == ErrorCategory.SEMANTIC_COMPILATION
    assert "No active semantic model" in (result.message or "")


def test_compiled_sql_error_is_preserved_over_the_missing_object_rewrite():
    """Behavioural 10: the server error survives when the SQL came from the compiler."""
    from app.services.sql_validator import SqlValidator

    validator = SqlValidator(source_id=None, dbms="SQL Server")
    validator._sql_server = lambda sql: (True, "", [])
    ok, err, _ = validator.validate(
        "SELECT 1 FROM bctr.trauma_scene", ["tsbc.other"], skip_object_scope=True
    )
    assert (ok, err) == (True, "")

    ok, err, _ = validator.validate(
        "SELECT 1 FROM bctr.trauma_scene", ["tsbc.other"], skip_object_scope=False
    )
    assert ok is False
    assert err.startswith("TABLE_VALIDATION_ERROR")
