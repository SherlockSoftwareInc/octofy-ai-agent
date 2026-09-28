"""SMQ (Semantic Model Query) payload handling.

The contract with the model is a fenced ```smq block, but models answer with
```json, bare fences, bare JSON, and JSON wrapped in prose. Extraction is
therefore shape-tolerant.

Two independent questions are answered here, and keeping them independent is the
whole point:

* ``extract_smq_json()`` -- is there a usable SMQ payload in this response?
* ``looks_like_smq()``   -- does this response carry SMQ-shaped JSON, usable or not?

The second question is what keeps an unusable semantic payload out of the SQL
validator: a malformed SMQ attempt must be retried semantically, never executed
as SQL, whatever the raw-SQL fallback policy says.

Neither predicate is a substring search. A legitimate query such as
``SELECT [metrics] FROM [dbo].[audit]`` must stay classified as SQL, so the guard
parses JSON structure instead.
"""

from __future__ import annotations

import json
import re
from typing import Any, List, Optional

from app.models.pipeline import SmqPayload

# Preferred contract: a ```smq fenced block.
_SMQ_FENCE_RE = re.compile(r"```smq\s*\n?(?P<body>.*?)```", re.IGNORECASE | re.DOTALL)

# Any fenced block. The optional tag group deliberately does not enumerate tags:
# an unrecognised tag ends up as the body's first line and _drop_fence_tag removes it.
_ANY_FENCE_RE = re.compile(r"```(?:sql)?\s*\n?(?P<body>.*?)```", re.IGNORECASE | re.DOTALL)

def _parse_object(text: Optional[str]) -> Optional[dict]:
    """Parse text as a JSON object, or return None."""
    if not text or not text.strip():
        return None
    try:
        parsed = json.loads(text)
    except (ValueError, TypeError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _is_smq_object(obj: Optional[dict]) -> bool:
    """An SMQ object carries a ``metrics`` or ``dimensions`` array.

    Either key alone is enough: a dimensions-only request is a valid detail query
    and must still be recognised, so that it is never executed as SQL.
    """
    if obj is None:
        return False
    return isinstance(obj.get("metrics"), list) or isinstance(obj.get("dimensions"), list)


def _drop_fence_tag(body: str) -> str:
    """Remove a leading markdown language tag line left inside a fence body."""
    first, sep, rest = body.partition("\n")
    if not sep:
        return body
    tag = first.strip()
    if tag and not tag.startswith("{") and "://" not in tag:
        candidate = rest.strip()
        if candidate.startswith("{"):
            return candidate
    return body


def _find_balanced_object(text: str) -> Optional[str]:
    """Return the first brace-balanced ``{...}`` region, ignoring braces in strings.

    String literals and backslash escapes must both be honoured. A scanner that
    ignores escapes closes the string early on a value such as ``"a \\" b {c"``,
    mis-counts the brace, and returns a truncated region -- which then fails to
    parse and lets a valid SMQ fall through to the SQL path.
    """
    start = text.find("{")
    while start >= 0:
        depth = 0
        in_string = False
        escaped = False
        for i in range(start, len(text)):
            ch = text[i]
            if in_string:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == '"':
                    in_string = False
                continue
            if ch == '"':
                in_string = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start : i + 1]
        start = text.find("{", start + 1)
    return None


def extract_smq_json(raw: Optional[str]) -> Optional[str]:
    """Extract the SMQ JSON object text from a raw model response."""
    if not raw or not raw.strip():
        return None
    text = raw.strip()

    for pattern in (_SMQ_FENCE_RE, _ANY_FENCE_RE):
        for match in pattern.finditer(text):
            body = _drop_fence_tag(match.group("body").strip())
            obj = _parse_object(body)
            if _is_smq_object(obj):
                return body

    region = _find_balanced_object(text)
    if region is not None and _is_smq_object(_parse_object(region)):
        return region

    if _is_smq_object(_parse_object(text)):
        return text

    return None


# A known SMQ key appearing where a top-level JSON object key appears. Matched only at
# depth 1, so a *nested* object's ``dimensions`` field does not read as an SMQ attempt.
_SMQ_KEY_RE = re.compile(r'"(?:metrics|dimensions)"\s*:', re.IGNORECASE)


def _has_top_level_smq_key(text: str) -> bool:
    """True when ``"metrics"`` / ``"dimensions"`` appears as a JSON key at depth 1.

    Structure-aware rather than a substring test: the token must be a quoted string that is
    immediately followed by a colon and sits at the top level of the object, outside every
    other string literal and outside any nested object. A query such as
    ``SELECT [metrics] FROM [dbo].[audit]`` therefore carries no such token, while a payload
    truncated mid-array still does.
    """
    start = text.find("{")
    if start < 0:
        return False
    depth = 0
    in_string = False
    escaped = False
    literal: List[str] = []
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escaped:
                literal.append(ch)
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
                name = "".join(literal).strip().lower()
                if depth == 1 and name in {"metrics", "dimensions"}:
                    if text[i + 1 :].lstrip().startswith(":"):
                        return True
            else:
                literal.append(ch)
            continue
        if ch == '"':
            in_string = True
            literal = []
        elif ch == "{":
            depth += 1
            if depth > 2:
                return False
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return False
    return False


def _looks_like_smq_text(text: Optional[str]) -> bool:
    """True when text is, or is a malformed attempt at, an SMQ JSON object.

    A valid JSON object is an SMQ when it carries ``metrics`` or ``dimensions``. Anything
    that does not parse as JSON is an SMQ attempt when an SMQ key appears where a top-level
    object key appears -- which is precisely the truncated payload that must never reach the
    SQL validator.
    """
    if not text or not text.strip():
        return False
    body = text.strip()
    obj = _parse_object(body)
    if obj is not None and _is_smq_object(obj):
        return True
    if _has_top_level_smq_key(body):
        return True
    # A brace-led fragment cut off before its first key was completed.
    head = body[:80]
    return body.startswith("{") and bool(_SMQ_KEY_RE.search(head))


def looks_like_smq(raw: Optional[str]) -> bool:
    """True when the response carries SMQ-shaped JSON, applicable or not.

    Used to refuse to execute a semantic payload as SQL, so it must be true for a malformed
    SMQ attempt -- a payload that fails to parse is exactly the case that must not be
    executed. Implemented by parsing structure -- never by searching for the bare substring
    ``metrics``, which would misclassify ``SELECT [metrics] FROM [dbo].[audit]``.
    """
    if not raw or not raw.strip():
        return False
    text = raw.strip()

    if _looks_like_smq_text(text):
        return True

    for match in _ANY_FENCE_RE.finditer(text):
        body = _drop_fence_tag(match.group("body").strip())
        if _looks_like_smq_text(body):
            return True

    return False


def parse_smq(raw: Optional[str]) -> Optional[SmqPayload]:
    """Tolerant second pass: the extracted payload as a strongly typed query.

    Kept separate from :func:`extract_smq_json` on purpose. The first pass answers
    "is there something SMQ-shaped here?", this one answers "can I use it?".
    A payload that is SMQ-shaped but unusable must return ``None`` *after* the
    guard in :func:`looks_like_smq` has had its say.
    """
    text = extract_smq_json(raw)
    if text is None:
        return None
    obj = _parse_object(text)
    if not _is_smq_object(obj):
        return None
    try:
        return SmqPayload.model_validate(obj)
    except Exception:
        return None


def _field(source: Any, key: str) -> Any:
    """Read ``key`` from a dict-shaped or attribute-shaped object."""
    if source is None:
        return None
    if isinstance(source, dict):
        return source.get(key)
    return getattr(source, key, None)


def valid_names_hint(model: Any) -> str:
    """Retry attachment enumerating the model's valid metric/dimension names.

    A semantic retry that is not told the valid vocabulary cannot converge.
    Accepts either a dict-shaped model (the shape the API transports) or an
    attribute-shaped one (a Pydantic/ORM instance), because both occur.
    """
    if isinstance(model, str):
        return model

    def names(collection: Any) -> List[str]:
        out: List[str] = []
        for item in collection or []:
            value = _field(item, "name")
            if isinstance(value, str) and value.strip() and value.strip() not in out:
                out.append(value.strip())
        return out

    measures = names(_field(model, "measures"))
    dimensions = names(_field(model, "dimensions"))

    parts = [
        " Return only a fenced smq code block with JSON of the shape "
        '{"metrics":[...],"dimensions":[...],"filters":[...],"timeframes":[...]}.'
        " Do not return SQL."
    ]
    if measures:
        parts.append(" Valid metrics: " + ", ".join(measures) + ".")
    if dimensions:
        parts.append(" Valid dimensions: " + ", ".join(dimensions) + ".")
    return "".join(parts)
