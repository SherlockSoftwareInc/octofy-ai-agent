"""The shared query vocabulary: one stop-word list, one name accessor."""

from app.core.orchestrator import session_context
from app.core.orchestrator.prompts import _first_model_name
from app.models.pipeline import SemanticMeasure, SemanticModel
from app.services import generation_service, schema_scan_service, skills_service, tool_function_invoker
from app.utils.query_vocabulary import (
    STOP_WORDS,
    can_answer,
    model_item_name,
    model_items,
    question_tokens,
    tokenize,
)


def test_every_normalizer_uses_the_one_stop_word_list():
    assert session_context._REPLACEMENT_STOPWORDS is STOP_WORDS
    assert tool_function_invoker.STOP_WORDS is STOP_WORDS
    assert schema_scan_service.STOP_WORDS is STOP_WORDS
    assert skills_service.STOP_WORDS is STOP_WORDS
    assert generation_service.STOP_WORDS is STOP_WORDS


def test_the_shared_list_ignores_query_words_in_every_direction():
    assert {"the", "show", "list", "data", "table", "column"} <= STOP_WORDS
    assert question_tokens("show me the data for table columns") == []
    assert question_tokens("sales amount by product") == ["sales", "amount", "product"]


def test_model_item_name_reads_dicts_and_objects_alike():
    assert model_item_name(SemanticMeasure(name="row_count", expression="COUNT(*)")) == "row_count"
    assert model_item_name({"name": "  row_count  "}) == "row_count"
    assert model_item_name({}) == ""
    assert model_item_name(None) == ""
    assert model_items(None, "measures") == []
    assert model_items({"measures": [{"name": "m"}]}, "measures") == [{"name": "m"}]


def test_prompt_and_gate_read_a_dict_model_the_same_way():
    model = {"measures": [{"name": "sales_amount"}], "dimensions": [{"name": "product_name"}]}
    assert _first_model_name(model, "measures") == "sales_amount"
    assert _first_model_name(model, "dimensions") == "product_name"
    assert can_answer(model, [], question_tokens("sales")) is True


def test_identifier_tokenization_is_unaffected_by_the_shared_stop_words():
    # "table"/"name"/"count" are stop words or structural, yet identifiers keep them:
    # tokenize is what the closest-name hint and the model vocabulary rely on.
    assert tokenize("product_name") == ["product", "name"]
    assert tokenize("order_count") == ["order", "count"]
    assert tokenize("[dbo].[Sales by Category]") == ["sales", "category"]


def test_can_answer_still_reads_object_models():
    model = SemanticModel(
        model_id="sales-model",
        label="Sales",
        measures=[SemanticMeasure(name="sales_amount", expression="SUM(SalesAmount)")],
    )
    assert can_answer(model, [], question_tokens("total sales")) is True
    assert can_answer(model, [], question_tokens("return rate")) is False
