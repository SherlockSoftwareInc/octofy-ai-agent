import React, { useEffect, useId, useState } from 'react';
import { api } from '../api/client';
import type { DataSourceResponse } from '../api/client';
import { Database, AlertCircle } from 'lucide-react';

interface DataSourceSelectorProps {
    selectedSourceId: string;
    onSourceChange: (sourceId: string) => void;
    disabled?: boolean;
}

export const DataSourceSelector: React.FC<DataSourceSelectorProps> = ({
    selectedSourceId,
    onSourceChange,
    disabled = false
}) => {
    const selectId = useId();
    const [dataSources, setDataSources] = useState<DataSourceResponse[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const fetchDataSources = async () => {
            setLoading(true);
            setError(null);
            try {
                const response = await api.dataSources.getAll();
                const sources = response.data_sources || [];
                setDataSources(sources);

                // Auto-select primary source if nothing selected yet
                if (!selectedSourceId && sources.length > 0) {
                    const primary = sources.find(s => s.is_primary);
                    onSourceChange(primary ? primary.source_id : sources[0].source_id);
                }
            } catch (err) {
                console.error('Failed to fetch data sources:', err);
                setError('Failed to load data sources');
            } finally {
                setLoading(false);
            }
        };

        fetchDataSources();
    }, []); // eslint-disable-line react-hooks/exhaustive-deps

    if (loading) {
        return (
            <div className="flex items-center gap-2 text-slate-400 text-sm py-2">
                <Database size={16} className="animate-pulse" />
                <span>Loading data sources...</span>
            </div>
        );
    }

    if (error) {
        return (
            <div className="flex items-center gap-2 text-amber-400 text-sm py-2">
                <AlertCircle size={16} />
                <span>{error}</span>
            </div>
        );
    }

    if (dataSources.length === 0) {
        return (
            <div className="flex items-center gap-2 text-amber-400 text-sm py-2">
                <AlertCircle size={16} />
                <span>No data sources configured. Please add a data source first.</span>
            </div>
        );
    }

    return (
        <div className="flex items-center gap-3">
            <label
                htmlFor={selectId}
                className="flex items-center gap-2 text-slate-300 text-sm font-medium whitespace-nowrap"
            >
                <Database size={16} className="text-slate-400" />
                Data Source:
            </label>
            <select
                id={selectId}
                value={selectedSourceId}
                onChange={(e) => onSourceChange(e.target.value)}
                disabled={disabled}
                className="flex-1 bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-indigo-500 transition disabled:opacity-50 disabled:cursor-not-allowed"
                title="Data source"
            >
                {dataSources.map((ds) => (
                    <option key={ds.source_id} value={ds.source_id}>
                        {ds.friendly_name}{ds.is_primary ? ' (Primary)' : ''} — {ds.database_name}
                    </option>
                ))}
            </select>
        </div>
    );
};
