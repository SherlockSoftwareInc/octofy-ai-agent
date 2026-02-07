# Value Index Relationship Tracing Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** When value index search matches a lookup/dimension table (e.g., Categories), automatically discover and include related fact/data tables (e.g., Products, Order Details) by tracing FK references embedded in schema descriptions.

**Architecture:** Build an in-memory relationship graph parsed from `Reference:` patterns in Milvus schema descriptions. After every value index hit, traverse this graph up to 2 hops (capped at 3 related tables per hit) to pull in associated data tables. Apply this enhancement to both discovery paths: `discovery_service.py` (Prong 3) and `generation_service.py` (Branch 1.2 dual-prong).

**Tech Stack:** Python, Pydantic, regex, pytest (unit tests with mocks)

---

## Background & Key Files

| File | Role | Lines |
|------|------|-------|
| `app/models/schemas.py` | Pydantic models (`TableSchema`, `RankedTable`, etc.) | 672 |
| `app/services/discovery_service.py` | Three-pronged discovery (Prong 3 = value index) | 724 |
| `app/services/generation_service.py` | SQL generation pipeline (Branch 1.2 = dual-prong) | ~1700 |
| `app/services/vector_store.py` | Milvus CRUD, `get_all_schemas()`, `search_values()` | ~1468 |
| `app/services/admin_service.py` | Schema sync, `build_table_markdown_description()` | - |
| `tests/conftest.py` | Test config (adds project root to sys.path) | 8 |

### How FK References Are Stored Today

FK data is embedded as free text in the `description` field of each `TableSchema` (stored in Milvus `schema_index`). Two formats exist:

1. **Bracket format** (from `admin_service.py` sync): `Reference: [dbo].[Products].[ProductID]`
2. **Dot format** (from AI enhancement): `Reference: Categories.CategoryID`

Example from `dbo.Products.md`:
```
| 4 | `CategoryID` | INTEGER | Identifier of the product category. Reference: Categories.CategoryID |
```

There is **no structured FK field** on `TableSchema` or `ColumnInfo` today. The relationship graph must be parsed from these description strings.

### Current Value Index Flow

**Discovery Service (`discovery_service.py:92-125`):**
1. `perform_value_index_search(query)` calls `vector_store.search_values(query)`
2. Each hit becomes a `RankedTable(score=8, matched_by=['value_index'])`
3. These are merged with skills results in `rerank_candidates()` (weights: skills=10, value=8, kb=5)
4. No relationship tracing occurs

**Generation Service (`generation_service.py:1639-1663`):**
1. LLM extracts filter values, searches each via `vector_store.search_values(val)`
2. Results feed into `rerank_and_select_tables()` (weights: value=10, fewshot=5, schema=2)
3. No relationship tracing occurs

---

## Task 1: Create Relationship Graph Module

**Files:**
- Create: `app/services/relationship_graph.py`
- Test: `tests/test_relationship_graph.py`

### Step 1: Write the failing tests

Create `tests/test_relationship_graph.py`:

```python
"""Tests for FK relationship graph built from schema descriptions."""
import pytest
from app.models.schemas import TableSchema
from app.services.relationship_graph import RelationshipGraph


# ── Fixtures ──────────────────────────────────────────────

def _make_schema(schema: str, table: str, description: str) -> TableSchema:
    return TableSchema(
        schema_name=schema,
        table_name=table,
        description=description,
        columns=[]
    )


SCHEMAS = [
    # Lookup table – no outbound FK references
    _make_schema("dbo", "Categories", (
        "# **Table:** `[dbo].[Categories]`\n"
        "> Product categories.\n"
        "| 1 | `CategoryID` | Primary key |\n"
        "| 2 | `CategoryName` | Name |\n"
    )),
    # Bridge table – references Categories and Suppliers
    _make_schema("dbo", "Products", (
        "# **Table:** `[dbo].[Products]`\n"
        "> Products for sale.\n"
        "| 3 | `SupplierID` | Reference: [dbo].[Suppliers].[SupplierID] |\n"
        "| 4 | `CategoryID` | Reference: Categories.CategoryID |\n"
    )),
    # Fact table – references Orders and Products
    _make_schema("dbo", "Order Details", (
        "# **Table:** `[dbo].[Order Details]`\n"
        "> Line items.\n"
        "| 1 | `OrderID` | Reference: [dbo].[Orders].[OrderID] |\n"
        "| 2 | `ProductID` | Reference: [dbo].[Products].[ProductID] |\n"
    )),
    # Another table referencing Products
    _make_schema("dbo", "Orders", (
        "# **Table:** `[dbo].[Orders]`\n"
        "> Customer orders.\n"
        "| 3 | `CustomerID` | Reference: [dbo].[Customers].[CustomerID] |\n"
    )),
    # Standalone lookup – no FK refs to or from
    _make_schema("dbo", "Suppliers", (
        "# **Table:** `[dbo].[Suppliers]`\n"
        "> Supplier info.\n"
        "| 1 | `SupplierID` | Primary key |\n"
    )),
    # Standalone lookup referenced by Orders
    _make_schema("dbo", "Customers", (
        "# **Table:** `[dbo].[Customers]`\n"
        "> Customer info.\n"
        "| 1 | `CustomerID` | Primary key |\n"
    )),
]


# ── Test: parse_references ────────────────────────────────

class TestParseReferences:
    def test_bracket_format(self):
        """Parse 'Reference: [dbo].[Products].[ProductID]' format."""
        graph = RelationshipGraph(SCHEMAS)
        refs = graph._parse_references(SCHEMAS[2].description)  # Order Details
        assert ("dbo", "Orders") in refs
        assert ("dbo", "Products") in refs

    def test_dot_format(self):
        """Parse 'Reference: Categories.CategoryID' format (no brackets)."""
        graph = RelationshipGraph(SCHEMAS)
        refs = graph._parse_references(SCHEMAS[1].description)  # Products
        assert ("dbo", "Categories") in refs
        assert ("dbo", "Suppliers") in refs

    def test_no_references(self):
        """Tables with no Reference: patterns return empty set."""
        graph = RelationshipGraph(SCHEMAS)
        refs = graph._parse_references(SCHEMAS[0].description)  # Categories
        assert refs == set()


# ── Test: referencing_tables (reverse lookup) ─────────────

class TestReferencingTables:
    def test_categories_referenced_by_products(self):
        """Categories is referenced by Products (via CategoryID FK)."""
        graph = RelationshipGraph(SCHEMAS)
        result = graph.get_referencing_tables("dbo", "Categories")
        names = {(t.schema_name, t.table_name) for t in result}
        assert ("dbo", "Products") in names

    def test_products_referenced_by_order_details(self):
        """Products is referenced by Order Details (via ProductID FK)."""
        graph = RelationshipGraph(SCHEMAS)
        result = graph.get_referencing_tables("dbo", "Products")
        names = {(t.schema_name, t.table_name) for t in result}
        assert ("dbo", "Order Details") in names

    def test_standalone_table_has_no_referencers(self):
        """Customers is only referenced by Orders."""
        graph = RelationshipGraph(SCHEMAS)
        result = graph.get_referencing_tables("dbo", "Customers")
        names = {(t.schema_name, t.table_name) for t in result}
        assert ("dbo", "Orders") in names

    def test_unreferenced_table(self):
        """Order Details is not referenced by anyone in our test set."""
        graph = RelationshipGraph(SCHEMAS)
        result = graph.get_referencing_tables("dbo", "Order Details")
        assert result == []


# ── Test: referenced_tables (forward lookup) ──────────────

class TestReferencedTables:
    def test_products_references_categories_and_suppliers(self):
        """Products references Categories and Suppliers."""
        graph = RelationshipGraph(SCHEMAS)
        result = graph.get_referenced_tables("dbo", "Products")
        names = {(t.schema_name, t.table_name) for t in result}
        assert ("dbo", "Categories") in names
        assert ("dbo", "Suppliers") in names

    def test_categories_references_nothing(self):
        """Categories has no outbound FK references."""
        graph = RelationshipGraph(SCHEMAS)
        result = graph.get_referenced_tables("dbo", "Categories")
        assert result == []


# ── Test: multi-hop tracing ───────────────────────────────

class TestTraceRelated:
    def test_1_hop_from_categories(self):
        """1 hop from Categories -> finds Products."""
        graph = RelationshipGraph(SCHEMAS)
        result = graph.trace_related_tables("dbo", "Categories", max_hops=1, max_tables=10)
        names = {(t.schema_name, t.table_name) for t in result}
        assert ("dbo", "Products") in names
        assert ("dbo", "Order Details") not in names  # 2 hops away

    def test_2_hop_from_categories(self):
        """2 hops from Categories -> finds Products AND Order Details."""
        graph = RelationshipGraph(SCHEMAS)
        result = graph.trace_related_tables("dbo", "Categories", max_hops=2, max_tables=10)
        names = {(t.schema_name, t.table_name) for t in result}
        assert ("dbo", "Products") in names
        assert ("dbo", "Order Details") in names

    def test_max_tables_cap(self):
        """trace_related_tables respects max_tables limit."""
        graph = RelationshipGraph(SCHEMAS)
        result = graph.trace_related_tables("dbo", "Categories", max_hops=2, max_tables=1)
        assert len(result) <= 1

    def test_does_not_include_self(self):
        """Traced results should not include the source table itself."""
        graph = RelationshipGraph(SCHEMAS)
        result = graph.trace_related_tables("dbo", "Categories", max_hops=2, max_tables=10)
        names = {(t.schema_name, t.table_name) for t in result}
        assert ("dbo", "Categories") not in names

    def test_nonexistent_table(self):
        """Querying a table not in the graph returns empty list."""
        graph = RelationshipGraph(SCHEMAS)
        result = graph.trace_related_tables("dbo", "NonExistent", max_hops=2, max_tables=10)
        assert result == []
```

### Step 2: Run tests to verify they fail

Run: `pytest tests/test_relationship_graph.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.relationship_graph'`

### Step 3: Implement `relationship_graph.py`

Create `app/services/relationship_graph.py`:

```python
"""
Relationship Graph: FK-based table relationship discovery.

Parses 'Reference:' patterns from schema descriptions to build a
bidirectional adjacency graph of table relationships. Supports multi-hop
traversal to discover related data tables from lookup table matches.

Usage:
    graph = get_relationship_graph()  # module-level singleton
    related = graph.trace_related_tables("dbo", "Categories", max_hops=2, max_tables=3)
"""
import re
import logging
from typing import Dict, List, Set, Tuple, Optional
from collections import defaultdict

from app.models.schemas import TableSchema

logger = logging.getLogger(__name__)

# Regex patterns for FK references in Markdown descriptions
# Pattern 1: Reference: [schema].[table].[column]
_BRACKET_REF_PATTERN = re.compile(
    r'Reference:\s*\[([^\]]+)\]\.\[([^\]]+)\]\.\[([^\]]+)\]'
)
# Pattern 2: Reference: Table.Column  (no brackets, assumes dbo schema)
_DOT_REF_PATTERN = re.compile(
    r'Reference:\s*([A-Za-z_]\w*)\.([A-Za-z_]\w*)'
)

# Type alias for a normalized (schema, table) key
TableKey = Tuple[str, str]


class RelationshipGraph:
    """
    Bidirectional FK relationship graph built from schema descriptions.
    
    Edges:
        forward[A] = {B, C}  means A has FK columns referencing B and C
        reverse[B] = {A}     means B is referenced by A
    """

    def __init__(self, schemas: List[TableSchema]):
        # Map of normalized key -> TableSchema
        self._schemas: Dict[TableKey, TableSchema] = {}
        # Forward edges: table -> set of tables it references
        self._forward: Dict[TableKey, Set[TableKey]] = defaultdict(set)
        # Reverse edges: table -> set of tables that reference it
        self._reverse: Dict[TableKey, Set[TableKey]] = defaultdict(set)

        self._build(schemas)

    @staticmethod
    def _normalize_key(schema: str, table: str) -> TableKey:
        return (schema.lower().strip(), table.lower().strip())

    def _parse_references(self, description: Optional[str]) -> Set[TableKey]:
        """Extract all (schema, table) pairs referenced in a description string."""
        if not description:
            return set()

        refs: Set[TableKey] = set()

        # Pattern 1: bracket format  Reference: [dbo].[Orders].[OrderID]
        for match in _BRACKET_REF_PATTERN.finditer(description):
            schema, table, _col = match.groups()
            refs.add(self._normalize_key(schema, table))

        # Pattern 2: dot format  Reference: Categories.CategoryID
        # Only match if not already captured by bracket pattern
        for match in _DOT_REF_PATTERN.finditer(description):
            full_match_start = match.start()
            # Skip if this is part of a bracket reference (already captured)
            preceding = description[max(0, full_match_start - 5):full_match_start]
            if '].[' in preceding or '].[ ' in preceding:
                continue
            table, _col = match.groups()
            # Dot format has no schema qualifier -> assume dbo
            refs.add(self._normalize_key("dbo", table))

        return refs

    def _build(self, schemas: List[TableSchema]) -> None:
        """Parse all schemas and build the adjacency lists."""
        # Index schemas
        for s in schemas:
            key = self._normalize_key(s.schema_name, s.table_name)
            self._schemas[key] = s

        # Build edges
        for s in schemas:
            source_key = self._normalize_key(s.schema_name, s.table_name)
            refs = self._parse_references(s.description)
            for ref_key in refs:
                self._forward[source_key].add(ref_key)
                self._reverse[ref_key].add(source_key)

        logger.info(
            f"[RelationshipGraph] Built graph: {len(self._schemas)} tables, "
            f"{sum(len(v) for v in self._forward.values())} forward edges"
        )

    # ── Public API ────────────────────────────────────────

    def get_referencing_tables(self, schema: str, table: str) -> List[TableSchema]:
        """Get tables that have FK columns pointing TO this table (reverse lookup)."""
        key = self._normalize_key(schema, table)
        result = []
        for ref_key in self._reverse.get(key, set()):
            if ref_key in self._schemas:
                result.append(self._schemas[ref_key])
        return result

    def get_referenced_tables(self, schema: str, table: str) -> List[TableSchema]:
        """Get tables that this table's FK columns point TO (forward lookup)."""
        key = self._normalize_key(schema, table)
        result = []
        for ref_key in self._forward.get(key, set()):
            if ref_key in self._schemas:
                result.append(self._schemas[ref_key])
        return result

    def trace_related_tables(
        self,
        schema: str,
        table: str,
        max_hops: int = 2,
        max_tables: int = 3
    ) -> List[TableSchema]:
        """
        BFS traversal from a source table, following both forward and reverse
        FK edges, up to max_hops depth. Returns at most max_tables related
        tables (excluding the source itself).
        """
        start = self._normalize_key(schema, table)
        if start not in self._schemas:
            return []

        visited: Set[TableKey] = {start}
        queue: List[Tuple[TableKey, int]] = [(start, 0)]
        result: List[TableSchema] = []

        while queue and len(result) < max_tables:
            current, depth = queue.pop(0)
            if depth >= max_hops:
                continue

            # Traverse both directions
            neighbors: Set[TableKey] = set()
            neighbors.update(self._reverse.get(current, set()))
            neighbors.update(self._forward.get(current, set()))

            for neighbor in neighbors:
                if neighbor in visited:
                    continue
                visited.add(neighbor)
                if neighbor in self._schemas:
                    result.append(self._schemas[neighbor])
                    if len(result) >= max_tables:
                        break
                queue.append((neighbor, depth + 1))

        return result


# ── Module-level Singleton ────────────────────────────────

_graph_instance: Optional[RelationshipGraph] = None


def get_relationship_graph(force_rebuild: bool = False) -> RelationshipGraph:
    """
    Return the cached RelationshipGraph singleton.
    Lazily builds the graph on first call by fetching all schemas from Milvus.
    Pass force_rebuild=True to refresh (e.g., after schema sync).
    """
    global _graph_instance
    if _graph_instance is None or force_rebuild:
        from app.services.vector_store import get_vector_store
        vector_store = get_vector_store()
        all_schemas = vector_store.get_all_schemas()
        _graph_instance = RelationshipGraph(all_schemas)
        logger.info(f"[RelationshipGraph] Singleton initialized with {len(all_schemas)} schemas")
    return _graph_instance


def invalidate_relationship_graph() -> None:
    """Clear the cached graph (call after schema modifications)."""
    global _graph_instance
    _graph_instance = None
    logger.info("[RelationshipGraph] Cache invalidated")
```

### Step 4: Run tests to verify they pass

Run: `pytest tests/test_relationship_graph.py -v`
Expected: All 12 tests PASS

### Step 5: Commit

```bash
git add app/services/relationship_graph.py tests/test_relationship_graph.py
git commit -m "feat: add FK relationship graph with bidirectional traversal and 2-hop tracing"
```

---

## Task 2: Integrate into Discovery Service (Prong 3)

**Files:**
- Modify: `app/services/discovery_service.py` (lines 92-125, the `perform_value_index_search` function)
- Test: `tests/test_value_index_relationship_tracing.py`

### Step 1: Write the failing tests

Create `tests/test_value_index_relationship_tracing.py`:

```python
"""Tests for value index + relationship tracing integration in discovery_service."""
import pytest
from unittest.mock import patch, MagicMock
from app.models.schemas import TableSchema, RankedTable
from app.services.relationship_graph import RelationshipGraph


# ── Fixtures ──────────────────────────────────────────────

def _schema(schema: str, table: str, desc: str = "") -> TableSchema:
    return TableSchema(schema_name=schema, table_name=table, description=desc, columns=[])


# Simulate a small Northwind-like graph
_TEST_SCHEMAS = [
    _schema("dbo", "Categories", "| 1 | `CategoryID` | Primary key |"),
    _schema("dbo", "Products", "| 4 | `CategoryID` | Reference: Categories.CategoryID |"),
    _schema("dbo", "Order Details", "| 2 | `ProductID` | Reference: [dbo].[Products].[ProductID] |"),
    _schema("dbo", "Orders", "| 1 | `OrderID` | Primary key |"),
    _schema("dbo", "Suppliers", "| 1 | `SupplierID` | Primary key |"),
]

_TEST_GRAPH = RelationshipGraph(_TEST_SCHEMAS)


def _mock_value_result(schema: str, table: str) -> dict:
    """Create a mock value_index search result."""
    return {
        "entity": {
            "schema_name": schema,
            "table_name": table,
            "column_name": "CategoryName",
            "value": "Beverages"
        }
    }


# ── Tests ─────────────────────────────────────────────────

class TestPerformValueIndexSearchWithRelationships:
    """Test that perform_value_index_search includes related tables."""

    @patch("app.services.discovery_service.get_relationship_graph")
    @patch("app.services.discovery_service.get_vector_store")
    def test_adds_related_tables_for_lookup_hit(self, mock_vs, mock_graph):
        """When value index matches Categories, Products and Order Details should be added."""
        from app.services.discovery_service import perform_value_index_search

        # Mock value search returns Categories
        mock_store = MagicMock()
        mock_store.search_values.return_value = [_mock_value_result("dbo", "Categories")]
        mock_vs.return_value = mock_store

        # Mock relationship graph
        mock_graph.return_value = _TEST_GRAPH

        result = perform_value_index_search("Beverages sales")

        # Should contain Categories (direct match) + Products + Order Details (traced)
        table_names = {(t.schema_name, t.table_name) for t in result}
        assert ("dbo", "Categories") in table_names, "Direct match should be present"
        assert ("dbo", "Products") in table_names, "1-hop related table should be present"
        assert ("dbo", "Order Details") in table_names, "2-hop related table should be present"

    @patch("app.services.discovery_service.get_relationship_graph")
    @patch("app.services.discovery_service.get_vector_store")
    def test_related_tables_have_relationship_traced_marker(self, mock_vs, mock_graph):
        """Related tables should have 'relationship_traced' in matched_by."""
        from app.services.discovery_service import perform_value_index_search

        mock_store = MagicMock()
        mock_store.search_values.return_value = [_mock_value_result("dbo", "Categories")]
        mock_vs.return_value = mock_store
        mock_graph.return_value = _TEST_GRAPH

        result = perform_value_index_search("Beverages sales")

        direct = [t for t in result if t.table_name == "Categories"]
        traced = [t for t in result if t.table_name != "Categories"]

        assert all("value_index" in t.matched_by for t in direct)
        assert all("relationship_traced" in t.matched_by for t in traced)

    @patch("app.services.discovery_service.get_relationship_graph")
    @patch("app.services.discovery_service.get_vector_store")
    def test_related_tables_score_equals_direct(self, mock_vs, mock_graph):
        """Related tables should receive score=8 (same as direct value index match)."""
        from app.services.discovery_service import perform_value_index_search

        mock_store = MagicMock()
        mock_store.search_values.return_value = [_mock_value_result("dbo", "Categories")]
        mock_vs.return_value = mock_store
        mock_graph.return_value = _TEST_GRAPH

        result = perform_value_index_search("Beverages sales")

        for t in result:
            assert t.score == 8, f"{t.table_name} should have score=8, got {t.score}"

    @patch("app.services.discovery_service.get_relationship_graph")
    @patch("app.services.discovery_service.get_vector_store")
    def test_max_related_tables_cap(self, mock_vs, mock_graph):
        """Should not add more than MAX_RELATED_TABLES_PER_HIT related tables per hit."""
        from app.services.discovery_service import perform_value_index_search

        mock_store = MagicMock()
        mock_store.search_values.return_value = [_mock_value_result("dbo", "Categories")]
        mock_vs.return_value = mock_store
        mock_graph.return_value = _TEST_GRAPH

        result = perform_value_index_search("Beverages sales")

        # Direct hit = 1, related <= 3 (cap)
        assert len(result) <= 1 + 3, f"Should not exceed cap: got {len(result)} tables"

    @patch("app.services.discovery_service.get_relationship_graph")
    @patch("app.services.discovery_service.get_vector_store")
    def test_no_duplicates(self, mock_vs, mock_graph):
        """If two value hits resolve to the same table, no duplicates in result."""
        from app.services.discovery_service import perform_value_index_search

        mock_store = MagicMock()
        mock_store.search_values.return_value = [
            _mock_value_result("dbo", "Categories"),
            _mock_value_result("dbo", "Categories"),  # duplicate
        ]
        mock_vs.return_value = mock_store
        mock_graph.return_value = _TEST_GRAPH

        result = perform_value_index_search("Beverages Condiments")

        keys = [(t.schema_name.lower(), t.table_name.lower()) for t in result]
        assert len(keys) == len(set(keys)), f"Duplicate tables found: {keys}"

    @patch("app.services.discovery_service.get_relationship_graph")
    @patch("app.services.discovery_service.get_vector_store")
    def test_no_value_hits_returns_empty(self, mock_vs, mock_graph):
        """If value index returns nothing, result should be empty."""
        from app.services.discovery_service import perform_value_index_search

        mock_store = MagicMock()
        mock_store.search_values.return_value = []
        mock_vs.return_value = mock_store
        mock_graph.return_value = _TEST_GRAPH

        result = perform_value_index_search("unknown query")
        assert result == []


class TestRerankCandidatesWithTracedTables:
    """Test that rerank_candidates properly scores relationship_traced tables."""

    def test_traced_tables_get_value_index_weight(self):
        """Tables with matched_by=['relationship_traced'] should get value_index weight (8)."""
        from app.services.discovery_service import rerank_candidates

        value_tables = [
            RankedTable(schema_name="dbo", table_name="Categories", score=8, matched_by=["value_index"]),
            RankedTable(schema_name="dbo", table_name="Products", score=8, matched_by=["relationship_traced"]),
        ]

        result = rerank_candidates([], value_tables, [])

        products = [t for t in result if t.table_name == "Products"][0]
        assert products.score == 8, f"Traced table should get score 8, got {products.score}"
        assert "relationship_traced" in products.matched_by or "value_index" in products.matched_by
```

### Step 2: Run tests to verify they fail

Run: `pytest tests/test_value_index_relationship_tracing.py -v`
Expected: FAIL (tests reference `get_relationship_graph` import that doesn't exist in discovery_service yet)

### Step 3: Modify `perform_value_index_search` in `discovery_service.py`

Open `app/services/discovery_service.py`.

**At the top of file (around line 20-25, near the existing constants)**, add:

```python
# Relationship tracing constants
MAX_RELATED_TABLES_PER_HIT = 3  # Cap related tables added per value index hit
RELATIONSHIP_TRACE_HOPS = 2      # Max FK hops to traverse
```

**Add import** (near the existing imports at top of file):

```python
from app.services.relationship_graph import get_relationship_graph
```

**Replace the `perform_value_index_search` function** (lines 92-125) with:

```python
def perform_value_index_search(query: str, top_k: int = 5) -> List[RankedTable]:
    """
    Stage 2B: Value Index Search (Entity Mapping) with Relationship Tracing
    
    After finding direct value matches, traces FK relationships to discover
    related data/fact tables (up to RELATIONSHIP_TRACE_HOPS hops, capped at
    MAX_RELATED_TABLES_PER_HIT per direct hit).
    
    Args:
        query: User's natural language query
        top_k: Number of top results to return from value index
        
    Returns:
        List of RankedTable objects (direct matches + traced related tables)
    """
    vector_store = get_vector_store()
    
    # Phase 1: Direct value index search
    value_results = vector_store.search_values(query, top_k=top_k)
    
    ranked_tables = []
    seen_keys = set()  # (schema_lower, table_lower) for deduplication
    
    for result in value_results:
        if isinstance(result, dict):
            entity = result.get('entity', {})
            schema_name = entity.get('schema_name', 'dbo')
            table_name = entity.get('table_name', '')
            
            if not table_name:
                continue
                
            key = (schema_name.lower(), table_name.lower())
            if key in seen_keys:
                continue
            seen_keys.add(key)
            
            ranked_tables.append(RankedTable(
                schema_name=schema_name,
                table_name=table_name,
                score=8,  # Value index score
                matched_by=['value_index'],
                data_source=None,
                data_group=None
            ))
    
    if not ranked_tables:
        return ranked_tables
    
    # Phase 2: Relationship tracing for each direct hit
    try:
        graph = get_relationship_graph()
        
        for direct_hit in list(ranked_tables):  # iterate over copy
            related = graph.trace_related_tables(
                direct_hit.schema_name,
                direct_hit.table_name,
                max_hops=RELATIONSHIP_TRACE_HOPS,
                max_tables=MAX_RELATED_TABLES_PER_HIT
            )
            
            for rel_schema in related:
                rel_key = (rel_schema.schema_name.lower(), rel_schema.table_name.lower())
                if rel_key in seen_keys:
                    continue
                seen_keys.add(rel_key)
                
                ranked_tables.append(RankedTable(
                    schema_name=rel_schema.schema_name,
                    table_name=rel_schema.table_name,
                    score=8,  # Same weight as direct value match
                    matched_by=['relationship_traced'],
                    data_source=None,
                    data_group=None
                ))
                
                logging.info(
                    f"[Value Index] Relationship traced: "
                    f"{direct_hit.schema_name}.{direct_hit.table_name} -> "
                    f"{rel_schema.schema_name}.{rel_schema.table_name}"
                )
    except Exception as e:
        logging.warning(f"[Value Index] Relationship tracing failed (non-fatal): {e}")
    
    return ranked_tables
```

### Step 4: Run tests to verify they pass

Run: `pytest tests/test_value_index_relationship_tracing.py -v`
Expected: All 7 tests PASS

### Step 5: Commit

```bash
git add app/services/discovery_service.py tests/test_value_index_relationship_tracing.py
git commit -m "feat: add relationship tracing to discovery service value index search"
```

---

## Task 3: Integrate into Generation Service (Branch 1.2 Dual-Prong)

**Files:**
- Modify: `app/services/generation_service.py` (lines 1639-1667 dual-prong, lines ~1607 gap-fill)
- Test: `tests/test_generation_relationship_tracing.py`

### Step 1: Write the failing tests

Create `tests/test_generation_relationship_tracing.py`:

```python
"""Tests for relationship tracing in generation_service's dual-prong path."""
import pytest
from unittest.mock import patch, MagicMock
from app.models.schemas import TableSchema
from app.services.relationship_graph import RelationshipGraph


def _schema(schema: str, table: str, desc: str = "") -> TableSchema:
    return TableSchema(schema_name=schema, table_name=table, description=desc, columns=[])


_TEST_SCHEMAS = [
    _schema("dbo", "Categories", "| 1 | `CategoryID` | Primary key |"),
    _schema("dbo", "Products", "| 4 | `CategoryID` | Reference: Categories.CategoryID |"),
    _schema("dbo", "Order Details", "| 2 | `ProductID` | Reference: [dbo].[Products].[ProductID] |"),
]

_TEST_GRAPH = RelationshipGraph(_TEST_SCHEMAS)


class TestExpandValueTablesWithRelationships:
    """Test the new expand_value_tables_with_relationships helper."""

    @patch("app.services.generation_service.get_relationship_graph")
    def test_expands_lookup_tables(self, mock_graph):
        from app.services.generation_service import expand_value_tables_with_relationships

        mock_graph.return_value = _TEST_GRAPH

        input_tables = ["dbo.Categories"]
        result = expand_value_tables_with_relationships(input_tables)

        assert "dbo.Categories" in result
        # Should find Products (1 hop) and Order Details (2 hops)
        result_lower = [t.lower() for t in result]
        assert any("products" in t for t in result_lower)
        assert any("order details" in t for t in result_lower)

    @patch("app.services.generation_service.get_relationship_graph")
    def test_deduplicates(self, mock_graph):
        from app.services.generation_service import expand_value_tables_with_relationships

        mock_graph.return_value = _TEST_GRAPH

        input_tables = ["dbo.Categories", "dbo.Categories"]
        result = expand_value_tables_with_relationships(input_tables)

        normalized = [t.lower().replace('[', '').replace(']', '') for t in result]
        assert len(normalized) == len(set(normalized))

    @patch("app.services.generation_service.get_relationship_graph")
    def test_empty_input(self, mock_graph):
        from app.services.generation_service import expand_value_tables_with_relationships

        mock_graph.return_value = _TEST_GRAPH

        result = expand_value_tables_with_relationships([])
        assert result == []

    @patch("app.services.generation_service.get_relationship_graph")
    def test_graceful_on_graph_error(self, mock_graph):
        from app.services.generation_service import expand_value_tables_with_relationships

        mock_graph.side_effect = Exception("Milvus down")

        input_tables = ["dbo.Categories"]
        result = expand_value_tables_with_relationships(input_tables)
        # Should return original tables without crashing
        assert result == ["dbo.Categories"]
```

### Step 2: Run tests to verify they fail

Run: `pytest tests/test_generation_relationship_tracing.py -v`
Expected: FAIL with `ImportError: cannot import name 'expand_value_tables_with_relationships'`

### Step 3: Add helper and integrate into `generation_service.py`

**Add import** at top of `app/services/generation_service.py` (near existing imports):

```python
from app.services.relationship_graph import get_relationship_graph
```

**Add the helper function** after `expand_context_with_neighbors` (around line 137, before `extract_entities`):

```python
def expand_value_tables_with_relationships(
    value_tables: List[str],
    max_hops: int = 2,
    max_per_hit: int = 3
) -> List[str]:
    """
    Expand value index table list by tracing FK relationships.
    
    For each table in value_tables, follows FK edges up to max_hops
    to discover related data tables (capped at max_per_hit per source).
    
    Args:
        value_tables: List of "schema.table" strings from value index search
        max_hops: Maximum FK hops to traverse
        max_per_hit: Maximum related tables to add per source table
        
    Returns:
        Expanded list of "schema.table" strings (originals + discovered)
    """
    if not value_tables:
        return value_tables
    
    try:
        graph = get_relationship_graph()
    except Exception as e:
        logging.warning(f"[Relationship] Graph unavailable (non-fatal): {e}")
        return value_tables
    
    seen = set()
    result = []
    
    for table_str in value_tables:
        # Normalize and parse
        clean = table_str.replace('[', '').replace(']', '').strip()
        if '.' in clean:
            parts = clean.split('.', 1)
            schema_name, table_name = parts[0], parts[1]
        else:
            schema_name, table_name = 'dbo', clean
        
        key = (schema_name.lower(), table_name.lower())
        if key not in seen:
            seen.add(key)
            result.append(table_str)  # keep original formatting
        
        # Trace relationships
        related = graph.trace_related_tables(schema_name, table_name, max_hops=max_hops, max_tables=max_per_hit)
        for rel in related:
            rel_key = (rel.schema_name.lower(), rel.table_name.lower())
            if rel_key not in seen:
                seen.add(rel_key)
                result.append(f"{rel.schema_name}.{rel.table_name}")
                logging.info(f"[Relationship] Expanded: {schema_name}.{table_name} -> {rel.schema_name}.{rel.table_name}")
    
    return result
```

**Modify the dual-prong value section** (around lines 1639-1651). After `value_tables` is populated (both `if filter_values` and `else` branches), and before the `# 2. Few-Shot Discovery` comment, add:

```python
            # 1b. Expand value tables with FK relationship tracing
            if value_tables:
                original_count = len(value_tables)
                value_tables = expand_value_tables_with_relationships(value_tables)
                if len(value_tables) > original_count:
                    logging.info(
                        f"Discovery: Relationship tracing expanded value tables "
                        f"from {original_count} to {len(value_tables)}"
                    )
```

**Also modify Branch 1.1.2 gap fill** (around line 1607). Before the `all_tables = list(set(...))` line, add:

```python
                # Expand supplementary value tables with FK relationships
                if supplementary_value_tables:
                    supplementary_value_tables = expand_value_tables_with_relationships(supplementary_value_tables)
```

### Step 4: Run tests to verify they pass

Run: `pytest tests/test_generation_relationship_tracing.py -v`
Expected: All 4 tests PASS

### Step 5: Commit

```bash
git add app/services/generation_service.py tests/test_generation_relationship_tracing.py
git commit -m "feat: add relationship tracing to generation service dual-prong and gap-fill paths"
```

---

## Task 4: Invalidate Graph Cache on Schema Sync

**Files:**
- Modify: `app/services/admin_service.py` (find the schema upsert/sync functions)

### Step 1: Add import to `admin_service.py`

At the top of `app/services/admin_service.py`, add:

```python
from app.services.relationship_graph import invalidate_relationship_graph
```

### Step 2: Add invalidation call after schema sync

Find every function that calls `vector_store.upsert_schema()` or similar (likely `sync_specific_table` or bulk sync). After each successful upsert, add:

```python
invalidate_relationship_graph()
```

This ensures the relationship graph is rebuilt with fresh data on the next query after any schema change.

### Step 3: Commit

```bash
git add app/services/admin_service.py
git commit -m "feat: invalidate relationship graph cache after schema sync"
```

---

## Task 5: Run Full Test Suite & Integration Verification

### Step 1: Run all existing tests

Run: `pytest tests/ -v --tb=short`
Expected: All existing tests still pass (no regressions)

### Step 2: Run the new tests specifically

Run: `pytest tests/test_relationship_graph.py tests/test_value_index_relationship_tracing.py tests/test_generation_relationship_tracing.py -v`
Expected: All 23 new tests pass

### Step 3: Commit (if any fixes were needed)

```bash
git commit -m "fix: address test regressions from relationship tracing integration"
```

---

## Summary of Changes

| File | Change Type | Description |
|------|-------------|-------------|
| `app/services/relationship_graph.py` | **NEW** | FK relationship graph with bidirectional BFS traversal |
| `app/services/discovery_service.py` | MODIFY | Added relationship tracing to `perform_value_index_search()`, 2 new constants |
| `app/services/generation_service.py` | MODIFY | Added `expand_value_tables_with_relationships()` helper, integrated into Branch 1.2 and Branch 1.1.2 |
| `app/services/admin_service.py` | MODIFY | Cache invalidation on schema sync |
| `tests/test_relationship_graph.py` | **NEW** | 12 unit tests for graph construction, parsing, traversal |
| `tests/test_value_index_relationship_tracing.py` | **NEW** | 7 tests for discovery service integration |
| `tests/test_generation_relationship_tracing.py` | **NEW** | 4 tests for generation service integration |

### Configuration Constants

| Constant | Value | Location |
|----------|-------|----------|
| `RELATIONSHIP_TRACE_HOPS` | 2 | `discovery_service.py` |
| `MAX_RELATED_TABLES_PER_HIT` | 3 | `discovery_service.py` |

### Validation Example

Query: "2025年 饮料类 (Beverages) 的总销售额是多少？"

1. Value Index matches `Categories.CategoryName = 'Beverages'` -> direct hit: `dbo.Categories`
2. Relationship graph traces (hop 1): `dbo.Products` references `Categories.CategoryID` -> added
3. Relationship graph traces (hop 2): `dbo.Order Details` references `Products.ProductID` -> added
4. Final context: `Categories` (filter) + `Products` (bridge) + `Order Details` (calculation: `SUM(UnitPrice * Quantity)`)
