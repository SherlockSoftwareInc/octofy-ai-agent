import React, { useEffect, useState } from 'react';
import { api } from '../../api/client';
import './SchemaTreeManager.css';
import type { SchemaTreeNode, DataObject } from '../../api/client';
import {
    Database, FolderOpen, Folder, Table, Eye, Settings as SettingsIcon, Wrench,
    ChevronRight, ChevronDown, Loader2, RefreshCw, Trash2, Play, CheckCircle, AlertCircle
} from 'lucide-react';

export const SchemaTreeManager: React.FC = () => {
    const [treeData, setTreeData] = useState<SchemaTreeNode[]>([]);
    const [loading, setLoading] = useState(false);
    const [selectedNode, setSelectedNode] = useState<SchemaTreeNode | null>(null);
    const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set());
    const [syncing, setSyncing] = useState<string | null>(null);
    const [objectDetails, setObjectDetails] = useState<DataObject | null>(null);
    const [loadingDetails, setLoadingDetails] = useState(false);

    useEffect(() => {
        loadTree();
    }, []);

    const loadTree = async () => {
        setLoading(true);
        try {
            const response = await api.schemaTree.getTree();
            setTreeData(response.roots || []);
            // Auto-expand data sources
            const sourceNodeIds = (response.roots || []).map(node => node.node_id);
            setExpandedNodes(new Set(sourceNodeIds));
        } catch (error) {
            console.error('Failed to load schema tree:', error);
            alert('Failed to load schema tree');
        } finally {
            setLoading(false);
        }
    };

    const toggleNode = (nodeId: string) => {
        setExpandedNodes(prev => {
            const newSet = new Set(prev);
            if (newSet.has(nodeId)) {
                newSet.delete(nodeId);
            } else {
                newSet.add(nodeId);
            }
            return newSet;
        });
    };

    const handleNodeSelect = async (node: SchemaTreeNode) => {
        setSelectedNode(node);

        // If it's an object node, load full details
        if (node.type !== 'source' && node.type !== 'schema' && node.metadata.source_id) {
            setLoadingDetails(true);
            try {
                const objects = await api.schemaTree.getObjects(
                    node.metadata.source_id,
                    node.metadata.schema_name,
                    node.metadata.object_type
                );
                const objectDetail = objects.find(obj =>
                    obj.object_name === node.metadata.object_name &&
                    obj.schema_name === node.metadata.schema_name
                );
                setObjectDetails(objectDetail || null);
            } catch (error) {
                console.error('Failed to load object details:', error);
            } finally {
                setLoadingDetails(false);
            }
        } else {
            setObjectDetails(null);
        }
    };

    const handleSyncObject = async (node: SchemaTreeNode) => {
        if (!node.metadata.source_id || !node.metadata.schema_name || !node.metadata.object_name || !node.metadata.object_type) {
            return;
        }

        setSyncing(node.node_id);
        try {
            await api.objects.sync({
                source_id: node.metadata.source_id,
                schema_name: node.metadata.schema_name,
                object_name: node.metadata.object_name,
                object_type: node.metadata.object_type
            });
            await loadTree();
            alert('Object synced successfully!');
        } catch (error) {
            console.error('Failed to sync object:', error);
            alert('Failed to sync object');
        } finally {
            setSyncing(null);
        }
    };

    const handleDeleteObject = async (node: SchemaTreeNode) => {
        if (!node.metadata.source_id || !node.metadata.schema_name || !node.metadata.object_name) {
            return;
        }

        if (!confirm(`Are you sure you want to delete ${node.name} from the vector store?`)) {
            return;
        }

        try {
            await api.objects.delete(
                node.metadata.source_id,
                node.metadata.schema_name,
                node.metadata.object_name
            );
            await loadTree();
            setSelectedNode(null);
            setObjectDetails(null);
        } catch (error) {
            console.error('Failed to delete object:', error);
            alert('Failed to delete object');
        }
    };

    const getNodeIcon = (node: SchemaTreeNode, isExpanded: boolean) => {
        switch (node.type) {
            case 'source':
                return <Database size={16} className="text-blue-400" />;
            case 'schema':
                return isExpanded ? <FolderOpen size={16} className="text-amber-400" /> : <Folder size={16} className="text-amber-400" />;
            case 'table':
                return <Table size={16} className="text-emerald-400" />;
            case 'view':
                return <Eye size={16} className="text-purple-400" />;
            case 'stored_procedure':
                return <SettingsIcon size={16} className="text-orange-400" />;
            case 'function':
                return <Wrench size={16} className="text-cyan-400" />;
            default:
                return <Table size={16} className="text-slate-400" />;
        }
    };

    const renderTreeNode = (node: SchemaTreeNode, depth: number = 0): React.ReactNode => {
        const isExpanded = expandedNodes.has(node.node_id);
        const isSelected = selectedNode?.node_id === node.node_id;
        const hasChildren = node.children && node.children.length > 0;

        return (
            <div key={node.node_id}>
                <div
                    className={`flex items-center gap-2 px-3 py-2 rounded-lg cursor-pointer hover:bg-slate-800/50 ${
                        isSelected ? 'bg-indigo-500/20 border-l-2 border-indigo-400' : ''
                    } tree-depth-${Math.min(depth, 10)}`}
                >
                    {hasChildren && (
                        <button
                            onClick={(e) => {
                                e.stopPropagation();
                                toggleNode(node.node_id);
                            }}
                            className="p-0.5 hover:bg-slate-700 rounded"
                        >
                            {isExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                        </button>
                    )}

                    <div
                        className="flex items-center gap-2 flex-1"
                        onClick={() => {
                            handleNodeSelect(node);
                            if (hasChildren && !isExpanded) {
                                toggleNode(node.node_id);
                            }
                        }}
                    >
                        {getNodeIcon(node, isExpanded)}
                        <span className="text-sm">
                            {node.name}
                        </span>
                        {node.is_indexed && (
                            <CheckCircle size={12} className="text-emerald-400" />
                        )}
                        {!node.is_indexed && node.type !== 'source' && node.type !== 'schema' && (
                            <AlertCircle size={12} className="text-amber-400" />
                        )}
                    </div>

                    {/* Quick Actions */}
                    {node.type !== 'source' && node.type !== 'schema' && (
                        <div className="flex gap-1 opacity-0 group-hover:opacity-100">
                            <button
                                onClick={(e) => {
                                    e.stopPropagation();
                                    handleSyncObject(node);
                                }}
                                disabled={syncing === node.node_id}
                                className="p-1 bg-indigo-500/10 text-indigo-400 rounded hover:bg-indigo-500/20 disabled:opacity-50"
                                title="Sync to Vector Store"
                            >
                                <Play size={12} className={syncing === node.node_id ? "animate-spin" : ""} />
                            </button>
                            {node.is_indexed && (
                                <button
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        handleDeleteObject(node);
                                    }}
                                    className="p-1 bg-red-500/10 text-red-400 rounded hover:bg-red-500/20"
                                    title="Remove from Vector Store"
                                >
                                    <Trash2 size={12} />
                                </button>
                            )}
                        </div>
                    )}
                </div>

                {hasChildren && isExpanded && (
                    <div>
                        {node.children.map(child => renderTreeNode(child, depth + 1))}
                    </div>
                )}
            </div>
        );
    };

    return (
        <div className="flex h-full gap-4">
            {/* Tree Navigation - Left Panel */}
            <div className="w-1/3 flex flex-col gap-4">
                <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-4">
                    <div className="flex items-center justify-between mb-4">
                        <h3 className="text-lg font-medium">Schema Tree</h3>
                        <button
                            onClick={loadTree}
                            className="p-2 bg-slate-800 rounded-lg hover:bg-slate-700"
                            title="Refresh Tree"
                        >
                            <RefreshCw size={16} className={loading ? "animate-spin" : ""} />
                        </button>
                    </div>

                    {loading ? (
                        <div className="flex items-center justify-center py-8">
                            <Loader2 className="animate-spin text-slate-400" />
                        </div>
                    ) : (
                        <div className="space-y-1 max-h-[700px] overflow-y-auto">
                            {treeData.length > 0 ? (
                                treeData.map(node => renderTreeNode(node, 0))
                            ) : (
                                <div className="text-center py-8 text-slate-400">
                                    <Database size={48} className="mx-auto mb-2 opacity-50" />
                                    <p>No data sources found</p>
                                    <p className="text-xs mt-2">Add a data source to get started</p>
                                </div>
                            )}
                        </div>
                    )}
                </div>
            </div>

            {/* Details Panel - Right Panel */}
            <div className="flex-1 flex flex-col gap-4">
                <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-6">
                    {selectedNode ? (
                        <>
                            <div className="flex items-center justify-between mb-4">
                                <div className="flex items-center gap-3">
                                    {getNodeIcon(selectedNode, false)}
                                    <div>
                                        <h3 className="text-xl font-semibold text-white">{selectedNode.name}</h3>
                                        <p className="text-sm text-slate-400 capitalize">{selectedNode.type}</p>
                                    </div>
                                </div>
                                <div className="flex gap-2">
                                    {selectedNode.type !== 'source' && selectedNode.type !== 'schema' && (
                                        <>
                                            <button
                                                onClick={() => handleSyncObject(selectedNode)}
                                                disabled={syncing === selectedNode.node_id}
                                                className="px-4 py-2 bg-indigo-500/10 text-indigo-400 rounded hover:bg-indigo-500/20 disabled:opacity-50"
                                            >
                                                {syncing === selectedNode.node_id ? 'Syncing...' : 'Sync'}
                                            </button>
                                            {selectedNode.is_indexed && (
                                                <button
                                                    onClick={() => handleDeleteObject(selectedNode)}
                                                    className="px-4 py-2 bg-red-500/10 text-red-400 rounded hover:bg-red-500/20"
                                                >
                                                    Remove
                                                </button>
                                            )}
                                        </>
                                    )}
                                </div>
                            </div>

                            {/* Node Status */}
                            <div className="mb-4">
                                {selectedNode.is_indexed ? (
                                    <div className="flex items-center gap-2 text-emerald-400 text-sm">
                                        <CheckCircle size={16} />
                                        <span>Indexed in vector store</span>
                                    </div>
                                ) : selectedNode.type !== 'source' && selectedNode.type !== 'schema' ? (
                                    <div className="flex items-center gap-2 text-amber-400 text-sm">
                                        <AlertCircle size={16} />
                                        <span>Not indexed - click Sync to add to vector store</span>
                                    </div>
                                ) : null}
                            </div>

                            {/* Metadata Section */}
                            {selectedNode.metadata && (
                                <div className="space-y-4">
                                    {selectedNode.metadata.description && (
                                        <div>
                                            <h4 className="text-sm font-medium text-slate-400 mb-2">Description</h4>
                                            <p className="text-slate-300">{selectedNode.metadata.description}</p>
                                        </div>
                                    )}

                                    {selectedNode.type === 'source' && (
                                        <div className="grid grid-cols-2 gap-4 text-sm">
                                            <div>
                                                <span className="text-slate-500">Object Count:</span>
                                                <span className="text-slate-300 ml-2">{selectedNode.metadata.object_count || 0}</span>
                                            </div>
                                            {selectedNode.metadata.last_synced && (
                                                <div>
                                                    <span className="text-slate-500">Last Synced:</span>
                                                    <span className="text-slate-300 ml-2">
                                                        {new Date(selectedNode.metadata.last_synced).toLocaleString()}
                                                    </span>
                                                </div>
                                            )}
                                            <div>
                                                <span className="text-slate-500">Status:</span>
                                                <span className={`ml-2 ${selectedNode.metadata.enabled ? 'text-emerald-300' : 'text-red-300'}`}>
                                                    {selectedNode.metadata.enabled ? 'Enabled' : 'Disabled'}
                                                </span>
                                            </div>
                                            {selectedNode.metadata.is_primary && (
                                                <div>
                                                    <span className="px-2 py-1 bg-emerald-500/20 border border-emerald-500/30 text-emerald-300 text-xs rounded">
                                                        PRIMARY SOURCE
                                                    </span>
                                                </div>
                                            )}
                                        </div>
                                    )}

                                    {/* Object Details */}
                                    {loadingDetails ? (
                                        <div className="flex items-center justify-center py-4">
                                            <Loader2 className="animate-spin text-slate-400" />
                                        </div>
                                    ) : objectDetails ? (
                                        <div className="space-y-4">
                                            {objectDetails.columns && objectDetails.columns.length > 0 && (
                                                <div>
                                                    <h4 className="text-sm font-medium text-slate-400 mb-2">
                                                        Columns ({objectDetails.columns.length})
                                                    </h4>
                                                    <div className="bg-slate-950 rounded-lg p-3 max-h-60 overflow-y-auto">
                                                        <table className="w-full text-sm">
                                                            <thead className="text-slate-500">
                                                                <tr>
                                                                    <th className="text-left pb-2">Name</th>
                                                                    <th className="text-left pb-2">Type</th>
                                                                    <th className="text-left pb-2">Description</th>
                                                                </tr>
                                                            </thead>
                                                            <tbody className="text-slate-300">
                                                                {objectDetails.columns.map((col, idx) => (
                                                                    <tr key={idx} className="border-t border-slate-800">
                                                                        <td className="py-1 font-mono">{col.name}</td>
                                                                        <td className="py-1">{col.data_type}</td>
                                                                        <td className="py-1 text-xs text-slate-400">
                                                                            {col.description || '-'}
                                                                        </td>
                                                                    </tr>
                                                                ))}
                                                            </tbody>
                                                        </table>
                                                    </div>
                                                </div>
                                            )}

                                            {objectDetails.definition && (
                                                <div>
                                                    <h4 className="text-sm font-medium text-slate-400 mb-2">Definition</h4>
                                                    <pre className="bg-slate-950 rounded-lg p-3 text-xs font-mono text-slate-300 overflow-x-auto max-h-60">
                                                        {objectDetails.definition}
                                                    </pre>
                                                </div>
                                            )}

                                            {objectDetails.parameters && (
                                                <div>
                                                    <h4 className="text-sm font-medium text-slate-400 mb-2">Parameters</h4>
                                                    <p className="text-sm text-slate-300 font-mono bg-slate-950 rounded-lg p-3">
                                                        {objectDetails.parameters}
                                                    </p>
                                                </div>
                                            )}

                                            {objectDetails.return_type && (
                                                <div>
                                                    <h4 className="text-sm font-medium text-slate-400 mb-2">Return Type</h4>
                                                    <p className="text-sm text-slate-300 font-mono bg-slate-950 rounded-lg p-3">
                                                        {objectDetails.return_type}
                                                    </p>
                                                </div>
                                            )}
                                        </div>
                                    ) : null}
                                </div>
                            )}
                        </>
                    ) : (
                        <div className="text-center py-12 text-slate-400">
                            <Database size={48} className="mx-auto mb-4 opacity-50" />
                            <p>Select a node from the tree to view details</p>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};
