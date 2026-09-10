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


def test_few_shots_meta_sync_and_kb_exact(tmp_path):
    provider = SqliteVecProvider(tmp_path / "kb.sqlite")
    svc = FewShotVectorService(provider, "src-1")
    svc.upsert("How many customers?", "SELECT COUNT(*) FROM dbo.Customers")
    meta = provider.fetch_all("few_shots_meta", "src-1")
    shots = provider.fetch_all("few_shots", "src-1")
    assert len(meta) == 1 and len(shots) == 1
    assert meta[0]["question"] == shots[0]["question"]
    hit = svc.try_get_exact("  how   many CUSTOMERS? ")
    assert hit is not None
    assert hit.is_exact_match
    assert "COUNT(*)" in hit.sql
    assert svc.try_get_exact("unrelated") is None


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
