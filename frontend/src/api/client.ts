import axios from 'axios';

// Default values
const DEFAULT_API_BASE_URL = '/api/v1';
const DEFAULT_API_KEY = '***REMOVED***';

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
}


export interface ChartRecommendation {
    chart_type: 'bar' | 'line' | 'pie' | 'scatter' | 'kpi' | 'none';
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
}

export interface StructuredTableData {
    columns: string[];
    data: Array<Record<string, unknown>>;
}

export interface ChartMetadata {
    type: 'bar' | 'stacked-bar' | 'none';
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
        queryMode: 'generate' | 'search' = 'generate',
        signal?: AbortSignal,
        tableOverride?: string[]
    ): Promise<GenerateSQLResponse> => {
        const url = `${API_BASE_URL}/generate-sql`;
        const headers = {
            'Content-Type': 'application/json',
            'X-API-Key': getApiKey()
        };
        const body = JSON.stringify({ query, context, previousSQL, queryHistory, forceGeneral, queryMode, table_override: tableOverride });

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

    executePython: async (code: string, context?: any): Promise<ExecutePythonResponse> => {
        const response = await axios.post(`${API_BASE_URL}/execute-python`, { code, context });
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
        getSchemaStatus: async (): Promise<AdminSchemaStatus[]> => {
            const response = await axios.get(`${API_BASE_URL}/admin/schema/status`);
            return response.data;
        },
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
        backupVectorStore: async () => {
            const response = await axios.get(`${API_BASE_URL}/admin/vector-store/backup`, {
                responseType: 'blob'
            });
            return response.data;
        },
        verifySettings: async (): Promise<VerifySettingsResponse> => {
            const response = await axios.post(`${API_BASE_URL}/admin/verify-settings`);
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

export interface VerifySettingsResponse {
    db_connected: boolean;
    db_message: string;
    llm_connected: boolean;
    llm_message: string;
    milvus_connected: boolean;
    milvus_message: string;
}
