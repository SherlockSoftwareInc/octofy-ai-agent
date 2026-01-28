/**
 * Chart Intent Detection for Frontend
 * 
 * Detects user intent to change chart types from natural language queries.
 * Mirrors the backend chart_intent_service.py for consistent behavior.
 */

export type ChartType = 'bar' | 'line' | 'pie' | 'scatter' | 'kpi' | 'none';

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
    // Line chart patterns
    { pattern: /\b(line\s*(chart|graph|plot)?|trend\s*line)\b/i, chartType: 'line' },
    { pattern: /\b(time\s*series|over\s*time)\b/i, chartType: 'line' },
    
    // Bar chart patterns  
    { pattern: /\b(bar\s*(chart|graph)?|column\s*chart|histogram)\b/i, chartType: 'bar' },
    
    // Pie chart patterns
    { pattern: /\b(pie\s*(chart)?|donut|doughnut)\b/i, chartType: 'pie' },
    { pattern: /\bproportion(s)?\b/i, chartType: 'pie' },
    
    // Scatter plot patterns
    { pattern: /\b(scatter\s*(plot|chart)?|x\s*y\s*plot|correlation)\b/i, chartType: 'scatter' },
    { pattern: /\bplot\s+\w+\s+(vs|versus|against)\s+\w+/i, chartType: 'scatter' },
    
    // KPI patterns
    { pattern: /\b(kpi|metric|single\s*value|number\s*card)\b/i, chartType: 'kpi' },
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
        /\s*(as|in|using)\s+a?\s*(line|bar|pie|scatter|column|donut|doughnut)\s*(chart|graph|plot)?\s*/gi,
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
        kpi: 'KPI Card',
        none: 'No Chart',
    };
    return labels[chartType] || chartType;
}
