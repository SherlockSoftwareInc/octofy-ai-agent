/**
 * Chart Intent Detection for Frontend
 * 
 * Detects user intent to change chart types from natural language queries.
 * Mirrors the backend chart_intent_service.py for consistent behavior.
 */

export type ChartType = 'bar' | 'line' | 'pie' | 'scatter' | 'column' | 'stackedBar' | 'stackedColumn' | 'clusteredColumn' | 'area' | 'radar' | 'treemap' | 'funnel' | 'none';

export interface ChartIntent {
    chartType: ChartType;
    isChartOnlyRequest: boolean;
    originalQuery: string;
}

// Patterns that indicate a chart-only request (no new data query)
const CHART_ONLY_PATTERNS = [
    /^show\s+(this|that|it|the\s+results?|the\s+data)\s+(as|in)\s+a?\s*/i,
    /^(display|render|visualize)\s+(this|that|it|the\s+results?)\s+(as|in)\s+a?\s*/i,
    /^(switch|change|convert)\s+(to|this\s+to)\s+a?\s*/i,
    /^make\s+(this|it)\s+a\s*/i,
    /^(use|try)\s+a\s*\w+\s*(chart|graph|plot)/i,
];

// Chart type patterns - order matters (more specific patterns first)
const CHART_PATTERNS: Array<{ pattern: RegExp; chartType: ChartType }> = [
    // Stacked patterns (must come before basic bar/column to be more specific)
    { pattern: /\b(stacked\s*bar|bar\s*stacked)\b/i, chartType: 'stackedBar' },
    { pattern: /\b(stacked\s*column|column\s*stacked)\b/i, chartType: 'stackedColumn' },
    
    // Clustered patterns
    { pattern: /\b(clustered\s*column|grouped\s*column|clustered\s*bar|grouped\s*bar)\b/i, chartType: 'clusteredColumn' },
    
    // Area chart patterns
    { pattern: /\b(area\s*(chart|graph)?|filled\s*line)\b/i, chartType: 'area' },
    { pattern: /\bstacked\s*area\b/i, chartType: 'area' },
    
    // Radar chart patterns
    { pattern: /\b(radar\s*(chart)?|spider\s*(chart)?|web\s*chart)\b/i, chartType: 'radar' },
    
    // Treemap patterns
    { pattern: /\b(treemap|tree\s*map|hierarchical\s*chart)\b/i, chartType: 'treemap' },
    
    // Funnel chart patterns
    { pattern: /\b(funnel\s*(chart)?|sales\s*funnel|conversion\s*funnel)\b/i, chartType: 'funnel' },
    
    // Line chart patterns
    { pattern: /\b(line\s*(chart|graph|plot)?|trend\s*line)\b/i, chartType: 'line' },
    { pattern: /\b(time\s*series|over\s*time)\b/i, chartType: 'line' },
    
    // Column chart patterns (must come before bar)
    { pattern: /\bcolumn\s*(chart|graph)?\b/i, chartType: 'column' },
    
    // Bar chart patterns  
    { pattern: /\b(bar\s*(chart|graph)?|horizontal\s*bar)\b/i, chartType: 'bar' },
    { pattern: /\bhistogram\b/i, chartType: 'column' },
    
    // Scatter plot patterns
    { pattern: /\b(scatter\s*(plot|chart)?|x\s*y\s*plot|correlation)\b/i, chartType: 'scatter' },
    { pattern: /\bplot\s+\w+\s+(vs|versus|against)\s+\w+/i, chartType: 'scatter' },
    
    // Pie chart patterns
    { pattern: /\b(pie\s*(chart)?|donut|doughnut)\b/i, chartType: 'pie' },
    { pattern: /\bproportion(s)?\b/i, chartType: 'pie' },
];

/**
 * Detect chart type intent from a user query
 * @param query - The user's natural language query
 * @returns ChartIntent if chart type is detected, null otherwise
 */
export function detectChartIntent(query: string): ChartIntent | null {
    if (!query || typeof query !== 'string') {
        return null;
    }

    const trimmedQuery = query.trim();
    if (!trimmedQuery) {
        return null;
    }

    // Check for chart type in query
    let detectedType: ChartType | null = null;
    for (const { pattern, chartType } of CHART_PATTERNS) {
        if (pattern.test(trimmedQuery)) {
            detectedType = chartType;
            break;
        }
    }

    if (!detectedType) {
        return null;
    }

    // Check if this is a chart-only request (no data query)
    const isChartOnlyRequest = CHART_ONLY_PATTERNS.some(pattern => 
        pattern.test(trimmedQuery)
    );

    return {
        chartType: detectedType,
        isChartOnlyRequest,
        originalQuery: trimmedQuery,
    };
}

/**
 * Extract the data query portion from a combined chart + data request
 * @param query - Original user query
 * @param intent - Detected chart intent
 * @returns The data portion of the query, or original if not separable
 */
export function extractDataQuery(query: string, intent: ChartIntent | null): string {
    if (!intent) {
        return query;
    }

    if (intent.isChartOnlyRequest) {
        // This is a chart-only request, no data query to extract
        return query;
    }

    // Try to remove chart-related phrases from the query
    let dataQuery = query;
    
    // Remove patterns like "as a line chart", "in a bar graph", etc.
    const removalPatterns = [
        /\s*(as|in|using)\s+a?\s*(line|bar|pie|scatter|column|area|radar|treemap|donut|doughnut)\s*(chart|graph|plot)?\s*/gi,
        /\s*(show|display|visualize|render)\s+(it|this|that|the\s+results?)\s+(as|in)\s+a?\s*/gi,
    ];

    for (const pattern of removalPatterns) {
        dataQuery = dataQuery.replace(pattern, ' ');
    }

    return dataQuery.trim() || query;
}

/**
 * Check if a query is requesting a chart type change on existing results
 * @param query - The user's query
 * @returns true if this appears to be a re-visualization request
 */
export function isRevisualizationRequest(query: string): boolean {
    const intent = detectChartIntent(query);
    return intent?.isChartOnlyRequest ?? false;
}

/**
 * Get a user-friendly description of the chart type
 */
export function getChartTypeLabel(chartType: ChartType): string {
    const labels: Record<ChartType, string> = {
        bar: 'Bar Chart',
        line: 'Line Chart',
        pie: 'Pie Chart',
        scatter: 'Scatter Plot',
        column: 'Column Chart',
        stackedBar: 'Stacked Bar Chart',
        stackedColumn: 'Stacked Column Chart',
        clusteredColumn: 'Clustered Column Chart',
        area: 'Area Chart',
        radar: 'Radar Chart',
        treemap: 'Treemap',
        funnel: 'Funnel Chart',
        none: 'No Chart',
    };
    return labels[chartType] || chartType;
}

// =============================================================================
// ENHANCED RE-VISUALIZATION DETECTION
// =============================================================================
// These functions determine whether to re-visualize existing data with a new
// chart type vs. generating new code for different data.

/**
 * Common business metrics that indicate what data is being requested
 */
const METRICS = [
    'sales', 'revenue', 'profit', 'cost', 'expense', 'income', 'margin',
    'count', 'total', 'sum', 'average', 'avg', 'mean', 'median',
    'quantity', 'amount', 'price', 'rate', 'percentage', 'percent',
    'growth', 'change', 'difference', 'ratio', 'share',
    'orders', 'customers', 'users', 'visitors', 'transactions',
    'inventory', 'stock', 'units', 'volume', 'capacity'
];

/**
 * Common dimensions/groupings that indicate how data is sliced
 */
const DIMENSIONS = [
    'category', 'categories', 'region', 'regions', 'country', 'countries',
    'state', 'states', 'city', 'cities', 'location', 'locations',
    'product', 'products', 'brand', 'brands', 'department', 'departments',
    'customer', 'customers', 'segment', 'segments', 'channel', 'channels',
    'store', 'stores', 'team', 'teams', 'employee', 'employees',
    'vendor', 'vendors', 'supplier', 'suppliers'
];

/**
 * Timeframe indicators that suggest specific time periods
 */
const TIMEFRAMES = [
    // Years
    '2020', '2021', '2022', '2023', '2024', '2025', '2026',
    // Quarters
    'q1', 'q2', 'q3', 'q4',
    // Months
    'january', 'february', 'march', 'april', 'may', 'june',
    'july', 'august', 'september', 'october', 'november', 'december',
    'jan', 'feb', 'mar', 'apr', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec',
    // Relative periods
    'last year', 'this year', 'next year', 'previous year',
    'last month', 'this month', 'next month', 'previous month',
    'last quarter', 'this quarter', 'next quarter', 'previous quarter',
    'last week', 'this week', 'next week', 'previous week',
    'ytd', 'mtd', 'qtd', 'year to date', 'month to date',
    // Date ranges
    'daily', 'weekly', 'monthly', 'quarterly', 'yearly', 'annual'
];

/**
 * Modifiers that imply different data shape or aggregation
 * These suggest the user wants a fundamentally different view
 */
const DATA_SHAPE_MODIFIERS = [
    'trend', 'trends', 'trending',
    'growth', 'growing',
    'over time', 'by time', 'time series',
    'comparison', 'compare', 'comparing', 'vs', 'versus', 'against',
    'breakdown', 'break down', 'broken down',
    'distribution', 'spread',
    'top', 'bottom', 'best', 'worst', 'highest', 'lowest',
    'cumulative', 'running total', 'rolling'
];

/**
 * Explicit patterns that ALWAYS indicate chart-only (bypass keyword detection)
 */
const EXPLICIT_CHART_ONLY_PATTERNS = [
    /^show\s+(this|that|it)\s+(as|in)\s+/i,
    /^(display|render|visualize)\s+(this|that|it)\s+(as|in)\s+/i,
    /^(switch|change|convert)\s+(to|this\s+to)\s+/i,
    /^make\s+(this|it)\s+a\s+/i,
    /^(use|try)\s+a\s+\w+\s*(chart|graph|plot)/i,
    /^as\s+a?\s*(line|bar|pie|scatter|column|area|radar|treemap|funnel)/i,
    // Match simple chart requests like "line chart", "bar chart please", "pie chart pls"
    /^(line|bar|pie|scatter|column|area|radar|treemap|funnel)\s*(chart|graph|plot)?\s*(please|pls|plz|thanks|thx)?\s*$/i,
    // Match stacked and clustered variants
    /^(stacked|clustered)\s*(bar|column)\s*(chart|graph)?\s*(please|pls|plz|thanks|thx)?\s*$/i,
];

/**
 * Extract keywords from a query for comparison
 */
function extractKeywords(query: string): {
    metrics: string[];
    dimensions: string[];
    timeframes: string[];
    modifiers: string[];
} {
    const lowerQuery = query.toLowerCase();
    
    const foundMetrics = METRICS.filter(m => {
        const regex = new RegExp(`\\b${m}\\b`, 'i');
        return regex.test(lowerQuery);
    });
    
    const foundDimensions = DIMENSIONS.filter(d => {
        const regex = new RegExp(`\\b${d}\\b`, 'i');
        return regex.test(lowerQuery);
    });
    
    const foundTimeframes = TIMEFRAMES.filter(t => {
        // For multi-word timeframes, use includes; for single words, use word boundary
        if (t.includes(' ')) {
            return lowerQuery.includes(t.toLowerCase());
        }
        const regex = new RegExp(`\\b${t}\\b`, 'i');
        return regex.test(lowerQuery);
    });
    
    const foundModifiers = DATA_SHAPE_MODIFIERS.filter(m => {
        if (m.includes(' ')) {
            return lowerQuery.includes(m.toLowerCase());
        }
        const regex = new RegExp(`\\b${m}\\b`, 'i');
        return regex.test(lowerQuery);
    });
    
    return {
        metrics: foundMetrics,
        dimensions: foundDimensions,
        timeframes: foundTimeframes,
        modifiers: foundModifiers,
    };
}

/**
 * Check if two sets of keywords have conflicts (different data being requested)
 */
function hasConflictingKeywords(
    prevKeywords: ReturnType<typeof extractKeywords>,
    newKeywords: ReturnType<typeof extractKeywords>
): boolean {
    // If new query has different metrics, it's different data
    if (newKeywords.metrics.length > 0 && prevKeywords.metrics.length > 0) {
        const hasNewMetric = newKeywords.metrics.some(m => !prevKeywords.metrics.includes(m));
        if (hasNewMetric) return true;
    }
    
    // If new query has different dimensions, it's different data
    if (newKeywords.dimensions.length > 0 && prevKeywords.dimensions.length > 0) {
        const hasNewDimension = newKeywords.dimensions.some(d => !prevKeywords.dimensions.includes(d));
        if (hasNewDimension) return true;
    }
    
    // If new query has different timeframes, it's different data
    if (newKeywords.timeframes.length > 0 && prevKeywords.timeframes.length > 0) {
        const hasNewTimeframe = newKeywords.timeframes.some(t => !prevKeywords.timeframes.includes(t));
        if (hasNewTimeframe) return true;
    }
    
    // If new query adds timeframes where there were none, it might be more specific
    if (newKeywords.timeframes.length > 0 && prevKeywords.timeframes.length === 0) {
        return true;
    }
    
    return false;
}

/**
 * Check if a query is an explicit chart-only pattern
 * These patterns bypass all other detection and always trigger re-visualization
 */
export function isExplicitChartOnlyPattern(query: string): boolean {
    const trimmed = query.trim();
    return EXPLICIT_CHART_ONLY_PATTERNS.some(pattern => pattern.test(trimmed));
}

/**
 * Check if new query requests different data than the previous query
 */
export function isDifferentDataRequest(newQuery: string, prevQuery: string): boolean {
    const newKeywords = extractKeywords(newQuery);
    const prevKeywords = extractKeywords(prevQuery);
    
    // If new query has data shape modifiers, it likely wants different data/view
    if (newKeywords.modifiers.length > 0) {
        // Exception: if previous query had the same modifiers, it's okay
        const hasNewModifier = newKeywords.modifiers.some(m => !prevKeywords.modifiers.includes(m));
        if (hasNewModifier) return true;
    }
    
    // Check for conflicting keywords
    return hasConflictingKeywords(prevKeywords, newKeywords);
}

/**
 * Main decision function: Should we re-visualize existing data or generate new code?
 * 
 * @param chartIntent - Detected chart intent from the new query
 * @param newQuery - The user's new query
 * @param lastExecutedQuery - The query that produced the current results (if any)
 * @returns true if we should re-visualize, false if we should generate new code
 */
export function shouldTriggerRevisualization(
    chartIntent: ChartIntent | null,
    newQuery: string,
    lastExecutedQuery: string | undefined
): boolean {
    // No chart intent detected - definitely not a re-visualization
    if (!chartIntent) {
        console.log('🔍 shouldTriggerRevisualization: NO chart intent');
        return false;
    }
    
    // Priority 1: Explicit chart-only patterns ALWAYS re-visualize
    // Examples: "show it as line chart", "switch to bar chart"
    if (isExplicitChartOnlyPattern(newQuery)) {
        console.log('🔍 shouldTriggerRevisualization: YES - explicit chart-only pattern');
        return true;
    }
    
    // Priority 2: No previous execution - need to generate code first
    if (!lastExecutedQuery) {
        console.log('🔍 shouldTriggerRevisualization: NO - no previous execution');
        return false;
    }
    
    // Priority 3: Check if user is requesting different data
    if (isDifferentDataRequest(newQuery, lastExecutedQuery)) {
        console.log('🔍 shouldTriggerRevisualization: NO - different data requested');
        return false;
    }
    
    // Priority 4: If isChartOnlyRequest is true from basic detection, trust it
    if (chartIntent.isChartOnlyRequest) {
        console.log('🔍 shouldTriggerRevisualization: YES - isChartOnlyRequest=true');
        return true;
    }
    
    // Priority 5: Chart intent detected with no conflicting keywords - re-visualize
    // This catches cases like "show sales as line chart" after "show sales"
    console.log('🔍 shouldTriggerRevisualization: YES - chart intent with no conflicts');
    return true;
}

/**
 * Get a reason for why we're generating new code instead of re-visualizing
 * Useful for toast notifications
 */
export function getNewCodeReason(newQuery: string, lastExecutedQuery: string | undefined): string | null {
    if (!lastExecutedQuery) {
        return 'No previous results to re-visualize';
    }
    
    const newKeywords = extractKeywords(newQuery);
    const prevKeywords = extractKeywords(lastExecutedQuery);
    
    // Check for new modifiers
    if (newKeywords.modifiers.length > 0) {
        const newModifier = newKeywords.modifiers.find(m => !prevKeywords.modifiers.includes(m));
        if (newModifier) {
            return `Detected "${newModifier}" - generating new analysis`;
        }
    }
    
    // Check for different timeframes
    if (newKeywords.timeframes.length > 0) {
        const newTimeframe = newKeywords.timeframes.find(t => !prevKeywords.timeframes.includes(t));
        if (newTimeframe) {
            return `Different time period detected (${newTimeframe})`;
        }
    }
    
    // Check for different metrics
    if (newKeywords.metrics.length > 0) {
        const newMetric = newKeywords.metrics.find(m => !prevKeywords.metrics.includes(m));
        if (newMetric) {
            return `Different metric detected (${newMetric})`;
        }
    }
    
    // Check for different dimensions
    if (newKeywords.dimensions.length > 0) {
        const newDimension = newKeywords.dimensions.find(d => !prevKeywords.dimensions.includes(d));
        if (newDimension) {
            return `Different grouping detected (${newDimension})`;
        }
    }
    
    return null;
}
