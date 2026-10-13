"""Query and identifier vocabulary shared by routing, matching and keyword extraction.

These helpers used to live in :mod:`app.services.semantic_compiler`, so a query-matching
concern was importable only from the semantic layer. They hold no compiler state and are
used by the orchestrator's routing gate, by prompt building and by the compiler alike.

Three normalizations coexist on purpose and are *not* interchangeable:

* :func:`question_tokens` splits running text into comparison tokens.
* :func:`tokenize` splits an identifier, dropping the schema path and breaking
  underscores and camel humps into boundaries.
* ``app.utils.hashing.normalize_question`` returns the whitespace-collapsed string key
  used by cache and knowledge-base lookups.
"""

from __future__ import annotations

import re
from typing import List, Optional, Sequence

# The single stop-word list for the application: the union of the lists that five
# modules used to define privately, so one word is no longer a stop word in one
# normalizer and a keyword in another.
STOP_WORDS = frozenset(
    {
        "a", "about", "all", "an", "and", "are", "as", "at", "be", "been", "being",
        "but", "by", "can", "column", "columns", "contain", "containing", "contains",
        "could", "data", "database", "did", "do", "does", "during", "every", "field",
        "fields", "find", "for", "from", "get", "give", "had", "has", "have", "her",
        "how", "i", "in", "information", "instead", "into", "is", "it", "its", "list",
        "me", "my", "need", "not", "now", "object", "objects", "of", "on", "one", "or",
        "our", "out", "please", "records", "return", "returns", "schema", "should",
        "show", "store", "stored", "stores", "table", "tables", "that", "the", "their",
        "them", "this", "through", "to", "up", "us", "view", "views", "want", "was",
        "were", "what", "when", "where", "which", "who", "will", "with", "would", "you",
        "your",
    }
)

# Words that describe how a value is shaped rather than what it means. They are
# filtered at comparison time, never inside tokenize: dropping them there made
# ``product_name`` collapse to ``product`` and the closest-name hint went silent.
STRUCTURAL_TOKENS = frozenset(
    {
        "count", "number", "total", "sum", "avg", "average", "min", "max", "rate",
        "line", "id", "key", "item", "date", "year", "month", "day", "name",
    }
)

_LATIN_TOKEN_RE = re.compile(r"\b[a-z_][a-z0-9_]*\b")
_NON_LATIN_TOKEN_RE = re.compile(r"[^\u0000-\u007f\s]+")


def is_significant(token: Optional[str]) -> bool:
    """True when a token carries domain meaning rather than describing a value's shape.

    Structural words still match the model's vocabulary -- they simply cannot create
    a match on their own, because they are left out of that vocabulary.
    """
    return bool(token and token.strip()) and token.strip().lower() not in STRUCTURAL_TOKENS


def _split_camel_humps(value: str) -> List[str]:
    """Split on lower-to-upper boundaries. ``SalesAmount`` yields ``Sales`` and ``Amount``."""
    parts: List[str] = []
    start = 0
    for i in range(1, len(value)):
        if value[i].isupper() and value[i - 1].islower():
            parts.append(value[start:i])
            start = i
    parts.append(value[start:])
    return parts


def tokenize(name: Optional[str]) -> List[str]:
    """Split an identifier or phrase into comparable tokens.

    The schema path is dropped, quoting is stripped, and underscores and camel-case
    humps become boundaries. Tokens shorter than three characters are discarded.
    The result is lossless with respect to meaning: ``product_name`` yields
    ``product`` and ``name``. Structural words are filtered by :func:`is_significant`
    at comparison time, not here.

    This exists because :func:`question_tokens` lowercases before matching, so
    ``SalesAmount`` would survive as one opaque token instead of ``sales`` + ``amount``.
    """
    tokens: List[str] = []
    if not name or not str(name).strip():
        return tokens

    value = str(name).strip()
    last_dot = value.rfind(".")
    if 0 <= last_dot < len(value) - 1:
        value = value[last_dot + 1 :]

    for ch in "[]`\"'-_":
        value = value.replace(ch, " ")

    seen = set()
    for raw in value.split():
        for part in _split_camel_humps(raw):
            token = part.strip().lower()
            if len(token) < 3 or token in seen:
                continue
            seen.add(token)
            tokens.append(token)
    return tokens


def question_tokens(query: Optional[str]) -> List[str]:
    """Lowercase question tokens with stop words and length <= 2 removed.

    Camel-case is not split here. That is intentional: ``SalesAmount`` in running
    text is one token, and :func:`tokenize` is what splits it when the text is an
    identifier (a column or an entity), not a question word.
    """
    if not query or not str(query).strip():
        return []
    lower = str(query).lower()
    out: List[str] = []
    seen = set()
    for token in _LATIN_TOKEN_RE.findall(lower):
        if token in STOP_WORDS:
            continue
        if len(token) <= 2 and token != "get":
            continue
        if token in seen:
            continue
        seen.add(token)
        out.append(token)
    for token in _NON_LATIN_TOKEN_RE.findall(lower):
        text = token.strip()
        if text and text not in seen:
            seen.add(text)
            out.append(text)
    return out


def build_question_tokens(
    tokens: Optional[Sequence[str]],
    entities: Optional[Sequence[str]] = None,
) -> List[str]:
    """Question terms plus entity phrases, so a noun phrase is visible to the gate."""
    combined: List[str] = []
    seen = set()
    for token in tokens or []:
        text = (token or "").strip()
        key = text.lower()
        if text and key not in seen:
            seen.add(key)
            combined.append(text)
    for entity in entities or []:
        for token in tokenize(entity):
            key = token.lower()
            if key not in seen:
                seen.add(key)
                combined.append(token)
    return combined


def model_items(model: object, key: str) -> Sequence[object]:
    """The model's ``measures``/``dimensions`` items, whether it is a dict or an object."""
    if model is None:
        return []
    if isinstance(model, dict):
        return model.get(key) or []
    return getattr(model, key, None) or []


def model_item_name(item: object) -> str:
    """A measure/dimension item's name, whether the item is a dict or an object."""
    if isinstance(item, dict):
        value = item.get("name")
    else:
        value = getattr(item, "name", None)
    return value.strip() if isinstance(value, str) else ""


def can_answer(
    model: object,
    extracted_columns: Optional[Sequence[str]],
    question_tokens: Optional[Sequence[str]],
) -> bool:
    """Whether the active model has any vocabulary for this question.

    The caller may fall back to physical SQL only when the question shares no
    token at all with the model's measures and dimensions. Structural tokens are
    excluded from the vocabulary, so they cannot create a match; domain terms such
    as ``sales`` and ``amount`` are matched as whole tokens, which is what keeps
    an unrelated ``SalesTerritoryKey`` from holding a revenue question.

    A model with no vocabulary, and a missing model, cannot be judged unfit.
    """
    if model is None:
        return True

    vocabulary = set()
    for collection in ("measures", "dimensions"):
        for item in model_items(model, collection):
            for token in tokenize(model_item_name(item)):
                if is_significant(token):
                    vocabulary.add(token.lower())

    if not vocabulary:
        return True

    for column in extracted_columns or []:
        for token in tokenize(column):
            if token.lower() in vocabulary:
                return True

    for token in question_tokens or []:
        if (token or "").strip().lower() in vocabulary:
            return True
    return False


def closest_name(requested: str, candidates: Sequence[str]) -> Optional[str]:
    """Best candidate for ``requested``, or None when nothing overlaps.

    Token overlap is tried first. A prefix match then covers a concatenated near
    miss such as ``productname`` against ``product_name``.
    """
    requested_tokens = tokenize(requested)
    if not requested_tokens:
        return None
    requested_set = {token.lower() for token in requested_tokens}

    best: Optional[str] = None
    best_score = 0
    for candidate in candidates:
        if not candidate or not str(candidate).strip():
            continue
        score = sum(1 for token in tokenize(candidate) if token.lower() in requested_set)
        if score > best_score:
            best_score = score
            best = str(candidate)

    if best_score > 0:
        return best

    minimum_prefix = 5
    for candidate in candidates:
        if not candidate or not str(candidate).strip():
            continue
        candidate_tokens = tokenize(candidate)
        if not candidate_tokens:
            continue
        matched = False
        for requested_token in requested_tokens:
            for candidate_token in candidate_tokens:
                if (
                    len(requested_token) >= minimum_prefix
                    and candidate_token.lower().startswith(requested_token.lower())
                ) or (
                    len(candidate_token) >= minimum_prefix
                    and requested_token.lower().startswith(candidate_token.lower())
                ):
                    matched = True
                    break
            if matched:
                return str(candidate)
    return None
