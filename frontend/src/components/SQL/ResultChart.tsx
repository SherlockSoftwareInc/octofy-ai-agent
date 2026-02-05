import React from 'react';
import {
    BarChart,
    Bar,
    LineChart,
    Line,
    PieChart,
    Pie,
    Cell,
    ScatterChart,
    Scatter,
    AreaChart,
    Area,
    RadarChart,
    Radar,
    PolarGrid,
    PolarAngleAxis,
    PolarRadiusAxis,
    Treemap,
    FunnelChart,
    Funnel,
    LabelList,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    Legend,
    ResponsiveContainer
} from 'recharts';
import type { ChartMetadata } from '../../api/client';

interface ResultChartProps {
    data: any[];
    metadata: ChartMetadata;
}

const COLORS = ['#06b6d4', '#8b5cf6', '#f59e0b', '#ec4899', '#10b981', '#3b82f6', '#6366f1', '#14b8a6'];

// Common tooltip style
const TOOLTIP_STYLE = {
    contentStyle: { backgroundColor: '#0f172a', borderColor: '#334155', color: '#f1f5f9', borderRadius: '0.5rem' },
    itemStyle: { color: '#e2e8f0' },
    cursor: { fill: '#334155', opacity: 0.2 }
};

// Format numbers for display
const formatNumber = (value: any) => {
    if (typeof value === 'number') {
        return new Intl.NumberFormat('en-US').format(value);
    }
    return value;
};

const formatCompact = (value: number) => 
    new Intl.NumberFormat('en-US', { notation: "compact", compactDisplay: "short" }).format(value);

export const ResultChart: React.FC<ResultChartProps> = ({ data, metadata }) => {
    // Basic validation
    if (!metadata || metadata.type === 'none') {
        return null;
    }

    // For pie charts, we need at least x_axis OR y_axes
    // For other charts, we need both
    if (metadata.type !== 'pie' && (!metadata.x_axis || !metadata.y_axes || metadata.y_axes.length === 0)) {
        return null;
    }

    if (!data || data.length === 0) {
        return (
            <div className="w-full h-[200px] mt-4 bg-slate-900/50 rounded-xl border border-slate-800 p-4 flex items-center justify-center text-slate-400 text-sm">
                No visual data available
            </div>
        );
    }

    // --- Adaptive Data Processing ---
    const processedData = React.useMemo(() => {
        // For pie charts, limit to top 8 slices + Others
        if (metadata.type === 'pie' && data.length > 8 && metadata.x_axis) {
            const xAxisKey = metadata.x_axis;
            const valueKey = metadata.y_axes[0];

            const sorted = [...data].sort((a, b) => {
                const valA = typeof a[valueKey] === 'number' ? a[valueKey] : 0;
                const valB = typeof b[valueKey] === 'number' ? b[valueKey] : 0;
                return valB - valA;
            });

            const top7 = sorted.slice(0, 7);
            const othersVec = sorted.slice(7);

            if (othersVec.length > 0) {
                const othersItem: any = { [xAxisKey]: 'Others' };
                othersItem[valueKey] = othersVec.reduce((sum, row) => {
                    const val = row[valueKey];
                    return sum + (typeof val === 'number' ? val : 0);
                }, 0);
                return [...top7, othersItem];
            }
            return top7;
        }

        // For column charts, aggregate to Top 10 + "Others" if more than 15 categories
        if ((metadata.type === 'column' || metadata.type === 'stackedColumn') && data.length > 15 && metadata.x_axis) {
            const xAxisKey = metadata.x_axis;
            const sortMetric = metadata.y_axes[0];

            const sorted = [...data].sort((a, b) => {
                const valA = typeof a[sortMetric] === 'number' ? a[sortMetric] : 0;
                const valB = typeof b[sortMetric] === 'number' ? b[sortMetric] : 0;
                return valB - valA;
            });

            const top10 = sorted.slice(0, 10);
            const othersVec = sorted.slice(10);

            if (othersVec.length > 0) {
                const othersItem: any = { [xAxisKey]: 'Others' };
                metadata.y_axes.forEach(yKey => {
                    othersItem[yKey] = othersVec.reduce((sum, row) => {
                        const val = row[yKey];
                        return sum + (typeof val === 'number' ? val : 0);
                    }, 0);
                });
                return [...top10, othersItem];
            }
            return top10;
        }

        return data;
    }, [data, metadata]);

    // --- Layout Logic ---
    const rotateLabels = processedData.length > 10;
    const isStacked = metadata.is_stacked;

    // --- Render Bar Chart (used for column charts) ---
    const renderBarChart = () => (
        <BarChart
            data={processedData}
            margin={{
                top: 20,
                right: 30,
                left: 20,
                bottom: rotateLabels ? 60 : 20,
            }}
        >
            <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.3} />

            <XAxis
                dataKey={metadata.x_axis!}
                stroke="#94a3b8"
                fontSize={12}
                tickLine={false}
                axisLine={{ stroke: '#475569' }}
                tickFormatter={(value) => {
                    if (typeof value === 'string') {
                        return value.length > 15 ? `${value.substring(0, 15)}...` : value;
                    }
                    return value;
                }}
                angle={rotateLabels ? -45 : 0}
                textAnchor={rotateLabels ? "end" : "middle"}
                height={rotateLabels ? 70 : 30}
            />
            <YAxis
                stroke="#94a3b8"
                fontSize={12}
                tickLine={false}
                axisLine={false}
                tickFormatter={formatCompact}
            />

            <Tooltip {...TOOLTIP_STYLE} formatter={formatNumber} />
            <Legend wrapperStyle={{ paddingTop: '10px' }} />
            {metadata.y_axes.map((col, index) => (
                <Bar
                    key={col}
                    dataKey={col}
                    name={col}
                    stackId={isStacked ? "a" : undefined}
                    fill={COLORS[index % COLORS.length]}
                    radius={isStacked ? [0, 0, 0, 0] : [4, 4, 0, 0]}
                    animationDuration={1500}
                />
            ))}
        </BarChart>
    );

    // --- Render Line Chart ---
    const renderLineChart = () => (
        <LineChart
            data={processedData}
            margin={{ top: 20, right: 30, left: 20, bottom: rotateLabels ? 60 : 20 }}
        >
            <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.3} />
            <XAxis
                dataKey={metadata.x_axis!}
                stroke="#94a3b8"
                fontSize={12}
                tickLine={false}
                axisLine={{ stroke: '#475569' }}
                tickFormatter={(value) => {
                    if (typeof value === 'string') {
                        return value.length > 15 ? `${value.substring(0, 15)}...` : value;
                    }
                    // Format dates if applicable
                    if (value instanceof Date) {
                        return value.toLocaleDateString();
                    }
                    return value;
                }}
                angle={rotateLabels ? -45 : 0}
                textAnchor={rotateLabels ? "end" : "middle"}
                height={rotateLabels ? 70 : 30}
            />
            <YAxis
                stroke="#94a3b8"
                fontSize={12}
                tickLine={false}
                axisLine={false}
                tickFormatter={formatCompact}
            />
            <Tooltip {...TOOLTIP_STYLE} formatter={formatNumber} />
            <Legend wrapperStyle={{ paddingTop: '10px' }} />
            {metadata.y_axes.map((col, index) => (
                <Line
                    key={col}
                    type="monotone"
                    dataKey={col}
                    name={col}
                    stroke={COLORS[index % COLORS.length]}
                    strokeWidth={2}
                    dot={{ fill: COLORS[index % COLORS.length], strokeWidth: 2, r: 4 }}
                    activeDot={{ r: 6, strokeWidth: 2 }}
                    animationDuration={1500}
                />
            ))}
        </LineChart>
    );

    // --- Render Pie Chart ---
    const renderPieChart = () => {
        const nameKey = metadata.x_axis || Object.keys(processedData[0])[0];
        const valueKey = metadata.y_axes[0] || Object.keys(processedData[0])[1];

        return (
            <PieChart>
                <Pie
                    data={processedData}
                    dataKey={valueKey}
                    nameKey={nameKey}
                    cx="50%"
                    cy="50%"
                    outerRadius={150}
                    innerRadius={60}
                    paddingAngle={2}
                    animationDuration={1500}
                    label={({ name, percent }) => `${name}: ${percent !== undefined ? (percent * 100).toFixed(0) : '0'}%`}
                    labelLine={{ stroke: '#64748b', strokeWidth: 1 }}
                >
                    {processedData.map((_, index) => (
                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                </Pie>
                <Tooltip {...TOOLTIP_STYLE} formatter={formatNumber} />
                <Legend wrapperStyle={{ paddingTop: '10px' }} />
            </PieChart>
        );
    };

    // --- Render Scatter Chart ---
    const renderScatterChart = () => {
        const xKey = metadata.x_axis!;
        const yKey = metadata.y_axes[0];

        return (
            <ScatterChart margin={{ top: 20, right: 30, left: 20, bottom: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.3} />
                <XAxis
                    type="number"
                    dataKey={xKey}
                    name={xKey}
                    stroke="#94a3b8"
                    fontSize={12}
                    tickLine={false}
                    axisLine={{ stroke: '#475569' }}
                    tickFormatter={formatCompact}
                />
                <YAxis
                    type="number"
                    dataKey={yKey}
                    name={yKey}
                    stroke="#94a3b8"
                    fontSize={12}
                    tickLine={false}
                    axisLine={false}
                    tickFormatter={formatCompact}
                />
                <Tooltip
                    {...TOOLTIP_STYLE}
                    formatter={formatNumber}
                    cursor={{ strokeDasharray: '3 3' }}
                />
                <Legend wrapperStyle={{ paddingTop: '10px' }} />
                <Scatter
                    name={`${xKey} vs ${yKey}`}
                    data={processedData}
                    fill={COLORS[0]}
                    animationDuration={1500}
                />
            </ScatterChart>
        );
    };

    // --- Render Area Chart ---
    const renderAreaChart = () => (
        <AreaChart
            data={processedData}
            margin={{ top: 20, right: 30, left: 20, bottom: rotateLabels ? 60 : 20 }}
        >
            <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.3} />
            <XAxis
                dataKey={metadata.x_axis!}
                stroke="#94a3b8"
                fontSize={12}
                tickLine={false}
                axisLine={{ stroke: '#475569' }}
                angle={rotateLabels ? -45 : 0}
                textAnchor={rotateLabels ? "end" : "middle"}
                height={rotateLabels ? 70 : 30}
            />
            <YAxis
                stroke="#94a3b8"
                fontSize={12}
                tickLine={false}
                axisLine={false}
                tickFormatter={formatCompact}
            />
            <Tooltip {...TOOLTIP_STYLE} formatter={formatNumber} />
            <Legend wrapperStyle={{ paddingTop: '10px' }} />
            {metadata.y_axes.map((col, index) => (
                <Area
                    key={col}
                    type="monotone"
                    dataKey={col}
                    name={col}
                    stroke={COLORS[index % COLORS.length]}
                    fill={COLORS[index % COLORS.length]}
                    fillOpacity={0.3}
                    animationDuration={1500}
                />
            ))}
        </AreaChart>
    );

    // --- Render Radar Chart ---
    const renderRadarChart = () => (
        <RadarChart data={processedData} outerRadius={120}>
            <PolarGrid stroke="#334155" />
            <PolarAngleAxis dataKey={metadata.x_axis!} stroke="#94a3b8" fontSize={12} />
            <PolarRadiusAxis stroke="#94a3b8" fontSize={10} />
            <Tooltip {...TOOLTIP_STYLE} formatter={formatNumber} />
            <Legend wrapperStyle={{ paddingTop: '10px' }} />
            {metadata.y_axes.map((col, index) => (
                <Radar
                    key={col}
                    name={col}
                    dataKey={col}
                    stroke={COLORS[index % COLORS.length]}
                    fill={COLORS[index % COLORS.length]}
                    fillOpacity={0.3}
                    animationDuration={1500}
                />
            ))}
        </RadarChart>
    );

    // --- Render Treemap ---
    const renderTreemap = () => {
        const xKey = metadata.x_axis!;
        const yKey = metadata.y_axes[0];
        
        // Transform data for Treemap (needs 'name', 'size' or hierarchical structure)
        const treemapData = processedData.map((item, idx) => ({
            name: String(item[xKey] || `Item ${idx + 1}`),
            size: typeof item[yKey] === 'number' ? item[yKey] : 0,
            fill: COLORS[idx % COLORS.length]
        }));

        return (
            <Treemap
                width={600}
                height={300}
                data={treemapData}
                dataKey="size"
                aspectRatio={4 / 3}
                stroke="#1e293b"
                animationDuration={1500}
                content={({ x, y, width, height, name, value, fill }: any) => {
                    if (width < 30 || height < 20) return <g />;
                    return (
                        <g>
                            <rect
                                x={x}
                                y={y}
                                width={width}
                                height={height}
                                fill={fill}
                                stroke="#1e293b"
                                strokeWidth={2}
                                rx={4}
                            />
                            {width > 50 && height > 30 && (
                                <>
                                    <text
                                        x={x + width / 2}
                                        y={y + height / 2 - 6}
                                        textAnchor="middle"
                                        fill="#fff"
                                        fontSize={11}
                                        fontWeight={500}
                                    >
                                        {String(name).length > 12 ? `${String(name).slice(0, 12)}...` : name}
                                    </text>
                                    <text
                                        x={x + width / 2}
                                        y={y + height / 2 + 10}
                                        textAnchor="middle"
                                        fill="#e2e8f0"
                                        fontSize={10}
                                    >
                                        {formatNumber(value)}
                                    </text>
                                </>
                            )}
                        </g>
                    );
                }}
            />
        );
    };

    // --- Render Funnel Chart ---
    const renderFunnelChart = () => {
        const xKey = metadata.x_axis!;
        const yKey = metadata.y_axes[0];
        
        // Transform data for Funnel
        const funnelData = processedData
            .map((item, idx) => ({
                name: String(item[xKey] || `Stage ${idx + 1}`),
                value: typeof item[yKey] === 'number' ? item[yKey] : 0,
                fill: COLORS[idx % COLORS.length]
            }))
            .sort((a, b) => b.value - a.value); // Sort descending for funnel shape

        return (
            <FunnelChart>
                <Tooltip
                    contentStyle={{ backgroundColor: '#0f172a', borderColor: '#1e293b', color: '#f1f5f9' }}
                    formatter={(value) => typeof value === 'number' ? value.toLocaleString() : value}
                />
                <Funnel
                    dataKey="value"
                    data={funnelData}
                    isAnimationActive
                >
                    <LabelList
                        position="right"
                        fill="#e2e8f0"
                        stroke="none"
                        dataKey="name"
                        fontSize={12}
                    />
                    <LabelList
                        position="center"
                        fill="#fff"
                        stroke="none"
                        dataKey="value"
                        fontSize={11}
                        formatter={(value) => typeof value === 'number' ? value.toLocaleString() : String(value)}
                    />
                </Funnel>
            </FunnelChart>
        );
    };

    // --- Select Chart Type ---
    const renderChart = () => {
        switch (metadata.type) {
            case 'column':
            case 'stackedColumn':
            case 'clusteredColumn':
                return renderBarChart();
            case 'line':
                return renderLineChart();
            case 'area':
                return renderAreaChart();
            case 'pie':
                return renderPieChart();
            case 'scatter':
                return renderScatterChart();
            case 'radar':
                return renderRadarChart();
            case 'treemap':
                return renderTreemap();
            case 'funnel':
                return renderFunnelChart();
            default:
                return null;
        }
    };

    // Chart type labels for display
    const chartTypeLabels: Record<string, string> = {
        'column': 'Column Chart',
        'stackedColumn': 'Stacked Column Chart',
        'clusteredColumn': 'Clustered Column Chart',
        'line': 'Line Chart',
        'area': 'Area Chart',
        'pie': 'Pie Chart',
        'scatter': 'Scatter Plot',
        'radar': 'Radar Chart',
        'treemap': 'Treemap',
        'funnel': 'Funnel Chart',
    };

    return (
        <div className="w-full bg-slate-900/50 rounded-xl border border-slate-800 p-4 shadow-sm backdrop-blur-sm">
            <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2 flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-cyan-400"></span>
                {chartTypeLabels[metadata.type] || 'Visualization'}
            </h3>
            <ResponsiveContainer width="100%" height={400} aspect={metadata.type === 'pie' ? 1.5 : 2}>
                {renderChart() || <div />}
            </ResponsiveContainer>
        </div>
    );
};
