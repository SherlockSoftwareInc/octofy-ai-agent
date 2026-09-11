"""SQL Server + ODBC/dialect validation paths."""

from __future__ import annotations

from typing import List, Optional, Tuple

from app.core.errors import ErrorCategory
from app.services.sql_error_classifier import SqlErrorClassifier
from app.utils.sql_normalization import extract_sql_object_refs


class SqlValidator:
    def __init__(self, source_id: Optional[str] = None, dbms: str = "SQL Server"):
        self.source_id = source_id
        self.dbms = dbms
        self.classifier = SqlErrorClassifier()

    def validate(self, sql: str, allowed_objects: Optional[List[str]] = None) -> Tuple[bool, str, List[str]]:
        if not sql or not sql.strip():
            return False, "Empty SQL query generated", []
        kind = (self.dbms or "").lower()
        if "sql server" in kind or "mssql" in kind or not kind:
            ok, err, missing = self._sql_server(sql)
        else:
            ok, err, missing = self._odbc(sql)
        if ok and allowed_objects:
            scoped_err = self._out_of_scope(sql, allowed_objects)
            if scoped_err:
                return False, scoped_err, missing
        return ok, err, missing

    def _sql_server(self, sql: str) -> Tuple[bool, str, List[str]]:
        try:
            from app.services.validation_service import validate_sql_with_db

            return validate_sql_with_db(sql, self.source_id)
        except Exception as exc:
            return False, str(exc), []

    def _odbc(self, sql: str) -> Tuple[bool, str, List[str]]:
        try:
            from app.core.database import get_database_engine
            from sqlalchemy import text

            engine = get_database_engine(self.source_id)
            kind = (self.dbms or "").lower()
            if "oracle" in kind:
                prefix = "EXPLAIN PLAN FOR "
            elif any(x in kind for x in ("mysql", "mariadb", "postgres")):
                prefix = "EXPLAIN "
            else:
                prefix = "PREPARE _octofy_chk AS " if "postgres" in kind else ""
            with engine.connect() as conn:
                conn.execute(text(prefix + sql if prefix else sql))
            return True, "", []
        except Exception as exc:
            return False, str(exc), []

    def _out_of_scope(self, sql: str, allowed: List[str]) -> Optional[str]:
        allowed_set = {a.lower().replace("[", "").replace("]", "") for a in allowed}
        allowed_names = {a.split(".")[-1] for a in allowed_set}
        missing = []
        for ref in extract_sql_object_refs(sql):
            norm = ref.lower().replace("[", "").replace("]", "")
            if norm in allowed_set or norm.split(".")[-1] in allowed_names:
                continue
            missing.append(ref)
        if missing:
            return "TABLE_VALIDATION_ERROR: " + ", ".join(missing)
        return None
