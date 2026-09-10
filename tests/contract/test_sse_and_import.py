import json
from pathlib import Path

from app.utils.sse import sse_status, sse_result, sse_error, sse_done, format_sse
from app.services.stores.skills_folder import import_skills_folder, FORBIDDEN_VECTOR_DB
from app.services.stores.sqlite_vec_provider import SqliteVecProvider
from app.models.schemas import GenerateSQLRequest, GenerateSQLResponse


def test_sse_envelope_shape():
    event = sse_status("routing", "starting", step_id=1)
    assert set(event.keys()) == {"type", "payload", "message"}
    assert event["type"] == "status"
    assert event["payload"]["stage"] == "routing"
    result = sse_result({"sql": "SELECT 1"}, "ok")
    assert result["type"] == "result"
    err = sse_error("boom", {"error_category": "safety"})
    assert err["type"] == "error" and err["payload"]["error_category"] == "safety"
    done = sse_done()
    assert done["type"] == "done"
    raw = format_sse(event)
    assert raw.startswith("data: ")
    parsed = json.loads(raw[len("data: "):].strip())
    assert parsed["type"] == "status"


def test_response_parity_fields():
    resp = GenerateSQLResponse(
        sql="SELECT 1",
        success=True,
        discovery_branch="kb_exact",
        attempts=0,
        token_usage={"total_tokens": 0},
        processing_time_ms=1,
        hallucination_count=0,
        agentic_retry_count=0,
        canonical_question=None,
        error_category=None,
        failure_report=None,
    )
    data = resp.model_dump()
    for field in (
        "sql",
        "explanation",
        "query_type",
        "success",
        "discovery_branch",
        "attempts",
        "token_usage",
        "processing_time_ms",
        "hallucination_count",
        "agentic_retry_count",
        "canonical_question",
        "error_category",
        "failure_report",
    ):
        assert field in data
    req = GenerateSQLRequest(query="x", source_id="abc", top_k=3, semantic_mode=False)
    assert req.source_id == "abc"


def test_import_rejects_vector_index_db(tmp_path):
    src = tmp_path / "northwind"
    src.mkdir()
    (src / FORBIDDEN_VECTOR_DB).write_bytes(b"sqlite")
    dest = tmp_path / "skills"
    provider = SqliteVecProvider(tmp_path / "v.sqlite")
    report = import_skills_folder(src, dest, "src-1", provider)
    assert report.rejected_files
    assert any("vector-index.db" in f for f in report.rejected_files)
