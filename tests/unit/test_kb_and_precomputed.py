from app.services.fewshot_vector_service import FewShotVectorService
from app.services.stores.precomputed_store import PrecomputedQueryStore
from app.services.stores.sqlite_vec_provider import SqliteVecProvider
from app.core.orchestrator.discovery_engine import DiscoveryEngine
from app.models.pipeline import QueryAnalysis
from app.core.branch_taxonomy import DiscoveryBranch
from types import SimpleNamespace


class DummyStores:
    def __init__(self, provider, source_id):
        self.fewshots = FewShotVectorService(provider, source_id)
        self.vector_search = SimpleNamespace(
            try_get_precomputed_exact=lambda q: PrecomputedQueryStore(provider, source_id) and None
        )


def _seed_few_shot(provider, source_id, key, question, sql, created_at="2020-01-01T00:00:00+00:00"):
    provider.upsert(
        "few_shots",
        [{
            "data_source_id": source_id,
            "key": key,
            "question": question,
            "sql": sql,
            "created_at_utc": created_at,
            "vector": "",
        }],
    )


def test_try_get_exact_reads_authoritative_few_shots_table_with_whitespace_and_case_differences(tmp_path):
    provider = SqliteVecProvider(tmp_path / "kb.sqlite")
    _seed_few_shot(provider, "src-1", "k1", "  Find   Top Selling Products  ", "SELECT 1;")
    svc = FewShotVectorService(provider, "src-1")
    hit = svc.try_get_exact("find top selling products")
    assert hit is not None
    assert hit.is_exact_match
    assert hit.sql == "SELECT 1;"
    assert svc.try_get_exact("unrelated") is None


def test_try_get_exact_ignores_legacy_meta_table_and_drops_it(tmp_path):
    provider = SqliteVecProvider(tmp_path / "kb.sqlite")
    _seed_few_shot(provider, "src-1", "k1", "Find Top Selling Products", "SELECT 1;")
    provider.execute(
        "CREATE TABLE few_shots_meta ("
        " data_source_id TEXT NOT NULL,"
        " key TEXT,"
        " question TEXT NOT NULL,"
        " sql TEXT NOT NULL,"
        " created_at TEXT NOT NULL,"
        " PRIMARY KEY (data_source_id, key))"
    )
    provider.execute(
        "INSERT INTO few_shots_meta (data_source_id, key, question, sql, created_at) VALUES (?, ?, ?, ?, ?)",
        ("src-1", "k1", "Find Top Selling Products", "SELECT 999;", "t"),
    )
    assert provider.has_collection("few_shots_meta")
    svc = FewShotVectorService(provider, "src-1")
    hit = svc.try_get_exact("find top selling products")
    assert hit is not None
    assert hit.sql == "SELECT 1;"
    assert not provider.has_collection("few_shots_meta")


def test_try_get_exact_with_missing_few_shots_table_returns_null(tmp_path):
    provider = SqliteVecProvider(tmp_path / "empty.sqlite")
    provider.execute("DROP TABLE few_shots")
    svc = FewShotVectorService(provider, "src-1")
    assert svc.try_get_exact("find top selling products") is None


def test_replace_without_embedding_updates_scalars_in_place(tmp_path, monkeypatch):
    provider = SqliteVecProvider(tmp_path / "kb.sqlite")
    created = "2020-01-01T00:00:00+00:00"
    _seed_few_shot(provider, "src-1", "keep-me", "old q", "SELECT 0;", created)
    monkeypatch.setattr("app.services.fewshot_vector_service.try_embed_text", lambda *a, **k: None)
    svc = FewShotVectorService(provider, "src-1")
    ok = svc.replace("keep-me", "new q", "SELECT 2;")
    assert ok is False
    rows = provider.fetch_all("few_shots", "src-1")
    assert len(rows) == 1
    assert rows[0]["key"] == "keep-me"
    assert rows[0]["question"] == "new q"
    assert rows[0]["sql"] == "SELECT 2;"
    assert rows[0]["created_at_utc"] == created


def test_precomputed_exact_approved_and_modified_only(tmp_path):
    provider = SqliteVecProvider(tmp_path / "pc.sqlite")
    store = PrecomputedQueryStore(provider, "src-1")
    from app.services.vector_search_service import VectorSearchService

    store.upsert("approved q", "SELECT 1", "g", status="Approved")
    store.upsert("modified q", "SELECT 2", "g", status="Modified")
    store.upsert("pending q", "SELECT 3", "g", status="Pending")
    vs = VectorSearchService(provider, "src-1")
    assert vs.try_get_precomputed_exact("approved q").sql == "SELECT 1"
    assert vs.try_get_precomputed_exact("modified q").sql == "SELECT 2"
    assert vs.try_get_precomputed_exact("pending q") is None


def test_resolve_data_source_folder_by_source_id(tmp_path):
    from app.services.stores.skills_folder import resolve_data_source_folder

    folder = tmp_path / "northwind"
    folder.mkdir()
    (folder / "_data-source.md").write_text(
        "---\nsource_id: 1b2b4f87-5ef6-4389-976e-cee2ff56464f\n---\n# Northwind\n",
        encoding="utf-8",
    )
    found = resolve_data_source_folder("1b2b4f87-5ef6-4389-976e-cee2ff56464f", tmp_path)
    assert found == folder
    try:
        resolve_data_source_folder("missing-id", tmp_path)
        assert False, "expected FileNotFoundError"
    except FileNotFoundError:
        pass
