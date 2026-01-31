import React from 'react';
import { Sparkles, BarChart3, Loader2 } from 'lucide-react';

interface AnalysisButtonsProps {
  onRequestAISummary: () => void;
  onRequestDatasetAnalysis: () => void;
  aiSummaryLoading: boolean;
  datasetAnalysisLoading: boolean;
  hasAISummary: boolean;
  hasDatasetAnalysis: boolean;
}

const AnalysisButtons: React.FC<AnalysisButtonsProps> = ({
  onRequestAISummary,
  onRequestDatasetAnalysis,
  aiSummaryLoading,
  datasetAnalysisLoading,
  hasAISummary,
  hasDatasetAnalysis,
}) => {
  return (
    <div className="flex items-center gap-2 mt-3 mb-2">
      {/* AI Summary Button */}
      <button
        onClick={onRequestAISummary}
        disabled={aiSummaryLoading || hasAISummary}
        className={`
          flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md
          transition-all duration-200
          ${
            hasAISummary
              ? 'bg-green-100 text-green-700 cursor-default'
              : aiSummaryLoading
              ? 'bg-blue-100 text-blue-700 cursor-wait'
              : 'bg-blue-50 text-blue-600 hover:bg-blue-100 hover:text-blue-700 cursor-pointer'
          }
          disabled:opacity-70
        `}
        title={
          hasAISummary
            ? 'AI Summary generated'
            : aiSummaryLoading
            ? 'Generating AI insights...'
            : 'Generate AI-powered insights about patterns and trends'
        }
      >
        {aiSummaryLoading ? (
          <Loader2 className="w-3.5 h-3.5 animate-spin" />
        ) : (
          <Sparkles className="w-3.5 h-3.5" />
        )}
        <span>{hasAISummary ? 'AI Summary ✓' : 'AI Summary'}</span>
      </button>

      {/* Dataset Analysis Button */}
      <button
        onClick={onRequestDatasetAnalysis}
        disabled={datasetAnalysisLoading || hasDatasetAnalysis}
        className={`
          flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md
          transition-all duration-200
          ${
            hasDatasetAnalysis
              ? 'bg-green-100 text-green-700 cursor-default'
              : datasetAnalysisLoading
              ? 'bg-purple-100 text-purple-700 cursor-wait'
              : 'bg-purple-50 text-purple-600 hover:bg-purple-100 hover:text-purple-700 cursor-pointer'
          }
          disabled:opacity-70
        `}
        title={
          hasDatasetAnalysis
            ? 'Dataset Analysis generated'
            : datasetAnalysisLoading
            ? 'Analyzing dataset...'
            : 'Show statistical analysis and data profiling'
        }
      >
        {datasetAnalysisLoading ? (
          <Loader2 className="w-3.5 h-3.5 animate-spin" />
        ) : (
          <BarChart3 className="w-3.5 h-3.5" />
        )}
        <span>{hasDatasetAnalysis ? 'Dataset Analysis ✓' : 'Dataset Analysis'}</span>
      </button>
    </div>
  );
};

export default AnalysisButtons;
