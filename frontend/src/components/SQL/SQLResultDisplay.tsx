import React, { useMemo, useState } from 'react';
import { Copy, Check, Loader2, Gift, Play } from 'lucide-react';
import { Toast } from '../Toast';
import type { ToastType } from '../Toast';
import { api, type FewShotItem, type ExecutePythonResponse, type ExecutePythonResult, type StructuredTableData, type ChartRecommendation, type ChartMetadata, type ChartTypeOption } from '../../api/client';
import { DataTable } from '../DataTable/DataTable';




import { ResultChart } from './ResultChart';

const ResultsWrapper = ({ children }: { children: React.ReactNode }) => (
    <div style={{
        maxWidth: '100%',
        overflowX: 'auto',
        margin: '10px 0',
        border: '1px solid #334155', // slate-700
        borderRadius: '8px',
        backgroundColor: 'rgba(15, 23, 42, 0.3)' // slate-900/30
    }}>
        {children}
    </div>
);

/**
 * Convert a ChartRecommendation (from backend) to ChartMetadata (for ResultChart)
 */
function recommendationToMetadata(rec: ChartRecommendation): ChartMetadata {
    // Determine if this is a stacked chart type
    const isStacked = rec.chart_type === 'stackedBar' || rec.chart_type === 'stackedColumn';
    
    return {
        type: rec.chart_type as ChartMetadata['type'],
        x_axis: rec.x_axis || null,
        y_axes: rec.y_axis || [],
        is_stacked: isStacked,
    };
}

const ExecutionResultViewer: React.FC<{ results: ExecutePythonResult[]; recommendation?: ChartRecommendation; pythonSummary?: string }> = ({ results, recommendation, pythonSummary }) => {
    const normalizeTableData = (data: StructuredTableData | Array<Record<string, unknown>>, fallbackColumns?: string[]) => {
        if (Array.isArray(data)) {
            return { columns: fallbackColumns || Object.keys(data[0] || {}), rows: data };
        }
        return { columns: data.columns, rows: data.data };
    };

    const resultsWithRows = useMemo(() => {
        // Filter: If 'final_result_df' exists, show only that one.
        // Otherwise, show all results found (fallback).
        const finalResult = results.find(r => r.name === 'final_result_df');
        const filteredResults = finalResult ? [finalResult] : results;

        return filteredResults.map((res) => {
            const normalized = normalizeTableData(res.data as StructuredTableData | Array<Record<string, unknown>>, res.columns);
            return {
                ...res,
                normalized
            };
        });
    }, [results]);

    // Convert recommendation to chart metadata if available
    const chartMetadataFromRecommendation = useMemo(() => {
        if (!recommendation || recommendation.chart_type === 'none') {
            return undefined;
        }
        return recommendationToMetadata(recommendation);
    }, [recommendation]);

    return (
        <div className="space-y-6 w-full max-w-full">
            {resultsWithRows.map((res, idx) => {
                const title = res.name;
                
                // Determine which chart metadata to use:
                // 1. Prefer recommendation from backend (supports override)
                // 2. Fall back to result-level chart_metadata
                // 3. Fall back to viz_config based chart_metadata
                const effectiveMetadata = chartMetadataFromRecommendation || res.chart_metadata;
                const shouldShowChart = effectiveMetadata && effectiveMetadata.type !== 'none';
                const vizConfigBlocksChart = res.viz_config && 
                    (res.viz_config.category === 'no_chart' || res.viz_config.category === 'too_much_data');

                return (
                    <div key={idx} className="w-full max-w-full bg-slate-900/50 rounded-xl border border-slate-800 p-4 shadow-sm overflow-hidden">
                        <div className="flex items-center justify-between mb-4 border-b border-slate-700/50 pb-2">
                            <div className="flex items-center gap-2">
                                <div className="w-1.5 h-1.5 rounded-full bg-cyan-400"></div>
                                <h3 className="text-sm font-semibold text-slate-200 uppercase tracking-wider">
                                    EXECUTION RESULT ({title.toUpperCase()})
                                </h3>
                            </div>
                            {recommendation && (
                                <div className="text-xs text-slate-500">
                                    {recommendation.title}
                                </div>
                            )}
                        </div>

                        <ResultsWrapper>
                            <div className="w-full min-w-max">
                                <DataTable
                                    data={res.normalized.rows}
                                    columns={res.normalized.columns}
                                    pageSize={5}
                                />
                            </div>
                        </ResultsWrapper>

                        {/* LLM Summary Section */}
                        {idx === 0 && pythonSummary && (
                          <div className="mt-3 p-3 bg-slate-800/40 border border-indigo-700/30 rounded-lg">
                            <div className="text-xs text-indigo-300 font-semibold mb-1">AI Summary</div>
                            <div className="text-sm text-indigo-100 whitespace-pre-line">{pythonSummary}</div>
                          </div>
                        )}

                        {/* Chart Section */}
                        {vizConfigBlocksChart ? (
                            <div className="mt-4 p-3 bg-slate-800/50 border border-slate-700 rounded-lg">
                                <div className="flex items-center gap-2 text-sm text-slate-300">
                                    <svg className="w-4 h-4 text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                                    </svg>
                                    <span>{res.viz_config?.message}</span>
                                </div>
                            </div>
                        ) : shouldShowChart && effectiveMetadata ? (
                            <ResultsWrapper>
                                <ResultChart
                                    data={res.normalized.rows}
                                    metadata={effectiveMetadata as ChartMetadata}
                                />
                            </ResultsWrapper>
                        ) : null}

                        {/* Show recommendation explanation if available */}
                        {recommendation?.explanation && (
                            <div className="mt-2 text-xs text-slate-500 italic">
                                {recommendation.explanation}
                            </div>
                        )}
                    </div>
                );
            })}
        </div>
    );
};

interface SQLResultDisplayProps {
    sql: string;
    sourceQuestion?: string;
    allUserMessages?: string[];
    queryType?: 'database' | 'r_code' | 'sas_code' | 'python_code' | 'general' | 'uncertain' | 'search';
    executionResult?: ExecutePythonResponse;
    onExecutionComplete?: (result: ExecutePythonResponse) => void;
    /** Optional chart type override from user's natural language request */
    chartTypeOverride?: ChartTypeOption;
    /** If true, only show the chart (for re-visualization) */
    chartOnly?: boolean;
    /** LLM summary of the result, if available */
    pythonSummary?: string;
}

export const SQLResultDisplay: React.FC<SQLResultDisplayProps> = ({
    sql,
    sourceQuestion,
    allUserMessages = [],
    queryType,
    executionResult,
    onExecutionComplete,
    chartTypeOverride,
    chartOnly = false,
    pythonSummary
}) => {
    const [copied, setCopied] = useState(false);
    const [toast, setToast] = useState<{ message: string; type: ToastType } | null>(null);
    const [showDialog, setShowDialog] = useState(false);
    const [draftQuestion, setDraftQuestion] = useState('');
    const [draftSQL, setDraftSQL] = useState(sql);
    const [existingFewShots, setExistingFewShots] = useState<FewShotItem[]>([]);
    const [isLoadingFewShots, setIsLoadingFewShots] = useState(false);
    const [isSaving, setIsSaving] = useState(false);
    const [isRunning, setIsRunning] = useState(false);



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
        try {
            // Pass chart type override and source query to the execution API
            const result = await api.executePython(
                sql, 
                sourceQuestion ? { user_query: sourceQuestion } : undefined, 
                chartTypeOverride
            );

            // Call parent callback to persist the result
            if (onExecutionComplete) {
                onExecutionComplete(result);
            }

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

    // CHART ONLY MODE: Only show the chart for python_code results (for re-visualization)
    if (chartOnly && queryType === 'python_code' && executionResult && executionResult.results && executionResult.results.length > 0) {
        // Use the same normalization logic as ExecutionResultViewer
        const rec = executionResult.recommendation;
        const supportedChartTypes = ['bar', 'line', 'pie', 'scatter', 'column', 'stackedBar', 'stackedColumn', 'clusteredColumn', 'area', 'radar', 'treemap', 'funnel'];
        const requestedType = rec?.chart_type;
        const isSupported = requestedType && supportedChartTypes.includes(requestedType);
        // Only use chartMetadata if the requested type is supported and matches the recommendation exactly
        let chartMetadata = null;
        if (rec && isSupported && requestedType !== 'none') {
            const meta = recommendationToMetadata(rec);
            // Only use if the type matches exactly what was requested
            if (meta.type === requestedType) {
                chartMetadata = meta;
            }
        }

        // Normalize data for chart (handle both StructuredTableData and array)
        let rows: any[] = [];
        const result = executionResult.results.find(r => r.name === 'final_result_df') || executionResult.results[0];
        if (result) {
            if (Array.isArray(result.data)) {
                rows = result.data;
            } else if (result.data && Array.isArray(result.data)) {
                rows = result.data;
            } else if (result.data && (result.data as any).data) {
                rows = (result.data as any).data;
            }
        }

        // If not supported or not an exact match, show only the warning message, no chart
        const shouldShowWarning = !isSupported || !chartMetadata || requestedType !== chartMetadata?.type;
        return (
            <div className="relative group mt-4">
                <div className="absolute -inset-1 bg-gradient-to-r from-cyan-500 to-blue-500 rounded-2xl opacity-20 group-hover:opacity-30 blur transition duration-500"></div>
                <div className="relative bg-slate-900 rounded-xl border border-slate-700/50 shadow-xl overflow-hidden p-6 flex flex-col items-center">
                    {shouldShowWarning && (
                        <div className="mb-4 p-4 bg-amber-900/40 border border-amber-600/40 rounded-lg text-amber-200 text-center">
                            <div className="font-semibold mb-1">Sorry, I am not able to provide a <span className="uppercase">{requestedType}</span> chart.</div>
                            <div className="text-sm">Supported chart types are: <span className="font-mono">{supportedChartTypes.join(', ')}</span></div>
                        </div>
                    )}
                    {/* Only render the chart if the requested type is supported and matches the recommendation exactly */}
                    {!shouldShowWarning && (
                        <ResultChart data={rows} metadata={chartMetadata as ChartMetadata} />
                    )}
                </div>
            </div>
        );
    }

    // Default: full display
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
                    <div className="px-4 py-2 bg-slate-900 border-t border-slate-800 flex justify-end gap-2">
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
                        <div className="p-4 overflow-x-auto">
                            {executionResult.error && (
                                <div className="mb-4">
                                    <h4 className="text-xs text-red-400 font-semibold mb-2 uppercase">Error</h4>
                                    <pre className="text-xs text-red-300 font-mono bg-red-950/20 p-3 rounded-lg border border-red-900/50 whitespace-pre-wrap">
                                        {executionResult.error}
                                    </pre>
                                </div>
                            )}
                            {executionResult.results && executionResult.results.length > 0 && (
                                <ExecutionResultViewer
                                    results={executionResult.results}
                                    recommendation={executionResult.recommendation}
                                    pythonSummary={pythonSummary}
                                />
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
