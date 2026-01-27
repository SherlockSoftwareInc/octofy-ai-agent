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

    if (!data || data.length === 0) {
        return (
            <div className="w-full h-[200px] mt-4 bg-slate-900/50 rounded-xl border border-slate-800 p-4 flex items-center justify-center text-slate-400 text-sm">
                No visual data available
            </div>
        );
    }

    // --- Adaptive Data Processing ---
    const processedData = React.useMemo(() => {
        // If more than 15 categories, aggregate to Top 10 + "Others"
        if (data.length > 15 && metadata.x_axis) {
            const xAxisKey = metadata.x_axis;
            // Sort by the first Y-axis value (descending) to find top items
            // Heuristic available: Sum all Y attributes or just pick the first.
            // Using first Y axis for sorting logic.
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
                // Sum up numeric columns for "Others"
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

    // --- Adaptive Layout Logic ---
    const useHorizontalLayout = processedData.length > 20; // Unlikely if aggregated, but good safety
    const rotateLabels = processedData.length > 10;
    const isStacked = metadata.is_stacked;

    const renderChart = () => {
        if (metadata.type === 'bar' || metadata.type === 'stacked-bar') {
            return (
                <BarChart
                    data={processedData}
                    layout={useHorizontalLayout ? 'vertical' : 'horizontal'}
                    margin={{
                        top: 20,
                        right: 30,
                        left: 20,
                        bottom: useHorizontalLayout ? 5 : (rotateLabels ? 60 : 20), // Extra bottom margin for rotated labels
                    }}
                >
                    <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.3} horizontal={!useHorizontalLayout} vertical={useHorizontalLayout} />

                    {useHorizontalLayout ? (
                        // Horizontal Layout: Y is Category, X is Number
                        <>
                            <XAxis type="number" stroke="#94a3b8" fontSize={12} tickLine={false} axisLine={false}
                                tickFormatter={(value) => new Intl.NumberFormat('en-US', { notation: "compact", compactDisplay: "short" }).format(value)} />
                            <YAxis type="category" dataKey={metadata.x_axis!} stroke="#94a3b8" fontSize={12} tickLine={false} axisLine={{ stroke: '#475569' }} width={100} />
                        </>
                    ) : (
                        // Vertical Layout: X is Category, Y is Number
                        <>
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
                                tickFormatter={(value) => new Intl.NumberFormat('en-US', { notation: "compact", compactDisplay: "short" }).format(value)}
                            />
                        </>
                    )}

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
                            radius={useHorizontalLayout ? [0, 4, 4, 0] : (isStacked ? [0, 0, 0, 0] : [4, 4, 0, 0])}
                            animationDuration={1500}
                        />
                    ))}
                </BarChart>
            );
        }
        return null;
    };

    return (
        <div className="w-full bg-slate-900/50 rounded-xl border border-slate-800 p-4 shadow-sm backdrop-blur-sm">
            <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2 flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-cyan-400"></span>
                Visualization
            </h3>
            <ResponsiveContainer width="100%" height={400} aspect={2}>
                {renderChart() || <div />}
            </ResponsiveContainer>
        </div>
    );
};
