import React from 'react';
import {
    LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
    ScatterChart, Scatter
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
            default:
                return null;
        }
    };

    return (
        <div className="w-full h-64 mt-4">
            <ResponsiveContainer width="100%" height="100%">
                {renderChart() || <div></div>}
            </ResponsiveContainer>
        </div>
    );
};
