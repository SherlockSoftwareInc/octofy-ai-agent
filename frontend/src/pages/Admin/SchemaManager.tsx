import React, { useEffect, useState, useMemo } from 'react';
import { api } from '../../api/client';
import type { AdminSchemaStatus } from '../../api/client';
import { RefreshCw, CheckCircle, AlertCircle, Play, Edit, Trash2, Download, Upload, Loader2, PlayCircle, Search } from 'lucide-react';
import { SchemaDescriptionEditor } from '../../components/SchemaDescriptionEditor';
import { Pagination } from '../../components/Pagination';

interface UploadStatus {
    status: 'idle' | 'loading' | 'success' | 'error';
    message?: string;
    rowsProcessed?: number;
    totalRows?: number;
}

interface BatchSyncResult {
    table_name: string;
    schema_name: string;
    success: boolean;
    message: string;
}

interface BatchSyncResponse {
    total: number;
    successful: number;
    failed: number;
    results: BatchSyncResult[];
}

interface SchemaManagerProps {
    onUploadStateChange?: (isUploading: boolean) => void;
}

export const SchemaManager: React.FC<SchemaManagerProps> = ({ onUploadStateChange }) => {
    const [schemas, setSchemas] = useState<AdminSchemaStatus[]>([]);
    const [loading, setLoading] = useState(false);
    const [syncing, setSyncing] = useState<string | null>(null);
    const [syncingAll, setSyncingAll] = useState(false);
    const [editingSchema, setEditingSchema] = useState<AdminSchemaStatus | null>(null);
    const [showEditModal, setShowEditModal] = useState(false);
    const [uploadStatus, setUploadStatus] = useState<UploadStatus>({ status: 'idle' });
    const [uploadProgress, setUploadProgress] = useState(0);
    const [uploadMode, setUploadMode] = useState<'append' | 'replace'>('append');
    const [showBatchSyncDialog, setShowBatchSyncDialog] = useState(false);
    const [batchSyncInput, setBatchSyncInput] = useState('');
    const [batchSyncing, setBatchSyncing] = useState(false);
    const [batchSyncResults, setBatchSyncResults] = useState<BatchSyncResponse | null>(null);
    const [searchQuery, setSearchQuery] = useState('');
    const [currentPage, setCurrentPage] = useState(0);

    // Prevent page navigation during upload
    useEffect(() => {
        const handleBeforeUnload = (e: BeforeUnloadEvent) => {
            if (uploadStatus.status === 'loading') {
                e.preventDefault();
                e.returnValue = 'Upload in progress. Are you sure you want to leave?';
                return 'Upload in progress. Are you sure you want to leave?';
            }
        };

        window.addEventListener('beforeunload', handleBeforeUnload);
        return () => window.removeEventListener('beforeunload', handleBeforeUnload);
    }, [uploadStatus.status]);

    // Notify parent when upload state changes
    useEffect(() => {
        if (onUploadStateChange) {
            onUploadStateChange(uploadStatus.status === 'loading');
        }
    }, [uploadStatus.status, onUploadStateChange]);

    const fetchData = async () => {
        setLoading(true);
        try {
            const data = await api.admin.getSchemaStatus();
            if (Array.isArray(data)) {
                setSchemas(data);
            } else {
                console.warn("Invalid schema data received:", data);
                setSchemas([]);
            }
        } catch (e) {
            console.error("Failed to fetch schemas", e);
        } finally {
            setLoading(false);
        }
    };

    const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0];
        if (!file) return;

        // Validate file type - Excel only
        if (!file.name.endsWith('.xlsx') && !file.name.endsWith('.xls')) {
            setUploadStatus({
                status: 'error',
                message: 'Please upload an Excel file (.xlsx or .xls)',
            });
            return;
        }

        setUploadStatus({ status: 'loading' });
        setUploadProgress(0);

        try {
            const response = await api.admin.ingestSchemas(file, uploadMode, (progress) => {
                setUploadProgress(progress.percentage);
            });

            setUploadStatus({
                status: 'success',
                message: response.message,
                rowsProcessed: response.rows_processed,
                totalRows: response.total_rows,
            });

            // Reload schemas after successful upload
            setTimeout(() => fetchData(), 1000);
        } catch (error) {
            const errorWithResponse = error as { response?: { data?: { detail?: string } } };
            setUploadStatus({
                status: 'error',
                message: errorWithResponse.response?.data?.detail || 'Error uploading file',
            });
        }

        // Reset file input
        event.target.value = '';
    };

    const handleSync = async (schema: string, table: string) => {
        setSyncing(`${schema}.${table}`);
        try {
            await api.admin.syncTable(schema, table);
            await fetchData(); // Refresh status
        } catch (error) {
            console.error(error);
            alert(`Failed to sync ${table}`);
        } finally {
            setSyncing(null);
        }
    };

    const handleEdit = (schema: AdminSchemaStatus) => {
        setEditingSchema(schema);
        setShowEditModal(true);
    };

    const handleSaveDescription = async (newDescription: string) => {
        if (!editingSchema) return;

        await api.admin.updateSchemaDescription(
            editingSchema.schema_name,
            editingSchema.table_name,
            newDescription
        );
        await fetchData(); // Refresh status
    };

    const handleDelete = async (schema: AdminSchemaStatus) => {
        const confirmed = window.confirm(
            `Are you sure you want to delete ${schema.schema_name}.${schema.table_name} from the vector database? This action cannot be undone.`
        );

        if (!confirmed) return;

        try {
            await api.admin.deleteSchema(schema.schema_name, schema.table_name);
            await fetchData(); // Refresh status
        } catch (error) {
            console.error(error);
            alert(`Failed to delete ${schema.table_name}`);
        }
    };

    const handleSyncAll = async () => {
        const confirmed = window.confirm(
            'This will sync all database schemas and rebuild the vector index. This may take a few minutes. Continue?'
        );

        if (!confirmed) return;

        setSyncingAll(true);
        try {
            await api.admin.syncAllSchemas();
            await fetchData(); // Refresh status
            alert('Successfully synced all schemas and rebuilt the vector index!');
        } catch (error) {
            console.error(error);
            alert('Failed to sync schemas');
        } finally {
            setSyncingAll(false);
        }
    };

    const handleBatchSync = async () => {
        if (!batchSyncInput.trim()) {
            alert('Please enter at least one table name');
            return;
        }

        setBatchSyncing(true);
        setBatchSyncResults(null);

        try {
            // Parse input - split by comma or newline
            const tableNames = batchSyncInput
                .split(/[,\n]+/)
                .map(name => name.trim())
                .filter(name => name.length > 0);

            if (tableNames.length === 0) {
                alert('No valid table names found');
                return;
            }

            const results = await api.admin.batchSyncTables(tableNames);
            setBatchSyncResults(results);

            // Refresh schema list
            await fetchData();
        } catch (error) {
            const errorWithResponse = error as { response?: { data?: { detail?: string } }; message?: string };
            alert(`Batch sync failed: ${errorWithResponse.response?.data?.detail || errorWithResponse.message || 'Unknown error'}`);
        } finally {
            setBatchSyncing(false);
        }
    };

    const handleCloseBatchSyncDialog = () => {
        setShowBatchSyncDialog(false);
        setBatchSyncInput('');
        setBatchSyncResults(null);
    };

    // Filter and paginate schemas
    const filteredAndPaginatedSchemas = useMemo(() => {
        const PAGE_SIZE = 50;

        // Filter by search query
        let filtered = schemas;
        if (searchQuery.trim()) {
            const query = searchQuery.toLowerCase();
            filtered = schemas.filter(schema =>
                schema.table_name.toLowerCase().includes(query) ||
                schema.schema_name.toLowerCase().includes(query) ||
                (schema.description && schema.description.toLowerCase().includes(query))
            );
        }

        // Paginate
        const startIndex = currentPage * PAGE_SIZE;
        const endIndex = startIndex + PAGE_SIZE;
        const paginated = filtered.slice(startIndex, endIndex);

        return { items: paginated, totalItems: filtered.length };
    }, [schemas, searchQuery, currentPage]);

    useEffect(() => {
        fetchData();
    }, []);

    const handleDownload = async () => {
        try {
            const blob = await api.admin.exportSchemas();
            const url = window.URL.createObjectURL(new Blob([blob]));
            const link = document.createElement('a');
            link.href = url;
            const timestamp = new Date().toISOString().slice(0, 10);
            link.setAttribute('download', `schema_index_${timestamp}.xlsx`);
            document.body.appendChild(link);
            link.click();
            link.parentNode?.removeChild(link);
            window.URL.revokeObjectURL(url);
        } catch (error) {
            console.error('Error downloading schemas:', error);
            alert('Failed to download schemas');
        }
    };

    const handleDownloadTemplate = async () => {
        try {
            const blob = await api.admin.getSchemaTemplate();
            const url = window.URL.createObjectURL(new Blob([blob]));
            const link = document.createElement('a');
            link.href = url;
            link.setAttribute('download', 'schema_import_template.xlsx');
            document.body.appendChild(link);
            link.click();
            link.parentNode?.removeChild(link);
            window.URL.revokeObjectURL(url);
        } catch (error) {
            console.error('Error downloading template:', error);
            alert('Failed to download template');
        }
    };

    const handleClearAllSchemas = async () => {
        const confirmed = window.confirm(
            'AR YOU SURE? This will delete ALL schemas from the vector store. This action cannot be undone.'
        );

        if (!confirmed) return;

        try {
            await api.admin.clearAllSchemas();
            await fetchData(); // Refresh status
            alert('All schemas have been cleared.');
        } catch (error) {
            const errorWithResponse = error as { response?: { data?: { detail?: string } }; message?: string };
            alert(`Failed to clear schemas: ${errorWithResponse.response?.data?.detail || errorWithResponse.message || 'Unknown error'}`);
        }
    };

    return (
        <div className="p-6 w-full h-full">
            <div className="flex justify-between items-center mb-6">
                <h2 className="text-2xl font-bold bg-gradient-to-r from-blue-400 to-indigo-400 bg-clip-text text-transparent">
                    Schema Management
                </h2>
                <div className="flex gap-2">
                    <button
                        onClick={() => setShowBatchSyncDialog(true)}
                        className="flex items-center gap-2 px-4 py-2 bg-indigo-600 rounded-lg hover:bg-indigo-700 transition"
                        title="Batch Sync Tables"
                    >
                        <PlayCircle size={18} />
                        Batch Sync
                    </button>
                    <button
                        onClick={handleDownload}
                        className="flex items-center gap-2 px-4 py-2 bg-slate-800 rounded-lg hover:bg-slate-700 transition"
                        title="Download as Excel"
                    >
                        <Download size={18} />
                        Download
                    </button>
                    <button
                        onClick={fetchData}
                        className="flex items-center gap-2 px-4 py-2 bg-slate-800 rounded-lg hover:bg-slate-700 transition"
                    >
                        <RefreshCw size={18} className={loading ? "animate-spin" : ""} />
                        Refresh Status
                    </button>
                </div>
            </div>

            {/* Upload Section */}
            <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-6 mb-6">
                <h3 className="text-lg font-semibold text-white mb-4">Upload Schemas (Excel)</h3>

                <div className="space-y-4">
                    {/* Mode Selection */}
                    <div className="flex gap-4">
                        <label className="flex items-center gap-2 cursor-pointer">
                            <input
                                type="radio"
                                checked={uploadMode === 'append'}
                                onChange={() => setUploadMode('append')}
                                className="w-4 h-4"
                            />
                            <span className="text-slate-300">Append to existing schemas</span>
                        </label>
                        <label className="flex items-center gap-2 cursor-pointer">
                            <input
                                type="radio"
                                checked={uploadMode === 'replace'}
                                onChange={() => setUploadMode('replace')}
                                className="w-4 h-4"
                            />
                            <span className="text-slate-300">Replace all schemas (clear first)</span>
                        </label>
                    </div>

                    {/* Upload Area */}
                    <div className="border-2 border-dashed border-slate-700 rounded-lg p-8 text-center hover:border-indigo-500/50 transition">
                        <input
                            type="file"
                            id="schema-file-upload"
                            accept=".xlsx,.xls"
                            onChange={handleFileUpload}
                            disabled={uploadStatus.status === 'loading'}
                            className="hidden"
                        />
                        <label htmlFor="schema-file-upload" className="cursor-pointer block">
                            <Upload className="w-8 h-8 text-slate-400 mx-auto mb-2" />
                            <p className="text-slate-300 font-medium">Click to upload or drag and drop</p>
                            <p className="text-slate-500 text-sm">Excel files only (.xlsx, .xls)</p>
                        </label>
                    </div>

                    {/* Action Buttons */}
                    <div className="flex gap-3 pt-2 justify-center">
                        <button
                            onClick={handleDownloadTemplate}
                            className="flex items-center gap-2 px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white rounded-lg transition"
                        >
                            <Download className="w-4 h-4" />
                            Download Template
                        </button>
                        <button
                            onClick={handleClearAllSchemas}
                            disabled={schemas.length === 0}
                            className="flex items-center gap-2 px-4 py-2 bg-red-900/20 hover:bg-red-900/30 text-red-400 hover:text-red-300 rounded-lg transition disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                            <Trash2 className="w-4 h-4" />
                            Clear All Schemas
                        </button>
                    </div>

                    {/* Progress Bar */}
                    {uploadStatus.status === 'loading' && (
                        <div className="space-y-3 bg-indigo-500/10 border border-indigo-500/30 rounded-lg p-4">
                            <div className="flex items-center gap-3">
                                <div className="flex items-center gap-2">
                                    <Loader2 className="w-5 h-5 animate-spin text-indigo-400" />
                                    <div>
                                        <p className="text-slate-300 font-medium">Uploading in progress...</p>
                                        <p className="text-indigo-300 text-sm">Processing schema data</p>
                                    </div>
                                </div>
                            </div>
                            <div className="w-full bg-slate-800 rounded-full h-3">
                                <div
                                    className="bg-gradient-to-r from-indigo-500 to-purple-500 h-3 rounded-full transition-all"
                                    style={{ width: `${uploadProgress}%` }}
                                ></div>
                            </div>
                            <p className="text-xs text-indigo-300/70">Do not close this page or navigate away until the upload is complete</p>
                        </div>
                    )}

                    {/* Status Messages */}
                    {uploadStatus.status === 'success' && (
                        <div className="bg-emerald-500/10 border border-emerald-500/30 rounded-lg p-4 flex items-start gap-3">
                            <CheckCircle className="w-5 h-5 text-emerald-400 flex-shrink-0 mt-0.5" />
                            <div>
                                <p className="text-emerald-300 font-medium">{uploadStatus.message}</p>
                                {uploadStatus.rowsProcessed && (
                                    <p className="text-emerald-300/70 text-sm">
                                        Processed: {uploadStatus.rowsProcessed} of {uploadStatus.totalRows} rows
                                    </p>
                                )}
                            </div>
                        </div>
                    )}

                    {uploadStatus.status === 'error' && (
                        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4 flex items-start gap-3">
                            <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
                            <div>
                                <p className="text-red-300 font-medium">Upload Failed</p>
                                <p className="text-red-300/70 text-sm">{uploadStatus.message}</p>
                            </div>
                        </div>
                    )}
                </div>
            </div>

            {/* Info Section */}
            <div className="bg-blue-500/10 border border-blue-500/30 rounded-xl p-4 mb-6">
                <h4 className="text-blue-300 font-semibold mb-2">📋 Excel Format Guide</h4>
                <ul className="text-blue-300/80 text-sm space-y-1">
                    <li>• Column 1 (schema_name): Database schema (e.g., 'dbo')</li>
                    <li>• Column 2 (table_name): Table name (e.g., 'Customers')</li>
                    <li>• Column 3 (description): Table description for semantic search</li>
                </ul>
            </div>

            {/* Search Box */}
            <div className="mb-4">
                <div className="relative">
                    <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-slate-500" size={18} />
                    <input
                        type="text"
                        placeholder="Search by table name, schema, or description..."
                        value={searchQuery}
                        onChange={(e) => {
                            setSearchQuery(e.target.value);
                            setCurrentPage(0);
                        }}
                        className="w-full pl-10 pr-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition"
                    />
                    {searchQuery && (
                        <button
                            onClick={() => setSearchQuery('')}
                            className="absolute right-3 top-1/2 transform -translate-y-1/2 text-slate-500 hover:text-slate-300"
                            aria-label="Clear search"
                        >
                            ×
                        </button>
                    )}
                </div>
            </div>

            {/* Schemas Table */}
            <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
                <table className="w-full text-left">
                    <thead className="bg-slate-950 text-slate-400">
                        <tr>
                            <th className="p-4">Table</th>
                            <th className="p-4">Type</th>
                            <th className="p-4">Indexed</th>
                            <th className="p-4">Description (Knowledge)</th>
                            <th className="p-4">Actions</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800">
                        {filteredAndPaginatedSchemas.items.map((item) => (
                            <tr key={`${item.schema_name}.${item.table_name}`} className="hover:bg-slate-800/50">
                                <td className="p-4">
                                    <div className="font-mono font-medium text-slate-200">
                                        {item.table_name}
                                    </div>
                                    <div className="text-xs text-slate-500">{item.schema_name}</div>
                                </td>
                                <td className="p-4">
                                    <span className={`text-xs px-2 py-1 rounded-full ${item.table_type === 'view' ? 'bg-purple-500/20 text-purple-300' : 'bg-blue-500/20 text-blue-300'}`}>
                                        {item.table_type || 'table'}
                                    </span>
                                </td>
                                <td className="p-4">
                                    {item.is_indexed ? (
                                        <span className="flex items-center gap-1 text-emerald-400 text-sm">
                                            <CheckCircle size={14} /> Indexed
                                        </span>
                                    ) : (
                                        <span className="flex items-center gap-1 text-amber-500 text-sm">
                                            <AlertCircle size={14} /> Missing
                                        </span>
                                    )}
                                </td>
                                <td className="p-4 max-w-md">
                                    <p className="text-xs text-slate-400 truncate" title={item.description || ''}>
                                        {item.description || <span className="italic opacity-50">No description generated</span>}
                                    </p>
                                </td>
                                <td className="p-4">
                                    <div className="flex gap-2">
                                        <button
                                            onClick={() => handleSync(item.schema_name, item.table_name)}
                                            disabled={!!syncing}
                                            className="p-2 bg-indigo-500/10 text-indigo-400 rounded hover:bg-indigo-500/20 disabled:opacity-50"
                                            title="Sync to Vector Store"
                                        >
                                            <Play size={16} className={syncing === `${item.schema_name}.${item.table_name}` ? "animate-spin" : ""} />
                                        </button>
                                        {item.is_indexed && (
                                            <>
                                                <button
                                                    onClick={() => handleEdit(item)}
                                                    className="p-2 bg-amber-500/10 text-amber-400 rounded hover:bg-amber-500/20"
                                                    title="Edit Description"
                                                >
                                                    <Edit size={16} />
                                                </button>
                                                <button
                                                    onClick={() => handleDelete(item)}
                                                    className="p-2 bg-red-500/10 text-red-400 rounded hover:bg-red-500/20"
                                                    title="Delete from Vector Store"
                                                >
                                                    <Trash2 size={16} />
                                                </button>
                                            </>
                                        )}
                                    </div>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
                {filteredAndPaginatedSchemas.totalItems === 0 && searchQuery && (
                    <div className="p-8 text-center">
                        <p className="text-slate-500">No results found for "{searchQuery}"</p>
                        <button
                            onClick={() => setSearchQuery('')}
                            className="mt-2 text-indigo-400 hover:text-indigo-300 text-sm"
                        >
                            Clear search
                        </button>
                    </div>
                )}
                {schemas.length === 0 && !loading && !searchQuery && (
                    <div className="p-8 text-center space-y-4">
                        <p className="text-slate-500 mb-4">No schemas found in the vector database.</p>
                        <button
                            onClick={handleSyncAll}
                            disabled={syncingAll}
                            className="inline-flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-emerald-500 to-teal-500 text-white rounded-lg hover:shadow-lg hover:shadow-emerald-500/30 disabled:opacity-50 disabled:cursor-not-allowed transition"
                        >
                            {syncingAll ? (
                                <>
                                    <RefreshCw size={18} className="animate-spin" />
                                    Syncing Schemas...
                                </>
                            ) : (
                                <>
                                    <Download size={18} />
                                    Sync All Schemas
                                </>
                            )}
                        </button>
                        <p className="text-xs text-slate-600 max-w-md mx-auto">
                            Click this button to discover all database tables and build the vector search index. This process may take a few minutes.
                        </p>
                    </div>
                )}
                <Pagination
                    currentPage={currentPage}
                    totalItems={filteredAndPaginatedSchemas.totalItems}
                    pageSize={50}
                    onPageChange={setCurrentPage}
                />
            </div>

            <SchemaDescriptionEditor
                isOpen={showEditModal}
                onClose={() => setShowEditModal(false)}
                onSave={handleSaveDescription}
                schemaName={editingSchema?.schema_name || ''}
                tableName={editingSchema?.table_name || ''}
                currentDescription={editingSchema?.description || ''}
            />

            {/* Batch Sync Dialog */}
            {showBatchSyncDialog && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
                    <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 max-w-2xl w-full mx-4">
                        <h3 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
                            <PlayCircle className="text-indigo-400" size={24} />
                            Batch Sync Tables
                        </h3>

                        <p className="text-slate-400 text-sm mb-4">
                            Enter table names to sync (one per line or comma-separated). Supports formats:
                        </p>
                        <ul className="text-slate-400 text-sm mb-4 list-disc list-inside">
                            <li><code className="bg-slate-800 px-1 rounded">TableName</code> - uses default schema (dbo)</li>
                            <li><code className="bg-slate-800 px-1 rounded">schema.TableName</code> - explicit schema</li>
                        </ul>

                        <textarea
                            value={batchSyncInput}
                            onChange={(e) => setBatchSyncInput(e.target.value)}
                            placeholder="e.g., Customers, dbo.Orders, Sales.Invoices"
                            className="w-full h-40 bg-slate-800 border border-slate-700 rounded-lg p-3 text-white font-mono text-sm resize-none focus:outline-none focus:border-indigo-500"
                            disabled={batchSyncing}
                        />

                        {batchSyncResults && (
                            <div className="mt-4 space-y-2">
                                <div className="flex items-center gap-4 text-sm">
                                    <span className="text-slate-300">
                                        Total: <strong>{batchSyncResults.total}</strong>
                                    </span>
                                    <span className="text-emerald-400">
                                        Success: <strong>{batchSyncResults.successful}</strong>
                                    </span>
                                    <span className="text-red-400">
                                        Failed: <strong>{batchSyncResults.failed}</strong>
                                    </span>
                                </div>

                                <div className="max-h-48 overflow-y-auto space-y-1">
                                    {batchSyncResults.results.map((result, idx) => (
                                        <div
                                            key={idx}
                                            className={`text-xs p-2 rounded flex items-start gap-2 ${result.success
                                                ? 'bg-emerald-500/10 text-emerald-300'
                                                : 'bg-red-500/10 text-red-300'
                                                }`}
                                        >
                                            {result.success ? (
                                                <CheckCircle size={14} className="flex-shrink-0 mt-0.5" />
                                            ) : (
                                                <AlertCircle size={14} className="flex-shrink-0 mt-0.5" />
                                            )}
                                            <span className="font-mono">{result.schema_name}.{result.table_name}</span>
                                            <span className="flex-1">- {result.message}</span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}

                        <div className="flex gap-2 mt-6">
                            <button
                                onClick={handleBatchSync}
                                disabled={batchSyncing || !batchSyncInput.trim()}
                                className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition"
                            >
                                {batchSyncing ? (
                                    <>
                                        <Loader2 size={18} className="animate-spin" />
                                        Syncing...
                                    </>
                                ) : (
                                    <>
                                        <PlayCircle size={18} />
                                        Sync Tables
                                    </>
                                )}
                            </button>
                            <button
                                onClick={handleCloseBatchSyncDialog}
                                disabled={batchSyncing}
                                className="px-4 py-2 bg-slate-800 text-white rounded-lg hover:bg-slate-700 disabled:opacity-50 transition"
                            >
                                {batchSyncResults ? 'Close' : 'Cancel'}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};
