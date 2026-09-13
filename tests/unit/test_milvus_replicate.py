from app.services.stores.milvus_replicate import (
    DUMMY_VECTOR,
    DUMMY_VECTOR_FIELD,
    milvus_schema_field_names,
    needs_dummy_vector,
    prepare_milvus_row,
    replicate_sqlite_to_milvus,
    resolve_data_source_id,
    row_pk,
    uses_native_vector,
)
from app.services.stores.schema_contracts import COLLECTIONS, COLLECTION_BY_NAME, PARTITION_FIELD
from app.services.stores.sqlite_vec_provider import SqliteVecProvider
from app.services.stores.score_utils import dumps_vector


class _FakeMilvus:
    def __init__(self):
        self.upserts = []

    def upsert(self, collection, records):
        self.upserts.append((collection, list(records)))


def test_every_milvus_table_includes_data_source_id():
    for spec in COLLECTIONS:
        names = milvus_schema_field_names(spec)
        assert names[0] == "pk"
        assert names[1] == PARTITION_FIELD
        assert names.count(PARTITION_FIELD) == 1
        if needs_dummy_vector(spec):
            assert DUMMY_VECTOR_FIELD in names
        else:
            assert DUMMY_VECTOR_FIELD not in names


def test_prepare_requires_data_source_id():
    spec = COLLECTION_BY_NAME["contribution_library"]
    assert prepare_milvus_row(spec, {"key": "1", "question": "q", "sql_query": "SELECT 1", "knowledge_type": "sql_query", "status": "pending"}) is None
    from_alias = prepare_milvus_row(
        spec,
        {"source_guid": "src-9", "key": "1", "question": "q", "sql_query": "SELECT 1", "knowledge_type": "sql_query", "status": "pending"},
    )
    assert from_alias is not None
    assert from_alias["data_source_id"] == "src-9"
    assert from_alias[DUMMY_VECTOR_FIELD] == DUMMY_VECTOR
    assert resolve_data_source_id({"source_id": "abc"}) == "abc"


def test_replicate_writes_data_source_id_on_every_row(tmp_path):
    sqlite = SqliteVecProvider(tmp_path / "v.sqlite")
    sqlite.upsert(
        "contribution_library",
        [{"data_source_id": "A", "key": "1", "question": "q", "sql_query": "SELECT 1", "knowledge_type": "sql_query", "status": "pending"}],
    )
    milvus = _FakeMilvus()
    replicate_sqlite_to_milvus(sqlite, milvus)
    rows = next(recs for name, recs in milvus.upserts if name == "contribution_library")
    assert all(row.get("data_source_id") == "A" for row in rows)


def test_native_vector_only_for_single_float_field():
    assert uses_native_vector(COLLECTION_BY_NAME["schemas"]) is True
    assert uses_native_vector(COLLECTION_BY_NAME["data_group_metadata"]) is False
    assert uses_native_vector(COLLECTION_BY_NAME["data_group_vectors_vec0"]) is False
    assert uses_native_vector(COLLECTION_BY_NAME["data_group_vectors_cache"]) is False


def test_prepare_schema_row_converts_json_vector():
    spec = COLLECTION_BY_NAME["schemas"]
    vec = [0.1, 0.2, 0.3]
    row = prepare_milvus_row(
        spec,
        {
            "data_source_id": "src-1",
            "key": "k1",
            "schema_name": "dbo",
            "object_name": "Customers",
            "object_type": "Table",
            "entity_type": "Table",
            "column_name": "",
            "description": "customers",
            "vector": dumps_vector(vec),
        },
    )
    assert row is not None
    assert row["vector"] == vec
    assert row["pk"] == "src-1|k1"
    assert row["data_source_id"] == "src-1"


def test_prepare_skips_missing_native_vector():
    spec = COLLECTION_BY_NAME["schemas"]
    assert prepare_milvus_row(spec, {"data_source_id": "s", "key": "k", "vector": ""}) is None


def test_prepare_multi_vector_as_json_strings():
    spec = COLLECTION_BY_NAME["data_group_vectors_vec0"]
    vec = [1.0, 2.0]
    row = prepare_milvus_row(
        spec,
        {
            "data_source_id": "src-1",
            "rowid": 9,
            "semantic_vector": vec,
            "functional_vector": dumps_vector(vec),
            "object_vector": dumps_vector(vec),
        },
    )
    assert row is not None
    assert row["semantic_vector"] == dumps_vector(vec)
    assert row["functional_vector"] == dumps_vector(vec)
    assert "rowid" not in row
    assert row["pk"] == "9"


def test_scalar_pk_from_unique_with_source():
    spec = COLLECTION_BY_NAME["semantic_joins"]
    row = {
        "data_source_id": "src",
        "model_id": "m",
        "from_table": "a",
        "to_table": "b",
        "join_expression": "a.id=b.id",
        "join_type": "inner",
    }
    assert row_pk(spec, row) == "src|m|a|b|a.id=b.id"


def test_replicate_copies_every_populated_table(tmp_path):
    sqlite = SqliteVecProvider(tmp_path / "v.sqlite")
    sqlite.upsert(
        "contribution_library",
        [{"data_source_id": "A", "key": "1", "question": "q", "sql_query": "SELECT 1", "knowledge_type": "sql_query", "status": "pending"}],
    )
    sqlite.upsert(
        "data_group_metadata",
        [{
            "data_source_id": "A",
            "group_id": "g1",
            "group_name": "Sales",
            "description": "d",
            "keywords_json": "[]",
            "members_json": "[]",
            "updated_at_utc": "t",
        }],
    )
    milvus = _FakeMilvus()
    counts = replicate_sqlite_to_milvus(sqlite, milvus)
    assert counts["contribution_library"] == 1
    assert counts["data_group_metadata"] == 1
    names = {name for name, _ in milvus.upserts}
    assert "contribution_library" in names
    assert "data_group_metadata" in names
    contrib = next(rows for name, rows in milvus.upserts if name == "contribution_library")
    assert contrib[0]["question"] == "q"
    assert contrib[0]["pk"] == "A|1"


def test_sqlite_fetch_all_rows_and_source_ids(tmp_path):
    provider = SqliteVecProvider(tmp_path / "v.sqlite")
    provider.upsert(
        "schemas",
        [
            {
                "data_source_id": "A",
                "key": "1",
                "schema_name": "dbo",
                "object_name": "T",
                "object_type": "Table",
                "entity_type": "Table",
                "column_name": "",
                "description": "d",
                "vector": "[0.1]",
            },
            {
                "data_source_id": "B",
                "key": "1",
                "schema_name": "dbo",
                "object_name": "U",
                "object_type": "Table",
                "entity_type": "Table",
                "column_name": "",
                "description": "d",
                "vector": "[0.2]",
            },
        ],
    )
    rows = provider.fetch_all_rows("schemas")
    assert len(rows) == 2
    assert set(provider.list_data_source_ids()) == {"A", "B"}
