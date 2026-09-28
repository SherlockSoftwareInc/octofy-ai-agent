"""Contract: attempt-loop status events stream while the loop is running.

Regression guard for the gap where the orchestrator called ``run_attempt_loop``
with a no-op progress callback (``lambda stage, msg, **kw: None``): the attempt /
critic / db-validation / recovery status events built inside the loop never
reached the SSE stream, so clients saw one closing "Completed in N attempt(s)"
status only after the whole loop had finished (and never saw the attempt number).
"""

import inspect

from app.core.branch_taxonomy import PipelineStage
from app.core.constants import MaxRetries
from app.core.orchestrator import builtin_sql_generator as bsg
from app.core.orchestrator.attempts import run_attempt_loop
from app.core.orchestrator.discovery_engine import DiscoveryEngine
from app.models.pipeline import BuiltInGenerateResult, DiscoveryResult, ScoredObject, TokenUsage
from app.models.schemas import GenerateSQLRequest
from app.services.stores.bundle import build_source_stores
from app.services.stores.sqlite_vec_provider import SqliteVecProvider


class FakeLlm:
    """Returns one valid-looking script per attempt."""

    def __init__(self, sql: str = "SELECT 1 AS n"):
        self.token_usage = TokenUsage()
        self._sql = sql
        self.calls = 0

    def complete(self, messages, **kwargs):
        self.calls += 1
        return f"```sql\n{self._sql}\n```"

    def complete_json(self, messages, **kwargs):
        return {}


def _pipeline(tmp_path, monkeypatch):
    stores = build_source_stores("s1", provider=SqliteVecProvider(tmp_path / "progress.sqlite"))
    monkeypatch.setattr(
        DiscoveryEngine,
        "discover",
        lambda self, query, analysis, **kwargs: DiscoveryResult(
            objects=[ScoredObject(schema_name="dbo", object_name="Customers", score=0.9)],
            branch="dual_prong",
        ),
    )
    request = GenerateSQLRequest(query="count customers", top_k=5)
    return request, stores, FakeLlm()


def _stage(event):
    return (event.get("payload") or {}).get("stage")


def test_attempt_loop_is_a_generator():
    """The loop must be drivable step by step, otherwise nothing can stream."""
    assert inspect.isgeneratorfunction(run_attempt_loop)


def test_attempt_status_is_streamed_before_the_result(tmp_path, monkeypatch):
    request, stores, llm = _pipeline(tmp_path, monkeypatch)

    events = list(bsg.generate_sql_builtin(request, stores, llm=llm))

    attempt_events = [
        (i, e) for i, e in enumerate(events)
        if e.get("type") == "status" and _stage(e) == PipelineStage.ATTEMPT
    ]
    result_index = next(i for i, e in enumerate(events) if e.get("type") == "result")

    assert attempt_events, "the attempt loop must emit attempt status events"
    first_index, first_event = attempt_events[0]
    assert first_index < result_index, "attempt progress must stream before the result"
    assert first_event["payload"].get("attempt") == 1
    assert first_event["payload"].get("max_attempts") == MaxRetries
    assert first_event["message"].startswith("Generation attempt 1/")


def test_every_loop_event_is_forwarded_in_order(tmp_path, monkeypatch):
    """Whatever the loop yields must reach the stream, ahead of the result."""
    request, stores, llm = _pipeline(tmp_path, monkeypatch)

    def fake_loop(context, discovery, stores_, llm_, emit, **kwargs):
        yield emit(PipelineStage.ATTEMPT, "Generation attempt 1/5", attempt=1, max_attempts=5)
        yield emit(PipelineStage.CRITIC, "LLM critic")
        yield emit(PipelineStage.DB_VALIDATION, "Database validation")
        return BuiltInGenerateResult(success=False, sql="", message="fake loop", attempts=1)

    monkeypatch.setattr(bsg, "run_attempt_loop", fake_loop)

    events = list(bsg.generate_sql_builtin(request, stores, llm=llm))

    stages = [_stage(e) for e in events if e.get("type") == "status"]
    assert stages.index(PipelineStage.ATTEMPT) < stages.index(PipelineStage.CRITIC)
    assert stages.index(PipelineStage.CRITIC) < stages.index(PipelineStage.DB_VALIDATION)

    result = next(e for e in events if e.get("type") == "result")
    assert result["payload"]["attempts"] == 1
    assert result["message"] == "fake loop"
    assert any(e.get("type") == "done" for e in events)
