import React, { useState, useMemo } from 'react';
import { ChevronUp, ChevronDown, ChevronsUpDown } from 'lucide-react';
import { Pagination } from '../Pagination';

interface DataTableProps {
    data: any[];
    columns: string[];
    pageSize?: number;
    title?: string;
}

type SortDirection = 'asc' | 'desc' | null;

interface SortConfig {
    key: string | null;
    direction: SortDirection;
}

const DataTableCell: React.FC<{ value: React.ReactNode; rawValue: string; align: 'left' | 'right' }> = ({ value, rawValue, align }) => {
    const [isExpanded, setIsExpanded] = useState(false);

    return (
        <td
            className={`px-4 py-2 border border-[#444] ${align === 'right' ? 'text-right' : 'text-left'} transition-all duration-200`}
            style={{
                maxWidth: isExpanded ? 'none' : '300px',
                whiteSpace: isExpanded ? 'normal' : 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                cursor: 'pointer'
            }}
            onClick={() => setIsExpanded(!isExpanded)}
            title={rawValue} // Native tooltip
        >
            {value !== null ? (
                value
            ) : (
                <span className="text-slate-600 italic">null</span>
            )}
        </td>
    );
};

export const DataTable: React.FC<DataTableProps> = ({
    data,
    columns,
    pageSize = 10,
    title
}) => {
    const [currentPage, setCurrentPage] = useState(0);
    const [sortConfig, setSortConfig] = useState<SortConfig>({ key: null, direction: null });

    const columnAlignment = useMemo(() => {
        return columns.reduce<Record<string, 'left' | 'right'>>((acc, col) => {
            const values = data.map((row) => row?.[col]).filter((value) => value !== null && value !== undefined);
            const isNumeric = values.length > 0 && values.every((value) => typeof value === 'number' && !Number.isNaN(value));
            acc[col] = isNumeric ? 'right' : 'left';
            return acc;
        }, {});
    }, [columns, data]);

    const formatValue = (value: unknown, align: 'left' | 'right') => {
        if (typeof value === 'number' && align === 'right' && Number.isFinite(value)) {
            return value.toFixed(4);
        }
        if (value !== null && value !== undefined) {
            return typeof value === 'object' ? JSON.stringify(value) : String(value);
        }
        return null;
    };

    const handleSort = (key: string) => {
        let direction: SortDirection = 'asc';
        if (sortConfig.key === key && sortConfig.direction === 'asc') {
            direction = 'desc';
        } else if (sortConfig.key === key && sortConfig.direction === 'desc') {
            direction = null;
        }
        setSortConfig({ key, direction });
    };

    const sortedData = useMemo(() => {
        if (!sortConfig.key || !sortConfig.direction) {
            return data;
        }

        return [...data].sort((a, b) => {
            const aValue = a[sortConfig.key!];
            const bValue = b[sortConfig.key!];

            if (aValue === null) return 1;
            if (bValue === null) return -1;

            if (aValue < bValue) {
                return sortConfig.direction === 'asc' ? -1 : 1;
            }
            if (aValue > bValue) {
                return sortConfig.direction === 'asc' ? 1 : -1;
            }
            return 0;
        });
    }, [data, sortConfig]);

    const paginatedData = useMemo(() => {
        const start = currentPage * pageSize;
        return sortedData.slice(start, start + pageSize);
    }, [sortedData, currentPage, pageSize]);

    // Reset pagination when data changes
    React.useEffect(() => {
        setCurrentPage(0);
    }, [data]);

    if (!data || data.length === 0) {
        return <div className="p-4 text-center text-slate-500 italic">No data available</div>;
    }

    return (
        <div className="w-full">
            {title && (
                <div className="px-4 py-3 bg-slate-800/50 border-b border-slate-700/50 flex justify-between items-center">
                    <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-wider">{title}</h3>
                    <div className="text-xs text-slate-500 font-mono">
                        {data.length} rows &bull; {columns.length} columns
                    </div>
                </div>
            )}

            <div className="overflow-x-auto border border-[#444] rounded-lg">
                <table className="w-full text-xs text-slate-300 border-collapse">
                    <thead className="text-xs uppercase bg-slate-800 text-slate-400">
                        <tr>
                            {columns.map((col) => (
                                <th
                                    key={col}
                                    className={`px-4 py-3 cursor-pointer hover:bg-slate-700/50 transition-colors group select-none border border-[#444] ${columnAlignment[col] === 'right' ? 'text-right' : 'text-left'}`}
                                    style={{ minWidth: '150px' }}
                                    onClick={() => handleSort(col)}
                                >
                                    <div className={`flex items-center gap-2 ${columnAlignment[col] === 'right' ? 'justify-end' : 'justify-start'}`}>
                                        <span className="truncate" title={col}>{col}</span>
                                        {/* Sort Icon */}
                                        <span className="text-slate-600 group-hover:text-slate-400 flex-shrink-0">
                                            {sortConfig.key === col ? (
                                                sortConfig.direction === 'asc' ? <ChevronUp size={14} /> :
                                                    sortConfig.direction === 'desc' ? <ChevronDown size={14} /> :
                                                        <ChevronsUpDown size={14} />
                                            ) : (
                                                <ChevronsUpDown size={14} className="opacity-0 group-hover:opacity-100 transition-opacity" />
                                            )}
                                        </span>
                                    </div>
                                </th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {paginatedData.map((row, rIdx) => (
                            <tr key={rIdx} className="bg-slate-900/50 hover:bg-slate-800/60 transition-colors">
                                {columns.map((col) => {
                                    const formattedValue = formatValue(row[col], columnAlignment[col]);
                                    const rawValue = row[col] !== null && row[col] !== undefined
                                        ? (typeof row[col] === 'object' ? JSON.stringify(row[col]) : String(row[col]))
                                        : 'null';

                                    // Local state for expansion could be tricky in a loop without extraction, 
                                    // but we can use a class-based approach or a simple CSS toggle if we had it.
                                    // For React, best to extract Cell or use a simple toggle.
                                    // Let's create a small internal component for the Cell to handle state.
                                    return (
                                        <DataTableCell
                                            key={`${rIdx}-${col}`}
                                            value={formattedValue}
                                            rawValue={rawValue}
                                            align={columnAlignment[col]}
                                        />
                                    );
                                })}
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            {data.length > pageSize && (
                <Pagination
                    currentPage={currentPage}
                    totalItems={data.length}
                    pageSize={pageSize}
                    onPageChange={setCurrentPage}
                />
            )}
        </div>
    );
};
