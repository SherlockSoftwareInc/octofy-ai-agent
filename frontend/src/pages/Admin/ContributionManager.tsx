import React, { useEffect, useState } from 'react';
import { api } from '../../api/client';
import type { ContributionItem } from '../../api/client';
import { Trash2, Check, AlertTriangle, Loader2, Inbox, Clock } from 'lucide-react';

interface ContributionManagerProps {
    onUploadStateChange?: (isUploading: boolean) => void;
}

// eslint-disable-next-line @typescript-eslint/no-unused-vars
export const ContributionManager: React.FC<ContributionManagerProps> = ({ onUploadStateChange: _onUploadStateChange }) => {
    const [items, setItems] = useState<ContributionItem[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [processingId, setProcessingId] = useState<string | null>(null);
    const [confirmDialog, setConfirmDialog] = useState<{ visible: boolean; action: 'approve' | 'reject'; item?: ContributionItem }>({ visible: false, action: 'approve' });
    const [editedQuestion, setEditedQuestion] = useState('');
    const [editedSQL, setEditedSQL] = useState('');
    const [similarQuestion, setSimilarQuestion] = useState<{ question: string; sql_query: string } | null>(null);
    const [isCheckingSimilarity, setIsCheckingSimilarity] = useState(false);

    const fetchData = async () => {
        setIsLoading(true);
        try {
            const data = await api.admin.getContributions();
            if (Array.isArray(data)) {
                setItems(data);
            } else {
                setItems([]);
            }
        } catch (e) {
            console.error('Failed to fetch contributions:', e);
            setItems([]);
        } finally {
            setIsLoading(false);
        }
    };

    const handleApprove = async (item: ContributionItem) => {
        if (!item.id) return;

        setProcessingId(item.id);
        try {
            await api.admin.approveContribution(item.id, editedQuestion, editedSQL, item.knowledge_type);
            // Remove from list
            setItems(prev => prev.filter(i => i.id !== item.id));
        } catch (e) {
            alert('Failed to approve contribution');
            console.error(e);
        } finally {
            setProcessingId(null);
            setConfirmDialog({ visible: false, action: 'approve' });
        }
    };

    const handleReject = async (item: ContributionItem) => {
        if (!item.id) return;

        setProcessingId(item.id);
        try {
            await api.admin.rejectContribution(item.id);
            // Remove from list
            setItems(prev => prev.filter(i => i.id !== item.id));
        } catch (e) {
            alert('Failed to reject contribution');
            console.error(e);
        } finally {
            setProcessingId(null);
            setConfirmDialog({ visible: false, action: 'reject' });
        }
    };

    const openConfirmDialog = async (action: 'approve' | 'reject', item: ContributionItem) => {
        setEditedQuestion(item.question);
        setEditedSQL(item.sql_query);
        setSimilarQuestion(null);
        setConfirmDialog({ visible: true, action, item });

        // Check for similar questions in knowledge base when opening approve dialog
        if (action === 'approve') {
            setIsCheckingSimilarity(true);
            try {
                // Fetch all fewshots and find similar one by ID if available
                const fewshots = await api.admin.getFewShots();

                if (item.similar_to_id) {
                    // Find the similar item by ID
                    const similar = fewshots.find(fs => fs.id === item.similar_to_id);
                    if (similar) {
                        setSimilarQuestion({ question: similar.question, sql_query: similar.sql_query });
                    }
                } else if (item.similarity_score && item.similarity_score >= 0.9) {
                    // If we have a high similarity score but no ID, search by matching question
                    // This is a fallback - ideally the server would provide the similar_to_id
                }
            } catch (e) {
                console.error('Failed to check similarity:', e);
            } finally {
                setIsCheckingSimilarity(false);
            }
        }
    };

    useEffect(() => {
        fetchData();
    }, []);

    // Format timestamp for display
    const formatDate = (isoString?: string) => {
        if (!isoString) return 'Unknown';
        try {
            return new Date(isoString).toLocaleString();
        } catch {
            return isoString;
        }
    };

    const getCodeLabel = (type?: string) => {
        if (type === 'r_code') return 'R Code';
        if (type === 'sas_code') return 'SAS Code';
        if (type === 'python_code') return 'Python Code';
        return 'SQL Query';
    };

    return (
        <div className="p-6 w-full h-full">
            <div className="flex justify-between items-center mb-6">
                <h2 className="text-2xl font-bold bg-gradient-to-r from-amber-400 to-orange-400 bg-clip-text text-transparent">
                    Contribution Review
                </h2>
                <button
                    onClick={fetchData}
                    disabled={isLoading}
                    className="flex items-center gap-2 px-4 py-2 bg-slate-700 rounded-lg hover:bg-slate-600 transition text-white"
                >
                    {isLoading ? <Loader2 size={18} className="animate-spin" /> : <Clock size={18} />}
                    Refresh
                </button>
            </div>

            {/* Info Banner */}
            <div className="bg-amber-500/10 border border-amber-500/30 rounded-xl p-4 mb-6">
                <div className="flex items-start gap-3">
                    <AlertTriangle className="w-5 h-5 text-amber-400 flex-shrink-0 mt-0.5" />
                    <div>
                        <h4 className="text-amber-300 font-semibold mb-1">Review Pending Contributions</h4>
                        <p className="text-amber-300/80 text-sm">
                            Items shown here were submitted by users as potential training examples.
                            Approve them to add to the Knowledge Base, or reject them to discard.
                            A yellow badge indicates a similar example already exists in the Knowledge Base.
                        </p>
                    </div>
                </div>
            </div>

            {/* Loading State */}
            {isLoading && (
                <div className="text-center p-12">
                    <Loader2 className="w-8 h-8 animate-spin text-amber-400 mx-auto mb-3" />
                    <p className="text-slate-400">Loading contributions...</p>
                </div>
            )}

            {/* Empty State */}
            {!isLoading && items.length === 0 && (
                <div className="text-center p-12 bg-slate-900/50 border border-slate-800 rounded-xl">
                    <Inbox className="w-12 h-12 text-slate-600 mx-auto mb-4" />
                    <h3 className="text-lg font-semibold text-slate-400 mb-2">No Pending Contributions</h3>
                    <p className="text-slate-500 text-sm">
                        User-submitted examples will appear here for your review.
                    </p>
                </div>
            )}

            {/* Contribution List */}
            {!isLoading && items.length > 0 && (
                <div className="grid gap-4">
                    {items.map((item, idx) => (
                        <div
                            key={item.id || idx}
                            className="bg-slate-900 border border-slate-800 rounded-xl p-5 relative group"
                        >
                            {/* Header Row */}
                            <div className="flex justify-between items-start mb-3">
                                <div className="flex-1">
                                    <div className="flex items-center gap-2 mb-1">
                                        {/* Knowledge Type Badge */}
                                        <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs border ${item.knowledge_type === 'r_code'
                                            ? 'bg-orange-500/20 text-orange-300 border-orange-500/30'
                                            : item.knowledge_type === 'sas_code'
                                                ? 'bg-blue-500/20 text-blue-300 border-blue-500/30'
                                                : item.knowledge_type === 'python_code'
                                                    ? 'bg-yellow-500/20 text-yellow-300 border-yellow-500/30'
                                                    : 'bg-cyan-500/20 text-cyan-300 border-cyan-500/30'
                                            }`}>
                                            {getCodeLabel(item.knowledge_type)}
                                        </span>

                                        {/* Similarity Warning Badge */}
                                        {item.similarity_score && item.similarity_score >= 0.9 && (
                                            <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-amber-500/20 text-amber-300 text-xs rounded-full border border-amber-500/30">
                                                <AlertTriangle size={12} />
                                                Similar exists ({Math.round(item.similarity_score * 100)}%)
                                            </span>
                                        )}
                                        <span className="text-xs text-slate-500">
                                            Submitted: {formatDate(item.submitted_at)}
                                        </span>
                                        {item.user_id && item.user_id !== 'anonymous' && (
                                            <span className="text-xs text-slate-500">
                                                by {item.user_id}
                                            </span>
                                        )}
                                    </div>
                                    <p className="text-indigo-300 font-medium">{item.question}</p>
                                </div>

                                {/* Action Buttons */}
                                <div className="flex items-center gap-2 ml-4">
                                    <button
                                        onClick={() => openConfirmDialog('approve', item)}
                                        disabled={processingId === item.id}
                                        className="flex items-center gap-1 px-3 py-1.5 bg-emerald-600/20 text-emerald-300 border border-emerald-500/30 rounded-lg hover:bg-emerald-500/30 transition disabled:opacity-50"
                                        title="Review and add to Knowledge Base"
                                    >
                                        {processingId === item.id ? (
                                            <Loader2 size={14} className="animate-spin" />
                                        ) : (
                                            <Check size={14} />
                                        )}
                                        Review
                                    </button>
                                    <button
                                        onClick={() => openConfirmDialog('reject', item)}
                                        disabled={processingId === item.id}
                                        className="flex items-center gap-1 px-3 py-1.5 bg-red-600/20 text-red-300 border border-red-500/30 rounded-lg hover:bg-red-500/30 transition disabled:opacity-50"
                                        title="Reject and delete"
                                    >
                                        {processingId === item.id ? (
                                            <Loader2 size={14} className="animate-spin" />
                                        ) : (
                                            <Trash2 size={14} />
                                        )}
                                        Reject
                                    </button>
                                </div>
                            </div>

                            {/* SQL Content */}
                            <div className="bg-slate-950 rounded-lg p-3 text-xs font-mono text-slate-400 overflow-x-auto">
                                <pre className="whitespace-pre-wrap break-all">{item.sql_query}</pre>
                            </div>
                        </div>
                    ))}
                </div>
            )}

            {/* Confirmation Dialog */}
            {
                confirmDialog.visible && confirmDialog.item && (
                    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 backdrop-blur-sm">
                        <div className="bg-slate-900 border border-slate-800 rounded-lg p-6 max-w-lg w-full mx-4 shadow-2xl">
                            <h2 className="text-lg font-bold text-white mb-2 flex items-center gap-2">
                                {confirmDialog.action === 'approve' ? 'Review Contribution' : 'Reject Contribution?'}
                                {confirmDialog.item && (
                                    <span className={`text-xs font-normal px-2 py-0.5 rounded-full border ${confirmDialog.item.knowledge_type === 'r_code'
                                        ? 'bg-orange-500/20 text-orange-300 border-orange-500/30'
                                        : confirmDialog.item.knowledge_type === 'sas_code'
                                            ? 'bg-blue-500/20 text-blue-300 border-blue-500/30'
                                            : confirmDialog.item.knowledge_type === 'python_code'
                                                ? 'bg-yellow-500/20 text-yellow-300 border-yellow-500/30'
                                                : 'bg-cyan-500/20 text-cyan-300 border-cyan-500/30'
                                        }`}>
                                        {getCodeLabel(confirmDialog.item.knowledge_type)}
                                    </span>
                                )}
                            </h2>
                            <p className="text-slate-300 mb-4">
                                {confirmDialog.action === 'approve'
                                    ? 'Review and edit the question if needed, then add to the Knowledge Base.'
                                    : 'This will permanently delete the contribution. This action cannot be undone.'}
                            </p>

                            {/* Similarity Warning */}
                            {confirmDialog.action === 'approve' && (
                                <div className="mb-4">
                                    {isCheckingSimilarity ? (
                                        <div className="flex items-center gap-2 text-slate-400 text-sm">
                                            <Loader2 size={14} className="animate-spin" />
                                            Checking for similar questions...
                                        </div>
                                    ) : similarQuestion ? (
                                        <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-3">
                                            <div className="flex items-center gap-2 text-amber-300 text-sm font-medium mb-2">
                                                <AlertTriangle size={14} />
                                                Similar question found in Knowledge Base ({Math.round((confirmDialog.item?.similarity_score || 0) * 100)}% match)
                                            </div>
                                            <div className="text-amber-200/80 text-sm mb-1">
                                                <strong>Existing:</strong> {similarQuestion.question}
                                            </div>
                                            <div className="text-amber-200/60 text-xs font-mono truncate">
                                                {similarQuestion.sql_query.substring(0, 100)}...
                                            </div>
                                        </div>
                                    ) : confirmDialog.item?.similarity_score && confirmDialog.item.similarity_score >= 0.9 ? (
                                        <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-3">
                                            <div className="flex items-center gap-2 text-amber-300 text-sm font-medium">
                                                <AlertTriangle size={14} />
                                                A similar question already exists ({Math.round(confirmDialog.item.similarity_score * 100)}% match)
                                            </div>
                                        </div>
                                    ) : (
                                        <div className="bg-emerald-500/10 border border-emerald-500/30 rounded-lg p-3">
                                            <div className="flex items-center gap-2 text-emerald-300 text-sm font-medium">
                                                <Check size={14} />
                                                No similar questions found - this appears to be unique
                                            </div>
                                        </div>
                                    )}
                                </div>
                            )}

                            {/* Editable Question / Preview */}
                            <div className="space-y-4 mb-6">
                                <div>
                                    <label htmlFor="edit-question" className="block text-sm font-medium text-slate-400 mb-1">Question</label>
                                    {confirmDialog.action === 'approve' ? (
                                        <textarea
                                            id="edit-question"
                                            value={editedQuestion}
                                            onChange={(e) => setEditedQuestion(e.target.value)}
                                            rows={3}
                                            placeholder={`Enter the question for this ${confirmDialog.item?.knowledge_type === 'r_code' ? 'R' : confirmDialog.item?.knowledge_type === 'sas_code' ? 'SAS' : confirmDialog.item?.knowledge_type === 'python_code' ? 'Python' : 'SQL'} example`}
                                            className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-slate-200 focus:outline-none focus:ring-2 focus:ring-emerald-500/50 focus:border-emerald-500 resize-none"
                                        />
                                    ) : (
                                        <p className="px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-slate-400">{confirmDialog.item.question}</p>
                                    )}
                                </div>
                                <div>
                                    <label htmlFor="sql-query-preview" className="block text-sm font-medium text-slate-400 mb-1">
                                        {getCodeLabel(confirmDialog.item?.knowledge_type)}
                                    </label>
                                    {confirmDialog.action === 'approve' ? (
                                        <textarea
                                            id="sql-query-preview"
                                            value={editedSQL}
                                            onChange={(e) => setEditedSQL(e.target.value)}
                                            rows={4}
                                            placeholder={`Enter the ${getCodeLabel(confirmDialog.item?.knowledge_type)}`}
                                            className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-slate-200 font-mono text-xs focus:outline-none focus:ring-2 focus:ring-emerald-500/50 focus:border-emerald-500 resize-none"
                                        />
                                    ) : (
                                        <textarea
                                            id="sql-query-preview"
                                            readOnly
                                            value={confirmDialog.item.sql_query}
                                            rows={4}
                                            title={getCodeLabel(confirmDialog.item?.knowledge_type)}
                                            className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-slate-500 font-mono text-xs resize-none cursor-default"
                                        />
                                    )}
                                </div>
                            </div>

                            <div className="flex gap-3 justify-end">
                                <button
                                    onClick={() => setConfirmDialog({ visible: false, action: 'approve' })}
                                    disabled={!!processingId}
                                    className="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                                >
                                    Cancel
                                </button>
                                <button
                                    onClick={() => {
                                        if (confirmDialog.action === 'approve') {
                                            handleApprove(confirmDialog.item!);
                                        } else {
                                            handleReject(confirmDialog.item!);
                                        }
                                    }}
                                    disabled={!!processingId}
                                    className={`flex items-center gap-2 px-4 py-2 text-white rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${confirmDialog.action === 'approve'
                                        ? 'bg-emerald-600 hover:bg-emerald-700'
                                        : 'bg-red-600 hover:bg-red-700'
                                        }`}
                                >
                                    {processingId === confirmDialog.item?.id && <Loader2 size={16} className="animate-spin" />}
                                    {confirmDialog.action === 'approve'
                                        ? (processingId === confirmDialog.item?.id ? 'Adding...' : 'Add to Knowledge Base')
                                        : (processingId === confirmDialog.item?.id ? 'Rejecting...' : 'Reject')}
                                </button>
                            </div>
                        </div>
                    </div>
                )
            }
        </div >
    );
};
