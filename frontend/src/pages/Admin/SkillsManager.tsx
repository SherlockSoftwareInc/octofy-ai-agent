import React, { useEffect, useState, useCallback } from 'react';
import { api } from '../../api/client';
import './SkillsManager.css';
import type { FolderTreeNode } from '../../api/client';
import {
    FolderTree, FolderOpen, Folder, FileText, ChevronRight, ChevronDown, 
    Loader2, AlertCircle, CheckCircle, X, FileCode, Save, Eye, Edit3, Sparkles, Undo2,
    Plus, Trash2, Database, Layers, Table
} from 'lucide-react';
import { MarkdownViewer } from '../../components/MarkdownViewer';
import { MarkdownEditor } from '../../components/MarkdownEditor';

export const SkillsManager: React.FC = () => {
    const [treeData, setTreeData] = useState<FolderTreeNode | null>(null);
    const [loading, setLoading] = useState(false);
    const [selectedFile, setSelectedFile] = useState<string | null>(null);
    const [selectedFolder, setSelectedFolder] = useState<FolderTreeNode | null>(null);
    const [markdownContent, setMarkdownContent] = useState<string>('');
    const [isEditing, setIsEditing] = useState(false);
    const [viewMode, setViewMode] = useState<'view' | 'edit'>('view');
    const [saving, setSaving] = useState(false);
    const [toast, setToast] = useState<{ type: 'success' | 'error', message: string } | null>(null);
    const [expandedFolders, setExpandedFolders] = useState<Set<string>>(new Set());
    
    // AI Assistant states
    const [showAIModal, setShowAIModal] = useState(false);
    const [aiContext, setAiContext] = useState('');
    const [aiProcessing, setAiProcessing] = useState(false);
    const [originalContent, setOriginalContent] = useState<string | null>(null);

    // CRUD modals
    const [showCreateDataSourceModal, setShowCreateDataSourceModal] = useState(false);
    const [showCreateDataGroupModal, setShowCreateDataGroupModal] = useState(false);
    const [showCreateTableModal, setShowCreateTableModal] = useState(false);
    const [newItemName, setNewItemName] = useState('');

    const loadFolderTree = useCallback(async () => {
        setLoading(true);
        try {
            const tree = await api.admin.getFolderTree();
            setTreeData(tree);
            // Auto-expand root folders
            if (tree.children) {
                const rootFolders = new Set(tree.children.filter(c => !c.is_file).map(c => c.path));
                setExpandedFolders(rootFolders);
            }
        } catch (error) {
            showToast('error', 'Failed to load folder tree');
            console.error(error);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        loadFolderTree();
    }, [loadFolderTree]);

    const loadMarkdownFile = async (filePath: string) => {
        try {
            const content = await api.admin.getRawMarkdown(filePath);
            setMarkdownContent(content);
            setSelectedFile(filePath);
            setIsEditing(false);
            setViewMode('view');
        } catch (error) {
            showToast('error', 'Failed to load markdown file');
            console.error(error);
        }
    };

    const handleSave = async () => {
        if (!selectedFile) return;

        setSaving(true);
        try {
            await api.admin.saveRawMarkdown(selectedFile, markdownContent);
            showToast('success', 'File saved successfully');
            setIsEditing(false);
            // Clear undo state after successful save
            setOriginalContent(null);
            // Reload tree to reflect any changes
            await loadFolderTree();
        } catch (error) {
            showToast('error', 'Failed to save file');
            console.error(error);
        } finally {
            setSaving(false);
        }
    };

    const handleAIEnhance = async () => {
        if (!selectedFile) return;

        setAiProcessing(true);
        try {
            // Save current content for undo
            setOriginalContent(markdownContent);

            // Call backend API
            const response = await api.admin.enhanceSchemaWithAI({
                file_path: selectedFile,
                current_content: markdownContent,
                user_context: aiContext || undefined
            });

            // Apply enhanced content
            setMarkdownContent(response.enhanced_markdown);
            setShowAIModal(false);
            setAiContext('');
            showToast('success', 'Schema enhanced by AI - Review changes and click Save');
        } catch (error) {
            showToast('error', 'AI enhancement failed');
            console.error(error);
            // Restore original content on error
            if (originalContent) {
                setMarkdownContent(originalContent);
            }
            setOriginalContent(null);
        } finally {
            setAiProcessing(false);
        }
    };

    const handleUndoAI = () => {
        if (originalContent) {
            setMarkdownContent(originalContent);
            setOriginalContent(null);
            showToast('success', 'AI changes undone');
        }
    };

    const toggleFolder = (path: string) => {
        setExpandedFolders(prev => {
            const newSet = new Set(prev);
            if (newSet.has(path)) {
                newSet.delete(path);
            } else {
                newSet.add(path);
            }
            return newSet;
        });
    };

    const showToast = (type: 'success' | 'error', message: string) => {
        setToast({ type, message });
        setTimeout(() => setToast(null), 3000);
    };

    const getFolderDepth = (node: FolderTreeNode): number => {
        const pathParts = node.relative_path.split('/').filter(p => p.length > 0);
        return pathParts.length;
    };

    const handleCreateDataSource = async () => {
        if (!newItemName.trim()) return;
        
        try {
            // Create data source folder with _index.md
            const dataSource = {
                name: newItemName,
                description: '',
                keywords: [],
                status: 'active',
                type: 'sql_server'
            };
            await api.admin.createDataSource(dataSource);
            showToast('success', `Data source "${newItemName}" created`);
            setShowCreateDataSourceModal(false);
            setNewItemName('');
            await loadFolderTree();
        } catch (error) {
            showToast('error', 'Failed to create data source');
            console.error(error);
        }
    };

    const handleCreateDataGroup = async () => {
        if (!newItemName.trim() || !selectedFolder) return;
        
        try {
            const dataGroup = {
                name: newItemName,
                data_source: selectedFolder.name,
                description: '',
                keywords: [],
                tables: []
            };
            await api.admin.createDataGroup(dataGroup);
            showToast('success', `Data group "${newItemName}" created`);
            setShowCreateDataGroupModal(false);
            setNewItemName('');
            await loadFolderTree();
        } catch (error) {
            showToast('error', 'Failed to create data group');
            console.error(error);
        }
    };

    const handleCreateTable = async () => {
        if (!newItemName.trim() || !selectedFolder) return;
        
        try {
            // Create a basic table markdown file
            const tableName = newItemName.endsWith('.md') ? newItemName : `${newItemName}.md`;
            const content = `# ${newItemName.replace('.md', '')}

## Description
[Add table description here]

## Columns
- **column1**: [type] - [description]
- **column2**: [type] - [description]
`;
            
            const filePath = `${selectedFolder.path}/${tableName}`;
            await api.admin.saveRawMarkdown(filePath, content);
            showToast('success', `Table "${newItemName}" created`);
            setShowCreateTableModal(false);
            setNewItemName('');
            await loadFolderTree();
        } catch (error) {
            showToast('error', 'Failed to create table');
            console.error(error);
        }
    };

    const handleDeleteFolder = async () => {
        if (!selectedFolder) return;
        
        if (!confirm(`Are you sure you want to delete "${selectedFolder.name}"? This cannot be undone.`)) {
            return;
        }

        try {
            const depth = getFolderDepth(selectedFolder);
            
            if (depth === 1) {
                // Delete data source
                await api.admin.deleteDataSource(selectedFolder.name);
                showToast('success', 'Data source deleted');
            } else if (depth === 2) {
                // Delete data group
                await api.admin.deleteDataGroup(selectedFolder.path);
                showToast('success', 'Data group deleted');
            }
            
            setSelectedFolder(null);
            await loadFolderTree();
        } catch (error) {
            showToast('error', 'Failed to delete folder');
            console.error(error);
        }
    };

    const renderTreeNode = (node: FolderTreeNode, depth: number = 0): React.ReactNode => {
        const isExpanded = expandedFolders.has(node.path);
        const isSelected = selectedFile === node.path || selectedFolder?.path === node.path;

        // Skip _index.md at root level
        if (node.name === '_index.md' && depth === 1) {
            return null;
        }

        return (
            <div key={node.path}>
                <div
                    className={`flex items-center gap-2 px-3 py-2 rounded-lg cursor-pointer hover:bg-slate-800/50 ${
                        isSelected ? 'bg-indigo-500/20 border-l-2 border-indigo-400' : ''
                    } tree-node-depth-${Math.min(depth, 10)}`}
                >
                    {!node.is_file && node.children && node.children.length > 0 && (
                        <button
                            onClick={(e) => {
                                e.stopPropagation();
                                toggleFolder(node.path);
                            }}
                            className="p-0.5 hover:bg-slate-700 rounded"
                            title={isExpanded ? 'Collapse folder' : 'Expand folder'}
                        >
                            {isExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                        </button>
                    )}

                    <div
                        className="flex items-center gap-2 flex-1"
                        onClick={() => {
                            if (node.is_file && node.is_markdown) {
                                loadMarkdownFile(node.path);
                                setSelectedFolder(null);
                            } else if (!node.is_file) {
                                toggleFolder(node.path);
                                setSelectedFolder(node);
                                setSelectedFile(null);
                            }
                        }}
                    >
                        {node.is_file ? (
                            <>
                                {node.is_markdown ? (
                                    <FileText size={16} className="text-emerald-400" />
                                ) : (
                                    <FileText size={16} className="text-slate-500" />
                                )}
                            </>
                        ) : (
                            <>
                                {isExpanded ? (
                                    <FolderOpen size={16} className="text-amber-400" />
                                ) : (
                                    <Folder size={16} className="text-amber-400" />
                                )}
                            </>
                        )}

                        <span className={`text-sm ${!node.is_markdown && node.is_file ? 'text-slate-500' : ''}`}>
                            {node.name}
                        </span>
                    </div>
                </div>

                {!node.is_file && isExpanded && node.children && (
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
                        <div className="flex items-center gap-2">
                            <FolderTree size={20} className="text-indigo-400" />
                            <h3 className="text-lg font-medium">Skills Folder</h3>
                        </div>
                        <button
                            onClick={() => setShowCreateDataSourceModal(true)}
                            className="p-2 bg-indigo-500/10 text-indigo-400 rounded-lg hover:bg-indigo-500/20"
                            title="Add Data Source"
                        >
                            <Plus size={16} />
                        </button>
                    </div>

                    {loading ? (
                        <div className="flex items-center justify-center py-8">
                            <Loader2 className="animate-spin text-slate-400" />
                        </div>
                    ) : (
                        <div className="space-y-1 max-h-[700px] overflow-y-auto">
                            {treeData && treeData.children ? (
                                treeData.children.map(child => renderTreeNode(child, 1))
                            ) : (
                                <div className="text-center py-8 text-slate-400">
                                    <FolderTree size={48} className="mx-auto mb-2 opacity-50" />
                                    <p>No skills folder found</p>
                                </div>
                            )}
                        </div>
                    )}
                </div>

                {selectedFile && (
                    <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-4">
                        <h4 className="text-sm font-medium mb-2 text-slate-400">File Info</h4>
                        <div className="text-xs text-slate-500 space-y-1">
                            <div className="truncate" title={selectedFile}>
                                <span className="font-medium">Path:</span> {selectedFile}
                            </div>
                            <div>
                                <span className="font-medium">Lines:</span> {markdownContent.split('\n').length}
                            </div>
                            <div>
                                <span className="font-medium">Size:</span> {markdownContent.length} chars
                            </div>
                        </div>
                    </div>
                )}

                {selectedFolder && !selectedFile && (
                    <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-4">
                        <h4 className="text-sm font-medium mb-3 text-slate-400">Folder Actions</h4>
                        <div className="space-y-2">
                            {getFolderDepth(selectedFolder) === 1 && (
                                <>
                                    {/* Data Source Level - Can add Data Groups */}
                                    <button
                                        onClick={() => setShowCreateDataGroupModal(true)}
                                        className="w-full flex items-center gap-2 px-3 py-2 bg-indigo-500/10 text-indigo-400 rounded-lg hover:bg-indigo-500/20"
                                    >
                                        <Plus size={16} />
                                        Add Data Group
                                    </button>
                                    <button
                                        onClick={handleDeleteFolder}
                                        className="w-full flex items-center gap-2 px-3 py-2 bg-red-500/10 text-red-400 rounded-lg hover:bg-red-500/20"
                                    >
                                        <Trash2 size={16} />
                                        Delete Data Source
                                    </button>
                                </>
                            )}
                            {getFolderDepth(selectedFolder) === 2 && (
                                <>
                                    {/* Data Group Level - Can add Tables */}
                                    <button
                                        onClick={() => setShowCreateTableModal(true)}
                                        className="w-full flex items-center gap-2 px-3 py-2 bg-emerald-500/10 text-emerald-400 rounded-lg hover:bg-emerald-500/20"
                                    >
                                        <Plus size={16} />
                                        Add Table/Object
                                    </button>
                                    <button
                                        onClick={handleDeleteFolder}
                                        className="w-full flex items-center gap-2 px-3 py-2 bg-red-500/10 text-red-400 rounded-lg hover:bg-red-500/20"
                                    >
                                        <Trash2 size={16} />
                                        Delete Data Group
                                    </button>
                                </>
                            )}
                        </div>
                        <div className="mt-3 pt-3 border-t border-slate-700 text-xs text-slate-500">
                            <div className="truncate" title={selectedFolder.path}>
                                <span className="font-medium">Path:</span> {selectedFolder.relative_path}
                            </div>
                        </div>
                    </div>
                )}
            </div>

            {/* Editor Panel - Right */}
            <div className="flex-1">
                {selectedFile ? (
                    <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-6 h-full flex flex-col">
                        <div className="flex items-center justify-between mb-4">
                            <div className="flex items-center gap-2">
                                <FileCode size={20} className="text-emerald-400" />
                                <h3 className="text-lg font-medium">
                                    {selectedFile.split('/').pop()}
                                </h3>
                            </div>
                            <div className="flex items-center gap-2">
                                {/* View/Edit Mode Toggle */}
                                {!isEditing && (
                                    <div className="flex items-center gap-1 bg-slate-800 rounded-lg p-1">
                                        <button
                                            onClick={() => setViewMode('view')}
                                            className={`px-3 py-1.5 rounded-md flex items-center gap-2 text-sm transition-colors ${
                                                viewMode === 'view'
                                                    ? 'bg-indigo-600 text-white'
                                                    : 'text-slate-400 hover:text-slate-200'
                                            }`}
                                        >
                                            <Eye size={16} />
                                            View
                                        </button>
                                        <button
                                            onClick={() => setViewMode('edit')}
                                            className={`px-3 py-1.5 rounded-md flex items-center gap-2 text-sm transition-colors ${
                                                viewMode === 'edit'
                                                    ? 'bg-indigo-600 text-white'
                                                    : 'text-slate-400 hover:text-slate-200'
                                            }`}
                                        >
                                            <FileCode size={16} />
                                            Raw
                                        </button>
                                    </div>
                                )}

                                {isEditing ? (
                                    <>
                                        {originalContent ? (
                                            <button
                                                onClick={handleUndoAI}
                                                disabled={saving || aiProcessing}
                                                className="px-3 py-1.5 bg-amber-600 text-white rounded-lg hover:bg-amber-500 flex items-center gap-2 disabled:opacity-50"
                                            >
                                                <Undo2 size={16} />
                                                Undo AI Changes
                                            </button>
                                        ) : (
                                            <button
                                                onClick={() => setShowAIModal(true)}
                                                disabled={saving || aiProcessing || !selectedFile}
                                                className="px-3 py-1.5 bg-purple-600 text-white rounded-lg hover:bg-purple-500 flex items-center gap-2 disabled:opacity-50"
                                            >
                                                {aiProcessing ? (
                                                    <>
                                                        <Loader2 size={16} className="animate-spin" />
                                                        Processing...
                                                    </>
                                                ) : (
                                                    <>
                                                        <Sparkles size={16} />
                                                        AI Assistant
                                                    </>
                                                )}
                                            </button>
                                        )}
                                        <button
                                            onClick={() => {
                                                setIsEditing(false);
                                                setViewMode('view');
                                                loadMarkdownFile(selectedFile);
                                                setOriginalContent(null); // Clear undo state
                                            }}
                                            disabled={saving || aiProcessing}
                                            className="px-3 py-1.5 bg-slate-700 text-slate-300 rounded-lg hover:bg-slate-600 flex items-center gap-2 disabled:opacity-50"
                                        >
                                            Cancel
                                        </button>
                                        <button
                                            onClick={handleSave}
                                            disabled={saving || aiProcessing}
                                            className="px-3 py-1.5 bg-indigo-600 text-white rounded-lg hover:bg-indigo-500 flex items-center gap-2 disabled:opacity-50"
                                        >
                                            {saving ? (
                                                <>
                                                    <Loader2 size={16} className="animate-spin" />
                                                    Saving...
                                                </>
                                            ) : (
                                                <>
                                                    <Save size={16} />
                                                    Save
                                                </>
                                            )}
                                        </button>
                                    </>
                                ) : (
                                    <button
                                        onClick={() => setIsEditing(true)}
                                        className="px-3 py-1.5 bg-indigo-500/10 text-indigo-400 rounded-lg hover:bg-indigo-500/20 flex items-center gap-2"
                                    >
                                        <Edit3 size={16} />
                                        Edit
                                    </button>
                                )}
                            </div>
                        </div>

                        <div className="flex-1 flex flex-col overflow-hidden">
                            {isEditing ? (
                                <MarkdownEditor
                                    content={markdownContent}
                                    onChange={setMarkdownContent}
                                    className="flex-1"
                                    placeholder="Enter markdown content..."
                                />
                            ) : viewMode === 'view' ? (
                                <div className="flex-1 overflow-auto px-4 py-3 bg-slate-950/50 border border-slate-700 rounded-lg">
                                    {markdownContent ? (
                                        <MarkdownViewer content={markdownContent} />
                                    ) : (
                                        <div className="flex items-center justify-center h-full">
                                            <span className="text-slate-500 italic">Empty file</span>
                                        </div>
                                    )}
                                </div>
                            ) : (
                                <pre className="flex-1 overflow-auto px-4 py-3 bg-slate-950/50 border border-slate-700 rounded-lg text-slate-200 font-mono text-sm">
                                    {markdownContent || <span className="text-slate-500 italic">Empty file</span>}
                                </pre>
                            )}
                            <div className="flex items-center gap-2 mt-3 text-xs text-slate-500">
                                <AlertCircle size={14} />
                                <span>
                                    {isEditing 
                                        ? 'Editing mode - make your changes and click Save' 
                                        : viewMode === 'view'
                                        ? 'Viewing rendered markdown - toggle to Raw to see source'
                                        : 'Viewing raw markdown - toggle to View to see rendered HTML'}
                                </span>
                            </div>
                        </div>
                    </div>
                ) : (
                    <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-8 h-full flex items-center justify-center">
                        <div className="text-center text-slate-400">
                            <FileText size={48} className="mx-auto mb-3 opacity-50" />
                            <p className="text-lg font-medium mb-2">No File Selected</p>
                            <p className="text-sm">Select a markdown file from the tree to view and edit</p>
                        </div>
                    </div>
                )}
            </div>

            {/* Toast Notification */}
            {toast && (
                <div
                    className={`fixed top-4 right-4 px-4 py-3 rounded-lg shadow-lg flex items-center gap-2 z-50 ${
                        toast.type === 'success'
                            ? 'bg-emerald-500/20 border border-emerald-500/50 text-emerald-300'
                            : 'bg-red-500/20 border border-red-500/50 text-red-300'
                    }`}
                >
                    {toast.type === 'success' ? <CheckCircle size={20} /> : <AlertCircle size={20} />}
                    <span>{toast.message}</span>
                    <button onClick={() => setToast(null)} className="ml-2" title="Dismiss notification">
                        <X size={16} />
                    </button>
                </div>
            )}

            {/* AI Assistant Modal */}
            {showAIModal && (
                <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
                    <div className="bg-slate-800 border border-slate-700 rounded-xl shadow-2xl max-w-2xl w-full">
                        <div className="flex items-center justify-between p-6 border-b border-slate-700">
                            <div className="flex items-center gap-3">
                                <div className="p-2 bg-purple-500/10 rounded-lg">
                                    <Sparkles className="text-purple-400" size={24} />
                                </div>
                                <div>
                                    <h3 className="text-lg font-semibold text-slate-200">AI Schema Assistant</h3>
                                    <p className="text-sm text-slate-400">Enhance table and column descriptions</p>
                                </div>
                            </div>
                            <button
                                onClick={() => {
                                    setShowAIModal(false);
                                    setAiContext('');
                                }}
                                className="text-slate-400 hover:text-slate-200 transition"
                                title="Close"
                            >
                                <X size={24} />
                            </button>
                        </div>

                        <div className="p-6">
                            <div className="mb-4">
                                <label className="block text-sm font-medium text-slate-300 mb-2">
                                    Additional Context (Optional)
                                </label>
                                <textarea
                                    value={aiContext}
                                    onChange={(e) => setAiContext(e.target.value)}
                                    placeholder="Paste documentation URL, describe business rules, or add any helpful context..."
                                    className="w-full h-32 px-3 py-2 bg-slate-900/50 border border-slate-700 rounded-lg text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-purple-500/50 resize-none"
                                />
                            </div>

                            <div className="bg-slate-900/50 border border-slate-700 rounded-lg p-4 mb-4">
                                <h4 className="text-sm font-medium text-slate-300 mb-2 flex items-center gap-2">
                                    <AlertCircle size={16} />
                                    How it works
                                </h4>
                                <ul className="text-sm text-slate-400 space-y-1">
                                    <li>• Extracts table and column info from the markdown</li>
                                    <li>• Queries database for live schema metadata</li>
                                    <li>• Uses AI to generate enhanced descriptions</li>
                                    <li>• Applies changes to the editor (you can undo)</li>
                                </ul>
                            </div>

                            <div className="flex items-center gap-3 justify-end">
                                <button
                                    onClick={() => {
                                        setShowAIModal(false);
                                        setAiContext('');
                                    }}
                                    className="px-4 py-2 bg-slate-700 text-slate-300 rounded-lg hover:bg-slate-600 transition"
                                >
                                    Cancel
                                </button>
                                <button
                                    onClick={handleAIEnhance}
                                    disabled={aiProcessing}
                                    className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-500 transition disabled:opacity-50 flex items-center gap-2"
                                >
                                    {aiProcessing ? (
                                        <>
                                            <Loader2 size={16} className="animate-spin" />
                                            Processing...
                                        </>
                                    ) : (
                                        <>
                                            <Sparkles size={16} />
                                            Generate
                                        </>
                                    )}
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {/* Create Data Source Modal */}
            {showCreateDataSourceModal && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
                    <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 max-w-md w-full mx-4">
                        <h3 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
                            <Database className="text-indigo-400" size={24} />
                            Create Data Source
                        </h3>
                        <input
                            type="text"
                            value={newItemName}
                            onChange={(e) => setNewItemName(e.target.value)}
                            placeholder="Data source name (e.g., Northwind)"
                            className="w-full bg-slate-800 border border-slate-700 rounded-lg p-3 text-white mb-4"
                            autoFocus
                        />
                        <div className="flex justify-end gap-2">
                            <button
                                onClick={() => {
                                    setShowCreateDataSourceModal(false);
                                    setNewItemName('');
                                }}
                                className="px-4 py-2 text-slate-400 hover:text-white"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={handleCreateDataSource}
                                disabled={!newItemName.trim()}
                                className="px-4 py-2 bg-indigo-600 rounded hover:bg-indigo-500 text-white disabled:opacity-50"
                            >
                                Create
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Create Data Group Modal */}
            {showCreateDataGroupModal && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
                    <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 max-w-md w-full mx-4">
                        <h3 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
                            <Layers className="text-indigo-400" size={24} />
                            Create Data Group
                        </h3>
                        <p className="text-slate-400 text-sm mb-4">
                            Adding to: <span className="font-mono text-emerald-400">{selectedFolder?.name}</span>
                        </p>
                        <input
                            type="text"
                            value={newItemName}
                            onChange={(e) => setNewItemName(e.target.value)}
                            placeholder="Data group name (e.g., Sales)"
                            className="w-full bg-slate-800 border border-slate-700 rounded-lg p-3 text-white mb-4"
                            autoFocus
                        />
                        <div className="flex justify-end gap-2">
                            <button
                                onClick={() => {
                                    setShowCreateDataGroupModal(false);
                                    setNewItemName('');
                                }}
                                className="px-4 py-2 text-slate-400 hover:text-white"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={handleCreateDataGroup}
                                disabled={!newItemName.trim()}
                                className="px-4 py-2 bg-indigo-600 rounded hover:bg-indigo-500 text-white disabled:opacity-50"
                            >
                                Create
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Create Table Modal */}
            {showCreateTableModal && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
                    <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 max-w-md w-full mx-4">
                        <h3 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
                            <Table className="text-emerald-400" size={24} />
                            Create Table/Object
                        </h3>
                        <p className="text-slate-400 text-sm mb-4">
                            Adding to: <span className="font-mono text-emerald-400">{selectedFolder?.relative_path}</span>
                        </p>
                        <input
                            type="text"
                            value={newItemName}
                            onChange={(e) => setNewItemName(e.target.value)}
                            placeholder="Object name (e.g., Customers)"
                            className="w-full bg-slate-800 border border-slate-700 rounded-lg p-3 text-white mb-4"
                            autoFocus
                        />
                        <div className="flex justify-end gap-2">
                            <button
                                onClick={() => {
                                    setShowCreateTableModal(false);
                                    setNewItemName('');
                                }}
                                className="px-4 py-2 text-slate-400 hover:text-white"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={handleCreateTable}
                                disabled={!newItemName.trim()}
                                className="px-4 py-2 bg-emerald-600 rounded hover:bg-emerald-500 text-white disabled:opacity-50"
                            >
                                Create
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};
