"""
Chart Intent Detection Service

Detects user intent to change or specify chart types from natural language queries.
Supports commands like "show me the results as a line chart", "make it a bar chart", etc.
"""

import re
from dataclasses import dataclass
from typing import Optional, Literal

ChartType = Literal['bar', 'line', 'pie', 'scatter', 'column', 'stackedBar', 'stackedColumn', 'clusteredColumn', 'area', 'radar', 'treemap', 'funnel', 'none']

@dataclass
class ChartIntent:
    """Represents detected chart intent from user query"""
    chart_type: ChartType
    is_chart_only_request: bool  # True if ONLY changing chart type, no new data needed
    original_query: str


# Patterns that indicate user wants to change/specify chart type
CHART_TYPE_PATTERNS = {
    'line': [
        r'\bline\s*chart\b',
        r'\bas\s+a?\s*line\b',
        r'\bline\s*graph\b',
        r'\bplot\s+.*\s+over\s+time\b',
        r'\btrend\s*line\b',
        r'\btime\s*series\b',
    ],
    'bar': [
        r'\bbar\s*chart\b',
        r'\bas\s+a?\s*bar\b',
        r'\bbar\s*graph\b',
        r'\bhistogram\b',
    ],
    'scatter': [
        r'\bscatter\s*plot\b',
        r'\bscatter\s*chart\b',
        r'\bas\s+a?\s*scatter\b',
        r'\bxy\s*chart\b',
        r'\bxy\s*plot\b',
    ],
    'pie': [
        r'\bpie\s*chart\b',
        r'\bas\s+a?\s*pie\b',
        r'\bdoughnut\s*chart\b',
        r'\bdonut\s*chart\b',
    ],
    'treemap': [
        r'\btreemap\b',
        r'\btree\s*map\b',
        r'\bhierarchical\s*chart\b',
    ],
    'area': [
        r'\barea\s*chart\b',
        r'\barea\s*graph\b',
        r'\bas\s+a?\s*area\b',
        r'\bfilled\s*line\b',
        r'\bstacked\s*area\b',
    ],
    'radar': [
        r'\bradar\s*chart\b',
        r'\bspider\s*chart\b',
        r'\bweb\s*chart\b',
        r'\bas\s+a?\s*radar\b',
    ],
    'column': [
        r'\bcolumn\s*chart\b',
        r'\bcolumn\s*graph\b',
    ],
    'stackedBar': [
        r'\bstacked\s*bar\b',
        r'\bbar\s*stacked\b',
    ],
    'stackedColumn': [
        r'\bstacked\s*column\b',
        r'\bcolumn\s*stacked\b',
    ],
    'clusteredColumn': [
        r'\bclustered\s*column\b',
        r'\bgrouped\s*column\b',
        r'\bclustered\s*bar\b',
        r'\bgrouped\s*bar\b',
    ],
    'funnel': [
        r'\bfunnel\s*chart\b',
        r'\bfunnel\b',
        r'\bsales\s*funnel\b',
        r'\bconversion\s*funnel\b',
        r'\bas\s+a?\s*funnel\b',
    ],
}

# Patterns that indicate this is ONLY about changing chart type (no new data query)
CHART_ONLY_PATTERNS = [
    r'^show\s+(me\s+)?(it\s+|the\s+results?\s+|that\s+|this\s+)?as\s+',
    r'^(can\s+you\s+)?make\s+(it|that|this)\s+',
    r'^change\s+(it\s+|the\s+chart\s+)?to\s+',
    r'^switch\s+to\s+',
    r'^display\s+(it\s+|this\s+|that\s+)?as\s+',
    r'^i\'?d?\s+(like|prefer|want)\s+(to\s+see\s+)?(it\s+|a\s+)?',
    r'^convert\s+to\s+',
    r'^use\s+a?\s*\w+\s*chart',
    r'^(please\s+)?show\s+(this|that|it)\s+',
    r'^visualize\s+(it\s+|this\s+|that\s+)?as\s+',
]


def detect_chart_intent(query: str) -> Optional[ChartIntent]:
    """
    Detect if user query contains chart type preference.
    
    Args:
        query: User's natural language query
        
    Returns:
        ChartIntent if chart preference detected, None otherwise
        
    Examples:
        >>> detect_chart_intent("show me the results as a line chart")
        ChartIntent(chart_type='line', is_chart_only_request=True, ...)
        
        >>> detect_chart_intent("show monthly revenue as a bar chart")
        ChartIntent(chart_type='bar', is_chart_only_request=False, ...)
        
        >>> detect_chart_intent("show me sales by region")
        None
    """
    query_lower = query.lower().strip()
    
    # First, detect which chart type (if any) is requested
    detected_type: Optional[ChartType] = None
    
    for chart_type_key, patterns in CHART_TYPE_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, query_lower, re.IGNORECASE):
                # Cast to ChartType since we know keys are valid
                detected_type = chart_type_key  # type: ignore
                break
        if detected_type:
            break
    
    if not detected_type:
        return None
    
    # Determine if this is ONLY about chart type (no new data query)
    is_chart_only = False
    for pattern in CHART_ONLY_PATTERNS:
        if re.search(pattern, query_lower, re.IGNORECASE):
            is_chart_only = True
            break
    
    return ChartIntent(
        chart_type=detected_type,
        is_chart_only_request=is_chart_only,
        original_query=query
    )


def extract_data_query(query: str, chart_intent: Optional[ChartIntent]) -> str:
    """
    Extract the data-related portion of the query, removing chart type specification.
    
    Args:
        query: Original user query
        chart_intent: Detected chart intent
        
    Returns:
        Query string with chart type specification removed
    """
    if not chart_intent or chart_intent.is_chart_only_request:
        return query
    
    # Remove chart type patterns from query
    cleaned = query
    for patterns in CHART_TYPE_PATTERNS.values():
        for pattern in patterns:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
    
    # Clean up common connecting phrases
    cleaned = re.sub(r'\s+as\s+a?\s*$', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s+in\s+a?\s*$', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s+using\s+a?\s*$', '', cleaned, flags=re.IGNORECASE)
    
    # Clean up extra whitespace
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    
    return cleaned if cleaned else query
