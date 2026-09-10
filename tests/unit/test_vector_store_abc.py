import inspect

from app.services.vector_store import MilvusVectorStore, NullVectorStore


def test_milvus_vector_store_is_concrete():
    assert not inspect.isabstract(MilvusVectorStore)
    assert MilvusVectorStore.__abstractmethods__ == frozenset()
    assert "delete_fewshot_item" in MilvusVectorStore.__dict__
    assert callable(MilvusVectorStore.delete_fewshot_item)


def test_null_vector_store_is_concrete():
    assert not inspect.isabstract(NullVectorStore)
    store = NullVectorStore()
    assert store.delete_fewshot_item(1) is None
