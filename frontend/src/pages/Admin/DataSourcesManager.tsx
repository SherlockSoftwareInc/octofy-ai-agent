import React, { useEffect, useState } from 'react';
import { api } from '../../api/client';
import type { DataSourceResponse, AddDataSourceRequest, ConnectionTestResponse } from '../../api/client';
import { Database, Plus, RefreshCw, Edit, Trash2, Loader2, Settings, AlertCircle, CheckCircle } from 'lucide-react';

export const DataSourcesManager: React.FC = () => {
    const [dataSources, setDataSources] = useState<DataSourceResponse[]>([]);
    const [loading, setLoading] = useState(false);
    const [showAddModal, setShowAddModal] = useState(false);
    const [editingSourceId, setEditingSourceId] = useState<string | null>(null);
    const [testingConnection, setTestingConnection] = useState<string | null>(null);
    const [connectionTestResult, setConnectionTestResult] = useState<{ sourceId: string; result: ConnectionTestResponse } | null>(null);

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
        } catch (error: any) {
            console.error('Failed to fetch data sources:', error);
            console.error('Error details:', error.response || error.message);
            setDataSources([]); // Ensure we always have an array
            
            // Show more helpful error message
            const errorMessage = error.response?.data?.detail || error.message || 'Unknown error';
            alert(`Failed to load data sources: ${errorMessage}\n\nPlease check:\n- Backend is running\n- You are logged in\n- API key is valid`);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchDataSources();
    }, []);

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
        setShowAddModal(true);
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
        const payload = { ...formData, keywords };

        try {
            if (editingSourceId) {
                await api.dataSources.update(editingSourceId, payload);
            } else {
                await api.dataSources.add(payload);
            }
            setShowAddModal(false);
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
                {dataSources.map((source) => (
                    <div key={source.source_id} className="bg-slate-900 border border-slate-800 rounded-xl p-5 relative group">
                        <div className="flex justify-between items-start mb-3">
                            <div className="flex items-center gap-3">
                                <Database size={24} className="text-blue-400" />
                                <div>
                                    <div className="flex items-center gap-2">
                                        <h3 className="text-lg font-semibold text-white">{source.friendly_name}</h3>
                                        {source.source_id.startsWith('skill_') && (
                                            <span className="px-2 py-1 bg-blue-500/20 border border-blue-500/30 text-blue-300 text-xs rounded-full">
                                                SCHEMA LIBRARY
                                            </span>
                                        )}
                                        {source.is_primary && (
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
                                {!source.source_id.startsWith('skill_') && (
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
                                        {!source.is_primary && (
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
                                {source.source_id.startsWith('skill_') && (
                                    <div className="text-xs text-slate-500 italic">
                                        Edit <span className="font-mono">skills/data-sources/</span> files
                                    </div>
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

                        {!source.source_id.startsWith('skill_') && (
                            <div className="flex gap-2 mt-3 pt-3 border-t border-slate-800">
                                {!source.is_primary && (
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
                    </div>
                ))}

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
                                    onClick={() => setShowAddModal(false)}
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
        </div>
    );
};
