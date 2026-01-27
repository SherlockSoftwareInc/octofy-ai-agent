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

export const DataTable: React.FC<DataTableProps> = ({
    data,
    columns,
    pageSize = 10,
    title
}) => {
    const [currentPage, setCurrentPage] = useState(0);
    const [sortConfig, setSortConfig] = useState<SortConfig>({ key: null, direction: null });

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

            <div className="overflow-x-auto">
                <table className="w-full text-xs text-left text-slate-300">
                    <thead className="text-xs uppercase bg-slate-800 text-slate-400">
                        <tr>
                            {columns.map((col) => (
                                <th
                                    key={col}
                                    className="px-4 py-3 whitespace-nowrap cursor-pointer hover:bg-slate-700/50 transition-colors group select-none"
                                    onClick={() => handleSort(col)}
                                >
                                    <div className="flex items-center gap-2">
                                        <span>{col}</span>
                                        <span className="text-slate-600 group-hover:text-slate-400">
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
                            <tr key={rIdx} className="bg-slate-900/50 border-b border-slate-800 last:border-0 hover:bg-slate-800/50 transition-colors">
                                {columns.map((col) => (
                                    <td key={col} className="px-4 py-2 whitespace-nowrap border-r border-slate-800/30 last:border-r-0">
                                        {row[col] !== null && row[col] !== undefined ? (
                                            typeof row[col] === 'object' ? JSON.stringify(row[col]) : String(row[col])
                                        ) : (
                                            <span className="text-slate-600 italic">null</span>
                                        )}
                                    </td>
                                ))}
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
