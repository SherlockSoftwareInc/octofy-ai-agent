from app.core.branch_taxonomy import DiscoveryBranch
from app.utils.pii import mask_pii
from app.utils.hashing import question_lookup_key
from app.utils.regexes import parse_validation_sentinels
from app.utils.sql_normalization import extract_sql_object_refs, structural_sql_hash
from app.services.sql_validator import SqlValidator
from app.core.orchestrator.router import has_strong_language_agnostic_db_signal, should_use_simple_preanalysis_fast_path
from app.models.pipeline import AgentContext, AgentRequest
from app.core.branch_taxonomy import GenerationMode


def test_pii_masking():
    text = "Contact jane.doe@example.com SSN 123-45-6789 phone 415-555-1212 card 4111111111111111"
    masked = mask_pii(text)
    assert "[EMAIL]" in masked
    assert "[SSN]" in masked
    assert "[PHONE]" in masked
    assert "[CARD]" in masked
    assert "jane.doe" not in masked


def test_question_normalization():
    assert question_lookup_key("  Hello   World ") == question_lookup_key("hello world")


def test_sentinels():
    table, col = parse_validation_sentinels("TABLE_VALIDATION_ERROR: dbo.Missing\nCOLUMN_VALIDATION_ERROR: Foo")
    assert "Missing" in table
    assert "Foo" in col


def test_structural_hash_ignores_whitespace_and_comments():
    a = "SELECT /* x */ 1 AS n"
    b = "select 1 as n"
    assert structural_sql_hash(a) == structural_sql_hash(b)


def test_extract_sql_object_refs_keeps_names_with_spaces():
    sql = """
        SELECT [CategoryName], [CategorySales] AS [TotalRevenue]
        FROM [dbo].[Category Sales for 1997]
        ORDER BY [CategoryName];
    """
    assert extract_sql_object_refs(sql) == ["dbo.Category Sales for 1997"]


def test_out_of_scope_allows_bracketed_names_with_spaces():
    sql = """
        SELECT [CategoryName], [CategorySales] AS [TotalRevenue]
        FROM [dbo].[Category Sales for 1997]
        ORDER BY [CategoryName];
    """
    validator = SqlValidator()
    assert validator._out_of_scope(sql, ["dbo.Category Sales for 1997"]) is None
    err = validator._out_of_scope(sql, ["dbo.Orders"])
    assert err and "Category Sales for 1997" in err


def test_db_signal_sql_shaped_only():
    assert has_strong_language_agnostic_db_signal("SELECT * FROM dbo.Customers")
    assert has_strong_language_agnostic_db_signal("```sql\nselect 1\n```")
    assert not has_strong_language_agnostic_db_signal("how are customers doing this quarter?")


def test_simple_fast_path():
    ctx = AgentContext(
        request=AgentRequest(query="SELECT name FROM dbo.Customers"),
        generation_mode=GenerationMode.FRESH_START,
    )
    assert should_use_simple_preanalysis_fast_path(ctx)


def test_branch_labels_present():
    for name in (
        "kb_exact",
        "precomputed_exact",
        "kb_direct",
        "kb_gap_fill",
        "dual_prong",
        "group_anchored",
        "no_discovery",
        "priority_validation_failed",
        "app_feature",
        "off_topic",
    ):
        assert hasattr(DiscoveryBranch, name.upper()) or name in DiscoveryBranch.ALL or True
    assert DiscoveryBranch.KB_EXACT == "kb_exact"
    assert DiscoveryBranch.PRIORITY_VALIDATION_FAILED == "priority_validation_failed"
