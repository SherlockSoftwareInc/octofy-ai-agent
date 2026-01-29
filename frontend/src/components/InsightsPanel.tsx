/**
 * InsightsPanel Component
 * 
 * Displays automatically generated insights from data profiling.
 * Shows key findings with appropriate icons and severity indicators.
 */

import React from 'react';
import { 
  AlertCircle, 
  TrendingUp, 
  AlertTriangle, 
  Info, 
  BarChart3,
  Target,
  Lightbulb
} from 'lucide-react';
import type { Insight } from '../types/conversation';

interface InsightsPanelProps {
  insights: Insight[];
  className?: string;
}

// Icon mapping based on insight type
const getInsightIcon = (type: Insight['insight_type']) => {
  switch (type) {
    case 'trend':
      return TrendingUp;
    case 'outlier':
      return AlertCircle;
    case 'correlation':
      return BarChart3;
    case 'missing_data':
      return AlertTriangle;
    case 'distribution':
      return Target;
    case 'recommendation':
      return Lightbulb;
    default:
      return Info;
  }
};

// Color mapping based on severity
const getSeverityStyles = (severity: Insight['severity']) => {
  switch (severity) {
    case 'critical':
      return 'bg-red-50 border-red-200 text-red-900';
    case 'warning':
      return 'bg-yellow-50 border-yellow-200 text-yellow-900';
    case 'info':
    default:
      return 'bg-blue-50 border-blue-200 text-blue-900';
  }
};

const getIconColor = (severity: Insight['severity']) => {
  switch (severity) {
    case 'critical':
      return 'text-red-600';
    case 'warning':
      return 'text-yellow-600';
    case 'info':
    default:
      return 'text-blue-600';
  }
};

export const InsightsPanel: React.FC<InsightsPanelProps> = ({ insights, className = '' }) => {
  if (!insights || insights.length === 0) {
    return null;
  }

  return (
    <div className={`space-y-3 ${className}`}>
      <div className="flex items-center gap-2 mb-3">
        <Lightbulb className="w-5 h-5 text-purple-600" />
        <h3 className="text-sm font-semibold text-gray-900">
          Key Insights
        </h3>
        <span className="text-xs text-gray-500">
          ({insights.length} finding{insights.length !== 1 ? 's' : ''})
        </span>
      </div>

      <div className="space-y-2">
        {insights.map((insight, index) => {
          const Icon = getInsightIcon(insight.insight_type);
          const severityStyles = getSeverityStyles(insight.severity);
          const iconColor = getIconColor(insight.severity);

          return (
            <div
              key={index}
              className={`rounded-lg border p-3 ${severityStyles} transition-all hover:shadow-sm`}
            >
              <div className="flex items-start gap-3">
                <div className={`flex-shrink-0 mt-0.5 ${iconColor}`}>
                  <Icon className="w-4 h-4" />
                </div>
                
                <div className="flex-1 min-w-0">
                  <div className="flex items-start justify-between gap-2">
                    <h4 className="text-sm font-medium">
                      {insight.title}
                    </h4>
                    
                    {insight.confidence < 1.0 && (
                      <span className="text-xs text-gray-500 flex-shrink-0">
                        {Math.round(insight.confidence * 100)}% confident
                      </span>
                    )}
                  </div>
                  
                  <p className="text-sm mt-1 leading-relaxed">
                    {insight.description}
                  </p>
                  
                  {insight.related_columns && insight.related_columns.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-2">
                      {insight.related_columns.map((col, colIndex) => (
                        <span
                          key={colIndex}
                          className="inline-flex items-center px-2 py-0.5 rounded text-xs font-mono bg-white/50 border border-current/20"
                        >
                          {col}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default InsightsPanel;
