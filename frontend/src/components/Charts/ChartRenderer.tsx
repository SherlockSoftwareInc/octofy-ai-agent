import React from 'react';
import {
    LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
    ScatterChart, Scatter, AreaChart, Area, RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
    Treemap, PieChart, Pie, Cell, FunnelChart, Funnel, LabelList
} from 'recharts';
import type { ChartSuggestion } from '../../utils/chartSuggester';

interface ChartRendererProps {
    data: any[];
    suggestion: ChartSuggestion;
}

const DEFAULT_COLORS = ['#10b981', '#3b82f6', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899'];

export const ChartRenderer: React.FC<ChartRendererProps> = ({ data, suggestion }) => {
    const colors = suggestion.colors && suggestion.colors.length > 0 ? suggestion.colors : DEFAULT_COLORS;
    if (suggestion.type === 'none' || !suggestion.xAxisKey || !suggestion.seriesKeys) {
        return <div className="text-slate-500 text-xs italic p-4">Visualization not available</div>;
    }

    // Render logic based on type
    const renderChart = () => {
        switch (suggestion.type) {
            case 'line':
                return (
                    <LineChart data={data}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                        <XAxis
                            dataKey={suggestion.xAxisKey}
                            stroke="#94a3b8"
                            fontSize={12}
                            tickFormatter={(val) => {
                                // Truncate long labels
                                return String(val).length > 10 ? String(val).substring(0, 10) + '...' : String(val);
                            }}
                        />
                        <YAxis stroke="#94a3b8" fontSize={12} />
                        <Tooltip
                            contentStyle={{ backgroundColor: '#0f172a', borderColor: '#1e293b', color: '#f1f5f9' }}
                            itemStyle={{ color: '#e2e8f0' }}
                        />
                        <Legend />
                        {suggestion.seriesKeys!.map((key, index) => (
                            <Line
                                key={key}
                                type="monotone"
                                dataKey={key}
                                stroke={colors[index % colors.length]}
                                strokeWidth={2}
                                dot={{ r: 3, fill: colors[index % colors.length] }}
                                activeDot={{ r: 5 }}
                            />
                        ))}
                    </LineChart>
                );
            case 'bar':
                return (
                    <BarChart data={data}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} />
                        <XAxis
                            dataKey={suggestion.xAxisKey}
                            stroke="#94a3b8"
                            fontSize={12}
                            tickFormatter={(val) => {
                                return String(val).length > 10 ? String(val).substring(0, 10) + '...' : String(val);
                            }}
                        />
                        <YAxis stroke="#94a3b8" fontSize={12} />
                        <Tooltip
                            cursor={{ fill: '#334155', opacity: 0.2 }}
                            contentStyle={{ backgroundColor: '#0f172a', borderColor: '#1e293b', color: '#f1f5f9' }}
                        />
                        <Legend />
                        {suggestion.seriesKeys!.map((key, index) => (
                            <Bar
                                key={key}
                                dataKey={key}
                                fill={colors[index % colors.length]}
                                radius={[4, 4, 0, 0]}
                            />
                        ))}
                    </BarChart>
                );
            case 'scatter':
                return (
                    <ScatterChart>
                        <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                        <XAxis
                            dataKey={suggestion.xAxisKey}
                            type="number"
                            name={suggestion.xAxisKey}
                            stroke="#94a3b8"
                            fontSize={12}
                        />
                        <YAxis
                            dataKey={suggestion.seriesKeys![0]}
                            type="number"
                            name={suggestion.seriesKeys![0]}
                            stroke="#94a3b8"
                            fontSize={12}
                        />
                        <Tooltip cursor={{ strokeDasharray: '3 3' }} contentStyle={{ backgroundColor: '#0f172a', borderColor: '#1e293b', color: '#f1f5f9' }} />
                        <Legend />
                        <Scatter name={suggestion.seriesKeys![0]} data={data} fill="#8884d8" />
                    </ScatterChart>
                );
            case 'pie':
                // Transform data for pie chart
                const pieData = data.map((item, index) => ({
                    name: item[suggestion.xAxisKey!] || `Item ${index + 1}`,
                    value: item[suggestion.seriesKeys![0]] || 0,
                }));
                
                return (
                    <PieChart>
                        <Pie
                            data={pieData}
                            dataKey="value"
                            nameKey="name"
                            cx="50%"
                            cy="50%"
                            outerRadius={80}
                            label={({ name, percent }) => `${name}: ${((percent ?? 0) * 100).toFixed(0)}%`}
                            labelLine={{ stroke: '#94a3b8' }}
                        >
                            {pieData.map((_, index) => (
                                <Cell key={`cell-${index}`} fill={colors[index % colors.length]} />
                            ))}
                        </Pie>
                        <Tooltip
                            contentStyle={{ backgroundColor: '#0f172a', borderColor: '#1e293b', color: '#f1f5f9' }}
                            formatter={(value) => typeof value === 'number' ? value.toLocaleString() : value}
                        />
                        <Legend />
                    </PieChart>
                );
            case 'column':
                // Column chart is essentially a bar chart with vertical bars (default in Recharts BarChart)
                return (
                    <BarChart data={data}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} />
                        <XAxis
                            dataKey={suggestion.xAxisKey}
                            stroke="#94a3b8"
                            fontSize={12}
                            tickFormatter={(val) => {
                                return String(val).length > 10 ? String(val).substring(0, 10) + '...' : String(val);
                            }}
                        />
                        <YAxis stroke="#94a3b8" fontSize={12} />
                        <Tooltip
                            cursor={{ fill: '#334155', opacity: 0.2 }}
                            contentStyle={{ backgroundColor: '#0f172a', borderColor: '#1e293b', color: '#f1f5f9' }}
                        />
                        <Legend />
                        {suggestion.seriesKeys!.map((key, index) => (
                            <Bar
                                key={key}
                                dataKey={key}
                                fill={colors[index % colors.length]}
                                radius={[4, 4, 0, 0]}
                            />
                        ))}
                    </BarChart>
                );
            case 'stackedBar':
                return (
                    <BarChart data={data} layout="vertical">
                        <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                        <XAxis type="number" stroke="#94a3b8" fontSize={12} />
                        <YAxis
                            dataKey={suggestion.xAxisKey}
                            type="category"
                            stroke="#94a3b8"
                            fontSize={12}
                            width={100}
                            tickFormatter={(val) => {
                                return String(val).length > 15 ? String(val).substring(0, 15) + '...' : String(val);
                            }}
                        />
                        <Tooltip
                            contentStyle={{ backgroundColor: '#0f172a', borderColor: '#1e293b', color: '#f1f5f9' }}
                        />
                        <Legend />
                        {suggestion.seriesKeys!.map((key, index) => (
                            <Bar
                                key={key}
                                dataKey={key}
                                stackId="stack"
                                fill={colors[index % colors.length]}
                            />
                        ))}
                    </BarChart>
                );
            case 'stackedColumn':
                return (
                    <BarChart data={data}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} />
                        <XAxis
                            dataKey={suggestion.xAxisKey}
                            stroke="#94a3b8"
                            fontSize={12}
                            tickFormatter={(val) => {
                                return String(val).length > 10 ? String(val).substring(0, 10) + '...' : String(val);
                            }}
                        />
                        <YAxis stroke="#94a3b8" fontSize={12} />
                        <Tooltip
                            cursor={{ fill: '#334155', opacity: 0.2 }}
                            contentStyle={{ backgroundColor: '#0f172a', borderColor: '#1e293b', color: '#f1f5f9' }}
                        />
                        <Legend />
                        {suggestion.seriesKeys!.map((key, index) => (
                            <Bar
                                key={key}
                                dataKey={key}
                                stackId="stack"
                                fill={colors[index % colors.length]}
                                radius={index === suggestion.seriesKeys!.length - 1 ? [4, 4, 0, 0] : [0, 0, 0, 0]}
                            />
                        ))}
                    </BarChart>
                );
            case 'clusteredColumn':
                // Clustered column is the default grouped bar chart behavior
                return (
                    <BarChart data={data}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} />
                        <XAxis
                            dataKey={suggestion.xAxisKey}
                            stroke="#94a3b8"
                            fontSize={12}
                            tickFormatter={(val) => {
                                return String(val).length > 10 ? String(val).substring(0, 10) + '...' : String(val);
                            }}
                        />
                        <YAxis stroke="#94a3b8" fontSize={12} />
                        <Tooltip
                            cursor={{ fill: '#334155', opacity: 0.2 }}
                            contentStyle={{ backgroundColor: '#0f172a', borderColor: '#1e293b', color: '#f1f5f9' }}
                        />
                        <Legend />
                        {suggestion.seriesKeys!.map((key, index) => (
                            <Bar
                                key={key}
                                dataKey={key}
                                fill={colors[index % colors.length]}
                                radius={[4, 4, 0, 0]}
                            />
                        ))}
                    </BarChart>
                );
            case 'area':
                return (
                    <AreaChart data={data}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                        <XAxis
                            dataKey={suggestion.xAxisKey}
                            stroke="#94a3b8"
                            fontSize={12}
                            tickFormatter={(val) => {
                                return String(val).length > 10 ? String(val).substring(0, 10) + '...' : String(val);
                            }}
                        />
                        <YAxis stroke="#94a3b8" fontSize={12} />
                        <Tooltip
                            contentStyle={{ backgroundColor: '#0f172a', borderColor: '#1e293b', color: '#f1f5f9' }}
                            itemStyle={{ color: '#e2e8f0' }}
                        />
                        <Legend />
                        {suggestion.seriesKeys!.map((key, index) => (
                            <Area
                                key={key}
                                type="monotone"
                                dataKey={key}
                                stroke={colors[index % colors.length]}
                                fill={colors[index % colors.length]}
                                fillOpacity={0.6}
                                strokeWidth={2}
                            />
                        ))}
                    </AreaChart>
                );
            case 'radar':
                return (
                    <RadarChart data={data}>
                        <PolarGrid stroke="#334155" />
                        <PolarAngleAxis
                            dataKey={suggestion.xAxisKey}
                            stroke="#94a3b8"
                            fontSize={12}
                            tick={{ fill: '#94a3b8' }}
                        />
                        <PolarRadiusAxis stroke="#94a3b8" fontSize={10} />
                        <Tooltip
                            contentStyle={{ backgroundColor: '#0f172a', borderColor: '#1e293b', color: '#f1f5f9' }}
                        />
                        <Legend />
                        {suggestion.seriesKeys!.map((key, index) => (
                            <Radar
                                key={key}
                                name={key}
                                dataKey={key}
                                stroke={colors[index % colors.length]}
                                fill={colors[index % colors.length]}
                                fillOpacity={0.5}
                                strokeWidth={2}
                            />
                        ))}
                    </RadarChart>
                );
            case 'treemap': {
                // Transform data for treemap - create flat array with size property
                const treemapData = data
                    .map((item, index) => ({
                        name: String(item[suggestion.xAxisKey!] || `Item ${index + 1}`),
                        size: Number(item[suggestion.seriesKeys![0]]) || 0,
                    }))
                    .filter(item => item.size > 0); // Filter out zero/negative values
                
                if (treemapData.length === 0) {
                    return <div className="text-slate-500 text-xs italic p-4">No data available for treemap</div>;
                }
                
                // Treemap needs to be rendered without ResponsiveContainer for custom content
                return (
                    <Treemap
                        width={600}
                        height={256}
                        data={treemapData}
                        dataKey="size"
                        aspectRatio={4 / 3}
                        stroke="#0f172a"
                        fill="#10b981"
                        content={({ x, y, width, height, index, name, value }) => {
                            // Skip invalid dimensions
                            if (!width || !height || width < 5 || height < 5) {
                                return <g />;
                            }
                            const colorIndex = typeof index === 'number' ? index : 0;
                            return (
                                <g>
                                    <rect
                                        x={x}
                                        y={y}
                                        width={width}
                                        height={height}
                                        style={{
                                            fill: colors[colorIndex % colors.length],
                                            stroke: '#0f172a',
                                            strokeWidth: 2,
                                        }}
                                    />
                                    {width > 50 && height > 30 && (
                                        <>
                                            <text
                                                x={x + width / 2}
                                                y={y + height / 2 - 8}
                                                textAnchor="middle"
                                                fill="#fff"
                                                fontSize={12}
                                                fontWeight="bold"
                                            >
                                                {String(name).length > 15
                                                    ? String(name).substring(0, 15) + '...'
                                                    : name}
                                            </text>
                                            <text
                                                x={x + width / 2}
                                                y={y + height / 2 + 8}
                                                textAnchor="middle"
                                                fill="#e2e8f0"
                                                fontSize={11}
                                            >
                                                {typeof value === 'number' ? value.toLocaleString() : value}
                                            </text>
                                        </>
                                    )}
                                </g>
                            );
                        }}
                    />
                );
            }
            case 'funnel': {
                // Transform data for funnel chart
                const funnelData = data
                    .map((item, index) => ({
                        name: String(item[suggestion.xAxisKey!] || `Stage ${index + 1}`),
                        value: Number(item[suggestion.seriesKeys![0]]) || 0,
                        fill: colors[index % colors.length],
                    }))
                    .filter(item => item.value > 0)
                    .sort((a, b) => b.value - a.value); // Sort descending for funnel effect
                
                if (funnelData.length === 0) {
                    return <div className="text-slate-500 text-xs italic p-4">No data available for funnel chart</div>;
                }
                
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
            }
            default:
                return null;
        }
    };

    // Special case: Treemap doesn't work well with ResponsiveContainer
    if (suggestion.type === 'treemap') {
        return (
            <div className="w-full h-64 mt-4 overflow-auto">
                {renderChart()}
            </div>
        );
    }

    return (
        <div className="w-full h-64 mt-4">
            <ResponsiveContainer width="100%" height="100%">
                {renderChart() || <div></div>}
            </ResponsiveContainer>
        </div>
    );
};
