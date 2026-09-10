from app.core.orchestrator.discovery_engine import _stringify_terms
from app.utils.hashing import as_text_token, discovery_cache_key


def test_as_text_token_reads_entity_dicts():
    assert as_text_token("Revenue") == "Revenue"
    assert as_text_token({"name": "product category"}) == "product category"
    assert as_text_token({"entity": "Customers"}) == "Customers"
    assert as_text_token({"value": "1997"}) == "1997"
    assert as_text_token(None) == ""


def test_discovery_cache_key_accepts_entity_dicts():
    key = discovery_cache_key(
        [{"name": "category"}, "revenue", {"entity": "1997"}],
        "simple",
        8,
        [{"column": "CategoryName"}, "ProductName"],
    )
    assert "category" in key
    assert "revenue" in key
    assert "1997" in key
    assert "cols:" in key


def test_stringify_terms_dedupes_dict_and_string_entities():
    terms = _stringify_terms(
        [
            {"name": "product category"},
            "Product Category",
            {"entity": "revenue"},
            "",
        ]
    )
    assert terms == ["product category", "revenue"]
