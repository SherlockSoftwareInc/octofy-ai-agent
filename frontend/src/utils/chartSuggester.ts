
export interface ChartSuggestion {
    type: 'line' | 'bar' | 'pie' | 'scatter' | 'none';
    xAxisKey?: string;
    seriesKeys?: string[];
    reason?: string;
}

export const suggestChart = (data: any[]): ChartSuggestion => {
    if (!data || data.length === 0) {
        return { type: 'none', reason: 'No data' };
    }

    const keys = Object.keys(data[0]);
    if (keys.length < 2) {
        return { type: 'none', reason: 'Not enough columns for a meaningful chart' };
    }

    // Heuristics:
    // 1. Identify "Label" column (String/Date) and "Value" columns (Number)
    // 2. If 1 Label + 1+ Values => Bar Chart (if distinct labels) or Line Chart (if Date/Time)
    // 3. If mostly numbers => Scatter? (Maybe too complex for MVP)

    // Analyze first 5 rows to guess types
    const sample = data.slice(0, 5);
    const typeMap: Record<string, 'string' | 'number' | 'date' | 'boolean'> = {};

    keys.forEach(key => {
        let isNumber = true;
        let isDate = true;

        for (const row of sample) {
            const val = row[key];
            if (val === null || val === undefined) continue;

            if (typeof val === 'number') {
                isDate = false;
                continue;
            }
            if (typeof val === 'string') {
                isNumber = false;
                // Simple date check
                if (isNaN(Date.parse(val))) {
                    isDate = false;
                }
            } else {
                isNumber = false;
                isDate = false;
            }
        }

        if (isNumber) typeMap[key] = 'number';
        else if (isDate) typeMap[key] = 'date';
        else typeMap[key] = 'string';
    });

    const potentialXKeys = keys.filter(k => typeMap[k] === 'string' || typeMap[k] === 'date');
    const potentialSeriesKeys = keys.filter(k => typeMap[k] === 'number');

    if (potentialSeriesKeys.length === 0) {
        return { type: 'none', reason: 'No numeric data to plot' };
    }

    // Priority 1: Date on X-axis => Line Chart
    const dateKey = potentialXKeys.find(k => typeMap[k] === 'date');
    if (dateKey) {
        return {
            type: 'line',
            xAxisKey: dateKey,
            seriesKeys: potentialSeriesKeys,
            reason: 'Detected temporal data'
        };
    }

    // Priority 2: String on X-axis with few unique values => Bar Chart
    // (We don't check unique values here deeply, but assume string is categorical)
    const stringKey = potentialXKeys.find(k => typeMap[k] === 'string');
    if (stringKey) {
        // If too many points, maybe bar chart is crowded, but let's stick to bar for categorical
        return {
            type: 'bar',
            xAxisKey: stringKey,
            seriesKeys: potentialSeriesKeys,
            reason: 'Categorical data detected'
        };
    }

    // Priority 3: No clear X-axis but numbers? 
    // Maybe use index as X? Or if only number columns exist?
    // Let's default to none if no clear dimension
    if (potentialXKeys.length === 0 && potentialSeriesKeys.length > 0) {
        // Maybe the first number is X?
        if (potentialSeriesKeys.length >= 2) {
            return {
                type: 'scatter', // Or line
                xAxisKey: potentialSeriesKeys[0],
                seriesKeys: potentialSeriesKeys.slice(1),
                reason: 'Numeric relationships'
            };
        }
    }

    return { type: 'none', reason: 'Could not determine suitable chart type' };
};
