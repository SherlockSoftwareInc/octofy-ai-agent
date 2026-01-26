import React, { useEffect, useState, useMemo } from 'react';
import { api } from '../../api/client';
import type { FewShotItem } from '../../api/client';
import { Trash2, Plus, BrainCircuit, Upload, Loader2, CheckCircle, AlertCircle, Download, RefreshCw, Search } from 'lucide-react';
import { Pagination } from '../../components/Pagination';

interface UploadStatus {
    status: 'idle' | 'loading' | 'success' | 'error';
    message?: string;
    rowsProcessed?: number;
    totalRows?: number;
}

interface FewShotManagerProps {
    onUploadStateChange?: (isUploading: boolean) => void;
}

type KnowledgeType = NonNullable<FewShotItem['knowledge_type']>;

export const FewShotManager: React.FC<FewShotManagerProps> = ({ onUploadStateChange }) => {
    const [items, setItems] = useState<FewShotItem[]>([]);
    const [isCreating, setIsCreating] = useState(false);

    // Form State
    const [newQuestion, setNewQuestion] = useState('');
    const [newSQL, setNewSQL] = useState('');
    const [newKnowledgeType, setNewKnowledgeType] = useState<KnowledgeType>('sql_query');

    // Upload State
    const [uploadStatus, setUploadStatus] = useState<UploadStatus>({ status: 'idle' });
    const [uploadProgress, setUploadProgress] = useState(0);
    const [uploadMode, setUploadMode] = useState<'append' | 'replace'>('append');
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
        try {
            const data = await api.admin.getFewShots();
            if (Array.isArray(data)) {
                setItems(data);
            } else {
                setItems([]);
            }
        } catch (error) {
            console.error(error);
        }
    };

    const handleDelete = async (id: string) => {
        if (!confirm("Delete this example?")) return;
        try {
            await api.admin.deleteFewShot(id);
            fetchData();
        } catch (error) {
            console.error(error);
            alert("Failed to delete");
        }
    };

    const handleCreate = async (event: React.FormEvent) => {
        event.preventDefault();
        try {
            await api.admin.addFewShot({
                question: newQuestion,
                sql_query: newSQL,
                knowledge_type: newKnowledgeType,
                verified: true
            });
            setIsCreating(false);
            setNewQuestion('');
            setNewSQL('');
            setNewKnowledgeType('sql_query');
            fetchData();
        } catch (error) {
            console.error(error);
            alert("Failed to create");
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
            const response = await api.admin.ingestFewShots(file, uploadMode, (progress) => {
                setUploadProgress(progress.percentage);
            });

            setUploadStatus({
                status: 'success',
                message: response.message,
                rowsProcessed: response.rows_processed,
                totalRows: response.total_rows,
            });

            // Reload few-shots after successful upload
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

    // Filter and paginate items
    const filteredAndPaginatedItems = useMemo(() => {
        const PAGE_SIZE = 50;

        // Filter by search query
        let filtered = items;
        if (searchQuery.trim()) {
            const query = searchQuery.toLowerCase();
            filtered = items.filter(item =>
                item.question.toLowerCase().includes(query) ||
                item.sql_query.toLowerCase().includes(query)
            );
        }

        // Paginate
        const startIndex = currentPage * PAGE_SIZE;
        const endIndex = startIndex + PAGE_SIZE;
        const paginated = filtered.slice(startIndex, endIndex);

        return { items: paginated, totalItems: filtered.length };
    }, [items, searchQuery, currentPage]);

    useEffect(() => {
        // eslint-disable-next-line react-hooks/set-state-in-effect
        void fetchData();
    }, []);

    const handleDownload = async () => {
        try {
            const blob = await api.admin.exportFewShots();
            const url = window.URL.createObjectURL(new Blob([blob]));
            const link = document.createElement('a');
            link.href = url;
            const timestamp = new Date().toISOString().slice(0, 10);
            link.setAttribute('download', `knowledge_base_${timestamp}.xlsx`);
            document.body.appendChild(link);
            link.click();
            link.parentNode?.removeChild(link);
            window.URL.revokeObjectURL(url);
        } catch (error) {
            console.error('Error downloading knowledge base:', error);
            alert('Failed to download knowledge base');
        }
    };

    return (
        <div className="p-6 w-full h-full">
            <div className="flex justify-between items-center mb-6">
                <h2 className="text-2xl font-bold bg-gradient-to-r from-emerald-400 to-cyan-400 bg-clip-text text-transparent">
                    Knowledge Base
                </h2>
                <div className="flex gap-2">
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
                        <RefreshCw size={18} />
                        Refresh
                    </button>
                    <button
                        onClick={() => setIsCreating(true)}
                        className="flex items-center gap-2 px-4 py-2 bg-emerald-600 rounded-lg hover:bg-emerald-500 transition text-white"
                    >
                        <Plus size={18} />
                        Add Example
                    </button>
                </div>
            </div>

            {/* Upload Section */}
            <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-6 mb-6">
                <h3 className="text-lg font-semibold text-white mb-4">Upload Examples (Excel)</h3>

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
                            <span className="text-slate-300">Append to existing examples</span>
                        </label>
                        <label className="flex items-center gap-2 cursor-pointer">
                            <input
                                type="radio"
                                checked={uploadMode === 'replace'}
                                onChange={() => setUploadMode('replace')}
                                className="w-4 h-4"
                            />
                            <span className="text-slate-300">Replace all examples (clear first)</span>
                        </label>
                    </div>

                    {/* Upload Area */}
                    <div className="border-2 border-dashed border-slate-700 rounded-lg p-8 text-center hover:border-indigo-500/50 transition">
                        <input
                            type="file"
                            id="fewshot-file-upload"
                            accept=".xlsx,.xls"
                            onChange={handleFileUpload}
                            disabled={uploadStatus.status === 'loading'}
                            className="hidden"
                        />
                        <label htmlFor="fewshot-file-upload" className="cursor-pointer block">
                            <Upload className="w-8 h-8 text-slate-400 mx-auto mb-2" />
                            <p className="text-slate-300 font-medium">Click to upload or drag and drop</p>
                            <p className="text-slate-500 text-sm">Excel files only (.xlsx, .xls)</p>
                        </label>
                    </div>

                    {/* Progress Bar */}
                    {uploadStatus.status === 'loading' && (
                        <div className="space-y-3 bg-emerald-500/10 border border-emerald-500/30 rounded-lg p-4">
                            <div className="flex items-center gap-3">
                                <div className="flex items-center gap-2">
                                    <Loader2 className="w-5 h-5 animate-spin text-emerald-400" />
                                    <div>
                                        <p className="text-slate-300 font-medium">Uploading in progress...</p>
                                        <p className="text-emerald-300 text-sm">Processing knowledge base examples</p>
                                    </div>
                                </div>
                            </div>
                            <div className="w-full bg-slate-800 rounded-full h-3">
                                <div
                                    className="bg-gradient-to-r from-emerald-500 to-cyan-500 h-3 rounded-full transition-all"
                                    style={{ width: `${uploadProgress}%` }}
                                ></div>
                            </div>
                            <p className="text-xs text-emerald-300/70">Do not close this page or navigate away until the upload is complete</p>
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
                    <li>• Column 1 (question): Natural language question (e.g., 'Show me all customers from USA')</li>
                    <li>• Column 2 (sql_query): Correct T-SQL query that answers the question</li>
                </ul>
            </div>

            {/* Create Modal (Inline for now) */}
            {isCreating && (
                <div className="mb-6 bg-slate-900 border border-slate-700 rounded-xl p-6 animate-fade-in">
                    <h3 className="text-lg font-semibold mb-4 text-emerald-400">New Knowledge Base Example</h3>
                    <form onSubmit={handleCreate} className="space-y-4">
                        <div>
                            <label className="block text-sm text-slate-400 mb-1">Natural Language Question</label>
                            <input
                                className="w-full bg-slate-950 border border-slate-800 rounded p-2 focus:ring-2 focus:ring-emerald-500 outline-none"
                                value={newQuestion}
                                onChange={e => setNewQuestion(e.target.value)}
                                placeholder="e.g., Show me top 5 salesmen..."
                                required
                            />
                        </div>
                        <div>
                            <label className="block text-sm text-slate-400 mb-1">Knowledge Type</label>
                            <select
                                className="w-full bg-slate-950 border border-slate-800 rounded p-2 focus:ring-2 focus:ring-emerald-500 outline-none text-sm text-white"
                                value={newKnowledgeType}
                                onChange={(e) => setNewKnowledgeType(e.target.value as KnowledgeType)}
                            >
                                <option value="general">General Knowledge</option>
                                <option value="sql_query">SQL Query</option>
                                <option value="r_code">R Code</option>
                                <option value="sas_code">SAS Code</option>
                                <option value="python_code">Python Code</option>
                            </select>
                        </div>
                        <div>
                            <label className="block text-sm text-slate-400 mb-1">Correct SQL/Code</label>
                            <textarea
                                className="w-full bg-slate-950 border border-slate-800 rounded p-2 focus:ring-2 focus:ring-emerald-500 outline-none font-mono text-sm"
                                rows={4}
                                value={newSQL}
                                onChange={e => setNewSQL(e.target.value)}
                                placeholder="SELECT ... or library(dplyr)..."
                                required
                            />
                        </div>
                        <div className="flex justify-end gap-2">
                            <button type="button" onClick={() => setIsCreating(false)} className="px-4 py-2 text-slate-400 hover:text-white">Cancel</button>
                            <button type="submit" className="px-4 py-2 bg-emerald-600 rounded hover:bg-emerald-500">Save to Knowledge Base</button>
                        </div>
                    </form>
                </div>
            )}

            {/* Search Box */}
            <div className="mb-4">
                <div className="relative">
                    <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-slate-500" size={18} />
                    <input
                        type="text"
                        placeholder="Search by question or SQL query..."
                        value={searchQuery}
                        onChange={(e) => {
                            setSearchQuery(e.target.value);
                            setCurrentPage(0);
                        }}
                        className="w-full pl-10 pr-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-emerald-500 transition"
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

            <div className="grid gap-4">
                {filteredAndPaginatedItems.items.map((item, idx) => (
                    <div key={item.id || idx} className="bg-slate-900 border border-slate-800 rounded-xl p-5 relative group">
                        <div className="flex justify-between items-start mb-2">
                            <div className="flex items-center gap-2 text-indigo-300 font-medium">
                                <BrainCircuit size={16} />
                                <span>{item.question}</span>
                            </div>
                            <div className="flex items-center gap-2">
                                <span className={`text-xs px-2 py-1 rounded border ${item.knowledge_type === 'r_code' ? 'bg-orange-900/30 border-orange-800 text-orange-300' :
                                    item.knowledge_type === 'sas_code' ? 'bg-blue-900/30 border-blue-800 text-blue-300' :
                                        item.knowledge_type === 'python_code' ? 'bg-emerald-900/30 border-emerald-800 text-emerald-300' :
                                            item.knowledge_type === 'general' ? 'bg-purple-900/30 border-purple-800 text-purple-300' :
                                                'bg-slate-800 border-slate-700 text-slate-400'
                                    }`}>
                                    {item.knowledge_type === 'r_code' ? 'R' : item.knowledge_type === 'sas_code' ? 'SAS' : item.knowledge_type === 'python_code' ? 'Python' : item.knowledge_type === 'general' ? 'General' : 'SQL'}
                                </span>
                                <button
                                    onClick={() => item.id && handleDelete(item.id)}
                                    className="opacity-0 group-hover:opacity-100 p-2 text-slate-500 hover:text-red-400 transition"
                                >
                                    <Trash2 size={16} />
                                </button>
                            </div>
                        </div>
                        <div className="bg-slate-950 rounded p-3 text-xs font-mono text-slate-400 overflow-x-auto">
                            {item.sql_query}
                        </div>
                    </div>
                ))}
                {filteredAndPaginatedItems.totalItems === 0 && searchQuery && (
                    <div className="text-center p-8 text-slate-500">
                        <p>No results found for "{searchQuery}"</p>
                        <button
                            onClick={() => setSearchQuery('')}
                            className="mt-2 text-emerald-400 hover:text-emerald-300 text-sm"
                        >
                            Clear search
                        </button>
                    </div>
                )}
                {
                    items.length === 0 && !isCreating && !searchQuery && (
                        <div className="text-center p-8 text-slate-500">No knowledge base examples found. Add some to make me smarter!</div>
                    )
                }
            </div >

            <Pagination
                currentPage={currentPage}
                totalItems={filteredAndPaginatedItems.totalItems}
                pageSize={50}
                onPageChange={setCurrentPage}
            />
        </div >
    );
};
