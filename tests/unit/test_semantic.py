from app.services.semantic_compiler import SemanticCompiler, SemanticCompilationError
from app.models.pipeline import SemanticDimension, SemanticJoin, SemanticMeasure, SemanticModel, SmqPayload
from app.services.semantic_extraction_service import SemanticModelExtractionService


def _model():
    return SemanticModel(
        model_id="m1",
        label="Sales",
        measures=[SemanticMeasure(name="revenue", expression="SUM(dbo.Orders.Amount)", description="rev")],
        dimensions=[
            SemanticDimension(name="customer", column="CustomerID", table="dbo.Orders", description="c"),
            SemanticDimension(name="region", column="Region", table="dbo.Customers", description="r"),
        ],
        joins=[
            SemanticJoin(
                from_table="dbo.Orders",
                to_table="dbo.Customers",
                join_expression="dbo.Orders.CustomerID = dbo.Customers.CustomerID",
                join_type="INNER",
            )
        ],
    )


def test_compile_success():
    sql = SemanticCompiler().compile(
        SmqPayload(metrics=["revenue"], dimensions=["customer"]),
        _model(),
    )
    assert "SUM(dbo.Orders.Amount)" in sql
    assert "GROUP BY" in sql


def test_unknown_metric():
    try:
        SemanticCompiler().compile(SmqPayload(metrics=["nope"]), _model())
        assert False, "expected error"
    except SemanticCompilationError as exc:
        assert exc.code == "UNKNOWN_METRIC"


def test_incompatible_dimensions():
    model = _model()
    model.joins = []
    try:
        SemanticCompiler().compile(
            SmqPayload(metrics=["revenue"], dimensions=["customer", "region"]),
            model,
        )
        assert False, "expected error"
    except SemanticCompilationError as exc:
        assert exc.code in {"INCOMPATIBLE_DIMENSIONS", "MISSING_JOIN_PATH"}


def test_extraction_guarantees_measure():
    class DummyLlm:
        def complete_json(self, messages, **kwargs):
            return {"measures": [], "dimensions": [], "joins": []}

    model = SemanticModelExtractionService(llm=DummyLlm()).extract("schema", label="X")
    assert len(model.measures) >= 1
    assert model.measures[0].name == "row_count"
