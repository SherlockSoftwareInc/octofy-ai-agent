import React, { useEffect, useState, useRef, useCallback } from 'react';
import { api } from '../../api/client';
import type { DataSourceResponse, AddDataSourceRequest, ConnectionTestResponse } from '../../api/client';
import { Database, Plus, RefreshCw, Edit, Trash2, Loader2, Settings, AlertCircle, CheckCircle, Search } from 'lucide-react';

export const DataSourcesManager: React.FC = () => {
    const [dataSources, setDataSources] = useState<DataSourceResponse[]>([]);
    const [loading, setLoading] = useState(false);
    const [showAddModal, setShowAddModal] = useState(false);
    const [editingSourceId, setEditingSourceId] = useState<string | null>(null);
    const [activeSourceGuid, setActiveSourceGuid] = useState<string | null>(null);
    const [testingConnection, setTestingConnection] = useState<string | null>(null);
    const [connectionTestResult, setConnectionTestResult] = useState<{ sourceId: string; result: ConnectionTestResponse } | null>(null);
    const [scanningSourceId, setScanningSourceId] = useState<string | null>(null);
    const [scanStatus, setScanStatus] = useState<{ [key: string]: { status: string; message: string; result?: Record<string, unknown> } }>({});
    const scanPollRef = useRef<ReturnType<typeof setInterval> | null>(null);
    const [showScanModal, setShowScanModal] = useState(false);
    const [scanModalSourceId, setScanModalSourceId] = useState<string | null>(null);
    const [scanConnInfo, setScanConnInfo] = useState({ server: '', database_name: '', auth_type: 'windows' as string, driver: 'ODBC Driver 17 for SQL Server', trust_server_certificate: true });
    const [pendingExcludeFile, setPendingExcludeFile] = useState<File | null>(null);
    const excludeFileInputRef = useRef<HTMLInputElement | null>(null);

    // Form state
    const [formData, setFormData] = useState<AddDataSourceRequest>({
        friendly_name: '',
        description: '',
        keywords: [],
        db_type: 'mssql',
        server: '',
        database_name: '',
        connection_string_encrypted: '',
        driver: 'ODBC Driver 17 for SQL Server',
        auth_type: 'windows',
        username: '',
        trust_server_certificate: true
    });
    const [formKeywords, setFormKeywords] = useState('');

    const fetchDataSources = async () => {
        setLoading(true);
        try {
            const response = await api.dataSources.getAll();
            console.log('Data sources response:', response);
            setDataSources(response.data_sources || []);
            setActiveSourceGuid(response.primary_source_id || null);
        } catch (error: unknown) {
            console.error('Failed to fetch data sources:', error);
            console.error('Error details:', (error as { response?: unknown })?.response || (error as Error)?.message);
            setDataSources([]);

            const errorMessage = (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail || (error as Error)?.message || 'Unknown error';
            alert(`Failed to load data sources: ${errorMessage}\n\nPlease check:\n- Backend is running\n- You are logged in\n- API key is valid`);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchDataSources();
        return () => {
            if (scanPollRef.current) clearInterval(scanPollRef.current);
        };
    }, []);

    const pollScanStatus = useCallback((sourceId: string) => {
        if (scanPollRef.current) clearInterval(scanPollRef.current);
        setScanningSourceId(sourceId);
        scanPollRef.current = setInterval(async () => {
            try {
                const status = await api.dataSources.getScanStatus(sourceId);
                setScanStatus(prev => ({ ...prev, [sourceId]: status }));
                if (status.status === 'completed' || status.status === 'error') {
                    if (scanPollRef.current) clearInterval(scanPollRef.current);
                    scanPollRef.current = null;
                    setScanningSourceId(null);
                    if (status.status === 'completed') {
                        await fetchDataSources();
                    }
                }
            } catch {
                if (scanPollRef.current) clearInterval(scanPollRef.current);
                scanPollRef.current = null;
                setScanningSourceId(null);
            }
        }, 2000);
    }, []);

    const handleScanDatabase = async (sourceId: string, connInfo?: { server: string; database_name: string; auth_type?: string; driver?: string; trust_server_certificate?: boolean }) => {
        try {
            setScanStatus(prev => ({ ...prev, [sourceId]: { status: 'running', message: 'Starting scan...' } }));
            await api.dataSources.scanDatabase(sourceId, connInfo);
            pollScanStatus(sourceId);
        } catch (error: unknown) {
            const detail = (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed to start scan';
            if (detail === 'missing_connection_info') {
                // Show modal to collect connection info
                setScanStatus(prev => { const next = { ...prev }; delete next[sourceId]; return next; });
                // Pre-fill from data source card if available
                const source = dataSources.find(s => s.source_id === sourceId);
                setScanConnInfo({
                    server: (source?.server && source.server !== '(Defined in schema library)') ? source.server : '',
                    database_name: (source?.database_name && source.database_name !== '(Defined in schema library)') ? source.database_name : '',
                    auth_type: 'windows',
                    driver: 'ODBC Driver 17 for SQL Server',
                    trust_server_certificate: true,
                });
                setScanModalSourceId(sourceId);
                setShowScanModal(true);
            } else {
                setScanStatus(prev => ({ ...prev, [sourceId]: { status: 'error', message: detail } }));
            }
        }
    };

    const handleScanModalSubmit = async () => {
        if (!scanModalSourceId || !scanConnInfo.server || !scanConnInfo.database_name) return;
        setShowScanModal(false);
        await handleScanDatabase(scanModalSourceId, scanConnInfo);
    };

    const handleAdd = () => {
        setEditingSourceId(null);
        setFormData({
            friendly_name: '',
            description: '',
            keywords: [],
            db_type: 'mssql',
            server: '',
            database_name: '',
            connection_string_encrypted: '',
            driver: 'ODBC Driver 17 for SQL Server',
            auth_type: 'windows',
            username: '',
            trust_server_certificate: true
        });
        setFormKeywords('');
        setPendingExcludeFile(null);
        setShowAddModal(true);
        if (excludeFileInputRef.current) {
            excludeFileInputRef.current.value = '';
            excludeFileInputRef.current.click();
        }
    };

    const handleExcludeFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0] || null;
        if (!file) {
            setPendingExcludeFile(null);
            return;
        }
        if (!file.name.toLowerCase().endsWith('.txt')) {
            alert('Please select a .txt file for the exclusion list.');
            event.target.value = '';
            setPendingExcludeFile(null);
            return;
        }
        setPendingExcludeFile(file);
    };

    const handleEdit = async (sourceId: string) => {
        try {
            const source = await api.dataSources.get(sourceId);
            setEditingSourceId(sourceId);
            setFormData({
                friendly_name: source.friendly_name,
                description: source.description,
                keywords: source.keywords,
                db_type: source.db_type,
                server: source.server,
                database_name: source.database_name,
                connection_string_encrypted: '',
                driver: 'ODBC Driver 17 for SQL Server',
                auth_type: 'windows',
                username: '',
                trust_server_certificate: true
            });
            setFormKeywords(source.keywords.join(', '));
            setShowAddModal(true);
        } catch (error) {
            console.error('Failed to fetch data source:', error);
            alert('Failed to load data source');
        }
    };

    const handleDelete = async (sourceId: string, friendlyName: string) => {
        if (!confirm(`Are you sure you want to delete "${friendlyName}"? This will remove all indexed objects from this source.`)) {
            return;
        }

        try {
            await api.dataSources.delete(sourceId);
            await fetchDataSources();
        } catch (error) {
            console.error('Failed to delete data source:', error);
            alert('Failed to delete data source');
        }
    };

    const handleTestConnection = async (sourceId: string) => {
        setTestingConnection(sourceId);
        setConnectionTestResult(null);
        try {
            const result = await api.dataSources.testConnection(sourceId);
            setConnectionTestResult({ sourceId, result });
        } catch (error: unknown) {
            const errorMessage = error instanceof Error ? error.message : 
                (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 
                'Connection test failed';
            setConnectionTestResult({
                sourceId,
                result: {
                    success: false,
                    message: errorMessage
                }
            });
        } finally {
            setTestingConnection(null);
        }
    };

    const handleSetPrimary = async (sourceId: string) => {
        try {
            await api.dataSources.setPrimary(sourceId);
            setActiveSourceGuid(sourceId);
            await fetchDataSources();
        } catch (error) {
            console.error('Failed to set primary source:', error);
            alert('Failed to set primary source');
        }
    };

    const handleToggleEnabled = async (sourceId: string, currentEnabled: boolean) => {
        try {
            await api.dataSources.toggleEnabled(sourceId, !currentEnabled);
            await fetchDataSources();
        } catch (error) {
            console.error('Failed to toggle source:', error);
            alert('Failed to toggle source');
        }
    };

    const handleSaveDataSource = async (event: React.FormEvent) => {
        event.preventDefault();

        const keywords = formKeywords.split(',').map(k => k.trim()).filter(k => k.length > 0);
        const payload = { ...formData, keywords, skip_auto_scan: !!pendingExcludeFile };

        try {
            if (editingSourceId) {
                await api.dataSources.update(editingSourceId, payload);
            } else {
                const result = await api.dataSources.add(payload);
                let excludeUploadFailed = false;

                if (pendingExcludeFile && result.source_id) {
                    try {
                        await api.dataSources.uploadExcludeObjects(result.source_id, pendingExcludeFile);
                    } catch (error: unknown) {
                        excludeUploadFailed = true;
                        const errorMessage = (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
                            (error as Error)?.message || 'Failed to upload exclusion list';
                        alert(errorMessage);
                    }
                }

                if (payload.server && payload.database_name && result.source_id) {
                    if (pendingExcludeFile && !excludeUploadFailed) {
                        setScanStatus(prev => ({
                            ...prev,
                            [result.source_id]: { status: 'running', message: 'Scanning database objects...' }
                        }));
                        await api.dataSources.scanDatabase(result.source_id, {
                            server: payload.server,
                            database_name: payload.database_name,
                            auth_type: payload.auth_type,
                            driver: payload.driver,
                            trust_server_certificate: payload.trust_server_certificate
                        });
                        pollScanStatus(result.source_id);
                    } else if (!pendingExcludeFile) {
                        // Auto-scan starts on backend if server + database were provided
                        setScanStatus(prev => ({
                            ...prev,
                            [result.source_id]: { status: 'running', message: 'Auto-scanning database objects...' }
                        }));
                        pollScanStatus(result.source_id);
                    }
                }
            }
            setShowAddModal(false);
            setPendingExcludeFile(null);
            await fetchDataSources();
        } catch (error: unknown) {
            console.error('Failed to save data source:', error);
            const errorMessage = (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed to save data source';
            alert(errorMessage);
        }
    };

    const handleBuildConnectionString = async () => {
        try {
            const result = await api.admin.buildConnectionString({
                driver: formData.driver || 'ODBC Driver 17 for SQL Server',
                server: formData.server,
                database: formData.database_name,
                auth_type: (formData.auth_type || 'windows') as "windows" | "sql" | "ad_integrated" | "ad_password" | "ad_interactive" | "ad_service_principal",
                username: formData.username,
                password: '',
                trust_server_certificate: formData.trust_server_certificate
            });
            setFormData({ ...formData, connection_string_encrypted: result.encrypted });
            alert('Connection string built and encrypted successfully!');
        } catch (error: unknown) {
            console.error('Failed to build connection string:', error);
            const errorMessage = (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed to build connection string';
            alert(errorMessage);
        }
    };

    return (
        <div className="p-6 w-full h-full">
            <input
                ref={excludeFileInputRef}
                type="file"
                accept=".txt"
                className="hidden"
                onChange={handleExcludeFileChange}
            />
            <div className="flex justify-between items-center mb-6">
                <h2 className="text-2xl font-bold bg-gradient-to-r from-blue-400 to-indigo-400 bg-clip-text text-transparent">
                    Data Sources
                </h2>
                <div className="flex gap-2">
                    <button
                        onClick={fetchDataSources}
                        className="flex items-center gap-2 px-4 py-2 bg-slate-800 rounded-lg hover:bg-slate-700 transition"
                    >
                        <RefreshCw size={18} className={loading ? "animate-spin" : ""} />
                        Refresh
                    </button>
                    <button
                        onClick={handleAdd}
                        className="flex items-center gap-2 px-4 py-2 bg-indigo-600 rounded-lg hover:bg-indigo-500 transition text-white"
                    >
                        <Plus size={18} />
                        Add Data Source
                    </button>
                </div>
            </div>

            {/* Info message when data sources exist but have no indexed objects */}
            {dataSources.length > 0 && dataSources.every(source => source.object_count === 0) && !loading && (
                <div className="bg-blue-500/10 border border-blue-500/30 rounded-lg p-4 mb-4">
                    <div className="flex items-start gap-3">
                        <AlertCircle size={20} className="text-blue-400 mt-0.5 flex-shrink-0" />
                        <div>
                            <h4 className="text-blue-300 font-semibold mb-1">Schema Library Mode</h4>
                            <p className="text-slate-300 text-sm mb-2">
                                Data sources are configured using the <span className="font-mono text-blue-300">skills/data-sources/</span> directory.
                                Schemas are loaded from markdown files (0 objects indexed in vector store).
                            </p>
                            <p className="text-slate-400 text-xs">
                                💡 To index schemas in Milvus for semantic search, run: <span className="font-mono bg-slate-950 px-2 py-1 rounded">python scripts/ingest_metadata.py</span>
                            </p>
                        </div>
                    </div>
                </div>
            )}

            {/* Data Sources List */}
            <div className="grid gap-4">
                {dataSources.map((source) => {
                    const isSkillsSource = source.server === '(Defined in schema library)' || source.database_name === '(Defined in schema library)';
                    const isPrimary = source.is_primary || (!!activeSourceGuid && source.source_id === activeSourceGuid);
                    return (
                    <div key={source.source_id} className="bg-slate-900 border border-slate-800 rounded-xl p-5 relative group">
                        <div className="flex justify-between items-start mb-3">
                            <div className="flex items-center gap-3">
                                <Database size={24} className="text-blue-400" />
                                <div>
                                    <div className="flex items-center gap-2">
                                        <h3 className="text-lg font-semibold text-white">{source.friendly_name}</h3>
                                        {isSkillsSource && (
                                            <span className="px-2 py-1 bg-blue-500/20 border border-blue-500/30 text-blue-300 text-xs rounded-full">
                                                SCHEMA LIBRARY
                                            </span>
                                        )}
                                        {isPrimary && (
                                            <span className="px-2 py-1 bg-emerald-500/20 border border-emerald-500/30 text-emerald-300 text-xs rounded-full">
                                                PRIMARY
                                            </span>
                                        )}
                                        {!source.enabled && (
                                            <span className="px-2 py-1 bg-red-500/20 border border-red-500/30 text-red-300 text-xs rounded-full">
                                                DISABLED
                                            </span>
                                        )}
                                    </div>
                                    <p className="text-sm text-slate-400 mt-1">{source.description}</p>
                                </div>
                            </div>
                            <div className="flex items-center gap-2">
                                {!isSkillsSource && (
                                    <>
                                        <button
                                            onClick={() => handleTestConnection(source.source_id)}
                                            disabled={testingConnection === source.source_id}
                                            className="p-2 bg-blue-500/10 text-blue-400 rounded hover:bg-blue-500/20 disabled:opacity-50"
                                            title="Test Connection"
                                        >
                                            {testingConnection === source.source_id ? (
                                                <Loader2 size={16} className="animate-spin" />
                                            ) : (
                                                <Settings size={16} />
                                            )}
                                        </button>
                                        <button
                                            onClick={() => handleEdit(source.source_id)}
                                            className="p-2 bg-amber-500/10 text-amber-400 rounded hover:bg-amber-500/20"
                                            title="Edit"
                                        >
                                            <Edit size={16} />
                                        </button>
                                        {!isPrimary && (
                                            <button
                                                onClick={() => handleDelete(source.source_id, source.friendly_name)}
                                                className="p-2 bg-red-500/10 text-red-400 rounded hover:bg-red-500/20"
                                                title="Delete"
                                            >
                                                <Trash2 size={16} />
                                            </button>
                                        )}
                                    </>
                                )}
                                <button
                                    onClick={() => handleScanDatabase(source.source_id)}
                                    disabled={scanningSourceId === source.source_id || scanStatus[source.source_id]?.status === 'running'}
                                    className="p-2 bg-purple-500/10 text-purple-400 rounded hover:bg-purple-500/20 disabled:opacity-50"
                                    title="Scan Database Objects"
                                >
                                    {scanningSourceId === source.source_id || scanStatus[source.source_id]?.status === 'running' ? (
                                        <Loader2 size={16} className="animate-spin" />
                                    ) : (
                                        <Search size={16} />
                                    )}
                                </button>
                                {isSkillsSource && (
                                    <button
                                        onClick={() => handleDelete(source.source_id, source.friendly_name)}
                                        className="p-2 bg-red-500/10 text-red-400 rounded hover:bg-red-500/20"
                                        title="Delete"
                                    >
                                        <Trash2 size={16} />
                                    </button>
                                )}
                            </div>
                        </div>

                        {/* Connection Test Result */}
                        {connectionTestResult?.sourceId === source.source_id && (
                            <div className={`mb-3 p-3 rounded-lg flex items-start gap-2 ${
                                connectionTestResult.result.success
                                    ? 'bg-emerald-500/10 border border-emerald-500/30'
                                    : 'bg-red-500/10 border border-red-500/30'
                            }`}>
                                {connectionTestResult.result.success ? (
                                    <CheckCircle size={16} className="text-emerald-400 flex-shrink-0 mt-0.5" />
                                ) : (
                                    <AlertCircle size={16} className="text-red-400 flex-shrink-0 mt-0.5" />
                                )}
                                <div>
                                    <p className={`text-sm font-medium ${
                                        connectionTestResult.result.success ? 'text-emerald-300' : 'text-red-300'
                                    }`}>
                                        {connectionTestResult.result.message}
                                    </p>
                                </div>
                            </div>
                        )}

                        {/* Scan Status */}
                        {scanStatus[source.source_id] && scanStatus[source.source_id].status !== 'idle' && (
                            <div className={`mb-3 p-3 rounded-lg flex items-start gap-2 ${
                                scanStatus[source.source_id].status === 'completed'
                                    ? 'bg-emerald-500/10 border border-emerald-500/30'
                                    : scanStatus[source.source_id].status === 'error'
                                    ? 'bg-red-500/10 border border-red-500/30'
                                    : 'bg-purple-500/10 border border-purple-500/30'
                            }`}>
                                {scanStatus[source.source_id].status === 'completed' ? (
                                    <CheckCircle size={16} className="text-emerald-400 flex-shrink-0 mt-0.5" />
                                ) : scanStatus[source.source_id].status === 'error' ? (
                                    <AlertCircle size={16} className="text-red-400 flex-shrink-0 mt-0.5" />
                                ) : (
                                    <Loader2 size={16} className="text-purple-400 flex-shrink-0 mt-0.5 animate-spin" />
                                )}
                                <div className="flex-1">
                                    <p className={`text-sm font-medium ${
                                        scanStatus[source.source_id].status === 'completed' ? 'text-emerald-300'
                                        : scanStatus[source.source_id].status === 'error' ? 'text-red-300'
                                        : 'text-purple-300'
                                    }`}>
                                        {scanStatus[source.source_id].status === 'running' ? 'Scanning Database...' :
                                         scanStatus[source.source_id].status === 'completed' ? 'Scan Complete' : 'Scan Failed'}
                                    </p>
                                    <p className="text-xs text-slate-400 mt-1">
                                        {scanStatus[source.source_id].message}
                                    </p>
                                    {scanStatus[source.source_id].status !== 'running' && (
                                        <button
                                            onClick={() => setScanStatus(prev => {
                                                const next = { ...prev };
                                                delete next[source.source_id];
                                                return next;
                                            })}
                                            className="text-xs text-slate-500 hover:text-slate-300 mt-1"
                                        >
                                            Dismiss
                                        </button>
                                    )}
                                </div>
                            </div>
                        )}

                        <div className="grid grid-cols-2 gap-4 text-sm mb-3">
                            <div>
                                <span className="text-slate-500">Server:</span>
                                <span className="text-slate-300 ml-2 font-mono">{source.server}</span>
                            </div>
                            <div>
                                <span className="text-slate-500">Database:</span>
                                <span className="text-slate-300 ml-2 font-mono">{source.database_name}</span>
                            </div>
                            <div>
                                <span className="text-slate-500">Type:</span>
                                <span className="text-slate-300 ml-2">{source.db_type}</span>
                            </div>
                            <div>
                                <span className="text-slate-500">Indexed Objects:</span>
                                <span className="text-slate-300 ml-2">{source.object_count}</span>
                            </div>
                        </div>

                        {source.keywords && source.keywords.length > 0 && (
                            <div className="flex flex-wrap gap-2 mb-3">
                                {source.keywords.map((keyword, idx) => (
                                    <span
                                        key={idx}
                                        className="px-2 py-1 bg-slate-800 text-slate-400 text-xs rounded"
                                    >
                                        {keyword}
                                    </span>
                                ))}
                            </div>
                        )}

                        {source.last_synced && (
                            <div className="text-xs text-slate-500">
                                Last synced: {new Date(source.last_synced).toLocaleString()}
                            </div>
                        )}

                        {!isSkillsSource && (
                            <div className="flex gap-2 mt-3 pt-3 border-t border-slate-800">
                                {!isPrimary && (
                                    <button
                                        onClick={() => handleSetPrimary(source.source_id)}
                                        className="px-3 py-1 bg-emerald-500/10 text-emerald-400 rounded hover:bg-emerald-500/20 text-sm"
                                    >
                                        Set as Primary
                                    </button>
                                )}
                                <button
                                    onClick={() => handleToggleEnabled(source.source_id, source.enabled)}
                                    className={`px-3 py-1 rounded text-sm ${
                                        source.enabled
                                            ? 'bg-slate-700 text-slate-400 hover:bg-slate-600'
                                            : 'bg-blue-500/10 text-blue-400 hover:bg-blue-500/20'
                                    }`}
                                >
                                    {source.enabled ? 'Disable' : 'Enable'}
                                </button>
                            </div>
                        )}

                        {isSkillsSource && (
                            <div className="flex gap-2 mt-3 pt-3 border-t border-slate-800">
                                <button
                                    onClick={() => handleScanDatabase(source.source_id)}
                                    disabled={scanningSourceId === source.source_id || scanStatus[source.source_id]?.status === 'running'}
                                    className="px-3 py-1 bg-purple-500/10 text-purple-400 rounded hover:bg-purple-500/20 text-sm flex items-center gap-1 disabled:opacity-50"
                                >
                                    {scanningSourceId === source.source_id || scanStatus[source.source_id]?.status === 'running' ? (
                                        <><Loader2 size={14} className="animate-spin" /> Scanning...</>
                                    ) : (
                                        <><Search size={14} /> Scan Database</>
                                    )}
                                </button>
                            </div>
                        )}
                    </div>
                );
                })}

                {dataSources.length === 0 && !loading && (
                    <div className="text-center p-8 text-slate-500">
                        No data sources configured. Click "Add Data Source" to get started.
                    </div>
                )}
            </div>

            {/* Add/Edit Modal */}
            {showAddModal && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
                    <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 max-w-2xl w-full mx-4 max-h-[90vh] overflow-y-auto">
                        <h3 className="text-xl font-bold text-white mb-4">
                            {editingSourceId ? 'Edit Data Source' : 'Add Data Source'}
                        </h3>

                        <form onSubmit={handleSaveDataSource} className="space-y-4">
                            <div>
                                <label className="block text-sm text-slate-400 mb-1">Friendly Name</label>
                                <input
                                    type="text"
                                    value={formData.friendly_name}
                                    onChange={(e) => setFormData({ ...formData, friendly_name: e.target.value })}
                                    className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-white focus:ring-2 focus:ring-indigo-500 outline-none"
                                    placeholder="e.g., Production Database"
                                    required
                                />
                            </div>

                            <div>
                                <label className="block text-sm text-slate-400 mb-1">Description</label>
                                <textarea
                                    value={formData.description}
                                    onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                                    className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-white focus:ring-2 focus:ring-indigo-500 outline-none"
                                    rows={3}
                                    placeholder="Brief description of this data source"
                                />
                            </div>

                            <div>
                                <label className="block text-sm text-slate-400 mb-1">Keywords (comma-separated)</label>
                                <input
                                    type="text"
                                    value={formKeywords}
                                    onChange={(e) => setFormKeywords(e.target.value)}
                                    className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-white focus:ring-2 focus:ring-indigo-500 outline-none"
                                    placeholder="e.g., sales, customer, orders"
                                />
                            </div>

                            {!editingSourceId && (
                                <div>
                                    <label className="block text-sm text-slate-400 mb-1">Exclude Objects (optional)</label>
                                    <div className="flex items-center gap-3">
                                        <button
                                            type="button"
                                            onClick={() => excludeFileInputRef.current?.click()}
                                            className="px-3 py-1 bg-slate-800 text-slate-300 rounded hover:bg-slate-700 text-sm"
                                        >
                                            Choose File
                                        </button>
                                        <span className="text-xs text-slate-500">
                                            {pendingExcludeFile ? pendingExcludeFile.name : 'No file selected'}
                                        </span>
                                    </div>
                                    <p className="text-xs text-slate-500 mt-1">
                                        One object name per line. Lines starting with # are ignored.
                                    </p>
                                </div>
                            )}

                            <div className="grid grid-cols-2 gap-4">
                                <div>
                                    <label className="block text-sm text-slate-400 mb-1">Server</label>
                                    <input
                                        type="text"
                                        value={formData.server}
                                        onChange={(e) => setFormData({ ...formData, server: e.target.value })}
                                        className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-white focus:ring-2 focus:ring-indigo-500 outline-none"
                                        placeholder="e.g., localhost"
                                        required
                                    />
                                </div>

                                <div>
                                    <label className="block text-sm text-slate-400 mb-1">Database Name</label>
                                    <input
                                        type="text"
                                        value={formData.database_name}
                                        onChange={(e) => setFormData({ ...formData, database_name: e.target.value })}
                                        className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-white focus:ring-2 focus:ring-indigo-500 outline-none"
                                        placeholder="e.g., Northwind"
                                        required
                                    />
                                </div>
                            </div>

                            <div>
                                <label className="block text-sm text-slate-400 mb-1">Connection String (Encrypted)</label>
                                <textarea
                                    value={formData.connection_string_encrypted}
                                    onChange={(e) => setFormData({ ...formData, connection_string_encrypted: e.target.value })}
                                    className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-white font-mono text-xs focus:ring-2 focus:ring-indigo-500 outline-none"
                                    rows={3}
                                    placeholder="Paste encrypted connection string or use 'Build Connection String' button"
                                    required={!editingSourceId}
                                />
                                <button
                                    type="button"
                                    onClick={handleBuildConnectionString}
                                    className="mt-2 px-3 py-1 bg-blue-500/10 text-blue-400 rounded hover:bg-blue-500/20 text-sm"
                                >
                                    Build Connection String
                                </button>
                            </div>

                            <div className="flex justify-end gap-2 pt-4 border-t border-slate-800">
                                <button
                                    type="button"
                                    onClick={() => { setShowAddModal(false); setPendingExcludeFile(null); }}
                                    className="px-4 py-2 text-slate-400 hover:text-white"
                                >
                                    Cancel
                                </button>
                                <button
                                    type="submit"
                                    className="px-4 py-2 bg-indigo-600 rounded hover:bg-indigo-500 text-white"
                                >
                                    {editingSourceId ? 'Update' : 'Add'} Data Source
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}

            {/* Scan Connection Info Modal */}
            {showScanModal && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
                    <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 max-w-lg w-full mx-4">
                        <h3 className="text-xl font-bold text-white mb-2 flex items-center gap-2">
                            <Search size={20} className="text-purple-400" />
                            Database Connection
                        </h3>
                        <p className="text-sm text-slate-400 mb-4">
                            Enter the connection details to scan this database for tables and views.
                        </p>

                        <div className="space-y-4">
                            <div className="grid grid-cols-2 gap-4">
                                <div>
                                    <label className="block text-sm text-slate-400 mb-1">Server</label>
                                    <input
                                        type="text"
                                        value={scanConnInfo.server}
                                        onChange={(e) => setScanConnInfo({ ...scanConnInfo, server: e.target.value })}
                                        className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-white focus:ring-2 focus:ring-purple-500 outline-none"
                                        placeholder="e.g., localhost"
                                        autoFocus
                                    />
                                </div>
                                <div>
                                    <label className="block text-sm text-slate-400 mb-1">Database</label>
                                    <input
                                        type="text"
                                        value={scanConnInfo.database_name}
                                        onChange={(e) => setScanConnInfo({ ...scanConnInfo, database_name: e.target.value })}
                                        className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-white focus:ring-2 focus:ring-purple-500 outline-none"
                                        placeholder="e.g., Northwind"
                                    />
                                </div>
                            </div>

                            <div className="grid grid-cols-2 gap-4">
                                <div>
                                    <label className="block text-sm text-slate-400 mb-1">Authentication</label>
                                    <select
                                        value={scanConnInfo.auth_type}
                                        onChange={(e) => setScanConnInfo({ ...scanConnInfo, auth_type: e.target.value })}
                                        className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-white focus:ring-2 focus:ring-purple-500 outline-none"
                                        title="Authentication type"
                                    >
                                        <option value="windows">Windows Auth</option>
                                        <option value="sql">SQL Auth</option>
                                    </select>
                                </div>
                                <div className="flex items-end">
                                    <label className="flex items-center gap-2 text-sm text-slate-400 cursor-pointer">
                                        <input
                                            type="checkbox"
                                            checked={scanConnInfo.trust_server_certificate}
                                            onChange={(e) => setScanConnInfo({ ...scanConnInfo, trust_server_certificate: e.target.checked })}
                                            className="rounded bg-slate-950 border-slate-700"
                                        />
                                        Trust Server Certificate
                                    </label>
                                </div>
                            </div>

                            <div className="flex justify-end gap-2 pt-4 border-t border-slate-800">
                                <button
                                    type="button"
                                    onClick={() => { setShowScanModal(false); setScanModalSourceId(null); }}
                                    className="px-4 py-2 text-slate-400 hover:text-white"
                                >
                                    Cancel
                                </button>
                                <button
                                    type="button"
                                    onClick={handleScanModalSubmit}
                                    disabled={!scanConnInfo.server || !scanConnInfo.database_name}
                                    className="px-4 py-2 bg-purple-600 rounded hover:bg-purple-500 text-white disabled:opacity-50 flex items-center gap-2"
                                >
                                    <Search size={16} />
                                    Start Scan
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};
