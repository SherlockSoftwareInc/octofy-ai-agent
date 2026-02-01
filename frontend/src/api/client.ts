import axios from 'axios';

// Default values
const DEFAULT_API_BASE_URL = '/api/v1';
const DEFAULT_API_KEY = 'dev-api-key-12345';

// Get configuration from localStorage with fallbacks
const getApiBaseUrl = () => {
    return localStorage.getItem('api_base_url') || DEFAULT_API_BASE_URL;
};

const getApiKey = () => {
    return localStorage.getItem('api_key') || DEFAULT_API_KEY;
};

// Use dynamic API base URL
const API_BASE_URL = getApiBaseUrl();

// Configure axios to include API key in all requests
axios.interceptors.request.use(
    (config) => {
        // Add API key header to all requests (get fresh value each time)
        config.headers['X-API-Key'] = getApiKey();

        // Update base URL if it's using our API calls
        if (config.url?.startsWith('/api/v1') ||
            config.url?.startsWith('http://localhost:8000/api/v1') ||
            config.url?.startsWith('http://localhost:9000/api/v1') ||
            config.url?.startsWith('http://localhost:5000/api/v1')) {
            const currentBaseUrl = getApiBaseUrl();
            if (config.url.startsWith('/api/v1')) {
                config.url = currentBaseUrl + config.url.substring(7); // Remove '/api/v1' and append to base
            } else {
                // Replace the hardcoded URL with current setting
                config.url = config.url.replace('http://localhost:8000/api/v1', currentBaseUrl);
                config.url = config.url.replace('http://localhost:9000/api/v1', currentBaseUrl);
                config.url = config.url.replace('http://localhost:5000/api/v1', currentBaseUrl);
            }
        }

        return config;
    },
    (error) => {
        return Promise.reject(error);
    }
);

export interface ColumnInfo {
    name: string;
    data_type: string;
    description?: string;
}

export interface TableSchema {
    schema_name: string;
    table_name: string;
    columns: ColumnInfo[];
    description?: string;
}

export interface SimilarQuery {
    question: string;
    sql: string;
}

export interface DiscoveryContext {
    relevant_tables: TableSchema[];
    similar_queries: SimilarQuery[];
}

export interface DiscoveryResponse {
    query: string;
    reasoning: string;
    context: DiscoveryContext;
}

export interface GenerateSQLResponse {
    sql: string;
    explanation?: string;
    query_type?: string;
    context_text?: string;
    context_history?: string[];
    objects?: SearchObject[];
}

export interface SearchObject {
    schema: string;
    name: string;
    type?: string | null;
    auto_checked?: boolean;  // High-confidence flag for essential tables
}


export type ChartTypeOption = 'bar' | 'line' | 'pie' | 'scatter' | 'column' | 'stackedBar' | 'stackedColumn' | 'clusteredColumn' | 'area' | 'radar' | 'treemap' | 'funnel' | 'none';

export interface ChartRecommendation {
    chart_type: ChartTypeOption;
    x_axis?: string;
    y_axis?: string[];
    title?: string;
    explanation?: string;
    colors?: string[];
}

export interface ExecutePythonResponse {
    success: boolean;
    output?: unknown;
    error?: string;
    results?: ExecutePythonResult[];
    recommendation?: ChartRecommendation;
    execution_time: number;
    data_profile?: any; // DataProfile from backend (will be typed in conversation.ts)
    insights?: any[]; // Insight[] from backend (will be typed in conversation.ts)
    suggested_refinements?: string[]; // Suggested refinement queries
}

export interface ExecuteSQLResponse {
    success: boolean;
    output?: unknown;
    error?: string;
    results?: ExecutePythonResult[]; // Reuse same result type for SQL query results
    recommendation?: ChartRecommendation;
    execution_time: number;
    rows_affected?: number;
    data_profile?: any;
    insights?: any[];
    sql?: string; // Fixed SQL (if auto-corrected)
    auto_fixed?: boolean;
    fix_attempt?: number;
    original_error?: string;
}

export interface StructuredTableData {
    columns: string[];
    data: Array<Record<string, unknown>>;
}

export interface ChartMetadata {
    type: 'bar' | 'line' | 'pie' | 'scatter' | 'column' | 'stackedBar' | 'stackedColumn' | 'clusteredColumn' | 'area' | 'radar' | 'treemap' | 'funnel' | 'none';
    x_axis: string | null;
    y_axes: string[];
    is_stacked: boolean;
}

export interface VizConfig {
    category: '2d_data' | '3d_data' | 'no_chart' | 'too_much_data';
    allowed_charts: string[];
    message: string;
}

export interface ExecutePythonResult {
    name: string;
    type: 'dataframe' | string;
    data: StructuredTableData | Array<Record<string, unknown>>;
    rows: number;
    columns: string[];
    chart_metadata?: ChartMetadata; // Deprecated, keeping for backward compatibility
    viz_config?: VizConfig;
}

export interface SchemaMarkdownResponse {
    schema_name: string;
    table_name: string;
    table_type?: string;
    description?: string;
}

export interface AgentStatus {
    step_id: number;
    message: string;
    type: 'status' | 'result' | 'error';
    details?: Record<string, unknown>;
    timestamp: number;
}

export const api = {
    discovery: async (query: string): Promise<DiscoveryResponse> => {
        const response = await axios.post(`${API_BASE_URL}/discovery`, { query, top_k: 5 });
        return response.data;
    },

    generateSQL: async (
        query: string,
        context?: DiscoveryContext,
        previousSQL?: string,
        queryHistory?: string,
        forceGeneral: boolean = false,
        queryMode: 'generate' | 'search' = 'generate',
        tableOverride?: string[]
    ): Promise<GenerateSQLResponse> => {
        const response = await axios.post(`${API_BASE_URL}/generate-sql`, {
            query,
            context,
            previousSQL,
            queryHistory,
            forceGeneral,
            queryMode,
            table_override: tableOverride
        });
        return response.data;
    },

    generateSQLStream: async (
        query: string,
        onStatus: (status: AgentStatus) => void,
        context?: DiscoveryContext,
        previousSQL?: string,
        queryHistory?: string,
        forceGeneral: boolean = false,
        queryMode: 'generate' | 'search' | 'plan' = 'generate',
        signal?: AbortSignal,
        tableOverride?: string[],
        planningContext?: any
    ): Promise<GenerateSQLResponse> => {
        const url = `${API_BASE_URL}/generate-sql`;
        const headers = {
            'Content-Type': 'application/json',
            'X-API-Key': getApiKey()
        };
        const body = JSON.stringify({ 
            query, 
            context, 
            previousSQL, 
            queryHistory, 
            forceGeneral, 
            queryMode, 
            table_override: tableOverride,
            planning_context: planningContext
        });

        const response = await fetch(url, {
            method: 'POST',
            headers,
            body,
            signal
        });

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`Error ${response.status}: ${errorText || response.statusText}`);
        }

        const reader = response.body?.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let finalResult: GenerateSQLResponse | null = null;

        if (reader) {
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n\n');
                buffer = lines.pop() || '';

                for (const line of lines) {
                    const trimmedLine = line.trim();
                    if (trimmedLine.startsWith('data: ')) {
                        const jsonStr = trimmedLine.replace('data: ', '');
                        try {
                            const data = JSON.parse(jsonStr);
                            if (data.type === 'status') {
                                onStatus(data as AgentStatus);
                            } else if (data.type === 'result') {
                                finalResult = data.payload as GenerateSQLResponse;
                            } else if (data.type === 'error') {
                                throw new Error(data.message);
                            }
                        } catch (e) {
                            console.error('Error parsing stream data:', e);
                        }
                    }
                }
            }
        }

        if (!finalResult) {
            throw new Error("Stream ended without result");
        }
        return finalResult;
    },

    generateRStream: async (query: string, onStatus: (status: AgentStatus) => void, context?: DiscoveryContext, signal?: AbortSignal): Promise<GenerateSQLResponse> => {
        const url = `${API_BASE_URL}/generate-r`;
        const headers = {
            'Content-Type': 'application/json',
            'X-API-Key': getApiKey()
        };
        const body = JSON.stringify({ query, context });

        const response = await fetch(url, {
            method: 'POST',
            headers,
            body,
            signal
        });

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`Error ${response.status}: ${errorText || response.statusText}`);
        }

        const reader = response.body?.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let finalResult: GenerateSQLResponse | null = null;

        if (reader) {
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n\n');
                buffer = lines.pop() || '';

                for (const line of lines) {
                    const trimmedLine = line.trim();
                    if (trimmedLine.startsWith('data: ')) {
                        const jsonStr = trimmedLine.replace('data: ', '');
                        try {
                            const data = JSON.parse(jsonStr);
                            if (data.type === 'status') {
                                onStatus(data as AgentStatus);
                            } else if (data.type === 'result') {
                                finalResult = data.payload as GenerateSQLResponse;
                            } else if (data.type === 'error') {
                                throw new Error(data.message);
                            }
                        } catch (e) {
                            console.error('Error parsing stream data:', e);
                        }
                    }
                }
            }
        }

        if (!finalResult) {
            throw new Error("Stream ended without result");
        }
        return finalResult;
    },

    generateSASStream: async (query: string, onStatus: (status: AgentStatus) => void, context?: DiscoveryContext, signal?: AbortSignal): Promise<GenerateSQLResponse> => {
        const url = `${API_BASE_URL}/generate-sas`;
        const headers = {
            'Content-Type': 'application/json',
            'X-API-Key': getApiKey()
        };
        const body = JSON.stringify({ query, context });

        const response = await fetch(url, {
            method: 'POST',
            headers,
            body,
            signal
        });

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`Error ${response.status}: ${errorText || response.statusText}`);
        }

        const reader = response.body?.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let finalResult: GenerateSQLResponse | null = null;

        if (reader) {
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n\n');
                buffer = lines.pop() || '';

                for (const line of lines) {
                    const trimmedLine = line.trim();
                    if (trimmedLine.startsWith('data: ')) {
                        const jsonStr = trimmedLine.replace('data: ', '');
                        try {
                            const data = JSON.parse(jsonStr);
                            if (data.type === 'status') {
                                onStatus(data as AgentStatus);
                            } else if (data.type === 'result') {
                                finalResult = data.payload as GenerateSQLResponse;
                            } else if (data.type === 'error') {
                                throw new Error(data.message);
                            }
                        } catch (e) {
                            console.error('Error parsing stream data:', e);
                        }
                    }
                }
            }
        }

        if (!finalResult) {
            throw new Error("Stream ended without result");
        }
        return finalResult;
    },

    generatePythonStream: async (query: string, onStatus: (status: AgentStatus) => void, context?: DiscoveryContext, signal?: AbortSignal): Promise<GenerateSQLResponse> => {
        const url = `${API_BASE_URL}/generate-python`;
        const headers = {
            'Content-Type': 'application/json',
            'X-API-Key': getApiKey()
        };
        const body = JSON.stringify({ query, context });

        const response = await fetch(url, {
            method: 'POST',
            headers,
            body,
            signal
        });

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`Error ${response.status}: ${errorText || response.statusText}`);
        }

        const reader = response.body?.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let finalResult: GenerateSQLResponse | null = null;

        if (reader) {
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n\n');
                buffer = lines.pop() || '';

                for (const line of lines) {
                    const trimmedLine = line.trim();
                    if (trimmedLine.startsWith('data: ')) {
                        const jsonStr = trimmedLine.replace('data: ', '');
                        try {
                            const data = JSON.parse(jsonStr);
                            if (data.type === 'status') {
                                onStatus(data as AgentStatus);
                            } else if (data.type === 'result') {
                                finalResult = data.payload as GenerateSQLResponse;
                            } else if (data.type === 'error') {
                                throw new Error(data.message);
                            }
                        } catch (e) {
                            console.error('Error parsing stream data:', e);
                        }
                    }
                }
            }
        }

        if (!finalResult) {
            throw new Error("Stream ended without result");
        }
        return finalResult;
    },

    executePython: async (code: string, context?: any, chartTypeOverride?: ChartTypeOption, enableProfiling: boolean = false): Promise<ExecutePythonResponse> => {
        const response = await axios.post(`${API_BASE_URL}/execute-python`, { 
            code, 
            context,
            chart_type_override: chartTypeOverride,
            enable_profiling: enableProfiling
        });
        return response.data;
    },

    executeSQL: async (sql: string, context?: any, chartTypeOverride?: ChartTypeOption, timeoutSeconds?: number, maxRows?: number, enableProfiling: boolean = false): Promise<ExecuteSQLResponse> => {
        const response = await axios.post(`${API_BASE_URL}/execute-sql`, { 
            sql, 
            context,
            chart_type_override: chartTypeOverride,
            timeout_seconds: timeoutSeconds,
            max_rows: maxRows,
            enable_profiling: enableProfiling
        });
        return response.data;
    },

    /**
     * Summarize Python execution results using LLM
     */
    summarizeResults: async (
        userRequest: string,
        resultData: any,
        chartType?: string
    ): Promise<{ summary: string }> => {
        const response = await axios.post(`${API_BASE_URL}/summarize-results`, {
            user_request: userRequest,
            result_data: resultData,
            chart_type: chartType || undefined
        });
        return response.data;
    },

    // Contribution API (User-facing)
    contributions: {
        submit: async (request: ContributionRequest): Promise<ContributionResponse> => {
            const response = await axios.post(`${API_BASE_URL}/contributions`, request);
            return response.data;
        }
    },

    getSchemaMarkdown: async (objectName: string): Promise<SchemaMarkdownResponse> => {
        const response = await axios.get(`${API_BASE_URL}/schema/${encodeURIComponent(objectName)}`);
        return response.data;
    },

    // Admin API
    admin: {
        syncTable: async (schema: string, table: string) => {
            await axios.post(`${API_BASE_URL}/admin/schema/sync`, null, { params: { schema, table } });
        },
        syncAllSchemas: async () => {
            await axios.post(`${API_BASE_URL}/admin/schema/sync-full`);
        },
        batchSyncTables: async (tableNames: string[]) => {
            const response = await axios.post(`${API_BASE_URL}/admin/schema/batch-sync`, { table_names: tableNames });
            return response.data;
        },
        getFewShots: async (): Promise<FewShotItem[]> => {
            const response = await axios.get(`${API_BASE_URL}/admin/fewshots`);
            return response.data;
        },
        addFewShot: async (item: FewShotItem) => {
            await axios.post(`${API_BASE_URL}/admin/fewshots`, item);
        },
        deleteFewShot: async (id: string) => {
            await axios.delete(`${API_BASE_URL}/admin/fewshots/${id}`);
        },
        // Contribution Management (Admin)
        getContributions: async (): Promise<ContributionItem[]> => {
            const response = await axios.get(`${API_BASE_URL}/admin/contributions`);
            return response.data;
        },
        approveContribution: async (contributionId: string, editedQuestion?: string, editedSQL?: string, knowledgeType?: string) => {
            const response = await axios.post(`${API_BASE_URL}/admin/contributions/approve`, {
                contribution_id: contributionId,
                edited_question: editedQuestion,
                edited_sql: editedSQL,
                knowledge_type: knowledgeType
            });
            return response.data;
        },
        rejectContribution: async (contributionId: string) => {
            await axios.delete(`${API_BASE_URL}/admin/contributions/${contributionId}`);
        },
        updateSchemaDescription: async (schema: string, table: string, description: string) => {
            await axios.put(`${API_BASE_URL}/admin/schema/description`, null, {
                params: { schema, table, description }
            });
        },
        deleteSchema: async (schema: string, table: string) => {
            await axios.delete(`${API_BASE_URL}/admin/schema`, { params: { schema, table } });
        },
        clearAllSchemas: async () => {
            await axios.post(`${API_BASE_URL}/admin/schema/clear`);
        },
        getSchemaStatus: async (includeDbInspection: boolean = false): Promise<AdminSchemaStatus[]> => {
            const params = includeDbInspection ? { include_db_inspection: 'true' } : {};
            const response = await axios.get(`${API_BASE_URL}/admin/schema/status`, { params });
            return response.data;
        },
        inspectDatabase: async (): Promise<AdminSchemaStatus[]> => {
            const response = await axios.get(`${API_BASE_URL}/admin/schema/status`, {
                params: { include_db_inspection: 'true' }
            });
            return response.data;
        },
        getSchemaTemplate: async () => {
            const response = await axios.get(`${API_BASE_URL}/admin/schema/template`, {
                responseType: 'blob'
            });
            return response.data;
        },
        getValues: async (): Promise<ValueIndexItem[]> => {
            const response = await axios.get(`${API_BASE_URL}/admin/values`);
            return response.data;
        },
        searchValues: async (query: string, topK: number = 50): Promise<ValueIndexItem[]> => {
            const response = await axios.get(`${API_BASE_URL}/admin/values/search`, {
                params: { query, top_k: topK }
            });
            return response.data;
        },
        ingestValues: async (file: File, mode: 'append' | 'replace' = 'append', onProgress?: (progress: { current: number; total: number; percentage: number }) => void) => {
            const formData = new FormData();
            formData.append('file', file);
            formData.append('mode', mode);

            // Create abort controller for cleanup
            const abortController = new AbortController();

            // Start the POST request first
            const uploadPromise = axios.post(`${API_BASE_URL}/admin/ingest-values`, formData, {
                headers: { 'Content-Type': 'multipart/form-data' },
                signal: abortController.signal
            });

            // Give backend a moment to initialize progress, then start listening
            await new Promise(resolve => setTimeout(resolve, 100));

            // Start listening to progress updates via SSE
            const progressPromise = new Promise<void>((resolve) => {
                const eventSource = new EventSource(`${API_BASE_URL}/admin/ingest-progress`);

                eventSource.onmessage = (event) => {
                    try {
                        const data = JSON.parse(event.data);
                        if (onProgress) {
                            onProgress({
                                current: data.current || 0,
                                total: data.total || 0,
                                percentage: data.percentage || 0
                            });
                        }
                        // Close when complete or error
                        if (data.status === 'complete' || data.status === 'error') {
                            eventSource.close();
                            resolve();
                        }
                    } catch (e) {
                        console.error('Error parsing progress event:', e);
                    }
                };

                eventSource.onerror = () => {
                    eventSource.close();
                    resolve();
                };
            });

            try {
                const response = await uploadPromise;

                // Wait for progress stream to close
                await Promise.race([
                    progressPromise,
                    new Promise(resolve => setTimeout(resolve, 5000)) // Timeout after 5 seconds
                ]);

                return response.data;
            } catch (error) {
                abortController.abort();
                throw error;
            }
        },
        deleteValue: async (id: number) => {
            await axios.delete(`${API_BASE_URL}/admin/values/${id}`);
        },
        clearAllValues: async () => {
            await axios.post(`${API_BASE_URL}/admin/values/clear`);
        },
        getValueTemplate: async () => {
            const response = await axios.get(`${API_BASE_URL}/admin/values/template`, {
                responseType: 'blob'
            });
            return response.data;
        },
        // Export endpoints
        exportSchemas: async () => {
            const response = await axios.get(`${API_BASE_URL}/admin/schema/export`, {
                responseType: 'blob'
            });
            return response.data;
        },
        exportFewShots: async () => {
            const response = await axios.get(`${API_BASE_URL}/admin/fewshots/export`, {
                responseType: 'blob'
            });
            return response.data;
        },
        exportValues: async () => {
            const response = await axios.get(`${API_BASE_URL}/admin/values/export`, {
                responseType: 'blob'
            });
            return response.data;
        },
        ingestSchemas: async (file: File, mode: 'append' | 'replace' = 'append', onProgress?: (progress: { current: number; total: number; percentage: number }) => void) => {
            const formData = new FormData();
            formData.append('file', file);
            formData.append('mode', mode);

            // Create abort controller for cleanup
            const abortController = new AbortController();

            // Start the POST request first
            const uploadPromise = axios.post(`${API_BASE_URL}/admin/ingest-schemas`, formData, {
                headers: { 'Content-Type': 'multipart/form-data' },
                signal: abortController.signal
            });

            // Give backend a moment to initialize progress, then start listening
            await new Promise(resolve => setTimeout(resolve, 100));

            // Start listening to progress updates via SSE
            const progressPromise = new Promise<void>((resolve) => {
                const eventSource = new EventSource(`${API_BASE_URL}/admin/ingest-progress`);

                eventSource.onmessage = (event) => {
                    try {
                        const data = JSON.parse(event.data);
                        if (onProgress) {
                            onProgress({
                                current: data.current || 0,
                                total: data.total || 0,
                                percentage: data.percentage || 0
                            });
                        }
                        // Close when complete or error
                        if (data.status === 'complete' || data.status === 'error') {
                            eventSource.close();
                            resolve();
                        }
                    } catch (e) {
                        console.error('Error parsing progress event:', e);
                    }
                };

                eventSource.onerror = () => {
                    eventSource.close();
                    resolve();
                };
            });

            try {
                const response = await uploadPromise;

                // Wait for progress stream to close
                await Promise.race([
                    progressPromise,
                    new Promise(resolve => setTimeout(resolve, 5000)) // Timeout after 5 seconds
                ]);

                return response.data;
            } catch (error) {
                abortController.abort();
                throw error;
            }
        },
        ingestFewShots: async (file: File, mode: 'append' | 'replace' = 'append', onProgress?: (progress: { current: number; total: number; percentage: number }) => void) => {
            const formData = new FormData();
            formData.append('file', file);
            formData.append('mode', mode);

            // Create abort controller for cleanup
            const abortController = new AbortController();

            // Start the POST request first
            const uploadPromise = axios.post(`${API_BASE_URL}/admin/ingest-fewshots`, formData, {
                headers: { 'Content-Type': 'multipart/form-data' },
                signal: abortController.signal
            });

            // Give backend a moment to initialize progress, then start listening
            await new Promise(resolve => setTimeout(resolve, 100));

            // Start listening to progress updates via SSE
            const progressPromise = new Promise<void>((resolve) => {
                const eventSource = new EventSource(`${API_BASE_URL}/admin/ingest-progress`);

                eventSource.onmessage = (event) => {
                    try {
                        const data = JSON.parse(event.data);
                        if (onProgress) {
                            onProgress({
                                current: data.current || 0,
                                total: data.total || 0,
                                percentage: data.percentage || 0
                            });
                        }
                        // Close when complete or error
                        if (data.status === 'complete' || data.status === 'error') {
                            eventSource.close();
                            resolve();
                        }
                    } catch (e) {
                        console.error('Error parsing progress event:', e);
                    }
                };

                eventSource.onerror = () => {
                    eventSource.close();
                    resolve();
                };
            });

            try {
                const response = await uploadPromise;

                // Wait for progress stream to close
                await Promise.race([
                    progressPromise,
                    new Promise(resolve => setTimeout(resolve, 5000)) // Timeout after 5 seconds
                ]);

                return response.data;
            } catch (error) {
                abortController.abort();
                throw error;
            }
        },
        // Settings endpoints
        getSettings: async (): Promise<AgentSettings> => {
            const response = await axios.get(`${API_BASE_URL}/admin/settings`);
            return response.data;
        },
        updateSettings: async (settings: AgentSettings): Promise<AgentSettings> => {
            const response = await axios.put(`${API_BASE_URL}/admin/settings`, settings);
            return response.data;
        },
        testConnection: async (request: ConnectionTestRequest): Promise<ConnectionTestResponse> => {
            const response = await axios.post(`${API_BASE_URL}/admin/test-connection`, request);
            return response.data;
        },
        buildConnectionString: async (request: ConnectionTestRequest): Promise<{ connection_string: string; connection_string_masked: string; encrypted: string; python_connection_string: string; python_encrypted: string }> => {
            const response = await axios.post(`${API_BASE_URL}/admin/build-connection-string`, request);
            return response.data;
        },
        getModels: async () => {
            const response = await axios.get(`${API_BASE_URL}/admin/models`);
            return response.data;
        },
        fetchModels: async (endpoint: string, apiKey?: string) => {
            const response = await axios.post(`${API_BASE_URL}/admin/fetch-models`, {
                llm_endpoint: endpoint,
                llm_api_key: apiKey
            });
            return response.data;
        },
        getEnvApiKey: async (): Promise<EnvApiKeyResponse> => {
            const response = await axios.get(`${API_BASE_URL}/admin/api-key`);
            return response.data;
        },
        setEnvApiKey: async (apiKey: string): Promise<EnvApiKeyResponse> => {
            const response = await axios.post(`${API_BASE_URL}/admin/api-key`, {
                api_key: apiKey
            });
            return response.data;
        },
        backupVectorStore: async () => {
            const response = await axios.get(`${API_BASE_URL}/admin/vector-store/backup`, {
                responseType: 'blob'
            });
            return response.data;
        },
        verifySettings: async (): Promise<VerifySettingsResponse> => {
            const response = await axios.post(`${API_BASE_URL}/admin/verify-settings`);
            return response.data;
        },
        
        // Skills Management
        getDataSources: async (): Promise<DataSource[]> => {
            const response = await axios.get(`${API_BASE_URL}/admin/skills/data-sources`);
            return response.data;
        },
        createDataSource: async (data: Partial<DataSource>) => {
            const response = await axios.post(`${API_BASE_URL}/admin/skills/data-sources`, data);
            return response.data;
        },
        updateDataSource: async (name: string, data: Partial<DataSource>) => {
            const response = await axios.put(`${API_BASE_URL}/admin/skills/data-sources/${encodeURIComponent(name)}`, data);
            return response.data;
        },
        deleteDataSource: async (name: string) => {
            const response = await axios.delete(`${API_BASE_URL}/admin/skills/data-sources/${encodeURIComponent(name)}`);
            return response.data;
        },
        getDataGroups: async (dataSource?: string): Promise<DataGroup[]> => {
            const params = dataSource ? { data_source: dataSource } : {};
            const response = await axios.get(`${API_BASE_URL}/admin/skills/data-groups`, { params });
            return response.data;
        },
        createDataGroup: async (data: Partial<DataGroup>) => {
            const response = await axios.post(`${API_BASE_URL}/admin/skills/data-groups`, data);
            return response.data;
        },
        updateDataGroup: async (data: Partial<DataGroup>) => {
            const response = await axios.put(`${API_BASE_URL}/admin/skills/data-groups`, data);
            return response.data;
        },
        deleteDataGroup: async (filePath: string) => {
            const response = await axios.delete(`${API_BASE_URL}/admin/skills/data-groups`, {
                params: { file_path: filePath }
            });
            return response.data;
        },
        getTables: async (dataSource?: string, dataGroup?: string): Promise<SkillTableSchema[]> => {
            const params: any = {};
            if (dataSource) params.data_source = dataSource;
            if (dataGroup) params.data_group = dataGroup;
            const response = await axios.get(`${API_BASE_URL}/admin/skills/tables`, { params });
            return response.data;
        },
        getTableByPath: async (filePath: string): Promise<SkillTableSchema> => {
            const response = await axios.get(`${API_BASE_URL}/admin/skills/tables/by-path`, {
                params: { file_path: filePath }
            });
            return response.data;
        },
        updateTable: async (data: Partial<SkillTableSchema>) => {
            const response = await axios.put(`${API_BASE_URL}/admin/skills/tables`, data);
            return response.data;
        },
        
        // Read/Write Raw Markdown
        getRawMarkdown: async (filePath: string): Promise<string> => {
            const response = await axios.get(`${API_BASE_URL}/admin/skills/raw-markdown`, {
                params: { file_path: filePath }
            });
            return response.data.content;
        },
        saveRawMarkdown: async (filePath: string, content: string) => {
            const response = await axios.put(`${API_BASE_URL}/admin/skills/raw-markdown`, {
                file_path: filePath,
                content: content
            });
            return response.data;
        },
        
        // Get folder tree hierarchy
        getFolderTree: async (): Promise<FolderTreeNode> => {
            const response = await axios.get(`${API_BASE_URL}/admin/skills/folder-tree`);
            return response.data;
        },

        // Enhance schema descriptions with AI
        enhanceSchemaWithAI: async (params: {
            file_path: string;
            current_content: string;
            user_context?: string;
        }): Promise<{ enhanced_markdown: string }> => {
            const response = await axios.post(`${API_BASE_URL}/admin/enhance-schema`, params);
            return response.data;
        }
    },

    // Data Sources Management (V2 Multi-Source)
    dataSources: {
        getAll: async (): Promise<DataSourceListResponse> => {
            const response = await axios.get(`${API_BASE_URL}/admin/data-sources`);
            return response.data;
        },
        add: async (request: AddDataSourceRequest): Promise<DataSourceResponse> => {
            const response = await axios.post(`${API_BASE_URL}/admin/data-sources`, request);
            return response.data;
        },
        get: async (sourceId: string): Promise<DataSourceResponse> => {
            const response = await axios.get(`${API_BASE_URL}/admin/data-sources/${encodeURIComponent(sourceId)}`);
            return response.data;
        },
        update: async (sourceId: string, request: AddDataSourceRequest): Promise<void> => {
            await axios.put(`${API_BASE_URL}/admin/data-sources/${encodeURIComponent(sourceId)}`, request);
        },
        delete: async (sourceId: string): Promise<void> => {
            await axios.delete(`${API_BASE_URL}/admin/data-sources/${encodeURIComponent(sourceId)}`);
        },
        testConnection: async (sourceId: string): Promise<ConnectionTestResponse> => {
            const response = await axios.post(`${API_BASE_URL}/admin/data-sources/${encodeURIComponent(sourceId)}/test`);
            return response.data;
        },
        setPrimary: async (sourceId: string): Promise<void> => {
            await axios.post(`${API_BASE_URL}/admin/data-sources/${encodeURIComponent(sourceId)}/set-primary`);
        },
        toggleEnabled: async (sourceId: string, enabled: boolean): Promise<void> => {
            await axios.post(`${API_BASE_URL}/admin/data-sources/${encodeURIComponent(sourceId)}/enable`, { enabled });
        }
    },

    // Schema Tree Navigation (V2 Multi-Source)
    schemaTree: {
        getTree: async (sourceId?: string): Promise<SchemaTreeResponse> => {
            const params = sourceId ? { source_id: sourceId } : {};
            const response = await axios.get(`${API_BASE_URL}/admin/schema-tree`, { params });
            return response.data;
        },
        getTreeForSource: async (sourceId: string): Promise<SchemaTreeResponse> => {
            const response = await axios.get(`${API_BASE_URL}/admin/schema-tree/${encodeURIComponent(sourceId)}`);
            return response.data;
        },
        getSchemas: async (sourceId: string): Promise<string[]> => {
            const response = await axios.get(`${API_BASE_URL}/admin/schema-tree/${encodeURIComponent(sourceId)}/schemas`);
            return response.data.schemas;
        },
        getObjects: async (sourceId: string, schema?: string, objectType?: ObjectType): Promise<DataObject[]> => {
            const params: any = {};
            if (schema) params.schema = schema;
            if (objectType) params.object_type = objectType;
            const response = await axios.get(`${API_BASE_URL}/admin/schema-tree/${encodeURIComponent(sourceId)}/objects`, { params });
            return response.data.objects;
        },
        discoverObjects: async (request: DiscoverObjectsRequest): Promise<DiscoverObjectsResponse> => {
            const response = await axios.post(`${API_BASE_URL}/admin/schema-tree/${encodeURIComponent(request.source_id)}/discover`, request);
            return response.data;
        }
    },

    // Object Management (V2 Multi-Source)
    objects: {
        add: async (request: AddObjectRequest): Promise<void> => {
            await axios.post(`${API_BASE_URL}/admin/object`, request);
        },
        sync: async (request: SyncObjectRequest): Promise<void> => {
            await axios.post(`${API_BASE_URL}/admin/object/sync`, request);
        },
        delete: async (sourceId: string, schema: string, objectName: string): Promise<void> => {
            await axios.delete(`${API_BASE_URL}/admin/object`, {
                params: {
                    source_id: sourceId,
                    schema: schema,
                    object_name: objectName
                }
            });
        },
        discover: async (request: DiscoverObjectsRequest): Promise<DiscoverObjectsResponse> => {
            const response = await axios.post(`${API_BASE_URL}/admin/object/discover`, request);
            return response.data;
        }
    },


    // Generic client for backward compatibility
    client: axios
};

export interface ValueIndexItem {
    id?: number;
    value: string;
    schema_name: string;
    table_name: string;
    column_name: string;
}

export interface AdminSchemaStatus {
    schema_name: string;
    table_name: string;
    table_type?: string;  // 'table' or 'view'
    is_indexed: boolean;
    description?: string;
    column_count: number;
    last_updated?: string;
}

export interface FewShotItem {
    id?: string;
    question: string;
    sql_query: string;
    knowledge_type?: 'general' | 'sql_query' | 'r_code' | 'sas_code' | 'python_code';
    verified: boolean;
}

// Contribution Library Types
export interface ContributionItem {
    id?: string;
    question: string;
    sql_query: string;
    knowledge_type?: string;
    submitted_at?: string;
    user_id?: string;
    status: string;
    similarity_score?: number;
    similar_to_id?: string;
}

export interface ContributionRequest {
    question: string;
    sql_query: string;
    knowledge_type?: string;
    user_id?: string;
}

export interface ContributionResponse {
    success: boolean;
    message: string;
    contribution_id?: string;
    similarity_warning: boolean;
    similarity_score?: number;
}

// Settings Types
export interface TargetDBConfig {
    friendly_name: string;
    description: string;
    keywords: string[];
    db_type: string;
    server: string;
    database_name: string;
    connection_string_encrypted: string;
    connection_string_decrypted?: string;
    driver?: string;
    auth_type?: string;
    username?: string;
    trust_server_certificate?: boolean;
}

export interface LLMConfig {
    llm_model: string;
    model_id?: string;  // Alias for compatibility
    temperature: number;
    llm_endpoint?: string;
    llm_api_key?: string;
}

export interface EmbeddingConfig {
    provider: string;
    base_url?: string;
    api_key?: string;
    model: string;
    dimensions: number;
}

export interface VectorConfig {
    provider: string;
    host: string;
    port: string;
    // embedding_model moved to EmbeddingConfig
}

export interface AppMeta {
    app_name: string;
    version: string;
    project_name: string;
}

export interface AgentSettings {
    target_db: TargetDBConfig;
    llm_config: LLMConfig;
    embedding_config: EmbeddingConfig;
    vector_config: VectorConfig;
    app_meta: AppMeta;
}

export interface ConnectionTestRequest {
    driver: string;
    server: string;
    database: string;
    auth_type: 'sql' | 'windows' | 'ad_integrated' | 'ad_password' | 'ad_interactive' | 'ad_service_principal';
    username?: string;
    password?: string;
    trust_server_certificate?: boolean;
}

export interface ConnectionTestResponse {
    success: boolean;
    message: string;
    connection_string_masked?: string;
}

export interface EnvApiKeyResponse {
    api_key?: string | null;
    exists: boolean;
}

export interface VerifySettingsResponse {
    success: boolean;
    message: string;
    errors?: { [key: string]: string };
    db_connected?: boolean;
    db_message?: string;
    llm_connected?: boolean;
    llm_message?: string;
    milvus_connected?: boolean;
    milvus_message?: string;
}

// Skills Management Types
export interface DataSource {
    name: string;
    type: string;
    description: string;
    keywords: string[];
    status: string;
    connection_info?: any;
    data_groups?: string[];
    file_path?: string;
}

export interface DataGroup {
    name: string;
    data_source: string;
    description: string;
    keywords: string[];
    tables: string[];
    schema_notes?: string;
    category?: string;
    file_path?: string;
}

export interface SkillTableSchema {
    schema_name: string;
    table_name: string;
    table_type?: string;
    description?: string;
    columns: ColumnInfo[];
    file_path?: string;
}

export interface FolderTreeNode {
    name: string;
    path: string;
    relative_path: string;
    is_file: boolean;
    type: 'file' | 'folder';
    extension?: string;
    is_markdown?: boolean;
    children?: FolderTreeNode[];
}

// Multi-Source Schema Tree Types (V2)
export type ObjectType = 'table' | 'view' | 'stored_procedure' | 'function';

export interface DataObject {
    source_id: string;
    schema_name: string;
    object_name: string;
    object_type: ObjectType;
    description?: string;
    columns?: ColumnInfo[];
    definition?: string;
    parameters?: string;
    return_type?: string;
}

export interface TargetDBConfigV2 {
    source_id: string;
    friendly_name: string;
    description: string;
    keywords: string[];
    db_type: string;
    server: string;
    database_name: string;
    connection_string_encrypted: string;
    connection_string_decrypted?: string;
    driver?: string;
    auth_type?: string;
    username?: string;
    trust_server_certificate?: boolean;
    enabled: boolean;
    last_synced?: string;
    object_count: number;
}

export interface DataSourceResponse {
    source_id: string;
    friendly_name: string;
    description: string;
    keywords: string[];
    server: string;
    database_name: string;
    db_type: string;
    enabled: boolean;
    is_primary: boolean;
    object_count: number;
    last_synced?: string;
}

export interface DataSourceListResponse {
    data_sources: DataSourceResponse[];
    primary_source_id?: string;
}

export interface AddDataSourceRequest {
    friendly_name: string;
    description: string;
    keywords: string[];
    db_type: string;
    server: string;
    database_name: string;
    connection_string_encrypted: string;
    driver?: string;
    auth_type?: string;
    username?: string;
    trust_server_certificate?: boolean;
}

export interface SchemaTreeNode {
    node_id: string;
    name: string;
    type: 'source' | 'schema' | 'table' | 'view' | 'stored_procedure' | 'function';
    parent_id?: string;
    children: SchemaTreeNode[];
    metadata: {
        source_id?: string;
        schema_name?: string;
        object_name?: string;
        object_type?: ObjectType;
        description?: string;
        column_count?: number;
        enabled?: boolean;
        is_primary?: boolean;
        object_count?: number;
        last_synced?: string;
    };
    is_indexed: boolean;
}

export interface SchemaTreeResponse {
    roots: SchemaTreeNode[];
    total_sources: number;
    total_objects: number;
}

export interface AddObjectRequest {
    source_id: string;
    schema_name: string;
    object_name: string;
    object_type: ObjectType;
    description: string;
    columns?: ColumnInfo[];
    definition?: string;
    parameters?: string;
    return_type?: string;
}

export interface SyncObjectRequest {
    source_id: string;
    schema_name: string;
    object_name: string;
    object_type: ObjectType;
}

export interface DiscoverObjectsRequest {
    source_id: string;
    schema_name?: string;
    object_types?: ObjectType[];
}

export interface DiscoverObjectsResponse {
    objects: DataObject[];
    count: number;
}



/**
 * Summarize Python execution results using LLM
 * @param userRequest The original user request string
 * @param resultData The result data (tabular or otherwise) to summarize
 * @param chartType (optional) Chart type if relevant
 * @returns {Promise<{summary: string}>}
 */
// @ts-ignore
export const summarizeResults = async (
    userRequest: string,
    resultData: any,
    chartType?: string // Use string for compatibility
): Promise<{ summary: string }> => {
    const response = await axios.post(`${API_BASE_URL}/summarize-results`, {
        user_request: userRequest,
        result_data: resultData,
        chart_type: chartType || undefined
    });
    return response.data;
};

/**
 * Generate a planning summary from planning context
 * @param planningContext The accumulated planning state
 * @returns {Promise<{summary: string}>}
 */
export const generatePlanningSummary = async (
    planningContext: any
): Promise<{ summary: string }> => {
    const response = await axios.post(`${API_BASE_URL}/planning-summary`, {
        planning_context: planningContext
    });
    return response.data;
};
