"""Deterministic SMQ → physical SQL compiler (BFS join plan, dialect quoting)."""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Dict, List, Optional, Set, Tuple

from app.core.constants import SemanticCompilationTimeoutMs
from app.models.pipeline import SemanticModel, SmqPayload
from app.utils.dialect import quote_identifier, quote_qualified, quote_string_literal


class SemanticCompilationError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


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
        measures_by_name = {m.name.lower(): m for m in model.measures}
        dims_by_name = {d.name.lower(): d for d in model.dimensions}

        selected_measures = []
        for name in payload.metrics:
            m = measures_by_name.get(name.lower())
            if not m:
                raise SemanticCompilationError("UNKNOWN_METRIC", name)
            selected_measures.append(m)
        if not selected_measures and model.measures:
            selected_measures = [model.measures[0]]

        selected_dims = []
        for name in payload.dimensions:
            d = dims_by_name.get(name.lower())
            if not d:
                raise SemanticCompilationError("UNKNOWN_DIMENSION", name)
            selected_dims.append(d)

        required_tables: List[str] = []
        for d in selected_dims:
            if d.table and d.table not in required_tables:
                required_tables.append(d.table)
        if not required_tables and selected_dims:
            required_tables.append(selected_dims[0].table)
        if not required_tables and model.joins:
            required_tables.append(model.joins[0].from_table)
        if not required_tables:
            raise SemanticCompilationError("MISSING_JOIN_PATH", "no source table")

        join_sql = self._join_plan(required_tables, model, dbms)
        select_parts = []
        for d in selected_dims:
            select_parts.append(f"{self._col(d.table, d.column, dbms)} AS {quote_identifier(d.name, dbms)}")
        for m in selected_measures:
            select_parts.append(f"{m.expression} AS {quote_identifier(m.name, dbms)}")
        if not select_parts:
            select_parts.append("COUNT(*) AS row_count")

        where_parts = []
        for filt in payload.filters:
            where_parts.append(self._filter_sql(filt, dbms))
        for tf in payload.timeframes:
            field = tf.get("field")
            start = tf.get("start")
            end = tf.get("end")
            if field and start and end:
                where_parts.append(
                    f"{field} BETWEEN {quote_string_literal(str(start), dbms)} AND {quote_string_literal(str(end), dbms)}"
                )
        if include_governance:
            where_parts.extend(model.governance_predicates)

        sql = f"SELECT {', '.join(select_parts)}\nFROM {join_sql}"
        if where_parts:
            sql += "\nWHERE " + " AND ".join(p for p in where_parts if p)
        if selected_dims:
            sql += "\nGROUP BY " + ", ".join(self._col(d.table, d.column, dbms) for d in selected_dims)
        return sql

    def _col(self, table: str, column: str, dbms: str) -> str:
        if "." in table:
            schema, name = table.split(".", 1)
            return f"{quote_qualified(schema, name, dbms)}.{quote_identifier(column, dbms)}"
        return f"{quote_identifier(table, dbms)}.{quote_identifier(column, dbms)}"

    def _join_plan(self, required: List[str], model: SemanticModel, dbms: str) -> str:
        if len(required) == 1 and not model.joins:
            return self._table_ident(required[0], dbms)
        graph = defaultdict(list)
        edge_sql = {}
        for j in model.joins:
            graph[j.from_table].append(j.to_table)
            graph[j.to_table].append(j.from_table)
            edge_sql[(j.from_table, j.to_table)] = j
            edge_sql[(j.to_table, j.from_table)] = j
        anchor = required[0]
        visited: Set[str] = {anchor}
        order: List[Tuple[str, Optional[object]]] = [(anchor, None)]
        remaining = set(required[1:])
        q = deque([anchor])
        while q and remaining:
            node = q.popleft()
            for nbr in graph.get(node, []):
                if nbr in visited:
                    continue
                visited.add(nbr)
                order.append((nbr, edge_sql.get((node, nbr))))
                q.append(nbr)
                remaining.discard(nbr)
        if remaining:
            raise SemanticCompilationError("INCOMPATIBLE_DIMENSIONS", ", ".join(sorted(remaining)))
        parts = [self._table_ident(order[0][0], dbms)]
        for table, join in order[1:]:
            if join is None:
                raise SemanticCompilationError("MISSING_JOIN_PATH", table)
            jtype = join.join_type or "INNER"
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
