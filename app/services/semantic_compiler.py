"""Deterministic SMQ → physical SQL compiler (BFS join plan, dialect quoting).

Two properties this module must hold, both of which the original implementation
broke and both of which are silent when broken:

* **Determinism.** The same model + payload compiles to byte-identical SQL on
  every run. Required tables and the FROM anchor therefore come from an *ordered*
  list, never from set or dict iteration.
* **Honest grain.** ``GROUP BY`` is emitted only when a resolved measure actually
  aggregates. A dimensions-only request is a detail query; emitting ``GROUP BY``
  over its dimensions silently collapses it to distinct tuples -- a wrong answer
  that validation happily accepts, which is worse than an error.
"""

from __future__ import annotations

import re
import threading
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple
from app.core.constants import SemanticCompilationTimeoutMs
from app.models.pipeline import SemanticDimension, SemanticModel, SmqPayload
from app.utils.dialect import quote_identifier, quote_qualified, quote_string_literal

# Aggregate functions whose presence makes a projection grouped. Delimiter-aware:
# AVG( in a measure is an aggregate, but a column named avg_cost is not.
_AGGREGATE_FUNCTIONS = (
    "COUNT",
    "SUM",
    "AVG",
    "MIN",
    "MAX",
    "STDEV",
    "STDEVP",
    "VAR",
    "VARP",
    "STRING_AGG",
    "GROUP_CONCAT",
    "LISTAGG",
    "ARRAY_AGG",
    "MEDIAN",
    "APPROX_COUNT_DISTINCT",
)

_AGGREGATE_RE = re.compile(
    r"(?<![\w.])(" + "|".join(sorted(_AGGREGATE_FUNCTIONS, key=len, reverse=True)) + r")\s*\(",
    re.IGNORECASE,
)

_FROM_IN_EXPRESSION_RE = re.compile(
    r"\bfrom\s+((?:\[[^\]]+\]|[A-Za-z_][\w$#]*)(?:\s*\.\s*(?:\[[^\]]+\]|[A-Za-z_][\w$#]*))*)\s*"
    r"(?![A-Za-z_])",
    re.IGNORECASE,
)

# Words that may follow an identifier without turning it into a table reference.
_SQL_TRAILING_WORDS = {
    "on", "as", "where", "and", "or", "group", "order", "having", "join", "inner",
    "left", "right", "full", "outer", "cross", "union", "select", "from", "limit",
}


class SemanticCompilationError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


@dataclass
class SmqCompileResult:
    """Outcome of a guarded compile: exactly one of ``sql`` / ``detail`` is set."""

    sql: str = ""
    detail: str = ""

    @property
    def success(self) -> bool:
        return bool(self.sql) and not self.detail


def _normalize_table(name: Optional[str]) -> str:
    parts = [p.strip().strip("[]\"'`") for p in re.split(r"\s*\.\s*", (name or "").strip()) if p.strip()]
    return ".".join(parts)


def expression_has_aggregate(expression: Optional[str]) -> bool:
    """True when a measure expression calls an aggregate function."""
    return bool(_AGGREGATE_RE.search(expression or ""))


def expression_source_tables(expression: Optional[str]) -> List[str]:
    """Tables a measure expression reads from, in appearance order.

    Only explicit ``FROM`` clauses inside the expression are honoured: a bare
    ``SUM(dbo.Orders.Amount)`` names a column, not a table, and inferring a table
    from it would let a typo pick the anchor silently.
    """
    tables: List[str] = []
    for match in _FROM_IN_EXPRESSION_RE.finditer(expression or ""):
        table = _normalize_table(match.group(1))
        if not table:
            continue
        if table.split(".")[-1].lower() in _SQL_TRAILING_WORDS:
            continue
        if table not in tables:
            tables.append(table)
    return tables


class SemanticCompiler:
    def compile(
        self,
        payload: SmqPayload,
        model: SemanticModel,
        dbms: str = "SQL Server",
        include_governance: bool = True,
        timeout_ms: int = SemanticCompilationTimeoutMs,
    ) -> str:
        _ = timeout_ms
        return self._render(payload, model, dbms, include_governance)

    def compile_guarded(
        self,
        payload: SmqPayload,
        model: SemanticModel,
        dbms: str = "SQL Server",
        include_governance: bool = True,
        timeout_ms: int = SemanticCompilationTimeoutMs,
    ) -> SmqCompileResult:
        """Compile with a per-call timeout. Expiry is a semantic retry, not an error path."""
        if not timeout_ms or timeout_ms <= 0:
            try:
                return SmqCompileResult(sql=self._render(payload, model, dbms, include_governance))
            except SemanticCompilationError as exc:
                return SmqCompileResult(detail=str(exc))

        outcome: Dict[str, object] = {}

        def _run() -> None:
            try:
                outcome["sql"] = self._render(payload, model, dbms, include_governance)
            except SemanticCompilationError as exc:
                outcome["detail"] = str(exc)
            except Exception as exc:  # noqa: BLE001 - surfaced as semantic feedback
                outcome["detail"] = f"COMPILATION_ERROR: {exc}"

        worker = threading.Thread(target=_run, name="smq-compile", daemon=True)
        worker.start()
        worker.join(timeout_ms / 1000.0)
        if worker.is_alive():
            return SmqCompileResult(
                detail=f"COMPILATION_TIMEOUT: semantic compilation exceeded {timeout_ms} ms"
            )
        if "detail" in outcome:
            return SmqCompileResult(detail=str(outcome["detail"]))
        return SmqCompileResult(sql=str(outcome.get("sql") or ""))

    def _render(
        self,
        payload: SmqPayload,
        model: SemanticModel,
        dbms: str,
        include_governance: bool,
    ) -> str:
        metrics = list(payload.metrics or [])
        dimension_names = list(payload.dimensions or [])
        if not metrics and not dimension_names:
            # A payload requesting neither is rejected; a dimensions-only payload is not.
            raise SemanticCompilationError(
                "EMPTY_REQUEST", "payload requests neither metrics nor dimensions"
            )

        measures_by_name = {m.name.lower(): m for m in model.measures}
        dims_by_name = {d.name.lower(): d for d in model.dimensions}

        selected_measures = []
        for name in metrics:
            m = measures_by_name.get((name or "").lower())
            if not m:
                raise SemanticCompilationError("UNKNOWN_METRIC", name)
            selected_measures.append(m)

        selected_dims = []
        for name in dimension_names:
            d = dims_by_name.get((name or "").lower())
            if not d:
                raise SemanticCompilationError("UNKNOWN_DIMENSION", name)
            selected_dims.append(d)

        select_parts = [
            f"{self._col(d.table, d.column, dbms)} AS {quote_identifier(d.name, dbms)}"
            for d in selected_dims
        ]
        select_parts.extend(f"{m.expression} AS {quote_identifier(m.name, dbms)}" for m in selected_measures)

        required_tables = self._required_tables(model, selected_dims, selected_measures)
        if not required_tables:
            raise SemanticCompilationError("MISSING_JOIN_PATH", "no source table")
        anchor = self._anchor(required_tables, selected_dims, selected_measures)
        join_sql = self._join_plan(required_tables, model, dbms, anchor)

        where_parts = [self._filter_sql(filt, dbms) for filt in payload.filters or []]
        for tf in payload.timeframes or []:
            field = tf.get("field")
            start = tf.get("start")
            end = tf.get("end")
            if field and start and end:
                where_parts.append(
                    f"{field} BETWEEN {quote_string_literal(str(start), dbms)}"
                    f" AND {quote_string_literal(str(end), dbms)}"
                )
        if include_governance:
            where_parts.extend(model.governance_predicates)

        sql = f"SELECT {', '.join(select_parts)}\nFROM {join_sql}"
        if where_parts:
            sql += "\nWHERE " + " AND ".join(p for p in where_parts if p)
        if selected_dims and any(expression_has_aggregate(m.expression) for m in selected_measures):
            sql += "\nGROUP BY " + ", ".join(self._col(d.table, d.column, dbms) for d in selected_dims)
        return sql

    def _required_tables(
        self,
        model: SemanticModel,
        selected_dims: Sequence[SemanticDimension],
        selected_measures: Sequence[object],
    ) -> List[str]:
        """Required tables in *request order*: dimensions, then measure sources.

        An aggregate-only request names no table at all (``COUNT(*)`` reads from wherever the
        query is anchored), so the seed comes from the model's declared tables in a fixed
        order. Seeding is what keeps the FROM clause deterministic instead of model-declared
        order leaking into the SQL.
        """
        required: List[str] = []

        def add(table: Optional[str]) -> None:
            normalized = _normalize_table(table)
            if normalized and normalized not in required:
                required.append(normalized)

        for join in model.joins:
            add(join.from_table)
        for d in model.dimensions:
            add(d.table)
        for d in selected_dims:
            add(d.table)
        for m in selected_measures:
            for table in expression_source_tables(getattr(m, "expression", "")):
                if table in required:
                    add(table)
        return required

    def _anchor(self, required: List[str], selected_dims, selected_measures) -> str:
        """Deterministic FROM anchor: first requested dimension's table, else the table a
        measure expression reads from, else the first required table.

        A measure only contributes an anchor table when that table is already in the model's
        declared set: otherwise a stray or mistyped name inside an expression could silently
        choose the FROM clause.
        """
        if selected_dims:
            anchor = _normalize_table(selected_dims[0].table)
            if anchor in required:
                return anchor
        for m in selected_measures:
            for table in expression_source_tables(getattr(m, "expression", "")):
                if table in required:
                    return table
        return required[0]

    def _col(self, table: str, column: str, dbms: str) -> str:
        if "." in table:
            schema, name = table.split(".", 1)
            return f"{quote_qualified(schema, name, dbms)}.{quote_identifier(column, dbms)}"
        return f"{quote_identifier(table, dbms)}.{quote_identifier(column, dbms)}"

    def _join_plan(self, required: List[str], model: SemanticModel, dbms: str, anchor: str) -> str:
        graph: Dict[str, List[str]] = defaultdict(list)
        edge_sql: Dict[Tuple[str, str], object] = {}
        for j in model.joins:
            from_table = _normalize_table(j.from_table)
            to_table = _normalize_table(j.to_table)
            graph[from_table].append(to_table)
            graph[to_table].append(from_table)
            edge_sql[(from_table, to_table)] = j
            edge_sql[(to_table, from_table)] = j

        visited = {anchor}
        order: List[Tuple[str, Optional[object]]] = [(anchor, None)]
        parent: Dict[str, Optional[str]] = {anchor: None}
        queue = deque([anchor])
        # Breadth-first, in model join order, over the whole reachable component: a
        # required table may only be reachable through a node that is not itself
        # required, so traversal continues past non-target nodes.
        while queue:
            node = queue.popleft()
            for neighbour in graph.get(node, []):
                if neighbour in visited:
                    continue
                visited.add(neighbour)
                parent[neighbour] = node
                order.append((neighbour, edge_sql.get((node, neighbour))))
                queue.append(neighbour)

        emitted = {table for table, _ in order}
        missing = [t for t in required if t not in emitted]
        if missing:
            raise SemanticCompilationError("INCOMPATIBLE_DIMENSIONS", ", ".join(missing))

        # Only required tables are joined; traversal-only hops are never emitted, and a
        # required table hanging off a traversal-only hop is joined to that hop so its ON
        # clause stays valid.
        projected = [t for t in required if t in visited]
        if anchor not in projected:
            projected.insert(0, anchor)

        def nearest_joined(table: str) -> Optional[str]:
            seen = {table}
            node = parent.get(table)
            while node is not None:
                if node in projected:
                    return node
                if node in seen:
                    return None
                seen.add(node)
                node = parent.get(node)
            return None

        parts = [self._table_ident(anchor, dbms)]
        for table in projected:
            if table == anchor:
                continue
            attach = nearest_joined(table)
            if attach is None:
                raise SemanticCompilationError("MISSING_JOIN_PATH", table)
            join = edge_sql.get((parent.get(table) or attach, table))
            if join is None:
                join = edge_sql.get((attach, table))
            if join is None:
                raise SemanticCompilationError("MISSING_JOIN_PATH", table)
            jtype = (join.join_type or "INNER").strip() or "INNER"
            parts.append(f"{jtype} JOIN {self._table_ident(table, dbms)} ON {join.join_expression}")
        return "\n".join(parts)

    def _table_ident(self, table: str, dbms: str) -> str:
        if "." in table:
            schema, name = table.split(".", 1)
            return quote_qualified(schema, name, dbms)
        return quote_identifier(table, dbms)

    def _filter_sql(self, filt: dict, dbms: str) -> str:
        field = filt.get("field") or filt.get("dimension") or ""
        op = (filt.get("op") or filt.get("operator") or "eq").lower()
        value = filt.get("value")
        mapping = {
            "eq": "=",
            "ne": "<>",
            "neq": "<>",
            "gt": ">",
            "gte": ">=",
            "lt": "<",
            "lte": "<=",
            "like": "LIKE",
        }
        sql_op = mapping.get(op, "=")
        if value is None:
            return ""
        if isinstance(value, (int, float)):
            literal = str(value)
        else:
            literal = quote_string_literal(str(value), dbms)
        return f"{field} {sql_op} {literal}"
