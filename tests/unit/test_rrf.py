from app.models.pipeline import ScoredObject
from app.utils.rrf import rrf_merge, rrf_score
from app.core.constants import RrfK, RRF_WEIGHT_DATA_GROUP, RRF_WEIGHT_SCHEMA_VECTOR


def _obj(name, schema="dbo"):
    return ScoredObject(schema_name=schema, object_name=name, score=1.0)


def test_rrf_formula():
    assert rrf_score(0, 1.0) == 1.0 / (RrfK + 1)
    assert rrf_score(0, RRF_WEIGHT_DATA_GROUP) == RRF_WEIGHT_DATA_GROUP / (RrfK + 1)


def test_rrf_prefers_higher_weight_list():
    schema = [_obj("A"), _obj("B")]
    groups = [_obj("B"), _obj("C")]
    merged = rrf_merge({"schema_vector": schema, "data_group": groups}, max_results=8)
    names = [o.object_name for o in merged]
    assert "B" in names
    # B appears in both lists so should rank first
    assert names[0] == "B"
