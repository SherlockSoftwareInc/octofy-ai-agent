import React, { useMemo, useState, useRef, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { Copy, Check, Loader2, Gift, Play, CheckCircle, Sparkles, BarChart3, Pencil } from 'lucide-react';
import { Toast } from '../Toast';
import type { ToastType } from '../Toast';
import { api, type FewShotItem, type ExecutePythonResponse, type ExecuteSQLResponse, type ExecutePythonResult, type StructuredTableData, type ChartRecommendation, type ChartMetadata, type ChartTypeOption } from '../../api/client';
import { DataTable } from '../DataTable/DataTable';
import { InsightsPanel } from '../InsightsPanel';
import { DataProfileCard } from '../DataProfileCard';
import type { AnalysisContext, DataProfile, Insight } from '../../types/conversation';




import { ResultChart } from './ResultChart';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

const mergeClassNames = (...classes: Array<string | undefined>): string => classes.filter(Boolean).join(' ');

type MarkdownComponents = NonNullable<React.ComponentProps<typeof ReactMarkdown>['components']>;

const markdownComponents = {
    ul: (props) => {
        const { className, ...rest } = props as React.ComponentPropsWithoutRef<'ul'>;
        return (
            <ul
                className={mergeClassNames('list-disc list-outside ml-4 space-y-1', className)}
                {...rest}
            />
        );
    },
    ol: (props) => {
        const { className, ...rest } = props as React.ComponentPropsWithoutRef<'ol'>;
        return (
            <ol
                className={mergeClassNames('list-decimal list-outside ml-4 space-y-1', className)}
                {...rest}
            />
        );
    },
    strong: (props) => {
        const { className, ...rest } = props as React.ComponentPropsWithoutRef<'strong'>;
        return <strong className={mergeClassNames('font-bold text-white', className)} {...rest} />;
    },
    p: (props) => {
        const { className, ...rest } = props as React.ComponentPropsWithoutRef<'p'>;
        return <p className={mergeClassNames('mb-2 last:mb-0', className)} {...rest} />;
    },
    a: (props) => {
        const { className, ...rest } = props as React.ComponentPropsWithoutRef<'a'>;
        return (
            <a
                className={mergeClassNames('text-blue-400 hover:underline', className)}
                target="_blank"
                rel="noopener noreferrer"
                {...rest}
            />
        );
    },
} satisfies MarkdownComponents;

const ResultsWrapper = ({ children }: { children: React.ReactNode }) => (
    <div className="w-full max-w-full overflow-x-auto my-2.5 border border-slate-700 rounded-lg bg-slate-900/30">
        {children}
    </div>
);

type ResultWithExtras = ExecutePythonResult & { recommendation?: ChartRecommendation };
type DisplayableChartType = Exclude<ChartTypeOption, 'none'>;

const SUPPORTED_CHART_TYPES: readonly DisplayableChartType[] = ['line', 'pie', 'scatter', 'column', 'stackedColumn', 'clusteredColumn', 'area', 'radar', 'treemap', 'funnel'];

// Chart type labels for UI display
const CHART_TYPE_LABELS: Record<DisplayableChartType, string> = {
    line: 'Line',
    pie: 'Pie',
    scatter: 'Scatter',
    column: 'Column',
    stackedColumn: 'Stacked Column',
    clusteredColumn: 'Clustered Column',
    area: 'Area',
    radar: 'Radar',
    treemap: 'Treemap',
    funnel: 'Funnel',
};

// Chart Type Selector Component
interface ChartTypeSelectorProps {
    currentType: DisplayableChartType;
    onTypeChange: (newType: DisplayableChartType) => void;
    isLoading?: boolean;
}

const ChartTypeSelector: React.FC<ChartTypeSelectorProps> = ({ currentType, onTypeChange, isLoading }) => {
    return (
        <div className="mt-4 p-4 bg-slate-800/30 border border-slate-700/50 rounded-lg">
            <div className="flex items-center gap-2 mb-3">
                <BarChart3 size={16} className="text-cyan-400" />
                <span className="text-sm font-semibold text-slate-300">Chart Type</span>
            </div>
            <div className="flex flex-wrap gap-2">
                {SUPPORTED_CHART_TYPES.map((chartType) => (
                    <label
                        key={chartType}
                        className={`flex items-center gap-2.5 px-3 py-2.5 rounded-lg border cursor-pointer transition-all ${
                            currentType === chartType
                                ? 'bg-cyan-500/10 border-cyan-500/50'
                                : 'bg-slate-800/50 border-slate-700/50 hover:border-slate-600'
                        } ${isLoading ? 'opacity-50 cursor-not-allowed' : ''}`}
                    >
                        <input
                            type="radio"
                            name="chart-type"
                            value={chartType}
                            checked={currentType === chartType}
                            onChange={() => !isLoading && onTypeChange(chartType)}
                            disabled={isLoading}
                            className="w-4 h-4 text-cyan-500 bg-slate-700 border-slate-600 focus:ring-cyan-500 focus:ring-2 focus:ring-offset-0 disabled:opacity-50"
                        />
                        <span className={`text-sm font-medium ${
                            currentType === chartType ? 'text-cyan-300' : 'text-slate-300'
                        }`}>
                            {CHART_TYPE_LABELS[chartType]}
                        </span>
                    </label>
                ))}
            </div>
            {isLoading && (
                <div className="mt-3 flex items-center gap-2 text-xs text-slate-400">
                    <Loader2 size={14} className="animate-spin" />
                    <span>Updating chart...</span>
                </div>
            )}
        </div>
    );
};

const isSupportedChartType = (chartType?: ChartTypeOption): chartType is DisplayableChartType => {
    if (!chartType || chartType === 'none') {
        return false;
    }
    return SUPPORTED_CHART_TYPES.includes(chartType as DisplayableChartType);
};

const selectPrimaryResult = <T extends ExecutePythonResult>(results: T[]): T | undefined => {
    if (results.length === 0) {
        return undefined;
    }
    const finalResult = results.find(result => result.name === 'final_result_df');
    return finalResult ?? results[0];
};

const extractRows = (result?: ExecutePythonResult): Array<Record<string, unknown>> => {
    if (!result) {
        return [];
    }
    const payload = result.data;
    if (!payload) {
        return [];
    }
    return Array.isArray(payload) ? payload : payload.data;
};

/**
 * Convert a ChartRecommendation (from backend) to ChartMetadata (for ResultChart)
 */
function recommendationToMetadata(rec: ChartRecommendation): ChartMetadata {
    // Determine if this is a stacked chart type
    const isStacked = rec.chart_type === 'stackedColumn';

    return {
        type: rec.chart_type as ChartMetadata['type'],
        x_axis: rec.x_axis || null,
        y_axes: rec.y_axis || [],
        is_stacked: isStacked,
    };
}

interface ExecutionResultViewerProps {
    results: ResultWithExtras[];
    recommendation?: ChartRecommendation;
    pythonSummary?: string;
    onChartTypeChange?: (newType: DisplayableChartType, resultIndex: number) => void;
    isChangingChartType?: boolean;
    chartRefs?: React.MutableRefObject<Map<number, HTMLDivElement | null>>;
}

const ExecutionResultViewer: React.FC<ExecutionResultViewerProps> = ({ 
    results, 
    recommendation, 
    pythonSummary,
    onChartTypeChange,
    isChangingChartType = false,
    chartRefs
}) => {
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
            const normalized = normalizeTableData(res.data, res.columns);
            return {
                ...res,
                normalized
            };
        });
    }, [results]);

    // Note: Global recommendation is deprecated for multi-result support
    // Each result should have its own recommendation attached

    return (
        <div className="space-y-6 w-full max-w-full">
            {resultsWithRows.map((res, idx) => {
                const title = res.name;

                // Determine which chart metadata to use:
                // 1. Prefer result-specific recommendation (for multi-query support)
                // 2. Fall back to global recommendation (backward compatibility)
                // 3. Fall back to result-level chart_metadata
                // 4. Fall back to viz_config based chart_metadata
                const resultRecommendation = res.recommendation;
                const effectiveRecommendation = resultRecommendation || (idx === 0 ? recommendation : null);
                const chartMetadataFromRecommendation = effectiveRecommendation && effectiveRecommendation.chart_type !== 'none'
                    ? recommendationToMetadata(effectiveRecommendation)
                    : undefined;
                
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
                            {effectiveRecommendation && (
                                <div className="text-xs text-slate-500">
                                    {effectiveRecommendation.title}
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
                            <div ref={(el) => { chartRefs?.current.set(idx, el); }}>
                                <ResultsWrapper>
                                    <ResultChart
                                        data={res.normalized.rows}
                                        metadata={effectiveMetadata as ChartMetadata}
                                    />
                                </ResultsWrapper>
                            </div>
                        ) : null}

                        {/* LLM Summary Section */}
                        {idx === 0 && pythonSummary && (
                            <div className="mt-3 p-3 bg-slate-800/40 border border-indigo-700/30 rounded-lg">
                                <div className="text-xs text-indigo-300 font-semibold mb-1">AI Summary</div>
                                <div className="text-sm text-indigo-100">
                                    <ReactMarkdown
                                        remarkPlugins={[remarkGfm]}
                                        components={markdownComponents}
                                    >
                                        {pythonSummary}
                                    </ReactMarkdown>
                                </div>
                            </div>
                        )}

                        {/* Chart Type Selector - show when chart is displayed */}
                        {shouldShowChart && effectiveMetadata && !vizConfigBlocksChart && onChartTypeChange && (
                            <ChartTypeSelector
                                currentType={effectiveMetadata.type as DisplayableChartType}
                                onTypeChange={(newType) => onChartTypeChange(newType, idx)}
                                isLoading={isChangingChartType}
                            />
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
    /** Data source ID to use when executing this SQL */
    sourceId?: string;
    allUserMessages?: string[];
    queryType?: 'database' | 'r_code' | 'sas_code' | 'python_code' | 'general' | 'uncertain' | 'search';
    executionResult?: ExecutePythonResponse;
    sqlExecutionResult?: ExecuteSQLResponse;
    onExecutionComplete?: (result: ExecutePythonResponse) => void;
    onSQLExecutionComplete?: (result: ExecuteSQLResponse) => void;
    /** If true, only show the chart (for re-visualization) */
    chartOnly?: boolean;
    /** LLM summary of the Python execution result, if available */
    pythonSummary?: string;
    /** LLM summary of the SQL execution result, if available */
    sqlSummary?: string;
    /** Reference to the user input textarea for focus management */
    textareaRef?: React.RefObject<HTMLTextAreaElement | null>;
    /** Called when user edits the code in the Edit dialog and clicks Update */
    onCodeChange?: (newCode: string) => void;
}

export const SQLResultDisplay: React.FC<SQLResultDisplayProps> = ({
    sql,
    sourceQuestion,
    sourceId,
    allUserMessages = [],
    queryType,
    executionResult,
    sqlExecutionResult,
    onExecutionComplete,
    onSQLExecutionComplete,
    chartOnly = false,
    pythonSummary,
    sqlSummary,
    textareaRef,
    onCodeChange
}) => {
    const [copied, setCopied] = useState(false);
    const [toast, setToast] = useState<{ message: string; type: ToastType } | null>(null);
    const [showDialog, setShowDialog] = useState(false);
    const contributeDialogRef = useRef<HTMLDivElement>(null);
    const [showEditDialog, setShowEditDialog] = useState(false);
    const [editDraft, setEditDraft] = useState('');
    const aiSummaryRef = useRef<HTMLDivElement>(null);
    const datasetAnalysisRef = useRef<HTMLDivElement>(null);
    const dataProfileRef = useRef<HTMLDivElement>(null);
    const [draftQuestion, setDraftQuestion] = useState('');
    const [draftSQL, setDraftSQL] = useState(sql);
    const [existingFewShots, setExistingFewShots] = useState<FewShotItem[]>([]);
    const [isLoadingFewShots, setIsLoadingFewShots] = useState(false);
    const [isSaving, setIsSaving] = useState(false);
    const [isRunning, setIsRunning] = useState(false);
    const [isSQLRunning, setIsSQLRunning] = useState(false);
    const [analysisData, setAnalysisData] = useState<AnalysisContext | null>(null);
    const [aiSummaryLoading, setAISummaryLoading] = useState(false);
    const [datasetAnalysisLoading, setDatasetAnalysisLoading] = useState(false);
    const [dataProfileLoading, setDataProfileLoading] = useState(false);
    const [showAISummary, setShowAISummary] = useState(false);
    const [showFullAnalysis, setShowFullAnalysis] = useState(false);
    const [showDataProfile, setShowDataProfile] = useState(false);
    const [isChangingChartType, setIsChangingChartType] = useState(false);
    const chartRefs = React.useRef<Map<number, HTMLDivElement | null>>(new Map());

    // Scroll to AI summary panel and focus textarea after AI summary is generated
    useEffect(() => {
        if (showAISummary && analysisData?.insights && analysisData.insights.length > 0 && aiSummaryRef.current) {
            // Scroll to AI summary panel
            aiSummaryRef.current.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            
            // Focus textarea after a short delay to ensure scroll completes
            setTimeout(() => {
                if (textareaRef?.current) {
                    textareaRef.current.focus();
                }
            }, 600);
        }
    }, [showAISummary, analysisData?.insights, textareaRef]);

    // Scroll to Dataset Analysis panel and focus textarea after full analysis is generated
    useEffect(() => {
        if (showFullAnalysis && analysisData?.insights && analysisData.insights.length > 0 && datasetAnalysisRef.current) {
            // Scroll to Dataset Analysis panel
            datasetAnalysisRef.current.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            
            // Focus textarea after a short delay to ensure scroll completes
            setTimeout(() => {
                if (textareaRef?.current) {
                    textareaRef.current.focus();
                }
            }, 600);
        }
    }, [showFullAnalysis, analysisData?.insights, textareaRef]);

    // Bring Contribute Example dialog into view when opened
    useEffect(() => {
        if (showDialog && contributeDialogRef.current) {
            requestAnimationFrame(() => {
                contributeDialogRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' });
            });
        }
    }, [showDialog]);

    // Scroll to Data Profile panel and focus textarea after data profile is generated
    useEffect(() => {
        if (showDataProfile && analysisData?.data_profile && dataProfileRef.current) {
            // Scroll to Data Profile panel
            dataProfileRef.current.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            
            // Focus textarea after a short delay to ensure scroll completes
            setTimeout(() => {
                if (textareaRef?.current) {
                    textareaRef.current.focus();
                }
            }, 600);
        }
    }, [showDataProfile, analysisData?.data_profile, textareaRef]);



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
            // Pass source query to the execution API
            // enable_profiling is FALSE by default (on-demand only)
            const result = await api.executePython(
                sql,
                sourceQuestion ? { user_query: sourceQuestion } : undefined,
                undefined,
                false // explicitly disable automatic profiling
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

    const handleRunSQL = async () => {
        if (!sql) return;
        setIsSQLRunning(true);
        try {
            // enable_profiling is FALSE by default (on-demand only)
            const result = await api.executeSQL(
                sql,
                sourceQuestion ? {
                    user_query: sourceQuestion,
                    schema_context: 'Generated from SQL generation pipeline'
                } : undefined,
                undefined,
                undefined, // timeout
                undefined, // max rows
                false, // explicitly disable automatic profiling
                undefined,
                undefined,
                sourceId
            );

            // Call parent callback to persist the result
            if (onSQLExecutionComplete) {
                onSQLExecutionComplete(result);
            }

            // Show success notification if auto-fixed
            if (result.auto_fixed) {
                setToast({
                    message: `SQL automatically fixed on attempt ${result.fix_attempt}/5`,
                    type: 'success'
                });
            }

            // Scroll result into view
            setTimeout(() => {
                if (resultContainerRef.current) {
                    resultContainerRef.current.scrollIntoView({ behavior: 'smooth', block: 'end' });
                }
            }, 100);

        } catch (error) {
            console.error('SQL Execution failed:', error);
            setToast({ message: 'SQL Execution failed', type: 'error' });
        } finally {
            setIsSQLRunning(false);
        }
    };

    // Handle chart type change from selector
    const handleChartTypeChange = async (newType: DisplayableChartType, resultIndex: number) => {
        setIsChangingChartType(true);
        
        try {
            // Get the original recommendation to preserve axis columns
            let originalRecommendation: any = null;
            if (queryType === 'python_code' || queryType === 'r_code' || queryType === 'sas_code') {
                originalRecommendation = executionResult?.recommendation;
            } else if (queryType === 'database') {
                originalRecommendation = sqlExecutionResult?.recommendation;
            }
            
            // Extract preserved columns from original recommendation
            const preservedXAxis = originalRecommendation?.x_axis;
            const preservedYAxis = originalRecommendation?.y_axis;
            
            // Re-execute code/SQL with new chart type and preserved columns
            if (queryType === 'python_code' || queryType === 'r_code' || queryType === 'sas_code') {
                // Re-execute Python/R/SAS code with new chart type
                const result = await api.executePython(
                    sql,
                    sourceQuestion ? { user_query: sourceQuestion } : undefined,
                    newType,
                    false,
                    preservedXAxis,
                    preservedYAxis
                );
                
                if (onExecutionComplete) {
                    onExecutionComplete(result);
                }
            } else if (queryType === 'database') {
                // Re-execute SQL with new chart type
                const result = await api.executeSQL(
                    sql,
                    sourceQuestion ? {
                        user_query: sourceQuestion,
                        schema_context: 'Chart type change'
                    } : undefined,
                    newType,
                    undefined,
                    undefined,
                    false,
                    preservedXAxis,
                    preservedYAxis,
                    sourceId
                );
                
                if (onSQLExecutionComplete) {
                    onSQLExecutionComplete(result);
                }
            }
            
            setToast({ 
                message: `Chart updated to ${CHART_TYPE_LABELS[newType]}`, 
                type: 'success' 
            });
            
            // Scroll to the specific chart after update
            setTimeout(() => {
                const chartElement = chartRefs.current.get(resultIndex);
                if (chartElement) {
                    chartElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
                }
            }, 300);
        } catch (error) {
            console.error('Chart type change failed:', error);
            setToast({ 
                message: 'Failed to update chart type', 
                type: 'error' 
            });
        } finally {
            setIsChangingChartType(false);
        }
    };

    // CHART ONLY MODE: Only show the chart for code execution results (Python/R/SAS - for re-visualization)
    if (chartOnly && (queryType === 'python_code' || queryType === 'r_code' || queryType === 'sas_code') && executionResult && executionResult.results && executionResult.results.length > 0) {
        const rec = executionResult.recommendation;
        const requestedType = rec?.chart_type;

        const metadataFromRecommendation = rec && isSupportedChartType(rec.chart_type)
            ? recommendationToMetadata(rec)
            : null;

        const resolvedType: ChartMetadata['type'] | undefined = metadataFromRecommendation
            ? metadataFromRecommendation.type
            : undefined;

        const chartMetadata = metadataFromRecommendation && resolvedType
            ? { ...metadataFromRecommendation, type: resolvedType }
            : null;

        const primaryResult = selectPrimaryResult(executionResult.results);
        const rows = extractRows(primaryResult);

        const shouldShowWarning = !chartMetadata || (requestedType !== undefined && (!isSupportedChartType(requestedType) || requestedType !== chartMetadata.type));

        return (
            <div className="relative group mt-4">
                <div className="absolute -inset-1 bg-gradient-to-r from-cyan-500 to-blue-500 rounded-2xl opacity-20 group-hover:opacity-30 blur transition duration-500"></div>
                <div className="relative bg-slate-900 rounded-xl border border-slate-700/50 shadow-xl overflow-hidden p-6 flex flex-col items-center">
                    {shouldShowWarning && (
                        <div className="mb-4 p-4 bg-amber-900/40 border border-amber-600/40 rounded-lg text-amber-200 text-center">
                            <div className="font-semibold mb-1">
                                Sorry, I am not able to provide {requestedType ? `a ${requestedType.toUpperCase()} chart.` : 'the requested chart.'}
                            </div>
                            <div className="text-sm">Supported chart types are: <span className="font-mono">{SUPPORTED_CHART_TYPES.join(', ')}</span></div>
                        </div>
                    )}
                    {!shouldShowWarning && chartMetadata && (
                        <ResultChart data={rows} metadata={chartMetadata} />
                    )}
                </div>
            </div>
        );
    }

    // CHART ONLY MODE: Only show the chart for SQL execution results (for re-visualization)
    if (chartOnly && queryType === 'database' && sqlExecutionResult && sqlExecutionResult.success && sqlExecutionResult.results && sqlExecutionResult.results.length > 0) {
        const rec = sqlExecutionResult.recommendation;
        const requestedType = rec?.chart_type;

        const metadataFromRecommendation = rec && isSupportedChartType(rec.chart_type)
            ? recommendationToMetadata(rec)
            : null;

        const resolvedType: ChartMetadata['type'] | undefined = metadataFromRecommendation
            ? metadataFromRecommendation.type
            : undefined;

        const chartMetadata = metadataFromRecommendation && resolvedType
            ? { ...metadataFromRecommendation, type: resolvedType }
            : null;

        const primaryResult = selectPrimaryResult(sqlExecutionResult.results);
        const rows = extractRows(primaryResult);

        const shouldShowWarning = !chartMetadata || (requestedType !== undefined && (!isSupportedChartType(requestedType) || requestedType !== chartMetadata.type));

        return (
            <div className="relative group mt-4">
                <div className="absolute -inset-1 bg-gradient-to-r from-cyan-500 to-blue-500 rounded-2xl opacity-20 group-hover:opacity-30 blur transition duration-500"></div>
                <div className="relative bg-slate-900 rounded-xl border border-slate-700/50 shadow-xl overflow-hidden p-6 flex flex-col items-center">
                    {shouldShowWarning && (
                        <div className="mb-4 p-4 bg-amber-900/40 border border-amber-600/40 rounded-lg text-amber-200 text-center">
                            <div className="font-semibold mb-1">
                                Sorry, I am not able to provide {requestedType ? `a ${requestedType.toUpperCase()} chart.` : 'the requested chart.'}
                            </div>
                            <div className="text-sm">Supported chart types are: <span className="font-mono">{SUPPORTED_CHART_TYPES.join(', ')}</span></div>
                        </div>
                    )}
                    {!shouldShowWarning && chartMetadata && (
                        <ResultChart data={rows} metadata={chartMetadata} />
                    )}

                    {sqlSummary && (
                        <div className="w-full mt-4 p-4 bg-purple-900/20 border border-purple-500/30 rounded-lg">
                            <div className="flex items-center gap-2 mb-2 text-sm font-semibold text-purple-300">
                                <div className="w-2 h-2 bg-purple-500 rounded-full"></div>
                                AI Summary
                            </div>
                            <div className="text-sm text-purple-200">
                                <ReactMarkdown
                                    remarkPlugins={[remarkGfm]}
                                    components={markdownComponents}
                                >
                                    {sqlSummary}
                                </ReactMarkdown>
                            </div>
                        </div>
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
                        {onCodeChange && (
                            <button
                                onClick={() => {
                                    setEditDraft(sql);
                                    setShowEditDialog(true);
                                }}
                                className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg transition-all duration-200 border bg-slate-700 hover:bg-slate-600 text-slate-300 border-slate-600 hover:border-slate-500"
                                title="Edit code"
                            >
                                <Pencil size={12} />
                                <span>Edit</span>
                            </button>
                        )}
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

                {/* SQL Run Button */}
                {queryType === 'database' && (
                    <div className="px-4 py-2 bg-slate-900 border-t border-slate-800 flex justify-end gap-2">
                        <button
                            onClick={handleRunSQL}
                            disabled={isSQLRunning}
                            className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg transition-all duration-200 border ${isSQLRunning
                                ? 'bg-blue-600/20 text-blue-200 border-blue-500/40 cursor-wait'
                                : 'bg-blue-600/20 text-blue-200 border-blue-500/40 hover:bg-blue-500/30'
                                }`}
                            title="Run SQL Query"
                        >
                            {isSQLRunning ? <Loader2 size={12} className="animate-spin" /> : <Play size={12} className="fill-current" />}
                            <span>{isSQLRunning ? 'Running...' : 'Run SQL'}</span>
                        </button>
                    </div>
                )}

                {/* Execution Results - Python */}
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
                                <>
                                    <ExecutionResultViewer
                                        results={executionResult.results}
                                        recommendation={executionResult.recommendation}
                                        pythonSummary={pythonSummary}
                                        onChartTypeChange={handleChartTypeChange}
                                        isChangingChartType={isChangingChartType}
                                        chartRefs={chartRefs}
                                    />
                                    {/* On-Demand Analysis Buttons */}
                                    <div className="flex items-center gap-2 mt-4 mb-2">
                                        <button
                                            onClick={async () => {
                                                if (showAISummary && analysisData?.insights && analysisData.insights.length > 0) return;
                                                setAISummaryLoading(true);
                                                try {
                                                    // Use summarizeResults API for AI insights only
                                                    const summaryResult = await api.summarizeResults(
                                                        sourceQuestion || allUserMessages.join(' '),
                                                        executionResult?.output || executionResult?.results,
                                                        undefined
                                                    );
                                                    // Convert summary to insights format
                                                    const insights = summaryResult.summary ? [
                                                        {
                                                            insight_type: 'recommendation' as const,
                                                            title: 'AI Summary',
                                                            description: summaryResult.summary,
                                                            severity: 'info' as const,
                                                            related_columns: [],
                                                            confidence: 1.0
                                                        }
                                                    ] : [];
                                                    setAnalysisData({
                                                        data_profile: undefined,
                                                        insights: insights,
                                                        refinement_history: [],
                                                        suggested_refinements: []
                                                    });
                                                    setShowAISummary(true);
                                                    setShowFullAnalysis(false);
                                                    setShowDataProfile(false);
                                                } catch (err) {
                                                    console.error('Failed to fetch AI summary:', err);
                                                    setToast({ message: 'Failed to generate AI summary', type: 'error' });
                                                } finally {
                                                    setAISummaryLoading(false);
                                                }
                                            }}
                                            disabled={aiSummaryLoading || (showAISummary && analysisData?.insights && analysisData.insights.length > 0) || false}
                                            className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md transition-all duration-200 ${
                                                (showAISummary && analysisData?.insights && analysisData.insights.length > 0)
                                                    ? 'bg-green-600/20 text-green-300 border border-green-500/30 cursor-default'
                                                    : aiSummaryLoading
                                                    ? 'bg-blue-600/20 text-blue-300 border border-blue-500/30 cursor-wait'
                                                    : 'bg-blue-600/20 text-blue-300 border border-blue-500/30 hover:bg-blue-500/30 cursor-pointer'
                                            } disabled:opacity-70`}
                                            title={(showAISummary && analysisData?.insights && analysisData.insights.length > 0) ? 'AI Summary generated' : aiSummaryLoading ? 'Generating AI insights...' : 'Generate AI-powered insights about patterns and trends'}
                                        >
                                            {aiSummaryLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
                                            <span>{(showAISummary && analysisData?.insights && analysisData.insights.length > 0) ? 'AI Summary ✓' : 'AI Summary'}</span>
                                        </button>
                                        <button
                                            onClick={async () => {
                                                if (showFullAnalysis && analysisData?.insights && analysisData?.data_profile) return;
                                                setDatasetAnalysisLoading(true);
                                                try {
                                                    const result = await api.executePython(
                                                        sql,
                                                        sourceQuestion ? { user_query: sourceQuestion } : undefined,
                                                        undefined,
                                                        true // enable profiling for on-demand
                                                    );
                                                    if (result.success && (result.data_profile || result.insights)) {
                                                        setAnalysisData({
                                                            data_profile: result.data_profile as DataProfile | undefined,
                                                            insights: (result.insights || []) as Insight[],
                                                            refinement_history: [],
                                                            suggested_refinements: result.suggested_refinements || []
                                                        });
                                                        setShowFullAnalysis(true);
                                                        setShowAISummary(false);
                                                        setShowDataProfile(false);
                                                    }
                                                } catch (err) {
                                                    console.error('Failed to fetch dataset analysis:', err);
                                                    setToast({ message: 'Failed to generate dataset analysis', type: 'error' });
                                                } finally {
                                                    setDatasetAnalysisLoading(false);
                                                }
                                            }}
                                            disabled={datasetAnalysisLoading || (showFullAnalysis && !!analysisData?.insights && !!analysisData?.data_profile)}
                                            className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md transition-all duration-200 ${
                                                (showFullAnalysis && analysisData?.insights && analysisData?.data_profile)
                                                    ? 'bg-green-600/20 text-green-300 border border-green-500/30 cursor-default'
                                                    : datasetAnalysisLoading
                                                    ? 'bg-indigo-600/20 text-indigo-300 border border-indigo-500/30 cursor-wait'
                                                    : 'bg-indigo-600/20 text-indigo-300 border border-indigo-500/30 hover:bg-indigo-500/30 cursor-pointer'
                                            } disabled:opacity-70`}
                                            title={(showFullAnalysis && analysisData?.insights && analysisData?.data_profile) ? 'Data set analysis generated' : datasetAnalysisLoading ? 'Analyzing dataset...' : 'Generate complete dataset analysis with insights and profiling'}
                                        >
                                            {datasetAnalysisLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <BarChart3 className="w-3.5 h-3.5" />}
                                            <span>{(showFullAnalysis && analysisData?.insights && analysisData?.data_profile) ? 'Data set analysis ✓' : 'Data set analysis'}</span>
                                        </button>
                                        <button
                                            onClick={async () => {
                                                if (showDataProfile && analysisData?.data_profile) return;
                                                setDataProfileLoading(true);
                                                try {
                                                    const result = await api.executePython(
                                                        sql,
                                                        sourceQuestion ? { user_query: sourceQuestion } : undefined,
                                                        undefined,
                                                        true // enable profiling for on-demand
                                                    );
                                                    if (result.success && (result.data_profile || result.insights)) {
                                                        setAnalysisData({
                                                            data_profile: result.data_profile as DataProfile | undefined,
                                                            insights: (result.insights || []) as Insight[],
                                                            refinement_history: [],
                                                            suggested_refinements: result.suggested_refinements || []
                                                        });
                                                        setShowDataProfile(true);
                                                        setShowAISummary(false);
                                                        setShowFullAnalysis(false);
                                                    }
                                                } catch (err) {
                                                    console.error('Failed to fetch data profile:', err);
                                                    setToast({ message: 'Failed to generate data profile', type: 'error' });
                                                } finally {
                                                    setDataProfileLoading(false);
                                                }
                                            }}
                                            disabled={dataProfileLoading || (showDataProfile && !!analysisData?.data_profile)}
                                            className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md transition-all duration-200 ${
                                                (showDataProfile && analysisData?.data_profile)
                                                    ? 'bg-green-600/20 text-green-300 border border-green-500/30 cursor-default'
                                                    : dataProfileLoading
                                                    ? 'bg-purple-600/20 text-purple-300 border border-purple-500/30 cursor-wait'
                                                    : 'bg-purple-600/20 text-purple-300 border border-purple-500/30 hover:bg-purple-500/30 cursor-pointer'
                                            } disabled:opacity-70`}
                                            title={(showDataProfile && analysisData?.data_profile) ? 'Data Profile generated' : dataProfileLoading ? 'Analyzing dataset...' : 'Show statistical profiling and data distribution'}
                                        >
                                            {dataProfileLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <BarChart3 className="w-3.5 h-3.5" />}
                                            <span>{(showDataProfile && analysisData?.data_profile) ? 'Data Profile ✓' : 'Data Profile'}</span>
                                        </button>
                                    </div>
                                    {/* Analysis Results */}
                                    {analysisData && (
                                        <div className="mt-4 space-y-3">
                                            {showAISummary && analysisData.insights && analysisData.insights.length > 0 && (
                                                <div ref={aiSummaryRef}>
                                                    <InsightsPanel insights={analysisData.insights} />
                                                </div>
                                            )}
                                            {showFullAnalysis && analysisData.insights && analysisData.insights.length > 0 && (
                                                <div ref={datasetAnalysisRef}>
                                                    <InsightsPanel insights={analysisData.insights} />
                                                </div>
                                            )}
                                            {showDataProfile && analysisData.data_profile && (
                                                <div ref={dataProfileRef}>
                                                    <DataProfileCard profile={analysisData.data_profile} />
                                                </div>
                                            )}
                                        </div>
                                    )}
                                </>
                            )}
                        </div>
                    </div>
                )}

                {/* Execution Results - SQL */}
                {sqlExecutionResult && (
                    <div className="border-t border-slate-700/50 bg-slate-900/50">
                        <div className="p-4 overflow-x-auto">
                            {/* Show auto-fix notification if applicable */}
                            {sqlExecutionResult.auto_fixed && (
                                <div className="mb-4 p-3 bg-blue-950/20 border border-blue-900/50 rounded-lg">
                                    <div className="flex items-center gap-2 text-sm text-blue-300">
                                        <CheckCircle size={16} />
                                        <span>SQL automatically fixed on attempt {sqlExecutionResult.fix_attempt}/5</span>
                                    </div>
                                    {sqlExecutionResult.original_error && (
                                        <details className="mt-2">
                                            <summary className="text-xs text-blue-400 cursor-pointer">View original error</summary>
                                            <pre className="text-xs text-blue-300 mt-2 font-mono">{sqlExecutionResult.original_error}</pre>
                                        </details>
                                    )}
                                </div>
                            )}

                            {sqlExecutionResult.error && (
                                <div className="mb-4">
                                    <h4 className="text-xs text-red-400 font-semibold mb-2 uppercase">Error</h4>
                                    <pre className="text-xs text-red-300 font-mono bg-red-950/20 p-3 rounded-lg border border-red-900/50 whitespace-pre-wrap">
                                        {sqlExecutionResult.error}
                                    </pre>
                                </div>
                            )}

                            {sqlExecutionResult.results && sqlExecutionResult.results.length > 0 && (
                                <>
                                    <ExecutionResultViewer
                                        results={sqlExecutionResult.results}
                                        recommendation={sqlExecutionResult.recommendation}
                                        pythonSummary={sqlSummary}
                                        onChartTypeChange={handleChartTypeChange}
                                        isChangingChartType={isChangingChartType}
                                        chartRefs={chartRefs}
                                    />
                                    {/* On-Demand Analysis Buttons */}
                                    <div className="flex items-center gap-2 mt-4 mb-2">
                                        <button
                                            onClick={async () => {
                                                if (showAISummary && analysisData?.insights && analysisData.insights.length > 0) return;
                                                setAISummaryLoading(true);
                                                try {
                                                    // Use summarizeResults API for AI insights only
                                                    const summaryResult = await api.summarizeResults(
                                                        sourceQuestion || allUserMessages.join(' '),
                                                        sqlExecutionResult?.output || sqlExecutionResult?.results,
                                                        undefined
                                                    );
                                                    // Convert summary to insights format
                                                    const insights = summaryResult.summary ? [
                                                        {
                                                            insight_type: 'recommendation' as const,
                                                            title: 'AI Summary',
                                                            description: summaryResult.summary,
                                                            severity: 'info' as const,
                                                            related_columns: [],
                                                            confidence: 1.0
                                                        }
                                                    ] : [];
                                                    setAnalysisData({
                                                        data_profile: undefined,
                                                        insights: insights,
                                                        refinement_history: [],
                                                        suggested_refinements: []
                                                    });
                                                    setShowAISummary(true);
                                                    setShowFullAnalysis(false);
                                                    setShowDataProfile(false);
                                                } catch (err) {
                                                    console.error('Failed to fetch AI summary:', err);
                                                    setToast({ message: 'Failed to generate AI summary', type: 'error' });
                                                } finally {
                                                    setAISummaryLoading(false);
                                                }
                                            }}
                                            disabled={aiSummaryLoading || (showAISummary && analysisData?.insights && analysisData.insights.length > 0) || false}
                                            className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md transition-all duration-200 ${
                                                (showAISummary && analysisData?.insights && analysisData.insights.length > 0)
                                                    ? 'bg-green-600/20 text-green-300 border border-green-500/30 cursor-default'
                                                    : aiSummaryLoading
                                                    ? 'bg-blue-600/20 text-blue-300 border border-blue-500/30 cursor-wait'
                                                    : 'bg-blue-600/20 text-blue-300 border border-blue-500/30 hover:bg-blue-500/30 cursor-pointer'
                                            } disabled:opacity-70`}
                                            title={(showAISummary && analysisData?.insights && analysisData.insights.length > 0) ? 'AI Summary generated' : aiSummaryLoading ? 'Generating AI insights...' : 'Generate AI-powered insights about patterns and trends'}
                                        >
                                            {aiSummaryLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
                                            <span>{(showAISummary && analysisData?.insights && analysisData.insights.length > 0) ? 'AI Summary ✓' : 'AI Summary'}</span>
                                        </button>
                                        <button
                                            onClick={async () => {
                                                if (showFullAnalysis && analysisData?.insights && analysisData?.data_profile) return;
                                                setDatasetAnalysisLoading(true);
                                                try {
                                                    const result = await api.executeSQL(
                                                        sql,
                                                        sourceQuestion ? {
                                                            user_query: sourceQuestion,
                                                            schema_context: 'Generated from SQL generation pipeline'
                                                        } : undefined,
                                                        undefined,
                                                        undefined,
                                                        undefined,
                                                        true, // enable profiling for on-demand
                                                        undefined,
                                                        undefined,
                                                        sourceId
                                                    );
                                                    if (result.success && (result.data_profile || result.insights)) {
                                                        setAnalysisData({
                                                            data_profile: result.data_profile as DataProfile | undefined,
                                                            insights: (result.insights || []) as Insight[],
                                                            refinement_history: [],
                                                            suggested_refinements: []
                                                        });
                                                        setShowFullAnalysis(true);
                                                        setShowAISummary(false);
                                                        setShowDataProfile(false);
                                                    }
                                                } catch (err) {
                                                    console.error('Failed to fetch dataset analysis:', err);
                                                    setToast({ message: 'Failed to generate dataset analysis', type: 'error' });
                                                } finally {
                                                    setDatasetAnalysisLoading(false);
                                                }
                                            }}
                                            disabled={datasetAnalysisLoading || (showFullAnalysis && !!analysisData?.insights && !!analysisData?.data_profile)}
                                            className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md transition-all duration-200 ${
                                                (showFullAnalysis && analysisData?.insights && analysisData?.data_profile)
                                                    ? 'bg-green-600/20 text-green-300 border border-green-500/30 cursor-default'
                                                    : datasetAnalysisLoading
                                                    ? 'bg-indigo-600/20 text-indigo-300 border border-indigo-500/30 cursor-wait'
                                                    : 'bg-indigo-600/20 text-indigo-300 border border-indigo-500/30 hover:bg-indigo-500/30 cursor-pointer'
                                            } disabled:opacity-70`}
                                            title={(showFullAnalysis && analysisData?.insights && analysisData?.data_profile) ? 'Data set analysis generated' : datasetAnalysisLoading ? 'Analyzing dataset...' : 'Generate complete dataset analysis with insights and profiling'}
                                        >
                                            {datasetAnalysisLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <BarChart3 className="w-3.5 h-3.5" />}
                                            <span>{(showFullAnalysis && analysisData?.insights && analysisData?.data_profile) ? 'Data set analysis ✓' : 'Data set analysis'}</span>
                                        </button>
                                        <button
                                            onClick={async () => {
                                                if (showDataProfile && analysisData?.data_profile) return;
                                                setDataProfileLoading(true);
                                                try {
                                                    const result = await api.executeSQL(
                                                        sql,
                                                        sourceQuestion ? {
                                                            user_query: sourceQuestion,
                                                            schema_context: 'Generated from SQL generation pipeline'
                                                        } : undefined,
                                                        undefined,
                                                        undefined,
                                                        undefined,
                                                        true, // enable profiling for on-demand
                                                        undefined,
                                                        undefined,
                                                        sourceId
                                                    );
                                                    if (result.success && (result.data_profile || result.insights)) {
                                                        setAnalysisData({
                                                            data_profile: result.data_profile as DataProfile | undefined,
                                                            insights: (result.insights || []) as Insight[],
                                                            refinement_history: [],
                                                            suggested_refinements: []
                                                        });
                                                        setShowDataProfile(true);
                                                        setShowAISummary(false);
                                                        setShowFullAnalysis(false);
                                                    }
                                                } catch (err) {
                                                    console.error('Failed to fetch data profile:', err);
                                                    setToast({ message: 'Failed to generate data profile', type: 'error' });
                                                } finally {
                                                    setDataProfileLoading(false);
                                                }
                                            }}
                                            disabled={dataProfileLoading || (showDataProfile && !!analysisData?.data_profile)}
                                            className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md transition-all duration-200 ${
                                                (showDataProfile && analysisData?.data_profile)
                                                    ? 'bg-green-600/20 text-green-300 border border-green-500/30 cursor-default'
                                                    : dataProfileLoading
                                                    ? 'bg-purple-600/20 text-purple-300 border border-purple-500/30 cursor-wait'
                                                    : 'bg-purple-600/20 text-purple-300 border border-purple-500/30 hover:bg-purple-500/30 cursor-pointer'
                                            } disabled:opacity-70`}
                                            title={(showDataProfile && analysisData?.data_profile) ? 'Data Profile generated' : dataProfileLoading ? 'Analyzing dataset...' : 'Show statistical profiling and data distribution'}
                                        >
                                            {dataProfileLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <BarChart3 className="w-3.5 h-3.5" />}
                                            <span>{(showDataProfile && analysisData?.data_profile) ? 'Data Profile ✓' : 'Data Profile'}</span>
                                        </button>
                                    </div>
                                    {/* Analysis Results */}
                                    {analysisData && (
                                        <div className="mt-4 space-y-3">
                                            {showAISummary && analysisData.insights && analysisData.insights.length > 0 && (
                                                <div ref={aiSummaryRef}>
                                                    <InsightsPanel insights={analysisData.insights} />
                                                </div>
                                            )}
                                            {showFullAnalysis && analysisData.insights && analysisData.insights.length > 0 && (
                                                <div ref={datasetAnalysisRef}>
                                                    <InsightsPanel insights={analysisData.insights} />
                                                </div>
                                            )}
                                            {showDataProfile && analysisData.data_profile && (
                                                <div ref={dataProfileRef}>
                                                    <DataProfileCard profile={analysisData.data_profile} />
                                                </div>
                                            )}
                                        </div>
                                    )}
                                </>
                            )}
                        </div>
                    </div>
                )}
            </div>

            {/* Contribute Example Dialog */}
            {showDialog && (
                <div ref={contributeDialogRef} className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 px-4">
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

            {/* Edit Code Dialog - portaled to body so it stays viewport-visible */}
            {showEditDialog && createPortal(
                <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/70 px-4 overflow-y-auto py-8">
                    <div className="w-full max-w-2xl my-auto bg-slate-950 border border-slate-800 rounded-2xl shadow-2xl p-6 space-y-4">
                        <div className="flex items-start justify-between">
                            <p className="text-xs uppercase tracking-[0.2em] text-slate-500 mb-1">Edit code</p>
                            <button
                                onClick={() => setShowEditDialog(false)}
                                className="text-slate-400 hover:text-white p-1"
                                aria-label="Close"
                            >
                                ×
                            </button>
                        </div>
                        <div className="space-y-3">
                            <label className="text-sm text-slate-300">
                                {queryType === 'r_code' ? 'R Code' : queryType === 'sas_code' ? 'SAS Code' : queryType === 'python_code' ? 'Python Code' : 'SQL Query'}
                            </label>
                            <textarea
                                className="w-full bg-slate-900 border border-slate-700 rounded-lg p-3 text-sm font-mono text-cyan-100 focus:ring-2 focus:ring-cyan-500 outline-none min-h-[200px]"
                                rows={12}
                                value={editDraft}
                                onChange={(e) => setEditDraft(e.target.value)}
                                placeholder="Edit the code..."
                            />
                        </div>
                        <div className="flex justify-end gap-3 pt-2">
                            <button
                                onClick={() => setShowEditDialog(false)}
                                className="px-4 py-2 text-slate-300 hover:text-white bg-slate-800/80 border border-slate-700 rounded-lg"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={() => {
                                    onCodeChange?.(editDraft);
                                    setShowEditDialog(false);
                                }}
                                className="px-4 py-2 bg-cyan-600 hover:bg-cyan-500 text-white rounded-lg flex items-center gap-2"
                            >
                                <Check size={16} />
                                <span>Update</span>
                            </button>
                        </div>
                    </div>
                </div>,
                document.body
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
