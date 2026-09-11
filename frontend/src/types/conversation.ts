import type { DiscoveryResponse, GenerateSQLResponse, ExecutePythonResponse, ExecuteSQLResponse } from '../api/client';

// Workflow Analysis Types
export interface NumericStats {
  min: number;
  max: number;
  mean: number;
  median: number;
  std: number;
  q25: number;
  q75: number;
  null_count: number;
  null_percentage: number;
  outliers: any[];
}

export interface CategoricalStats {
  unique_count: number;
  top_values: Array<{
    value: string;
    count: number;
    percentage: number;
  }>;
  null_count: number;
  null_percentage: number;
}

export interface ColumnProfile {
  column_name: string;
  data_type: string;
  numeric_stats?: NumericStats;
  categorical_stats?: CategoricalStats;
}

export interface DataProfile {
  row_count: number;
  column_count: number;
  columns: ColumnProfile[];
  correlations?: Array<{
    col1: string;
    col2: string;
    correlation: number;
  }>;
  has_datetime: boolean;
  datetime_columns: string[];
  profiling_level: 'basic' | 'distribution' | 'relationship';
}

export interface Insight {
  insight_type: 'outlier' | 'trend' | 'correlation' | 'missing_data' | 'distribution' | 'recommendation';
  title: string;
  description: string;
  severity: 'info' | 'warning' | 'critical';
  related_columns: string[];
  confidence: number;
}

export interface RefinementIntent {
  intent_type: 'drill_down' | 'filter' | 'compare' | 'trend' | 'forecast' | 'new_query';
  confidence: number;
  target_columns: string[];
  comparison_dimension?: string;
  filter_values: string[];
}

export interface AnalysisContext {
  data_profile?: DataProfile;
  insights: Insight[];
  refinement_history: Array<{
    intent: string;
    query: string;
    timestamp: string;
  }>;
  suggested_refinements: string[];
}

export interface WorkflowTemplate {
  id: string;
  name: string;
  description: string;
  query_pattern: string;
  tables_used: string[];
  refinement_sequence: Array<{
    step: string;
    intent: string;
    description: string;
  }>;
  created_at: string;
  user_id: string;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';  // Changed from type to role for backend compatibility
  type?: 'user' | 'ai';  // Keep for backward compatibility
  content: string;
  timestamp: Date;
  discoveryResult?: DiscoveryResponse;
  sqlResult?: GenerateSQLResponse;
  queryType?: 'database' | 'general' | 'uncertain' | 'search' | 'plan' | 'ask' | 'planning_summary' | 'r_code' | 'sas_code' | 'python_code' | 'code_advisor';
  needsClarification?: boolean;
  sourceQuery?: string;
  executionResult?: ExecutePythonResponse;
  /** SQL execution results (separate from Python execution) */
  sqlExecutionResult?: ExecuteSQLResponse;
  /**
   * LLM-generated summary of the Python execution result (if available)
   */
  pythonSummary?: string;
  /**
   * LLM-generated summary of the SQL execution result (if available)
   */
  sqlSummary?: string;
  /**
   * Workflow analysis context (profiling, insights, refinements) - DEPRECATED for SQL queries with multiple result sets
   * Use resultSetAnalysisCache instead for multi-result SQL queries
   */
  analysisContext?: AnalysisContext;
  /**
   * Per-result-set analysis cache for SQL queries with multiple result sets
   * Key: result set index (0, 1, 2, etc.)
   * Value: Analysis context for that specific result set
   */
  resultSetAnalysisCache?: Record<number, AnalysisContext>;
}

export interface Conversation {
  id: string;
  backendId?: number;  // Backend conversation ID for syncing
  title: string;
  lastModified?: string;  // Keep for backward compatibility
  createdAt?: Date;
  updatedAt?: Date;
  messages: ChatMessage[];
  lastGeneratedSQL?: string;
  queryHistory?: string;
  selectedObjects?: string[];
  selectedSourceId?: string;
  planningContext?: any;  // Structured planning state for conversational exploration
  planningSummary?: string;  // Auto-generated summary from planning conversation
}

