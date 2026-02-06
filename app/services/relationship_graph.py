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
from collections import defaultdict, deque

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
        self._schemas: Dict[TableKey, TableSchema] = {}
        self._forward: Dict[TableKey, Set[TableKey]] = defaultdict(set)
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

        # Track bracket match positions to avoid double-matching with dot pattern
        bracket_spans = set()
        for match in _BRACKET_REF_PATTERN.finditer(description):
            schema, table, _col = match.groups()
            refs.add(self._normalize_key(schema, table))
            bracket_spans.add((match.start(), match.end()))

        for match in _DOT_REF_PATTERN.finditer(description):
            # Skip if this match overlaps with any bracket match
            overlaps = any(
                not (match.end() <= bs or match.start() >= be)
                for bs, be in bracket_spans
            )
            if overlaps:
                continue
            table, _col = match.groups()
            refs.add(self._normalize_key("dbo", table))

        return refs

    def _build(self, schemas: List[TableSchema]) -> None:
        """Parse all schemas and build the adjacency lists."""
        for s in schemas:
            key = self._normalize_key(s.schema_name, s.table_name)
            self._schemas[key] = s

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
        queue: deque[Tuple[TableKey, int]] = deque([(start, 0)])
        result: List[TableSchema] = []

        while queue and len(result) < max_tables:
            current, depth = queue.popleft()
            if depth >= max_hops:
                continue

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
                    # Only traverse through tables we have schemas for
                    queue.append((neighbor, depth + 1))

        return result


# Module-level Singleton
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
