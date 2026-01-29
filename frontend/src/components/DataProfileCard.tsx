/**
 * DataProfileCard Component
 * 
 * Displays a collapsible summary of data profiling statistics.
 * Shows row count, column types, correlations, and key statistics.
 */

import React, { useState } from 'react';
import {
  ChevronDown,
  ChevronRight,
  Database,
  Columns,
  Hash,
  Type,
  Calendar,
  TrendingUp
} from 'lucide-react';
import type { DataProfile } from '../types/conversation';

interface DataProfileCardProps {
  profile: DataProfile;
  className?: string;
}

export const DataProfileCard: React.FC<DataProfileCardProps> = ({
  profile,
  className = ''
}) => {
  const [isExpanded, setIsExpanded] = useState(false);

  if (!profile) {
    return null;
  }

  // Count column types
  const numericCols = profile.columns.filter(c => c.numeric_stats).length;
  const categoricalCols = profile.columns.filter(c => c.categorical_stats).length;

  return (
    <div className={`border border-gray-200 rounded-lg bg-white ${className}`}>
      {/* Header - Always visible */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full px-4 py-3 flex items-center justify-between hover:bg-gray-50 transition-colors rounded-lg"
      >
        <div className="flex items-center gap-3">
          <Database className="w-4 h-4 text-gray-600" />
          <div className="text-left">
            <h3 className="text-sm font-semibold text-gray-900">
              Data Profile
            </h3>
            <p className="text-xs text-gray-500">
              {profile.row_count.toLocaleString()} rows × {profile.column_count} columns
              {profile.profiling_level && (
                <span className="ml-2 text-xs bg-gray-100 px-2 py-0.5 rounded">
                  {profile.profiling_level}
                </span>
              )}
            </p>
          </div>
        </div>
        
        <div className="text-gray-400">
          {isExpanded ? (
            <ChevronDown className="w-4 h-4" />
          ) : (
            <ChevronRight className="w-4 h-4" />
          )}
        </div>
      </button>

      {/* Expanded Content */}
      {isExpanded && (
        <div className="px-4 pb-4 space-y-4 border-t border-gray-100">
          {/* Column Type Summary */}
          <div>
            <h4 className="text-xs font-semibold text-gray-700 mb-2 flex items-center gap-2">
              <Columns className="w-3 h-3" />
              Column Types
            </h4>
            <div className="grid grid-cols-2 gap-2">
              <div className="flex items-center gap-2 text-sm">
                <Hash className="w-3 h-3 text-blue-600" />
                <span className="text-gray-600">Numeric:</span>
                <span className="font-medium">{numericCols}</span>
              </div>
              <div className="flex items-center gap-2 text-sm">
                <Type className="w-3 h-3 text-purple-600" />
                <span className="text-gray-600">Categorical:</span>
                <span className="font-medium">{categoricalCols}</span>
              </div>
            </div>
            {profile.has_datetime && (
              <div className="flex items-center gap-2 text-sm mt-2">
                <Calendar className="w-3 h-3 text-green-600" />
                <span className="text-gray-600">Datetime columns:</span>
                <span className="font-medium">{profile.datetime_columns.join(', ')}</span>
              </div>
            )}
          </div>

          {/* Correlations */}
          {profile.correlations && profile.correlations.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold text-gray-700 mb-2 flex items-center gap-2">
                <TrendingUp className="w-3 h-3" />
                Strong Correlations
              </h4>
              <div className="space-y-1">
                {profile.correlations.slice(0, 5).map((corr, idx) => (
                  <div
                    key={idx}
                    className="flex items-center justify-between text-sm bg-gray-50 rounded px-2 py-1"
                  >
                    <span className="text-gray-700 font-mono text-xs">
                      {corr.col1} ↔ {corr.col2}
                    </span>
                    <span
                      className={`font-semibold ${
                        Math.abs(corr.correlation) > 0.7
                          ? 'text-red-600'
                          : 'text-orange-600'
                      }`}
                    >
                      r = {corr.correlation.toFixed(2)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Column Details */}
          <div>
            <h4 className="text-xs font-semibold text-gray-700 mb-2">
              Column Details
            </h4>
            <div className="space-y-2 max-h-64 overflow-y-auto">
              {profile.columns.map((col, idx) => (
                <div
                  key={idx}
                  className="text-xs bg-gray-50 rounded p-2 space-y-1"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-mono font-medium text-gray-900">
                      {col.column_name}
                    </span>
                    <span className="text-gray-500 text-[10px] uppercase">
                      {col.data_type}
                    </span>
                  </div>
                  
                  {col.numeric_stats && (
                    <div className="grid grid-cols-2 gap-1 text-[10px] text-gray-600">
                      <div>Min: {col.numeric_stats.min.toFixed(2)}</div>
                      <div>Max: {col.numeric_stats.max.toFixed(2)}</div>
                      <div>Mean: {col.numeric_stats.mean.toFixed(2)}</div>
                      <div>Median: {col.numeric_stats.median.toFixed(2)}</div>
                      {col.numeric_stats.null_percentage > 0 && (
                        <div className="col-span-2 text-yellow-600">
                          Nulls: {col.numeric_stats.null_percentage.toFixed(1)}%
                        </div>
                      )}
                      {col.numeric_stats.outliers.length > 0 && (
                        <div className="col-span-2 text-red-600">
                          Outliers: {col.numeric_stats.outliers.length}
                        </div>
                      )}
                    </div>
                  )}
                  
                  {col.categorical_stats && (
                    <div className="text-[10px] text-gray-600 space-y-1">
                      <div>Unique: {col.categorical_stats.unique_count}</div>
                      {col.categorical_stats.top_values.length > 0 && (
                        <div className="space-y-0.5">
                          <div className="font-medium">Top values:</div>
                          {col.categorical_stats.top_values.slice(0, 3).map((val, vidx) => (
                            <div key={vidx} className="pl-2">
                              {val.value}: {val.percentage.toFixed(1)}%
                            </div>
                          ))}
                        </div>
                      )}
                      {col.categorical_stats.null_percentage > 0 && (
                        <div className="text-yellow-600">
                          Nulls: {col.categorical_stats.null_percentage.toFixed(1)}%
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default DataProfileCard;
