import React, { useMemo, useState } from 'react';
import { Copy, Check, Loader2, Gift, Play } from 'lucide-react';
import { Toast } from '../Toast';
import type { ToastType } from '../Toast';
import { api, type FewShotItem, type ExecutePythonResponse } from '../../api/client';
import { DataTable } from '../DataTable/DataTable';
import { suggestChart } from '../../utils/chartSuggester';
import { ChartRenderer } from '../Charts/ChartRenderer';

const ExecutionResultViewer: React.FC<{ results: any[] }> = ({ results }) => {
    const [showRawData, setShowRawData] = useState(false);

    // 1. Identify valid charts
    const resultsWithCharts = useMemo(() => {
        return results.map((res: any) => ({
            ...res,
            chartSuggestion: suggestChart(res.data)
        }));
    }, [results]);

    // 2. Find the primary chart (prioritize the last one with a valid suggestion)
    const primaryChartIndex = resultsWithCharts.map(r => r.chartSuggestion.type).lastIndexOf('bar');
    // Heuristic: Prefer Bar charts as they are most common for "Category vs Value". 
    // If no bar, take last of any type.
    const lastAnyChartIndex = resultsWithCharts.map(r => r.chartSuggestion.type).reduce((lastIndex, type, idx) => type !== 'none' ? idx : lastIndex, -1);

    const targetIndex = primaryChartIndex !== -1 ? primaryChartIndex : lastAnyChartIndex;
    const primaryResult = targetIndex !== -1 ? resultsWithCharts[targetIndex] : null;

    // If we have a primary chart, we show it and hide the rest behind a toggle
    const hasPrimaryChart = !!primaryResult;

    return (
        <div className="space-y-6">
            {/* Primary Visualization Area */}
            {hasPrimaryChart && (
                <div className="bg-slate-900/50 rounded-xl border border-slate-800 p-4 shadow-sm">
                    <div className="flex items-center justify-between mb-4 border-b border-slate-700/50 pb-2">
                        <div className="flex items-center gap-2">
                            <div className="w-1.5 h-1.5 rounded-full bg-cyan-400"></div>
                            <h3 className="text-sm font-semibold text-slate-200 uppercase tracking-wider">
                                Visual Analysis: {primaryResult.name}
                            </h3>
                        </div>
                        <div className="text-[10px] text-slate-500 bg-slate-800 px-2 py-1 rounded">
                            {primaryResult.chartSuggestion.type.toUpperCase()} CHART
                        </div>
                    </div>

                    <div className="h-80 w-full">
                        <ChartRenderer data={primaryResult.data} suggestion={primaryResult.chartSuggestion} />
                    </div>
                </div>
            )}

            {/* Toggle for Raw Data */}
            {hasPrimaryChart && (
                <div className="flex justify-center">
                    <button
                        onClick={() => setShowRawData(!showRawData)}
                        className="text-xs text-slate-500 hover:text-slate-300 flex items-center gap-2 transition-colors"
                    >
                        <span>{showRawData ? 'Hide' : 'Show'} Raw DataFrames & Tables</span>
                        <div className={`transition-transform duration-200 ${showRawData ? 'rotate-180' : ''}`}>
                            ▼
                        </div>
                    </button>
                </div>
            )}

            {/* List of all DataFrames (shown if no chart or if toggled) */}
            {(!hasPrimaryChart || showRawData) && (
                <div className="space-y-8 animate-in fade-in slide-in-from-top-4 duration-300">
                    {resultsWithCharts.map((res: any, idx: number) => (
                        <div key={idx} className={`p-4 rounded-lg border ${hasPrimaryChart && idx === targetIndex ? 'border-cyan-900/30 bg-cyan-950/10' : 'border-slate-800 bg-slate-900/20'}`}>
                            <div className="flex items-center justify-between mb-3">
                                <div className="text-xs text-slate-400 font-mono flex items-center gap-2">
                                    <span className="font-semibold text-emerald-300">{res.name}</span>
                                    <span>({res.rows} rows, {res.columns.length} cols)</span>
                                </div>
                                {res.chartSuggestion.type !== 'none' && idx !== targetIndex && (
                                    <div className="text-[10px] text-slate-500">
                                        Chart Available
                                    </div>
                                )}
                            </div>

                            {/* Show chart here too if it's not the primary one we just showed above, OR if we just want to see everything */}
                            {res.chartSuggestion.type !== 'none' && idx !== targetIndex && (
                                <div className="mb-4 h-48 border border-slate-800/50 rounded bg-slate-900/50">
                                    <ChartRenderer data={res.data} suggestion={res.chartSuggestion} />
                                </div>
                            )}

                            <div className="rounded-lg border border-slate-700 overflow-hidden">
                                <DataTable
                                    data={res.data}
                                    columns={res.columns}
                                    pageSize={5}
                                />
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
};

interface SQLResultDisplayProps {
    sql: string;
    sourceQuestion?: string;
    allUserMessages?: string[];
    queryType?: 'database' | 'r_code' | 'sas_code' | 'python_code' | 'general' | 'uncertain' | 'search';
}

export const SQLResultDisplay: React.FC<SQLResultDisplayProps> = ({ sql, sourceQuestion, allUserMessages = [], queryType }) => {
    const [copied, setCopied] = useState(false);
    const [toast, setToast] = useState<{ message: string; type: ToastType } | null>(null);
    const [showDialog, setShowDialog] = useState(false);
    const [draftQuestion, setDraftQuestion] = useState('');
    const [draftSQL, setDraftSQL] = useState(sql);
    const [existingFewShots, setExistingFewShots] = useState<FewShotItem[]>([]);
    const [isLoadingFewShots, setIsLoadingFewShots] = useState(false);
    const [isSaving, setIsSaving] = useState(false);
    const [isRunning, setIsRunning] = useState(false);
    const [executionResult, setExecutionResult] = useState<ExecutePythonResponse | null>(null);

    const normalizedExisting = useMemo(() => {
        return existingFewShots.map(item => ({
            question: (item.question || '').trim().toLowerCase(),
            sql: (item.sql_query || '').replace(/\s+/g, ' ').trim().toLowerCase()
        }));
    }, [existingFewShots]);

    const handleCopy = async () => {
        if (!sql) return;

        try {
            await navigator.clipboard.writeText(sql);
            setCopied(true);
            setToast({ message: 'SQL copied to clipboard!', type: 'success' });

            // Reset state after 2 seconds
            setTimeout(() => {
                setCopied(false);
            }, 2000);
        } catch (err) {
            console.error('Failed to copy text: ', err);
            setToast({ message: 'Failed to copy SQL', type: 'error' });
        }
    };

    const openContributeDialog = async () => {
        if (!sourceQuestion) {
            setToast({ message: 'Missing source question to contribute.', type: 'error' });
            return;
        }

        // Combine all user messages from the conversation
        const combinedQuestion = allUserMessages.length > 0
            ? allUserMessages.join('\n')
            : sourceQuestion;

        setDraftQuestion(combinedQuestion);
        setDraftSQL(sql);
        setShowDialog(true);

        // Load existing knowledge base items for duplicate detection
        if (existingFewShots.length === 0 && !isLoadingFewShots) {
            setIsLoadingFewShots(true);
            try {
                const data = await api.admin.getFewShots();
                if (Array.isArray(data)) {
                    setExistingFewShots(data);
                }
            } catch (error) {
                console.error('Failed to fetch knowledge base', error);
            } finally {
                setIsLoadingFewShots(false);
            }
        }
    };

    const handleSubmitContribution = async () => {
        const trimmedQuestion = draftQuestion.trim();
        const trimmedSQL = draftSQL.trim();

        if (!trimmedQuestion || !trimmedSQL) {
            setToast({ message: 'Question and SQL are required.', type: 'error' });
            return;
        }

        setIsSaving(true);
        try {
            // Map queryType to knowledge_type
            let knowledgeType = 'sql_query';
            if (queryType === 'r_code') knowledgeType = 'r_code';
            if (queryType === 'sas_code') knowledgeType = 'sas_code';
            if (queryType === 'python_code') knowledgeType = 'python_code';

            // Submit to contribution library instead of directly to knowledge base
            const response = await api.contributions.submit({
                question: trimmedQuestion,
                sql_query: trimmedSQL,
                knowledge_type: knowledgeType
            });

            if (response.success) {
                // Show success message with potential similarity warning
                if (response.similarity_warning) {
                    setToast({
                        message: 'Thank you! Your contribution has been submitted for review. Note: A similar example may already exist.',
                        type: 'info'
                    });
                } else {
                    setToast({
                        message: 'Thank you! Your contribution has been submitted for review.',
                        type: 'success'
                    });
                }
                setShowDialog(false);
            } else {
                setToast({ message: response.message || 'Failed to submit contribution.', type: 'error' });
            }
        } catch (error) {
            console.error('Failed to submit contribution', error);
            setToast({ message: 'Failed to submit contribution. Please try again.', type: 'error' });
        } finally {
            setIsSaving(false);
        }
    };

    const resultContainerRef = React.useRef<HTMLDivElement>(null);

    const handleRun = async () => {
        if (!sql) return;
        setIsRunning(true);
        setExecutionResult(null);
        try {
            const result = await api.executePython(sql);
            setExecutionResult(result);

            // Scroll the result container into view
            setTimeout(() => {
                if (resultContainerRef.current) {
                    resultContainerRef.current.scrollIntoView({ behavior: 'smooth', block: 'end' });
                }
            }, 100);

        } catch (error) {
            console.error('Execution failed:', error);
            setToast({ message: 'Execution failed', type: 'error' });
        } finally {
            setIsRunning(false);
        }
    };

    return (
        <div className="relative group mt-4">
            {/* Decorative background blur */}
            <div className="absolute -inset-1 bg-gradient-to-r from-cyan-500 to-blue-500 rounded-2xl opacity-20 group-hover:opacity-30 blur transition duration-500"></div>

            <div className="relative bg-slate-900 rounded-xl border border-slate-700/50 shadow-xl overflow-hidden">
                {/* Header */}
                <div className="flex items-center justify-between px-4 py-2 bg-slate-800/50 border-b border-slate-700/50">
                    <div className="text-xs font-semibold text-slate-300 uppercase tracking-wider flex items-center gap-2">
                        <div className="w-2 h-2 bg-cyan-400 rounded-full animate-pulse"></div>
                        {queryType === 'r_code' ? 'Generated R Code' : queryType === 'sas_code' ? 'Generated SAS Code' : queryType === 'python_code' ? 'Generated Python Code' : 'Generated SQL Query'}
                    </div>
                    <div className="flex items-center gap-2">

                        <button
                            onClick={openContributeDialog}
                            disabled={!sourceQuestion}
                            className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg transition-all duration-200 border ${sourceQuestion
                                ? 'bg-amber-600/20 text-amber-200 border-amber-500/40 hover:bg-amber-500/30'
                                : 'bg-slate-800 text-slate-500 border-slate-700 cursor-not-allowed'
                                }`}
                            title={sourceQuestion ? 'Submit as a training example for review' : 'No user question available'}
                        >
                            <Gift size={12} />
                            <span>Contribute Example</span>
                        </button>
                        <button
                            onClick={handleCopy}
                            className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg transition-all duration-200 ${copied
                                ? 'bg-green-500/20 text-green-300 border border-green-500/30'
                                : 'bg-slate-700 hover:bg-slate-600 text-slate-300 border border-slate-600 hover:border-slate-500'
                                }`}
                            title="Copy to clipboard"
                        >
                            {copied ? (
                                <>
                                    <Check size={12} className="stroke-[3]" />
                                    <span>Copied!</span>
                                </>
                            ) : (
                                <>
                                    <Copy size={12} />
                                    <span>Copy</span>
                                </>
                            )}
                        </button>
                    </div>
                </div>

                {/* SQL Content */}
                <div className="p-4 bg-slate-950">
                    <pre className="text-sm text-cyan-50 font-mono overflow-x-auto whitespace-pre-wrap break-all select-text p-2">
                        {sql}
                    </pre>
                </div>

                {/* Run Action Toolbar */}
                {queryType === 'python_code' && (
                    <div className="px-4 py-2 bg-slate-900 border-t border-slate-800 flex justify-end">
                        <button
                            onClick={handleRun}
                            disabled={isRunning}
                            className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg transition-all duration-200 border ${isRunning
                                ? 'bg-emerald-600/20 text-emerald-200 border-emerald-500/40 cursor-wait'
                                : 'bg-emerald-600/20 text-emerald-200 border-emerald-500/40 hover:bg-emerald-500/30'
                                }`}
                            title="Run Python Code"
                        >
                            {isRunning ? <Loader2 size={12} className="animate-spin" /> : <Play size={12} className="fill-current" />}
                            <span>{isRunning ? 'Running...' : 'Run'}</span>
                        </button>
                    </div>
                )}

                {/* Execution Results */}
                {executionResult && (
                    <div className="border-t border-slate-700/50 bg-slate-900/50">
                        <div className="px-4 py-2 border-b border-slate-700/50 flex items-center gap-2">
                            <div className="w-2 h-2 bg-emerald-500 rounded-full"></div>
                            <span className="text-xs font-semibold text-slate-300 uppercase tracking-wider">Execution Result</span>
                        </div>
                        <div className="p-4 overflow-x-auto">
                            {executionResult.output && (
                                <div className="mb-4">
                                    <h4 className="text-xs text-slate-500 font-semibold mb-2 uppercase">Output</h4>
                                    <pre className="text-xs text-slate-300 font-mono bg-slate-950/50 p-3 rounded-lg border border-slate-800 whitespace-pre-wrap">
                                        {executionResult.output}
                                    </pre>
                                </div>
                            )}

                            {executionResult.error && (
                                <div className="mb-4">
                                    <h4 className="text-xs text-red-400 font-semibold mb-2 uppercase">Error</h4>
                                    <pre className="text-xs text-red-300 font-mono bg-red-950/20 p-3 rounded-lg border border-red-900/50 whitespace-pre-wrap">
                                        {executionResult.error}
                                    </pre>
                                </div>
                            )}

                            {executionResult.results && executionResult.results.length > 0 && (
                                <ExecutionResultViewer results={executionResult.results} />
                            )}
                        </div>
                    </div>
                )}
            </div>


            {/* Contribute Example Dialog */}
            {showDialog && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 px-4">
                    <div className="w-full max-w-2xl bg-slate-950 border border-slate-800 rounded-2xl shadow-2xl p-6 space-y-4">
                        <div className="flex items-start justify-between">
                            <div>
                                <p className="text-xs uppercase tracking-[0.2em] text-slate-500 mb-1">Review & Submit</p>
                                <h3 className="text-xl font-semibold text-white">Contribute Example</h3>
                            </div>
                            <div className="text-xs text-slate-500">{isLoadingFewShots ? 'Checking...' : 'Ready'}</div>
                        </div>

                        {/* Info Banner */}
                        <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-3 text-sm text-amber-300/80">
                            <Gift size={14} className="inline mr-2" />
                            Your contribution will be submitted for admin review before being added to the Knowledge Base.
                        </div>

                        <div className="space-y-3">
                            <label className="text-sm text-slate-300">User Request</label>
                            <textarea
                                className="w-full bg-slate-900 border border-slate-700 rounded-lg p-3 text-sm text-slate-100 focus:ring-2 focus:ring-amber-500 outline-none"
                                rows={3}
                                value={draftQuestion}
                                onChange={(e) => setDraftQuestion(e.target.value)}
                                placeholder="Enter the natural language question"
                            />
                        </div>

                        <div className="space-y-3">
                            <label className="text-sm text-slate-300">
                                {queryType === 'r_code' ? 'Generated R Code' : queryType === 'sas_code' ? 'Generated SAS Code' : queryType === 'python_code' ? 'Generated Python Code' : 'Generated SQL'}
                            </label>
                            <textarea
                                className="w-full bg-slate-900 border border-slate-700 rounded-lg p-3 text-sm font-mono text-cyan-100 focus:ring-2 focus:ring-amber-500 outline-none"
                                rows={6}
                                value={draftSQL}
                                onChange={(e) => setDraftSQL(e.target.value)}
                                placeholder={`Enter the ${queryType === 'r_code' ? 'R code' : queryType === 'sas_code' ? 'SAS code' : queryType === 'python_code' ? 'Python code' : 'SQL'} to store`}
                            />
                        </div>

                        <div className="flex items-center justify-between text-xs text-slate-400">
                            <span>Your contribution helps improve the AI agent.</span>
                            {hasSimilarIndicator(normalizedExisting, draftQuestion, draftSQL) && (
                                <span className="text-amber-300">Similar example may exist</span>
                            )}
                        </div>

                        <div className="flex justify-end gap-3 pt-2">
                            <button
                                onClick={() => setShowDialog(false)}
                                className="px-4 py-2 text-slate-300 hover:text-white bg-slate-800/80 border border-slate-700 rounded-lg"
                                disabled={isSaving}
                            >
                                Cancel
                            </button>
                            <button
                                onClick={handleSubmitContribution}
                                disabled={isSaving}
                                className="px-4 py-2 bg-amber-600 hover:bg-amber-500 text-white rounded-lg flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                                {isSaving ? <Loader2 size={16} className="animate-spin" /> : <Gift size={16} />}
                                <span>{isSaving ? 'Submitting...' : 'Submit for Review'}</span>
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Local Toast for this component interaction */}
            {toast && (
                <Toast
                    message={toast.message}
                    type={toast.type}
                    onClose={() => setToast(null)}
                />
            )}
            <div ref={resultContainerRef} />
        </div>
    );
};

function hasSimilarIndicator(existing: { question: string; sql: string }[], draftQuestion: string, draftSQL: string): boolean {
    const q = draftQuestion.trim().toLowerCase();
    const s = draftSQL.trim().replace(/\s+/g, ' ').toLowerCase();
    if (!q && !s) return false;
    return existing.some(item => item.question === q || item.sql === s);
}
