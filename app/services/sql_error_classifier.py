"""SQL error taxonomy including semantic compilation errors."""

from __future__ import annotations

import re
from typing import Optional


class SqlErrorClassifier:
    SEMANTIC_CODES = {
        "UNKNOWN_METRIC": "UnknownMetric",
        "UNKNOWN_DIMENSION": "UnknownDimension",
        "INCOMPATIBLE_DIMENSIONS": "IncompatibleDimensions",
        "MISSING_JOIN_PATH": "MissingJoinPath",
    }

    def classify(self, error_message: str, stage: str = "validation") -> str:
        text = error_message or ""
        upper = text.upper()
        if "SEMANTIC" in upper or any(code in upper for code in self.SEMANTIC_CODES):
            return "semantic_compilation"
        if "syntax" in text.lower() or "incorrect syntax" in text.lower():
            return "syntax"
        if "invalid object" in text.lower() or "invalid column" in text.lower():
            return "schema"
        if "timeout" in text.lower():
            return "timeout"
        if stage == "safety":
            return "safety"
        if stage == "generation":
            return "generation"
        if stage == "requirement":
            return "requirement"
        return "validation"

    def extract_missing_object(self, error_message: str) -> Optional[str]:
        match = re.search(r"Invalid object name '([^']+)'", error_message or "")
        if match:
            return match.group(1)
        match = re.search(r"Invalid column name '([^']+)'", error_message or "")
        if match:
            return match.group(1)
        return None

    def semantic_kind(self, error_message: str) -> Optional[str]:
        upper = (error_message or "").upper()
        for code, name in self.SEMANTIC_CODES.items():
            if code in upper:
                return name
        return None
