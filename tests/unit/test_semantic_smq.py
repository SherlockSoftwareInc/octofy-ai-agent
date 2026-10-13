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
from app.core.constants import SemanticRepeatTemperature
from app.core.orchestrator.prompts import build_system_prompt
from app.services.semantic_compiler import (
    SemanticCompiler,
    SemanticCompilationError,
    expression_has_aggregate,
)
from app.utils.query_vocabulary import (
    build_question_tokens,
    can_answer,
    is_significant,
    question_tokens,
    tokenize,
)
from app.services.semantic_smq import (
    SmqShapeError,
    extract_smq_json,
    looks_like_smq,
    parse_smq,
    semantic_payload_fingerprint,
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
    ("bare string metric", '{"metrics":"row_count"}'),
    ("object element", '{"metrics":[{"metric":"row_count"}],"dimensions":[{"dimension":"bctr_number"}]}'),
    ("singular root keys", '{"metric":"row_count","dimension":"bctr_number"}'),
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
        self.messages = []
        self.kwargs = []
        self.token_usage = SimpleNamespace(as_dict=lambda: {})

    def complete(self, messages, **kwargs):
        self.calls += 1
        self.messages.append(messages)
        self.kwargs.append(kwargs)
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
    # The question has to share a token with the fixture model. Otherwise the
    # availability gate correctly leaves semantic mode, and these tests would be
    # exercising the physical path.
    return AgentContext(
        request=AgentRequest(query="row count by transport mode", source_id="src-1"),
        combined_query="row count by transport mode",
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
        '{"metrics":[{"bogus":1}]}',                                  # SMQ key, unrecognized element
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


def test_bare_string_metric_is_compiled_not_executed_as_json(monkeypatch):
    """A bare string is an accepted name list, so it compiles instead of being retried."""
    payload = '{"metrics": "row_count"}'
    result, seen, llm = _run([payload], model=_model(), monkeypatch=monkeypatch)

    assert looks_like_smq(payload) is True
    assert result.success is True
    assert llm.calls == 1
    assert seen and seen[0]["skip_object_scope"] is True
    assert "COUNT(*)" in result.sql


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


# --------------------------------------------------------------------------------------
# §13 — element shape, retry divergence, availability gate
# --------------------------------------------------------------------------------------


def _order_line_model():
    return SemanticModel(
        model_id="vdmprep-order-lines",
        label="vDMPrep Order Lines",
        measures=[
            SemanticMeasure(name="row_count", expression="COUNT(*)"),
            SemanticMeasure(name="order_count", expression="COUNT([dbo].[vdmprep].[ordernumber])"),
            SemanticMeasure(name="model_count", expression="COUNT(DISTINCT [dbo].[vdmprep].[model])"),
        ],
        dimensions=[
            SemanticDimension(name="model", table="dbo.vdmprep", column="model"),
            SemanticDimension(name="ordernumber", table="dbo.vdmprep", column="ordernumber"),
            SemanticDimension(name="linenumber", table="dbo.vdmprep", column="linenumber"),
            SemanticDimension(name="fiscalyear", table="dbo.vdmprep", column="fiscalyear"),
        ],
    )


def _sales_model():
    return SemanticModel(
        model_id="sales-model",
        label="Sales",
        measures=[
            SemanticMeasure(
                name="sales_amount",
                expression="SUM([dbo].[FactInternetSales].[SalesAmount])",
            )
        ],
        dimensions=[
            SemanticDimension(name="product_name", table="dbo.DimProduct", column="EnglishProductName")
        ],
    )


def _question_tokens(question: str):
    return build_question_tokens(question_tokens(question), [])


def test_parse_unwraps_aliases_and_merges_singular_keys():
    smq = parse_smq('{"metrics":[{"measure":"row_count"}],"metric":"ROW_COUNT","dimension":"model"}')
    assert smq is not None
    assert smq.metrics == ["row_count"]
    assert smq.dimensions == ["model"]


def test_parse_keeps_a_present_empty_array_and_rejects_an_absent_one():
    empty = parse_smq('{"metrics":[],"dimensions":[]}')
    assert empty is not None
    assert empty.metrics == []
    assert empty.dimensions == []
    assert parse_smq('{"filters":[{"field":"x","op":"eq","value":"1"}]}') is None
    assert extract_smq_json('{"filters":[{"field":"x"}]}') is None


def test_parse_reports_the_offending_index_for_a_bad_element():
    with pytest.raises(SmqShapeError) as exc:
        parse_smq('{"metrics":["ok",{"bogus":1}]}')
    assert "metrics[1]" in str(exc.value)
    assert "metric" in str(exc.value)


def test_parse_drops_a_filter_without_a_field_and_accepts_operator():
    smq = parse_smq(
        '{"metrics":["row_count"],"filters":[{"nope":1},{"field":"model","operator":"eq","value":"M200"}],'
        '"timeframes":"nonsense"}'
    )
    assert smq is not None
    assert len(smq.filters) == 1
    assert smq.filters[0]["field"] == "model"
    assert smq.filters[0]["op"] == "eq"
    assert smq.timeframes == []


@pytest.mark.parametrize(
    "identifier,expected",
    [
        ("[dbo].[vdmprep].[model]", ["model"]),
        ("dbo.vdmprep.ordernumber", ["ordernumber"]),
        ("`customers`", ["customers"]),
        ("[SalesAmount]", ["sales", "amount"]),
        ("sales_amount", ["sales", "amount"]),
        ("order_count", ["order", "count"]),
        ("product_name", ["product", "name"]),
    ],
)
def test_tokenize_splits_decorations_paths_and_camel_humps(identifier, expected):
    assert tokenize(identifier) == expected


def test_tokenize_keeps_structural_terms():
    assert tokenize("fiscal_year_number_count") == ["fiscal", "year", "number", "count"]
    assert tokenize("product_name") == ["product", "name"]
    assert tokenize(None) == []
    assert tokenize("ab") == []


@pytest.mark.parametrize(
    "token,expected",
    [("count", False), ("name", False), ("sales", True), ("amount", True), ("product", True)],
)
def test_is_significant_distinguishes_structural_from_domain_terms(token, expected):
    assert is_significant(token) is expected


def test_can_answer_for_the_reported_question_against_the_order_line_model_is_false():
    question = "Please give the top selling products by sales amount"
    assert can_answer(_order_line_model(), ["SalesAmount"], _question_tokens(question)) is False


def test_can_answer_when_the_model_exposes_the_metric_is_true():
    question = "Please give the top selling products by sales amount"
    assert can_answer(_sales_model(), ["SalesAmount"], _question_tokens(question)) is True


def test_can_answer_when_only_structural_tokens_overlap_is_true():
    assert can_answer(_order_line_model(), ["RowCount"], _question_tokens("sales amount count")) is True


def test_can_answer_with_an_empty_vocabulary_or_no_signals():
    empty = SemanticModel(model_id="empty", label="Empty")
    assert can_answer(empty, ["SalesAmount"], _question_tokens("top selling products")) is True
    assert can_answer(None, ["SalesAmount"], _question_tokens("anything")) is True
    assert can_answer(_order_line_model(), [], []) is False


def test_unknown_metric_names_the_closest_candidate():
    result = SemanticCompiler().compile_guarded(SmqPayload(metrics=["sale_amount"]), _sales_model())
    assert result.success is False
    assert "UNKNOWN_METRIC" in result.detail
    assert "Unknown metric: sale_amount" in result.detail
    assert "sales_amount" in result.detail


def test_unknown_dimension_names_the_closest_candidate():
    result = SemanticCompiler().compile_guarded(SmqPayload(dimensions=["productname"]), _sales_model())
    assert "UNKNOWN_DIMENSION" in result.detail
    assert "Unknown dimension: productname" in result.detail
    assert "product_name" in result.detail


def test_unknown_metric_with_no_overlap_has_no_suggestion():
    result = SemanticCompiler().compile_guarded(SmqPayload(metrics=["zzz"]), _sales_model())
    assert "Unknown metric: zzz" in result.detail
    assert "Closest valid" not in result.detail


def test_semantic_prompt_states_the_plain_string_contract():
    prompt = build_system_prompt(
        _context(),
        _discovery(),
        semantic=True,
        semantic_models_json=_order_line_model().model_dump_json(),
        semantic_model=_order_line_model(),
    )
    assert "SEMANTIC OUTPUT FORMAT (STRICT)" in prompt
    assert "CRITICAL TYPE RULE" in prompt
    assert "arrays of PLAIN STRINGS" in prompt
    assert "`smq` code block" in prompt
    assert '{"metrics":["row_count"],"dimensions":["model"],"filters":[],"timeframes":[]}' in prompt
    assert "WRONG (rejected)" in prompt
    assert "RIGHT (accepted)" in prompt
    assert "CRITICAL SQL RULES" not in prompt


def test_fingerprint_ignores_whitespace_and_fences_but_not_key_order():
    fenced = '```smq\n{"metrics":["row_count"],"dimensions":["model"]}\n```'
    spaced = '```json\n{"metrics": ["row_count"], "dimensions": ["model"]}\n```'
    assert semantic_payload_fingerprint(fenced)
    assert semantic_payload_fingerprint(fenced) == semantic_payload_fingerprint(spaced)
    reordered = '{"dimensions":["model"],"metrics":["row_count"]}'
    assert semantic_payload_fingerprint(fenced) != semantic_payload_fingerprint(reordered)
    assert semantic_payload_fingerprint('{"metrics":["row_count"]}') != semantic_payload_fingerprint(
        '{"metrics":["order_count"]}'
    )
    assert semantic_payload_fingerprint("SELECT COUNT(*) FROM [dbo].[vdmprep];") == ""


def test_repeated_smq_payload_bumps_temperature_on_the_following_attempt(monkeypatch):
    """The repeat is known only after the second identical payload, so attempt 3 diverges."""
    payload = '{"metrics":["gross_margin"]}'
    result, seen, llm = _run([payload], model=_model(), monkeypatch=monkeypatch)

    assert result.error_category == ErrorCategory.SEMANTIC_COMPILATION
    assert seen == []
    assert "presence_penalty" not in llm.kwargs[0]
    assert "temperature" not in llm.kwargs[0]
    assert "presence_penalty" not in llm.kwargs[1]
    assert llm.kwargs[2]["presence_penalty"] == 0.4
    assert llm.kwargs[2]["temperature"] == SemanticRepeatTemperature
    assert result.agentic_retry_count >= 1


def test_shape_mismatch_feedback_names_the_element_and_the_vocabulary(monkeypatch):
    result, seen, _ = _run(['{"metrics":[123]}'], model=_model(), monkeypatch=monkeypatch)
    history = "\n".join(r.why_it_failed or "" for r in result.failure_report.attempts)
    assert result.error_category == ErrorCategory.SEMANTIC_COMPILATION
    assert seen == []
    assert "SCHEMA MISMATCH" in history
    assert "metrics[0]" in history
    assert "arrays of plain strings" in history
    assert "Valid metrics: row_count, avg_response_minutes." in history


def test_object_shaped_metric_compiles(monkeypatch):
    payload = '{"metrics":[{"metric":"row_count"}]}'
    result, seen, llm = _run([payload], model=_model(), monkeypatch=monkeypatch)
    assert result.success is True
    assert llm.calls == 1
    assert seen and seen[0]["skip_object_scope"] is True


def test_uncovered_question_falls_back_to_physical_sql_and_demotes_grain(monkeypatch):
    seen = _validate_calls(monkeypatch)
    context = AgentContext(
        request=AgentRequest(
            query="Please give the top selling products by sales amount",
            source_id="src-1",
        ),
        combined_query="Please give the top selling products by sales amount",
        dbms_type="SQL Server",
        target_grain="summary_by_product",
    )
    discovery = _discovery()
    discovery.query_analysis.extracted_columns = ["SalesAmount"]
    llm = FakeLlm(["SELECT COUNT(*) AS c FROM dbo.vdmprep;"])
    result = _drive(
        run_attempt_loop(
            context,
            discovery,
            FakeStores(model=_order_line_model()),
            llm,
            lambda *a, **k: None,
            semantic_mode=True,
        )
    )
    prompt = llm.messages[0][0]["content"]
    assert result.success is True
    assert "SEMANTIC OUTPUT FORMAT" not in prompt
    assert "AVAILABLE SCHEMAS" in prompt
    assert "Do not use this text as a table, column, alias, or GROUP BY target." in prompt
    assert seen and seen[0]["skip_object_scope"] is False


def test_covered_question_stays_in_semantic_mode(monkeypatch):
    _validate_calls(monkeypatch)
    context = AgentContext(
        request=AgentRequest(
            query="Please give the top selling products by sales amount",
            source_id="src-1",
        ),
        combined_query="Please give the top selling products by sales amount",
        dbms_type="SQL Server",
        target_grain="summary_by_product",
    )
    discovery = _discovery()
    discovery.query_analysis.extracted_columns = ["SalesAmount"]
    llm = FakeLlm(['{"metrics":["sales_amount"],"dimensions":["product_name"]}'])
    result = _drive(
        run_attempt_loop(
            context,
            discovery,
            FakeStores(model=_sales_model()),
            llm,
            lambda *a, **k: None,
            semantic_mode=True,
        )
    )
    prompt = llm.messages[0][0]["content"]
    assert result.success is True
    assert "SEMANTIC OUTPUT FORMAT (STRICT)" in prompt
    assert "Current target grain: summary_by_product" in prompt
    assert "Do not use this text as a table" not in prompt
