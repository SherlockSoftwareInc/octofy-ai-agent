from concurrent.futures import ThreadPoolExecutor

from app.services.fewshot_vector_service import FewShotVectorService
from app.services.stores.sqlite_vec_provider import SqliteVecProvider


def test_concurrent_sources_do_not_leak(tmp_path):
    provider = SqliteVecProvider(tmp_path / "iso.sqlite")

    def write(source, sql):
        FewShotVectorService(provider, source).upsert("same question", sql)
        return FewShotVectorService(provider, source).try_get_exact("same question").sql

    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(write, "source-a", "SELECT 'A'")
        b = pool.submit(write, "source-b", "SELECT 'B'")
        sql_a = a.result()
        sql_b = b.result()
    assert sql_a == "SELECT 'A'"
    assert sql_b == "SELECT 'B'"
