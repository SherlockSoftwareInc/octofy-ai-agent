"""
System Query Service - Handles SQL Server system metadata queries.

Detects when users ask about database internals (tables, columns, views,
server version, etc.) and generates T-SQL using system catalog views
instead of the business schema discovery pipeline.
"""

import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Patterns that indicate a system metadata query.
# Each pattern is a compiled regex tested against the lowercased query.
# Order does not matter - any match triggers system intent.
SYSTEM_QUERY_PATTERNS = [
    # Table discovery
    re.compile(r'\b(list|show|get|find|what|which|display)\b.*\btables?\b'),
    # Column / structure inspection
    re.compile(r'\b(list|show|get|find|what|which|display)\b.*\bcolumns?\b'),
    re.compile(r'\bcolumn\s*(info|information|details?|metadata)\b'),
    re.compile(r'\btable\s*(structure|definition|schema|layout|design)\b'),
    re.compile(r'\b(describe|definition\s+of)\b.*\btable\b'),
    # View discovery
    re.compile(r'\b(list|show|get|find|what|which|display)\b.*\bviews?\b'),
    # Schema discovery
    re.compile(r'\b(list|show|get|find|what|which|display)\b.*\bschemas?\b'),
    # Index inspection
    re.compile(r'\b(list|show|get|find|what|which|display)\b.*\bindexe?s\b'),
    # Stored procedure discovery
    re.compile(r'\b(list|show|get|find|what|which|display)\b.*\b(stored\s+)?procedures?\b'),
    # Database-level metadata
    re.compile(r'\b(list|show|get|find|what|which)\b.*\bdatabases?\b'),
    re.compile(r'\bdatabase\s*(size|info|information|details?|metadata|properties)\b'),
    re.compile(r'\brow\s*counts?\b.*\btables?\b'),
    # Server version
    re.compile(r'\bsql\s*(server)?\s*version\b'),
    re.compile(r'\bserver\s*version\b'),
    re.compile(r'\b(what|which)\s+version\b'),
    # Describe pattern (common DBA shorthand)
    re.compile(r'\bdescribe\b.*\b\w+\b'),
    # "how many tables" pattern
    re.compile(r'\bhow\s+many\s+tables\b'),
]

# Negative patterns - if these match, it is likely a business query even
# if a positive pattern also matched (e.g. "show me sales from the orders table").
BUSINESS_OVERRIDE_PATTERNS = [
    re.compile(r'\b(total|sum|average|avg|count|revenue|sales|profit|cost|amount)\b'),
    re.compile(r'\b(by|per|group\s+by|order\s+by|where|having|between|from\s+\d)\b'),
    re.compile(r'\b(compare|trend|forecast|growth|decline|ratio|percentage)\b'),
    re.compile(r'\b(customers?|employees?|products?|orders?|invoices?|shipments?)\b.*\b(who|how many|total|last|this)\b'),
]


def detect_system_query_intent(query: str) -> bool:
    """
    Detect whether a query is asking about SQL Server system metadata.

    Returns True if the query is about database internals (tables, columns,
    views, version, etc.) rather than business data.

    Args:
        query: The user's natural language query.

    Returns:
        True if system metadata intent is detected, False otherwise.
    """
    if not query or not query.strip():
        return False

    query_lower = query.lower().strip()

    # Check positive patterns
    has_system_signal = any(p.search(query_lower) for p in SYSTEM_QUERY_PATTERNS)
    if not has_system_signal:
        return False

    # Check negative overrides - business context overrules system signals
    has_business_signal = any(p.search(query_lower) for p in BUSINESS_OVERRIDE_PATTERNS)
    if has_business_signal:
        logger.debug(f"System intent suppressed by business signal for: {query[:80]}")
        return False

    logger.info(f"System metadata intent detected for: {query[:80]}")
    return True
