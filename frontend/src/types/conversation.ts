import type { DiscoveryResponse, GenerateSQLResponse, ExecutePythonResponse, ChartTypeOption } from '../api/client';

export interface ChatMessage {
  id: string;
  type: 'user' | 'ai';
  content: string;
  timestamp: Date;
  discoveryResult?: DiscoveryResponse;
  sqlResult?: GenerateSQLResponse;
  queryType?: 'database' | 'general' | 'uncertain' | 'search' | 'r_code' | 'sas_code' | 'python_code';
  needsClarification?: boolean;
  sourceQuery?: string;
  executionResult?: ExecutePythonResponse;
  /** User's requested chart type from natural language (e.g., "show as line chart") */
  chartTypeOverride?: ChartTypeOption;
}

export interface Conversation {
  id: string;
  title: string;
  lastModified: string;
  messages: ChatMessage[];
  lastGeneratedSQL?: string;
  queryHistory?: string;
  selectedObjects?: string[];
}
