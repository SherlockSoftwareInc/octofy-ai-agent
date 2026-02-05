import React, { useState } from 'react';
import { api, type ExecuteSQLResponse, type ExecutePythonResponse } from '../api/client';
import AnalysisButtons from './AnalysisButtons';
import InsightsPanel from './InsightsPanel';
import DataProfileCard from './DataProfileCard';
import type { AnalysisContext } from '../types/conversation';

interface ResultWithAnalysisProps {
  /** SQL query text (for SQL results) */
  sql?: string;
  /** Python code text (for Python results) */
  pythonCode?: string;
  /** Context to pass to execution (user_query, schema_context, etc.) */
  executionContext?: any;
  /** Result index (for SQL queries with multiple result sets) */
  resultIndex?: number;
  /** Cached analysis context if already fetched */
  cachedAnalysis?: AnalysisContext;
  /** Callback when analysis is fetched */
  onAnalysisFetched?: (analysis: AnalysisContext, resultIndex?: number) => void;
  /** Children to render (the actual result display) */
  children: React.ReactNode;
}

/**
 * Wrapper component that adds on-demand AI analysis buttons below result displays
 */
const ResultWithAnalysis: React.FC<ResultWithAnalysisProps> = ({
  sql,
  pythonCode,
  executionContext,
  resultIndex = 0,
  cachedAnalysis,
  onAnalysisFetched,
  children,
}) => {
  const [aiSummaryLoading, setAISummaryLoading] = useState(false);
  const [datasetAnalysisLoading, setDatasetAnalysisLoading] = useState(false);
  const [analysisData, setAnalysisData] = useState<AnalysisContext | null>(cachedAnalysis || null);
  const [error, setError] = useState<string | null>(null);

  // Determine what type of execution this is
  const isSQLExecution = !!sql;
  const isPythonExecution = !!pythonCode;

  const fetchAnalysis = async () => {
    if (!isSQLExecution && !isPythonExecution) {
      setError('No SQL or Python code provided for analysis');
      return null;
    }

    try {
      let result: ExecuteSQLResponse | ExecutePythonResponse;

      if (isSQLExecution && sql) {
        result = await api.executeSQL(
          sql,
          executionContext,
          undefined,
          undefined,
          undefined,
          true // enable_profiling
        );
      } else if (isPythonExecution && pythonCode) {
        result = await api.executePython(
          pythonCode,
          executionContext,
          undefined,
          true // enable_profiling
        );
      } else {
        throw new Error('Invalid execution type');
      }

      if (!result.success) {
        throw new Error(result.error || 'Execution failed');
      }

      const analysis: AnalysisContext = {
        data_profile: result.data_profile,
        insights: result.insights || [],
        refinement_history: [],
        suggested_refinements: (result as ExecutePythonResponse).suggested_refinements || [],
      };

      return analysis;
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to fetch analysis';
      setError(errorMessage);
      throw err;
    }
  };

  const handleAISummaryClick = async () => {
    if (analysisData?.insights && analysisData.insights.length > 0) {
      // Already have AI summary cached
      return;
    }

    setAISummaryLoading(true);
    setError(null);

    try {
      const analysis = await fetchAnalysis();
      if (analysis) {
        setAnalysisData(analysis);
        if (onAnalysisFetched) {
          onAnalysisFetched(analysis, resultIndex);
        }
      }
    } catch (err) {
      console.error('Failed to fetch AI summary:', err);
    } finally {
      setAISummaryLoading(false);
    }
  };

  const handleDatasetAnalysisClick = async () => {
    if (analysisData?.data_profile) {
      // Already have dataset analysis cached
      return;
    }

    setDatasetAnalysisLoading(true);
    setError(null);

    try {
      const analysis = await fetchAnalysis();
      if (analysis) {
        setAnalysisData(analysis);
        if (onAnalysisFetched) {
          onAnalysisFetched(analysis, resultIndex);
        }
      }
    } catch (err) {
      console.error('Failed to fetch dataset analysis:', err);
    } finally {
      setDatasetAnalysisLoading(false);
    }
  };

  const hasAISummary = !!(analysisData?.insights && analysisData.insights.length > 0);
  const hasDatasetAnalysis = !!analysisData?.data_profile;

  return (
    <div className="w-full">
      {/* Original result display */}
      {children}

      {/* Analysis Buttons */}
      <AnalysisButtons
        onRequestAISummary={handleAISummaryClick}
        onRequestDatasetAnalysis={handleDatasetAnalysisClick}
        aiSummaryLoading={aiSummaryLoading}
        datasetAnalysisLoading={datasetAnalysisLoading}
        hasAISummary={hasAISummary}
        hasDatasetAnalysis={hasDatasetAnalysis}
      />

      {/* Error Display */}
      {error && (
        <div className="mt-2 p-3 bg-red-900/20 border border-red-500/30 rounded-lg text-red-300 text-sm">
          {error}
        </div>
      )}

      {/* Analysis Results */}
      {analysisData && (
        <div className="mt-4 space-y-3">
          {/* AI Insights */}
          {hasAISummary && (
            <InsightsPanel insights={analysisData.insights} />
          )}

          {/* Dataset Analysis */}
          {hasDatasetAnalysis && (
            <DataProfileCard profile={analysisData.data_profile!} />
          )}
        </div>
      )}
    </div>
  );
};

export default ResultWithAnalysis;
