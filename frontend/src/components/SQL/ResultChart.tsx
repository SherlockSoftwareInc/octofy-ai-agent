import React from 'react';
import {
    BarChart,
    Bar,
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

export const ResultChart: React.FC<ResultChartProps> = ({ data, metadata }) => {
    // Basic validation
    if (!metadata || metadata.type === 'none' || !metadata.x_axis || !metadata.y_axes || metadata.y_axes.length === 0) {
        return null;
    }

    if (data.length === 0) {
        return (
            <div className="w-full h-[200px] mt-4 bg-slate-900/50 rounded-xl border border-slate-800 p-4 flex items-center justify-center text-slate-400 text-sm">
                No visual data available
            </div>
        );
    }

    const renderChart = () => {
        const isStacked = metadata.is_stacked;

        if (metadata.type === 'bar' || metadata.type === 'stacked-bar') {
            return (
                <BarChart
                    data={data}
                    margin={{
                        top: 20,
                        right: 30,
                        left: 20,
                        bottom: 5,
                    }}
                >
                    <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.3} vertical={false} />
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
                        // Rotate labels if there are many items
                        angle={data.length > 8 ? -45 : 0}
                        textAnchor={data.length > 8 ? "end" : "middle"}
                        height={data.length > 8 ? 70 : 30}
                    />
                    <YAxis
                        stroke="#94a3b8"
                        fontSize={12}
                        tickLine={false}
                        axisLine={false}
                        tickFormatter={(value) => new Intl.NumberFormat('en-US', { notation: "compact", compactDisplay: "short" }).format(value)}
                    />
                    <Tooltip
                        contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', color: '#f1f5f9', borderRadius: '0.5rem' }}
                        itemStyle={{ color: '#e2e8f0' }}
                        formatter={(value: any) => {
                            if (typeof value === 'number') {
                                return new Intl.NumberFormat('en-US').format(value);
                            }
                            return value;
                        }}
                        cursor={{ fill: '#334155', opacity: 0.2 }}
                    />
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
        }
        return null;
    };

    return (
        <div className="w-full h-[400px] mt-6 bg-slate-900/50 rounded-xl border border-slate-800 p-4 shadow-sm backdrop-blur-sm">
            <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2 flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-cyan-400"></span>
                Visualization
            </h3>
            <ResponsiveContainer width="100%" height="90%">
                {renderChart() || <div />}
            </ResponsiveContainer>
        </div>
    );
};
