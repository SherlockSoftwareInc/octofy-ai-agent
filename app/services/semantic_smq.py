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

import hashlib
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


# Root keys that mark a payload as SMQ-shaped. Singular aliases are included so
# ``{"metric":"row_count"}`` is compiled rather than executed as SQL.
_SMQ_ROOT_KEYS = ("metrics", "dimensions", "metric", "dimension")

_METRIC_ALIASES = ("metric", "measure", "name", "id")
_DIMENSION_ALIASES = ("dimension", "field", "column", "name", "id")


class SmqShapeError(Exception):
    """An SMQ payload whose envelope parsed, but an element has the wrong shape.

    Raised instead of returning ``None`` so the retry can name the offending index
    and the accepted aliases. A generic "could not be parsed" makes the model blame
    its Markdown fence and repeat the same payload.
    """


def _is_smq_object(obj: Optional[dict]) -> bool:
    """An SMQ object carries a metric or dimension key, usable or not.

    Either key alone is enough: a dimensions-only request is a valid detail query
    and must still be recognised, so that it is never executed as SQL. A present key
    whose value is a bare string, an empty array, or a wrong element type is still
    an SMQ — the typed parse decides whether it can be used.
    """
    if obj is None:
        return False
    return any(key in obj for key in _SMQ_ROOT_KEYS)


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
_SMQ_KEY_RE = re.compile(
    r'"(?:metrics|dimensions|metric|dimension)"\s*:', re.IGNORECASE
)


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
                if depth == 1 and name in {"metrics", "dimensions", "metric", "dimension"}:
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


def _scalar_name(value: Any) -> Optional[str]:
    """A name carried by a string or an integer. Booleans and floats are not names."""
    if isinstance(value, bool) or isinstance(value, float):
        return None
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _alias_name(obj: dict, aliases: tuple) -> Optional[str]:
    """First recognized alias on an element object that carries a scalar name."""
    for alias in aliases:
        if alias not in obj:
            continue
        name = _scalar_name(obj.get(alias))
        if name:
            return name
    return None


def _read_name_array(
    source: dict,
    plural_key: str,
    singular_key: str,
    aliases: tuple,
) -> Optional[List[str]]:
    """Read a name list, merging the plural key with its singular alias.

    A key that is present but empty yields an empty list: ``{"metrics":[]}`` is a
    well-formed SMQ asking for nothing. An absent key yields ``None``, so a payload
    with neither metrics nor dimensions stays on the caller's raw-SQL fallback path.

    A bare string becomes a one-element list. An object element is unwrapped through
    ``aliases``. A number, or an object with no recognized alias, raises
    :class:`SmqShapeError` — dropping it would hide the real shape problem behind
    "no metrics or dimensions".
    """
    if plural_key not in source and singular_key not in source:
        return None

    result: List[str] = []
    seen = set()

    def append_element(element: Any) -> None:
        if element is None:
            return
        if isinstance(element, str):
            text = element.strip()
            key = text.lower()
            if text and key not in seen:
                seen.add(key)
                result.append(text)
            return
        if isinstance(element, dict):
            name = _alias_name(element, aliases)
            if name is None:
                joined = "|".join(aliases)
                raise SmqShapeError(
                    f"{plural_key}[{len(result)}]: expected a string identifier or an object "
                    f"carrying one of {joined}."
                )
            key = name.lower()
            if key not in seen:
                seen.add(key)
                result.append(name)
            return
        joined = "|".join(aliases)
        raise SmqShapeError(
            f"{plural_key}[{len(result)}]: expected a string identifier or an object "
            f"carrying one of {joined}."
        )

    def append(token: Any) -> None:
        if token is None:
            return
        if isinstance(token, list):
            for element in token:
                append_element(element)
            return
        append_element(token)

    if plural_key in source:
        append(source.get(plural_key))
    if singular_key in source:
        append(source.get(singular_key))
    return result


def _read_scalar(obj: dict, key: str) -> Optional[str]:
    """String form of a scalar field, or None for a missing, nested, or blank value."""
    if key not in obj:
        return None
    value = obj.get(key)
    if value is None or isinstance(value, (dict, list)):
        return None
    if isinstance(value, bool):
        text = "true" if value else "false"
    else:
        text = str(value).strip()
    return text or None


def _read_filters(source: dict) -> List[dict]:
    """Lenient filters: drop an element with no usable field, accept ``operator`` for ``op``.

    A dropped filter only widens the row set. Failing the payload over a decoration
    would repeat the exhausting-retry failure this parsing exists to fix.
    """
    raw = source.get("filters")
    if not isinstance(raw, list):
        return []
    result: List[dict] = []
    for element in raw:
        if not isinstance(element, dict):
            continue
        field = _read_scalar(element, "field") or _read_scalar(element, "name")
        if not field:
            continue
        result.append(
            {
                "field": field,
                "op": _read_scalar(element, "op") or _read_scalar(element, "operator") or "",
                "value": _read_scalar(element, "value") or "",
            }
        )
    return result


def _read_timeframes(source: dict) -> List[dict]:
    """Lenient timeframes: drop an element with no usable field, accept ``name`` for ``field``."""
    raw = source.get("timeframes")
    if not isinstance(raw, list):
        return []
    result: List[dict] = []
    for element in raw:
        if not isinstance(element, dict):
            continue
        field = _read_scalar(element, "field") or _read_scalar(element, "name")
        if not field:
            continue
        result.append(
            {
                "field": field,
                "range": _read_scalar(element, "range") or "",
                "start": _read_scalar(element, "start"),
                "end": _read_scalar(element, "end"),
            }
        )
    return result


def smq_from_object(obj: dict) -> Optional[SmqPayload]:
    """Build a typed query from a parsed object, or None when it is not an SMQ.

    Raises :class:`SmqShapeError` when a name element has no usable identifier.
    """
    metrics = _read_name_array(obj, "metrics", "metric", _METRIC_ALIASES)
    dimensions = _read_name_array(obj, "dimensions", "dimension", _DIMENSION_ALIASES)
    if metrics is None and dimensions is None:
        return None
    return SmqPayload(
        metrics=metrics or [],
        dimensions=dimensions or [],
        filters=_read_filters(obj),
        timeframes=_read_timeframes(obj),
    )


def parse_smq(raw: Optional[str]) -> Optional[SmqPayload]:
    """Tolerant second pass: the extracted payload as a strongly typed query.

    Kept separate from :func:`extract_smq_json` on purpose. The first pass answers
    "is there something SMQ-shaped here?", this one answers "can I use it?".
    A payload that is SMQ-shaped but unusable raises :class:`SmqShapeError` *after*
    the guard in :func:`looks_like_smq` has had its say, so the retry names the
    offending element instead of treating the text as SQL.

    Accepts an array of strings, an array of single-key objects, a bare string, and
    the singular root keys ``metric`` / ``dimension``.
    """
    text = extract_smq_json(raw)
    if text is None:
        return None
    obj = _parse_object(text)
    if not _is_smq_object(obj):
        return None
    return smq_from_object(obj)


def semantic_payload_fingerprint(raw: Optional[str], cleaned: Optional[str] = None) -> str:
    """Fingerprint the SMQ payload behind a semantic retry.

    Whitespace and the surrounding Markdown fence are normalized away. Key order is
    preserved: reordering keys is a genuinely different payload. Returns an empty
    string when the response carries no SMQ payload, so a plain-SQL reply stays out
    of the semantic repeat signal.
    """
    payload = extract_smq_json(raw)
    if not payload:
        payload = extract_smq_json(cleaned)
    if not payload:
        return ""
    try:
        parsed = json.loads(payload)
    except (ValueError, TypeError):
        return ""
    normalized = json.dumps(parsed, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest().upper()


def build_smq_shape_mismatch_feedback(error: BaseException, smq_json: str, model: Any) -> str:
    """Retry text for a wrong element shape: where it failed, and what was expected."""
    received = (smq_json or "").strip()
    if not received:
        received = "(empty)"
    elif len(received) > 400:
        received = received[:400] + "..."
    return (
        "SCHEMA MISMATCH: the SMQ payload has the wrong element shape. "
        f"{error} "
        'Expected an array of plain string identifiers (for example ["row_count"]), '
        "but received a structured element. Received payload: "
        f"{received}."
        f"{valid_names_hint(model)}"
    )


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
        " Return only a fenced smq code block with JSON of this exact shape: "
        '{"metrics":["<metric_name>"],"dimensions":["<dimension_name>"],"filters":[],"timeframes":[]}.'
        ' CRITICAL: "metrics" and "dimensions" must be arrays of plain strings - '
        'never an array of objects such as [{"metric":"row_count"}].'
        " Do not return SQL."
    ]
    if measures:
        parts.append(" Valid metrics: " + ", ".join(measures) + ".")
    if dimensions:
        parts.append(" Valid dimensions: " + ", ".join(dimensions) + ".")
    return "".join(parts)
