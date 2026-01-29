import { useState, useEffect, useRef } from 'react';
import { Send, Loader2, Sparkles, LayoutDashboard, User, Bot, Square, Eye, X, CheckCircle } from 'lucide-react';
import { api } from './api/client';
import type { GenerateSQLResponse, AgentStatus, ExecutePythonResponse, ExecuteSQLResponse } from './api/client';
import { SQLResultDisplay } from './components/SQL/SQLResultDisplay';
import { AdminLayout } from './pages/Admin/AdminLayout';
import { SchemaManager } from './pages/Admin/SchemaManager';
import { FewShotManager } from './pages/Admin/FewShotManager';
import { ValueManager } from './pages/Admin/ValueManager';
import { ContributionManager } from './pages/Admin/ContributionManager';
import { Settings } from './pages/Admin/Settings';
import { Toast } from './components/Toast';
import type { ToastType } from './components/Toast';
import { ErrorBoundary } from './components/ErrorBoundary';
import { Sidebar } from './components/Sidebar/Sidebar';
import { ObjectTypeLabel } from './components/ObjectTypeLabel';
import type { Conversation, ChatMessage, AnalysisContext } from './types/conversation';
import { InsightsPanel } from './components/InsightsPanel';
import { RefinementSuggestions } from './components/RefinementSuggestions';
import { DataProfileCard } from './components/DataProfileCard';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  conversationStorage,
  generateConversationId,
  generateMessageId,
  generateInitialTitle,
  generateAutoTitle
} from './utils/conversationStorage';
import { detectChartIntent, getChartTypeLabel, shouldTriggerRevisualization, getNewCodeReason, isExplicitChartOnlyPattern } from './utils/chartIntentDetector';

function App() {
  // Simple Router State (Hash based or state based)
  const [currentRoute, setCurrentRoute] = useState<'chat' | 'admin'>(() =>
    window.location.pathname.startsWith('/admin') ? 'admin' : 'chat'
  );
  const [adminPage, setAdminPage] = useState('schema');
  const [isUploadingInAdmin, setIsUploadingInAdmin] = useState(false);

  useEffect(() => {
    if (window.location.pathname.startsWith('/admin')) {
      setCurrentRoute('admin');
    }
  }, []);

  // Multi-Conversation State
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [query, setQuery] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [queryMode, setQueryMode] = useState<'generate-sql' | 'generate-r' | 'generate-sas' | 'generate-python' | 'search'>('generate-sql');
  const [toast, setToast] = useState<{ message: string; type: ToastType } | null>(null);
  const [steps, setSteps] = useState<AgentStatus[]>([]);
  const abortControllerRef = useRef<AbortController | null>(null);
  const abortedRef = useRef(false);
  const [selectedObjects, setSelectedObjects] = useState<string[]>([]);
  const [isSchemaModalOpen, setIsSchemaModalOpen] = useState(false);
  const [schemaPreviewName, setSchemaPreviewName] = useState<string | null>(null);
  const [schemaPreviewMarkdown, setSchemaPreviewMarkdown] = useState('');
  const [schemaPreviewError, setSchemaPreviewError] = useState<string | null>(null);
  const [isSchemaPreviewLoading, setIsSchemaPreviewLoading] = useState(false);

  // Ref for auto-scrolling to bottom of chat
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Load conversations from localStorage on mount
  useEffect(() => {
    const loadedConversations = conversationStorage.loadConversations();
    const loadedActiveId = conversationStorage.loadActiveConversationId();

    if (loadedConversations.length > 0) {
      setConversations(loadedConversations);
      // If there's a saved active ID and it exists, use it. Otherwise use the first conversation
      if (loadedActiveId && loadedConversations.some(c => c.id === loadedActiveId)) {
        setActiveConversationId(loadedActiveId);
      } else {
        setActiveConversationId(loadedConversations[0].id);
      }
    }
  }, []);

  // Save conversations to localStorage whenever they change
  useEffect(() => {
    if (conversations.length > 0) {
      conversationStorage.saveConversations(conversations);
    }
  }, [conversations]);

  // Save active conversation ID whenever it changes
  useEffect(() => {
    if (activeConversationId) {
      conversationStorage.saveActiveConversationId(activeConversationId);
    }
  }, [activeConversationId]);

  // Get the current active conversation
  const activeConversation = conversations.find(c => c.id === activeConversationId);
  const chatHistory = activeConversation?.messages || [];
  const lastGeneratedSQL = activeConversation?.lastGeneratedSQL || '';
  const queryHistory = activeConversation?.queryHistory || '';

  useEffect(() => {
    if (activeConversation) {
      setSelectedObjects(activeConversation.selectedObjects || []);
    } else {
      setSelectedObjects([]);
    }
  }, [activeConversationId, activeConversation]);

  // Auto-scroll to bottom when conversation changes or new messages arrive
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [activeConversationId, activeConversation?.messages]);

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`;
    }
  }, [query]);

  // Update a conversation
  const updateConversation = (conversationId: string, updates: Partial<Conversation>) => {
    setConversations(prev =>
      prev.map(conv =>
        conv.id === conversationId
          ? { ...conv, ...updates, lastModified: new Date().toISOString() }
          : conv
      )
    );
  };

  // Create a new conversation
  const handleNewConversation = () => {
    const newConv: Conversation = {
      id: generateConversationId(),
      title: 'New Chat',
      lastModified: new Date().toISOString(),
      messages: [],
      lastGeneratedSQL: '',
      queryHistory: '',
      selectedObjects: [],
    };

    setConversations(prev => [newConv, ...prev]);
    setActiveConversationId(newConv.id);
    setSelectedObjects([]);
    return newConv;
  };

  // Delete a conversation
  const handleDeleteConversation = (conversationId: string) => {
    setConversations(prev => {
      const filtered = prev.filter(c => c.id !== conversationId);

      // If we deleted the active conversation, select another one
      if (conversationId === activeConversationId) {
        if (filtered.length > 0) {
          setActiveConversationId(filtered[0].id);
        } else {
          setActiveConversationId(null);
        }
      }

      return filtered;
    });
  };

  // Rename a conversation
  const handleRenameConversation = (conversationId: string, newTitle: string) => {
    updateConversation(conversationId, { title: newTitle });
  };

  // Select a conversation
  const handleSelectConversation = (conversationId: string) => {
    setActiveConversationId(conversationId);
  };


  const handleClarificationChoice = async (messageId: string, choice: 'database' | 'general') => {
    if (!activeConversationId) return;

    // Find the original user message that prompted this clarification
    const messageIndex = chatHistory.findIndex(msg => msg.id === messageId);
    if (messageIndex === -1) return;

    const aiMessage = chatHistory[messageIndex];
    const userMessageIndex = messageIndex - 1;
    if (userMessageIndex < 0) return;

    const userMessage = chatHistory[userMessageIndex];

    if (choice === 'database') {
      // Re-run as database query
      setIsLoading(true);
      try {
        const context = await api.discovery(userMessage.content);
        const result = await api.generateSQL(
          userMessage.content,
          context.context,
          lastGeneratedSQL || undefined,
          queryHistory || undefined,
          false,
          'generate',
          selectedObjects.length > 0 ? selectedObjects : undefined
        );

        // Update the AI message with the results
        const updatedMessage: ChatMessage = {
          ...aiMessage,
          content: 'Here is the query statement you need to use to query the database:',
          discoveryResult: context,
          sqlResult: result,
          queryType: 'database',
          sourceQuery: userMessage.content,
          needsClarification: false
        };

        // Update conversation
        const updatedMessages = chatHistory.map(msg =>
          msg.id === messageId ? updatedMessage : msg
        );

        updateConversation(activeConversationId, {
          messages: updatedMessages,
          lastGeneratedSQL: result.sql || lastGeneratedSQL,
          queryHistory: result.sql ? '' : queryHistory,
        });
      } catch (error) {
        console.error('Error processing database query:', error);
      } finally {
        setIsLoading(false);
      }
    } else {
      // Re-run as general query with forceGeneral flag
      setIsLoading(true);
      try {
        const result = await api.generateSQL(
          userMessage.content,
          undefined,
          lastGeneratedSQL || undefined,
          queryHistory || undefined,
          true,
          'generate',
          selectedObjects.length > 0 ? selectedObjects : undefined
        );

        // Update the AI message with the general answer
        const updatedMessage: ChatMessage = {
          ...aiMessage,
          content: result.explanation || 'I apologize, but I could not process your request.',
          sqlResult: result,
          queryType: 'general',
          sourceQuery: userMessage.content,
          needsClarification: false
        };

        // Update conversation
        const updatedMessages = chatHistory.map(msg =>
          msg.id === messageId ? updatedMessage : msg
        );

        updateConversation(activeConversationId, {
          messages: updatedMessages,
          queryHistory: '',
        });
      } catch (error) {
        console.error('Error processing general query:', error);
      } finally {
        setIsLoading(false);
      }
    }
  };

  // Handle execution result updates
  const handleExecutionComplete = async (messageId: string, result: ExecutePythonResponse) => {
    if (!activeConversationId) return;

    // Find the message to update
    const msgToUpdate = chatHistory.find(msg => msg.id === messageId);
    if (!msgToUpdate) {
      // fallback: just update executionResult
      const updatedMessages = chatHistory.map(msg =>
        msg.id === messageId ? { ...msg, executionResult: result } : msg
      );
      updateConversation(activeConversationId, { messages: updatedMessages });
      return;
    }

    // Store analysis context if profiling data is available
    let analysisContext: AnalysisContext | undefined;
    if (result.data_profile || result.insights) {
      analysisContext = {
        data_profile: result.data_profile,
        insights: result.insights || [],
        refinement_history: msgToUpdate.analysisContext?.refinement_history || [],
        suggested_refinements: result.suggested_refinements || []
      };
    }

    // First, update the UI immediately with execution results (no summary yet)
    const updatedMessagesImmediate = chatHistory.map(msg =>
      msg.id === messageId ? { 
        ...msg, 
        executionResult: result,
        analysisContext: analysisContext 
      } : msg
    );
    updateConversation(activeConversationId, { messages: updatedMessagesImmediate });

    // Then fetch summary in the background (non-blocking)
    if (result && result.success && result.results && result.results.length > 0) {
      try {
        const firstResult = result.results[0];
        const userRequest = msgToUpdate.sourceQuery || msgToUpdate.content;
        const chartType = msgToUpdate.chartTypeOverride;
        // Only send a preview of data (avoid huge payloads)
        let previewData = firstResult.data;
        if (Array.isArray(previewData) && previewData.length > 20) {
          previewData = previewData.slice(0, 20);
        }
        
        // Add timeout to prevent hanging
        const timeoutPromise = new Promise<never>((_, reject) => 
          setTimeout(() => reject(new Error('Summary timeout')), 15000)
        );
        
        const summaryPromise = api.summarizeResults(userRequest, previewData, chartType);
        const summaryResult = await Promise.race([summaryPromise, timeoutPromise]);
        
        // Update with summary after it arrives
        setConversations(prev => prev.map(conv => {
          if (conv.id !== activeConversationId) return conv;
          return {
            ...conv,
            messages: conv.messages.map(msg =>
              msg.id === messageId ? { ...msg, pythonSummary: summaryResult.summary } : msg
            )
          };
        }));
      } catch (e) {
        console.error('Summary fetch failed:', e);
        // Silently fail - summary is optional
      }
    }
  };

  const handleSQLExecutionComplete = async (messageId: string, result: ExecuteSQLResponse) => {
    if (!activeConversationId) return;

    // Find the message to update
    const msgToUpdate = chatHistory.find(msg => msg.id === messageId);
    if (!msgToUpdate) {
      // fallback: just update sqlExecutionResult
      const updatedMessages = chatHistory.map(msg =>
        msg.id === messageId ? { ...msg, sqlExecutionResult: result } : msg
      );
      updateConversation(activeConversationId, { messages: updatedMessages });
      return;
    }

    // Store analysis context if profiling data is available
    let analysisContext: AnalysisContext | undefined;
    if (result.data_profile || result.insights) {
      analysisContext = {
        data_profile: result.data_profile,
        insights: result.insights || [],
        refinement_history: msgToUpdate?.analysisContext?.refinement_history || [],
        suggested_refinements: [] // SQL doesn't have suggested refinements yet
      };
    }

    // First, update the UI immediately with execution results (no summary yet)
    const updatedMessagesImmediate = chatHistory.map(msg =>
      msg.id === messageId ? { 
        ...msg, 
        sqlExecutionResult: result,
        analysisContext: analysisContext 
      } : msg
    );
    updateConversation(activeConversationId, { messages: updatedMessagesImmediate });

    // Then fetch summary in the background (non-blocking)
    if (result && result.success && result.results && result.results.length > 0) {
      try {
        const firstResult = result.results[0];
        const userRequest = msgToUpdate.sourceQuery || msgToUpdate.content;
        const chartType = msgToUpdate.chartTypeOverride;
        // Only send a preview of data (avoid huge payloads)
        let previewData = firstResult.data;
        if (Array.isArray(previewData)) {
          // If it's structured table data format
          previewData = previewData.slice(0, 20);
        } else if (previewData && typeof previewData === 'object' && 'data' in previewData) {
          // If it's {columns: [], data: []} format
          const dataArray = (previewData as any).data;
          if (Array.isArray(dataArray) && dataArray.length > 20) {
            previewData = { ...(previewData as any), data: dataArray.slice(0, 20) };
          }
        }
        
        // Add timeout to prevent hanging
        const timeoutPromise = new Promise<never>((_, reject) => 
          setTimeout(() => reject(new Error('Summary timeout')), 15000)
        );
        
        const summaryPromise = api.summarizeResults(userRequest, previewData, chartType);
        const summaryResult = await Promise.race([summaryPromise, timeoutPromise]);
        
        // Update with summary after it arrives
        setConversations(prev => prev.map(conv => {
          if (conv.id !== activeConversationId) return conv;
          return {
            ...conv,
            messages: conv.messages.map(msg =>
              msg.id === messageId ? { ...msg, sqlSummary: summaryResult.summary } : msg
            )
          };
        }));
      } catch (e) {
        console.error('SQL summary fetch failed:', e);
        // Silently fail - summary is optional
      }
    }
  };

  const handleRefinementClick = async (suggestion: string) => {
    if (!activeConversationId) return;
    
    // Set the query input with the suggestion
    setQuery(suggestion);
    
    // Optionally focus on the textarea for user review
    if (textareaRef.current) {
      textareaRef.current.focus();
    }
  };

  const parseObjectName = (rawObject: string) => {
    const match = rawObject.match(/\[([^\]]+)\]\.\[([^\]]+)\]/);
    if (match) {
      const schema = match[1];
      const table = match[2];
      return {
        key: `${schema}.${table}`,
        label: `[${schema}].[${table}]`,
      };
    }
    const normalized = rawObject.replace(/\[|\]/g, '').replace(/\s+/g, '').trim();
    return {
      key: normalized,
      label: rawObject,
    };
  };

  const toggleSelectedObject = (objectName: string) => {
    if (!activeConversationId) {
      setSelectedObjects((prev) => (
        prev.includes(objectName)
          ? prev.filter((item) => item !== objectName)
          : [...prev, objectName]
      ));
      return;
    }

    setSelectedObjects((prev) => {
      const nextSelected = prev.includes(objectName)
        ? prev.filter((item) => item !== objectName)
        : [...prev, objectName];
      updateConversation(activeConversationId, { selectedObjects: nextSelected });
      return nextSelected;
    });
  };

  const handleViewSchema = async (objectName: string) => {
    setIsSchemaModalOpen(true);
    setSchemaPreviewName(objectName);
    setSchemaPreviewMarkdown('');
    setSchemaPreviewError(null);
    setIsSchemaPreviewLoading(true);

    try {
      const schema = await api.getSchemaMarkdown(objectName);
      setSchemaPreviewMarkdown(schema.description || 'No schema description found.');
    } catch (error) {
      console.error('Failed to fetch schema markdown:', error);
      setSchemaPreviewError('Unable to load schema. Please try again.');
    } finally {
      setIsSchemaPreviewLoading(false);
    }
  };

  const handleCloseSchemaPreview = () => {
    setIsSchemaModalOpen(false);
    setSchemaPreviewName(null);
    setSchemaPreviewMarkdown('');
    setSchemaPreviewError(null);
    setIsSchemaPreviewLoading(false);
  };

  const handleSend = async () => {
    if (!query.trim()) return;

    // Create new conversation if none exists
    let conversationId = activeConversationId;
    if (!conversationId) {
      const newConv = handleNewConversation();
      conversationId = newConv.id;
    }

    if (!conversationId) return;

    // Detect chart intent from user query
    const chartIntent = detectChartIntent(query);
    const chartTypeOverride = chartIntent?.chartType;

    // Find the last AI message with Python code and execution results
    const lastPythonMessage = [...chatHistory].reverse().find(
      msg => msg.type === 'ai' && 
             msg.queryType === 'python_code' && 
             msg.sqlResult?.sql &&
             msg.executionResult
    );

    // Find the last AI message with SQL execution results
    const lastSQLMessage = [...chatHistory].reverse().find(
      msg => msg.type === 'ai' && 
             msg.queryType === 'database' && 
             msg.sqlResult?.sql &&
             msg.sqlExecutionResult
    );

    // Also find the last generated SQL (even if not executed) for better UX
    const lastGeneratedSQLMessage = [...chatHistory].reverse().find(
      msg => msg.type === 'ai' && 
             msg.queryType === 'database' && 
             msg.sqlResult?.sql
    );

    // DEBUG: Log detection results
    console.log('=== RE-VISUALIZATION DEBUG ===');
    console.log('Query:', query);
    console.log('Chart Intent:', chartIntent);
    console.log('Last Python Message:', lastPythonMessage ? 'Found' : 'Not found');
    console.log('Last SQL Message (executed):', lastSQLMessage ? {
      hasSQL: !!lastSQLMessage.sqlResult?.sql,
      hasExecutionResult: !!lastSQLMessage.sqlExecutionResult,
      sourceQuery: lastSQLMessage.sourceQuery
    } : 'Not found');
    console.log('Last SQL Message (generated but maybe not executed):', lastGeneratedSQLMessage ? {
      hasSQL: !!lastGeneratedSQLMessage.sqlResult?.sql,
      hasExecutionResult: !!lastGeneratedSQLMessage.sqlExecutionResult,
      sourceQuery: lastGeneratedSQLMessage.sourceQuery
    } : 'Not found');

    // Get the source query from the last executed message for comparison
    const lastExecutedQuery = lastPythonMessage?.sourceQuery || lastSQLMessage?.sourceQuery;

    // Check if we should re-visualize Python code (vs generate new code)
    const shouldRevisualizePython = chartIntent && 
      lastPythonMessage?.sqlResult?.sql && 
      lastPythonMessage?.executionResult &&
      shouldTriggerRevisualization(chartIntent, query, lastPythonMessage?.sourceQuery);

    // Check if we should re-visualize SQL execution (vs generate new SQL)
    const shouldRevisualizeSQL = chartIntent && 
      lastSQLMessage?.sqlResult?.sql && 
      lastSQLMessage?.sqlExecutionResult &&
      shouldTriggerRevisualization(chartIntent, query, lastSQLMessage?.sourceQuery);

    console.log('Should Revisualize Python:', shouldRevisualizePython);
    console.log('Should Revisualize SQL:', shouldRevisualizeSQL);
    console.log('==============================');

    if (shouldRevisualizePython && lastPythonMessage) {
      // Re-visualization: Always create a new AI message for the new chart
      const userMessage: ChatMessage = {
        id: generateMessageId(),
        type: 'user',
        content: query,
        timestamp: new Date(),
        chartTypeOverride: chartTypeOverride
      };

      setQuery('');
      setIsLoading(true);

      try {
        // Re-execute the same Python code with the new chart type override
        const sourceQuery = lastPythonMessage.sourceQuery || lastPythonMessage.content || '';
        const result = await api.executePython(
          lastPythonMessage.sqlResult!.sql,
          { user_query: sourceQuery },
          chartTypeOverride
        );

        // Create a new AI message for the new chart
        const aiMessage: ChatMessage = {
          id: generateMessageId(),
          type: 'ai',
          content: 'Here is the updated visualization:',
          timestamp: new Date(),
          sqlResult: lastPythonMessage.sqlResult,
          executionResult: result,
          queryType: 'python_code',
          sourceQuery: lastPythonMessage.sourceQuery,
          chartTypeOverride: chartTypeOverride
        };

        // Add both user message and new AI message to the chat
        const updatedMessages = [...chatHistory, userMessage, aiMessage];
        updateConversation(conversationId, { messages: updatedMessages });
        
        // Fetch summary and analysis context for new visualization (non-blocking)
        await handleExecutionComplete(aiMessage.id, result);
        
      } catch (error) {
        console.error('Re-visualization failed:', error);
        // Build helpful error message with supported chart types
        const supportedCharts = ['Bar', 'Line', 'Pie', 'Scatter', 'Column', 'Area', 'Treemap', 'Radar', 'Funnel', 'Stacked Bar', 'Stacked Column', 'Clustered Column'];
        const requestedChartLabel = chartTypeOverride ? getChartTypeLabel(chartTypeOverride) : 'the requested chart';
        const errorContent = `Sorry, I couldn't update the visualization to ${requestedChartLabel}. This may be due to incompatible data structure for this chart type.\n\n**Supported chart types:** ${supportedCharts.join(', ')}.\n\nPlease try a different chart type or ensure your data has the required columns.`;
        
        const errorMessage: ChatMessage = {
          id: generateMessageId(),
          type: 'ai',
          content: errorContent,
          timestamp: new Date()
        };
        const updatedMessages = [...chatHistory, userMessage, errorMessage];
        updateConversation(conversationId, { messages: updatedMessages });
      } finally {
        setIsLoading(false);
      }
      return;
    }

    // Handle SQL re-visualization (for executed SQL queries with results)
    if (shouldRevisualizeSQL && lastSQLMessage) {
      // Re-visualization: Always create a new AI message for the new chart
      const userMessage: ChatMessage = {
        id: generateMessageId(),
        type: 'user',
        content: query,
        timestamp: new Date(),
        chartTypeOverride: chartTypeOverride
      };

      setQuery('');
      setIsLoading(true);

      try {
        // Re-execute the same SQL query with the new chart type override
        const sourceQuery = lastSQLMessage.sourceQuery || lastSQLMessage.content || '';
        const result = await api.executeSQL(
          lastSQLMessage.sqlResult!.sql,
          { 
            user_query: sourceQuery,
            schema_context: 'Re-visualization request' 
          },
          chartTypeOverride
        );

        // Create a new AI message for the new chart
        const aiMessage: ChatMessage = {
          id: generateMessageId(),
          type: 'ai',
          content: 'Here is the updated visualization:',
          timestamp: new Date(),
          sqlResult: lastSQLMessage.sqlResult,
          sqlExecutionResult: result,
          queryType: 'database',
          sourceQuery: lastSQLMessage.sourceQuery,
          chartTypeOverride: chartTypeOverride
        };

        // Add both user message and new AI message to the chat
        const updatedMessages = [...chatHistory, userMessage, aiMessage];
        updateConversation(conversationId, { messages: updatedMessages });
        
        // Fetch summary for new visualization (non-blocking)
        await handleSQLExecutionComplete(aiMessage.id, result);
        
      } catch (error) {
        console.error('SQL re-visualization failed:', error);
        // Build helpful error message with supported chart types
        const supportedCharts = ['Bar', 'Line', 'Pie', 'Scatter', 'Column', 'Area', 'Treemap', 'Radar', 'Funnel', 'Stacked Bar', 'Stacked Column', 'Clustered Column'];
        const requestedChartLabel = chartTypeOverride ? getChartTypeLabel(chartTypeOverride) : 'the requested chart';
        const errorContent = `Sorry, I couldn't update the visualization to ${requestedChartLabel}. This may be due to incompatible data structure for this chart type.\n\n**Supported chart types:** ${supportedCharts.join(', ')}.\n\nPlease try a different chart type or ensure your data has the required columns.`;
        
        const errorMessage: ChatMessage = {
          id: generateMessageId(),
          type: 'ai',
          content: errorContent,
          timestamp: new Date()
        };
        const updatedMessages = [...chatHistory, userMessage, errorMessage];
        updateConversation(conversationId, { messages: updatedMessages });
      } finally {
        setIsLoading(false);
      }
      return;
    }

    // Handle case where SQL is generated but NOT executed - execute it with chart type override
    // This handles the scenario where user says "Convert to line chart" after generating SQL
    const isChartOnlyRequest = chartIntent && isExplicitChartOnlyPattern(query);
    if (isChartOnlyRequest && !lastSQLMessage && lastGeneratedSQLMessage) {
      // User wants a chart type change, SQL exists but hasn't been executed yet
      const userMessage: ChatMessage = {
        id: generateMessageId(),
        type: 'user',
        content: query,
        timestamp: new Date(),
        chartTypeOverride: chartTypeOverride
      };

      setQuery('');
      setIsLoading(true);

      try {
        // Execute the generated SQL with the chart type override
        const sourceQuery = lastGeneratedSQLMessage.sourceQuery || lastGeneratedSQLMessage.content || '';
        const result = await api.executeSQL(
          lastGeneratedSQLMessage.sqlResult!.sql,
          { 
            user_query: sourceQuery,
            schema_context: 'First execution with chart type override' 
          },
          chartTypeOverride
        );

        // Create a new AI message with the visualization
        const aiMessage: ChatMessage = {
          id: generateMessageId(),
          type: 'ai',
          content: `Here is the ${getChartTypeLabel(chartTypeOverride || 'line')} visualization:`,
          timestamp: new Date(),
          sqlResult: lastGeneratedSQLMessage.sqlResult,
          sqlExecutionResult: result,
          queryType: 'database',
          sourceQuery: lastGeneratedSQLMessage.sourceQuery,
          chartTypeOverride: chartTypeOverride
        };

        // Add both user message and new AI message to the chat
        const updatedMessages = [...chatHistory, userMessage, aiMessage];
        updateConversation(conversationId, { messages: updatedMessages });
        
        // Fetch summary for visualization (non-blocking)
        await handleSQLExecutionComplete(aiMessage.id, result);
        
      } catch (error) {
        console.error('SQL visualization failed:', error);
        const supportedCharts = ['Bar', 'Line', 'Pie', 'Scatter', 'Column', 'Area', 'Treemap', 'Radar', 'Funnel', 'Stacked Bar', 'Stacked Column', 'Clustered Column'];
        const requestedChartLabel = chartTypeOverride ? getChartTypeLabel(chartTypeOverride) : 'the requested chart';
        const errorContent = `Sorry, I couldn't create the ${requestedChartLabel} visualization. The SQL execution may have failed or the data structure may be incompatible.\n\n**Supported chart types:** ${supportedCharts.join(', ')}.`;
        
        const errorMessage: ChatMessage = {
          id: generateMessageId(),
          type: 'ai',
          content: errorContent,
          timestamp: new Date()
        };
        const updatedMessages = [...chatHistory, userMessage, errorMessage];
        updateConversation(conversationId, { messages: updatedMessages });
      } finally {
        setIsLoading(false);
      }
      return;
    }

    // If chart intent detected but we're NOT re-visualizing, show toast explaining why
    if (chartIntent && lastExecutedQuery) {
      const reason = getNewCodeReason(query, lastExecutedQuery);
      if (reason) {
        setToast({ message: reason, type: 'info' });
      }
    }

    const userMessage: ChatMessage = {
      id: generateMessageId(),
      type: 'user',
      content: query,
      timestamp: new Date(),
      chartTypeOverride: chartTypeOverride
    };

    // Add user message to chat history
    const currentMessages = [...chatHistory, userMessage];
    updateConversation(conversationId, { messages: currentMessages });

    // Auto-title on first message
    if (chatHistory.length === 0) {
      const title = generateInitialTitle(query);
      updateConversation(conversationId, { title });
    }

    const currentQuery = query;
    setQuery('');
    setIsLoading(true);
    setSteps([]);
    abortControllerRef.current?.abort();
    abortControllerRef.current = new AbortController();
    abortedRef.current = false;

    try {
      let result: GenerateSQLResponse;
      const tableOverride = selectedObjects.length > 0 ? selectedObjects : undefined;

      if (queryMode === 'generate-r') {
        result = await api.generateRStream(currentQuery, (status) => {
          setSteps([status]);
        }, undefined, abortControllerRef.current.signal);
        // Ensure query_type is set
        if (!result.query_type) result.query_type = 'r_code';
      } else if (queryMode === 'generate-sas') {
        result = await api.generateSASStream(currentQuery, (status) => {
          setSteps([status]);
        }, undefined, abortControllerRef.current.signal);
        if (!result.query_type) result.query_type = 'sas_code';
      } else if (queryMode === 'generate-python') {
        result = await api.generatePythonStream(currentQuery, (status) => {
          setSteps([status]);
        }, undefined, abortControllerRef.current.signal);
        if (!result.query_type) result.query_type = 'python_code';
      } else {
        // 'generate-sql' or 'search'
        // Map 'generate-sql' to 'generate' for the API compatibility
        const apiMode = queryMode === 'search' ? 'search' : 'generate';

        // Pass accumulated query history and previous SQL
        result = await api.generateSQLStream(
          currentQuery,
          (status) => {
            setSteps([status]);
          },
          undefined,
          lastGeneratedSQL || undefined,
          queryHistory || undefined,
          false,
          apiMode,
          abortControllerRef.current.signal,
          tableOverride
        );
      }

      if (result.query_type === 'search') {
        // For search mode, display the found objects
        const aiMessage: ChatMessage = {
          id: generateMessageId(),
          type: 'ai',
          content: result.explanation || 'Search completed.',
          timestamp: new Date(),
          sqlResult: result,
          queryType: 'search',
          sourceQuery: currentQuery
        };

        const updatedMessages = [...currentMessages, aiMessage];
        updateConversation(conversationId, {
          messages: updatedMessages,
        });

        // Auto-generate title for search conversations too
        if (updatedMessages.length === 4) {
          const autoTitle = await generateAutoTitle(updatedMessages, api.generateSQL);
          if (autoTitle) {
            updateConversation(conversationId, { title: autoTitle });
          }
        }
      } else if (result.query_type === 'database' || result.query_type === 'r_code' || result.query_type === 'sas_code' || result.query_type === 'python_code') {
        // For database/R/SAS/Python queries, also get discovery context for display (only for SQL really, but safe to ignore)
        let context = undefined;
        if (result.query_type === 'database') {
          context = await api.discovery(currentQuery);
        }

        // Store the generated SQL for future reference
        const newSQL = result.sql || lastGeneratedSQL;
        const newQueryHistory = result.sql ? '' : (queryHistory ? `${queryHistory}. ${currentQuery}` : currentQuery);

        // Add AI response to chat history
        const normalizedQueryType: ChatMessage['queryType'] =
          result.query_type === 'r_code' ? 'r_code'
            : result.query_type === 'sas_code' ? 'sas_code'
              : result.query_type === 'python_code' ? 'python_code'
                : result.query_type === 'database' ? 'database'
                  : 'database';

        const aiMessage: ChatMessage = {
          id: generateMessageId(),
          type: 'ai',
          content: result.explanation || (result.query_type === 'database' ?
            'Here is the query statement you need to use to query the database:' :
            `Here is the generated ${result.query_type === 'r_code' ? 'R' : result.query_type === 'sas_code' ? 'SAS' : 'Python'} code:`),
          timestamp: new Date(),
          discoveryResult: context,
          sqlResult: result,
          queryType: normalizedQueryType,
          sourceQuery: currentQuery,
          chartTypeOverride: chartTypeOverride  // Pass chart type preference from user query
        };

        const updatedMessages = [...currentMessages, aiMessage];
        updateConversation(conversationId, {
          messages: updatedMessages,
          lastGeneratedSQL: newSQL,
          queryHistory: newQueryHistory,
        });

        // Auto-generate better title after a few messages
        if (updatedMessages.length === 4) { // After 2 exchanges
          const autoTitle = await generateAutoTitle(updatedMessages, api.generateSQL);
          if (autoTitle) {
            updateConversation(conversationId, { title: autoTitle });
          }
        }
      } else if (result.query_type === 'uncertain') {
        // For uncertain queries, show clarification options
        const newQueryHistory = queryHistory ? `${queryHistory}. ${currentQuery}` : currentQuery;

        const aiMessage: ChatMessage = {
          id: generateMessageId(),
          type: 'ai',
          content: result.explanation || 'I need clarification on your query.',
          timestamp: new Date(),
          sqlResult: result,
          queryType: 'uncertain',
          sourceQuery: currentQuery,
          needsClarification: true
        };

        const updatedMessages = [...currentMessages, aiMessage];
        updateConversation(conversationId, {
          messages: updatedMessages,
          queryHistory: newQueryHistory,
        });
      } else {
        // For general queries, just show the direct answer and clear history
        const aiMessage: ChatMessage = {
          id: generateMessageId(),
          type: 'ai',
          content: result.explanation || 'I apologize, but I could not process your request.',
          timestamp: new Date(),
          sqlResult: result,
          queryType: 'general',
          sourceQuery: currentQuery
        };

        const updatedMessages = [...currentMessages, aiMessage];
        updateConversation(conversationId, {
          messages: updatedMessages,
          queryHistory: '',
        });

        // Auto-generate title for general conversations too
        if (updatedMessages.length === 4) {
          const autoTitle = await generateAutoTitle(updatedMessages, api.generateSQL);
          if (autoTitle) {
            updateConversation(conversationId, { title: autoTitle });
          }
        }
      }

    } catch (error) {
      console.error(error);
      const errorWithName = error as { name?: string };
      const errorWithResponse = error as { response?: { data?: { detail?: string } } };
      const errorWithMessage = error as { message?: string };

      if (abortedRef.current || errorWithName.name === 'AbortError') {
        const cancelMessage: ChatMessage = {
          id: generateMessageId(),
          type: 'ai',
          content: 'Request cancelled.',
          timestamp: new Date()
        };

        const updatedMessages = [...currentMessages, cancelMessage];
        updateConversation(conversationId, { messages: updatedMessages });
        return;
      }

      let errorDisplay = 'Sorry, there was an error processing your request.';
      if (errorWithResponse.response?.data?.detail) {
        errorDisplay += `\nServer Error: ${errorWithResponse.response.data.detail}`;
      } else if (errorWithMessage.message) {
        errorDisplay += `\nError: ${errorWithMessage.message}`;
      }

      // Add error message to chat history
      const errorMessage: ChatMessage = {
        id: generateMessageId(),
        type: 'ai',
        content: errorDisplay,
        timestamp: new Date()
      };

      const updatedMessages = [...currentMessages, errorMessage];
      updateConversation(conversationId, { messages: updatedMessages });
    } finally {
      setIsLoading(false);
      abortControllerRef.current = null;
    }
  };

  const handleStopGeneration = () => {
    if (!isLoading || !abortControllerRef.current) return;
    abortedRef.current = true;
    abortControllerRef.current.abort();
    setSteps([]);
  };

  const navigateToAdmin = () => {
    window.history.pushState({}, '', '/admin');
    setCurrentRoute('admin');
  };

  if (currentRoute === 'admin') {
    return (
      <ErrorBoundary>
        <AdminLayout currentPage={adminPage} onNavigate={setAdminPage} isUploading={isUploadingInAdmin}>
          {adminPage === 'schema' && <SchemaManager onUploadStateChange={setIsUploadingInAdmin} />}
          {adminPage === 'fewshot' && <FewShotManager onUploadStateChange={setIsUploadingInAdmin} />}
          {adminPage === 'contributions' && <ContributionManager onUploadStateChange={setIsUploadingInAdmin} />}
          {adminPage === 'values' && <ValueManager onUploadStateChange={setIsUploadingInAdmin} />}
          {adminPage === 'settings' && <Settings />}
        </AdminLayout>
      </ErrorBoundary>
    );
  }

  return (
    <ErrorBoundary>
      <div className="flex h-screen w-screen bg-slate-950 text-slate-200 font-sans selection:bg-indigo-500/30">
        {/* Sidebar */}
        <Sidebar
          conversations={conversations}
          activeConversationId={activeConversationId}
          onSelectConversation={handleSelectConversation}
          onNewConversation={handleNewConversation}
          onDeleteConversation={handleDeleteConversation}
          onRenameConversation={handleRenameConversation}
        />

        {/* Main Chat Area */}
        <div className="flex flex-col flex-1 h-screen">
          {/* Header */}
          <header className="border-b border-slate-800 bg-slate-900/50 backdrop-blur-md sticky top-0 z-10">
            <div className="w-full px-6 h-16 flex items-center justify-between">
              <div className="flex items-center gap-3">
                {activeConversation && (
                  <h2 className="font-semibold text-lg text-slate-200 truncate max-w-md">
                    {activeConversation.title}
                  </h2>
                )}
              </div>
              <div className="flex items-center gap-4">
                <button
                  onClick={navigateToAdmin}
                  className="flex items-center gap-2 text-sm text-slate-400 hover:text-white transition-colors px-3 py-1.5 rounded-md hover:bg-slate-800"
                >
                  <LayoutDashboard size={16} /> Admin
                </button>
                <div className="flex items-center gap-2 text-xs font-mono text-emerald-400 bg-emerald-500/10 px-3 py-1.5 rounded-full border border-emerald-500/20">
                  <div className="w-2 h-2 bg-emerald-500 rounded-full animate-pulse" />
                  SYSTEM ONLINE
                </div>
              </div>
            </div>
          </header>

          {/* Chat UI */}
          <main className="flex-1 overflow-auto py-4 px-6 scroll-smooth">
            <div className="w-full space-y-6">
              {/* Welcome/Empty State */}
              {chatHistory.length === 0 && !isLoading && (
                <div className="text-center py-16 animate-fade-in-up">
                  <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-slate-900 border border-slate-800 mb-6 shadow-xl">
                    <Sparkles className="text-purple-400" size={32} />
                  </div>
                  <h2 className="text-3xl font-bold bg-gradient-to-b from-white to-slate-500 bg-clip-text text-transparent mb-4">
                    What would you like to know?
                  </h2>
                  <p className="text-slate-400 max-w-2xl mx-auto leading-relaxed">
                    I can help you query the database using natural language. Try asking logic questions about your data.
                  </p>

                  <div className="mt-8 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 max-w-5xl mx-auto">
                    {['Which countries supply the highest‑volume or highest‑value imports?', 'Which product categories are growing the fastest year‑over‑year?', 'What is the total value of imports for each country?', 'Which product categories have the highest import values?', 'What is the total value of imports for each country?', 'Who are the top customers by revenue, volume, or order frequency?', 'Show me all users', 'Count orders by status', 'Find top selling products'].map(q => (
                      <button key={q} onClick={() => setQuery(q)} className="text-sm p-4 rounded-xl bg-slate-900 border border-slate-800 hover:border-indigo-500/50 hover:bg-slate-800 hover:text-indigo-300 transition-all text-left">
                        {q}
                      </button>
                    ))}
                  </div>
                </div>
              )}



              {/* Chat History */}
              {chatHistory.length > 0 && (
                <div className="space-y-6 animate-fade-in">
                  {chatHistory.map((message) => (
                    <div
                      key={message.id}
                      className={`flex ${message.type === 'user' ? 'justify-end' : 'justify-start'}`}
                    >
                      <div className="w-[98%]">
                        {/* Message Header */}
                        <div className={`flex items-center gap-2 mb-2 text-xs text-slate-500 ${message.type === 'user' ? 'justify-end' : 'justify-start'}`}>
                          {message.type === 'user' ? (
                            <>
                              <User size={12} />
                              <span>You</span>
                            </>
                          ) : (
                            <>
                              <Bot size={12} />
                              <span>AI Agent</span>
                            </>
                          )}
                        </div>

                        {/* Message Content */}
                        <div className={`bg-slate-900/50 border border-slate-800 rounded-xl p-5 backdrop-blur-sm ${message.type === 'user' ? 'bg-indigo-900/20 border-indigo-500/20' : 'bg-slate-900/50 border-slate-800'
                          }`}>
                          {/* User Message */}
                          {message.type === 'user' && (
                            <div className="space-y-2">
                              <p className="text-slate-200 leading-relaxed">
                                {message.content}
                              </p>
                              {/* Chart Type Updated Badge */}
                              {message.chartTypeOverride && (
                                <div className="flex items-center gap-1.5 text-emerald-400 text-xs font-medium">
                                  <CheckCircle size={14} />
                                  <span>Updated to {getChartTypeLabel(message.chartTypeOverride)}</span>
                                </div>
                              )}
                            </div>
                          )}

                          {/* AI Message */}
                          {message.type === 'ai' && (
                            <div className="space-y-4">
                              {/* Hide raw content for search results since we display formatted grid */}
                              {message.queryType !== 'search' && (
                                <p className="text-slate-200 leading-relaxed">
                                  {message.content}
                                </p>
                              )}

                              {/* Search Results Grid - Only for search queries */}
                              {message.queryType === 'search' && message.sqlResult?.explanation && (
                                <div className="mt-2">
                                  {(() => {
                                    const apiObjects = message.sqlResult.objects;
                                    const objectMatches = message.sqlResult?.explanation?.match(/\[([^\]]+)\]\.\[([^\]]+)\]/g);
                                    const schemaByName = new Map<string, string>();
                                    if (objectMatches) {
                                      objectMatches.forEach((obj) => {
                                        const match = obj.match(/\[([^\]]+)\]\.\[([^\]]+)\]/);
                                        if (match?.[1] && match?.[2]) {
                                          schemaByName.set(match[2], match[1]);
                                        }
                                      });
                                    }

                                    const parsedObjects = apiObjects && apiObjects.length > 0
                                      ? apiObjects.map((obj) => {
                                        const rawSchema = (obj as { schema?: string; schema_name?: string }).schema
                                          ?? (obj as { schema?: string; schema_name?: string }).schema_name
                                          ?? '';
                                        const normalizedSchema = typeof rawSchema === 'string' ? rawSchema.trim() : '';
                                        const normalizedName = typeof obj.name === 'string' ? obj.name.trim() : obj.name;
                                        const fallbackSchema = schemaByName.get(obj.name) ?? 'dbo';
                                        const schema = normalizedSchema || fallbackSchema;
                                        return {
                                          key: `${schema}.${normalizedName}`,
                                          schema,
                                          name: normalizedName,
                                          type: obj.type ?? null
                                        };
                                      })
                                      : (() => {
                                        // Parse objects from explanation (format: "• [schema].[table]")
                                        if (!objectMatches) return [];
                                        return objectMatches.map((obj) => {
                                          const parsed = parseObjectName(obj);
                                          const match = obj.match(/\[([^\]]+)\]\.\[([^\]]+)\]/);
                                          return {
                                            key: parsed.key,
                                            schema: match?.[1] ?? parsed.key.split('.')[0],
                                            name: match?.[2] ?? parsed.key.split('.').slice(1).join('.'),
                                            type: null
                                          };
                                        });
                                      })();

                                    if (parsedObjects.length > 0) {
                                      return (
                                        <>
                                          <div className="flex items-center gap-2 mb-3 text-sm font-medium text-emerald-400">
                                            <div className="w-2 h-2 bg-emerald-500 rounded-full"></div>
                                            The following {parsedObjects.length} database object{parsedObjects.length !== 1 ? 's' : ''} may store the data you are looking for.
                                          </div>
                                          <div className="space-y-2">
                                            {parsedObjects.map((obj, idx) => (
                                              <div
                                                key={`${obj.key}-${idx}`}
                                                className="grid grid-cols-[auto,auto,1fr] items-center gap-3 rounded-lg border border-slate-800 bg-slate-900/40 px-3 py-2"
                                              >
                                                <input
                                                  type="checkbox"
                                                  checked={selectedObjects.includes(obj.key)}
                                                  onChange={() => toggleSelectedObject(obj.key)}
                                                  className="h-4 w-4 rounded border-slate-600 bg-slate-800 text-emerald-500 focus:ring-emerald-500"
                                                  aria-label={`Select ${obj.key}`}
                                                />
                                                <ObjectTypeLabel type={obj.type} />
                                                <div className="flex items-center gap-2 text-sm text-emerald-200">
                                                  <span className="font-mono">[{obj.schema}].[{obj.name}]</span>
                                                  <button
                                                    type="button"
                                                    onClick={() => handleViewSchema(obj.key)}
                                                    className="inline-flex items-center text-slate-400 hover:text-emerald-200 transition-colors"
                                                    aria-label={`View schema for ${obj.key}`}
                                                  >
                                                    <Eye size={14} />
                                                  </button>
                                                </div>
                                              </div>
                                            ))}
                                          </div>
                                        </>
                                      );
                                    }
                                    // No objects found - show a helpful message
                                    return (
                                      <div className="flex flex-col gap-3 p-4 bg-slate-800/50 border border-amber-500/30 rounded-lg">
                                        <div className="flex items-center gap-2 text-sm font-medium text-amber-400">
                                          <div className="w-2 h-2 bg-amber-500 rounded-full"></div>
                                          No matching database objects found
                                        </div>
                                        <p className="text-sm text-slate-400">
                                          Your search didn't match any tables, views, or indexed values. Try:
                                        </p>
                                        <ul className="text-sm text-slate-400 list-disc list-inside space-y-1">
                                          <li>Using different keywords or synonyms</li>
                                          <li>Checking for typos in your search terms</li>
                                          <li>Using more general terms (e.g., "customer" instead of "customers")</li>
                                          <li>Switching to <span className="text-indigo-400 font-medium">Generate Query</span> mode to ask a question</li>
                                        </ul>
                                      </div>
                                    );
                                  })()}
                                </div>
                              )}

                              {/* Clarification Options - Only for uncertain queries */}
                              {message.needsClarification && (
                                <div className="flex gap-3 mt-4">
                                  <button
                                    onClick={() => handleClarificationChoice(message.id, 'database')}
                                    className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg transition-colors duration-200"
                                  >
                                    🔍 Search Database
                                  </button>
                                  <button
                                    onClick={() => handleClarificationChoice(message.id, 'general')}
                                    className="px-4 py-2 bg-gray-600 hover:bg-gray-700 text-white text-sm font-medium rounded-lg transition-colors duration-200"
                                  >
                                    💬 General Answer
                                  </button>
                                </div>
                              )}



                              {/* SQL Result - Only for database/code generation queries */}
                              {/* Only show chart for python_code messages generated by chart type change (re-visualization) */}
                              {message.queryType === 'python_code' && message.executionResult && message.chartTypeOverride ? (
                                <div className="relative group">
                                  <SQLResultDisplay
                                    sql={message.sqlResult?.sql || ''}
                                    sourceQuestion={message.sourceQuery}
                                    allUserMessages={chatHistory
                                      .filter(msg => msg.type === 'user')
                                      .map(msg => msg.content)
                                    }
                                    queryType={message.queryType}
                                    executionResult={message.executionResult}
                                    sqlExecutionResult={message.sqlExecutionResult}
                                    onExecutionComplete={(result) => handleExecutionComplete(message.id, result)}
                                    onSQLExecutionComplete={(result) => handleSQLExecutionComplete(message.id, result)}
                                    chartTypeOverride={message.chartTypeOverride}
                                    chartOnly={true}
                                    pythonSummary={message.pythonSummary || ''}
                                    sqlSummary={message.sqlSummary || ''}
                                  />
                                </div>
                              ) : (
                                message.sqlResult && (message.queryType === 'database' || message.queryType === 'r_code' || message.queryType === 'sas_code' || message.queryType === 'python_code') && (message.sqlResult.sql || message.sqlResult.explanation) && (
                                  <div className="relative group">
                                    {message.sqlResult.sql ? (
                                      <SQLResultDisplay
                                        sql={message.sqlResult.sql}
                                        sourceQuestion={message.sourceQuery}
                                        allUserMessages={chatHistory
                                          .filter(msg => msg.type === 'user')
                                          .map(msg => msg.content)
                                        }
                                        queryType={message.queryType}
                                        executionResult={message.executionResult}
                                        sqlExecutionResult={message.sqlExecutionResult}
                                        onExecutionComplete={(result) => handleExecutionComplete(message.id, result)}
                                        onSQLExecutionComplete={(result) => handleSQLExecutionComplete(message.id, result)}
                                        chartTypeOverride={message.chartTypeOverride}
                                        pythonSummary={message.pythonSummary || ''}
                                        sqlSummary={message.sqlSummary || ''}
                                      />
                                    ) : (
                                      // Show explanation when no SQL was generated
                                      <div className="bg-slate-900/50 border border-red-500/50 rounded-lg p-4">
                                        <div className="flex items-center gap-2 mb-2 text-sm font-semibold text-red-400">
                                          <div className="w-2 h-2 bg-red-500 rounded-full"></div> Query Generation Failed
                                        </div>
                                        <div className="text-sm text-red-300">
                                          {message.sqlResult.explanation || "Unable to generate SQL query for this request."}
                                        </div>
                                      </div>
                                    )}
                                  </div>
                                  )
                                )}

                              {/* Workflow Components - Insights, Refinement Suggestions, and Data Profile */}
                              {message.analysisContext && (
                                <div className="mt-4 space-y-3">
                                  {/* Insights Panel */}
                                  {message.analysisContext.insights && 
                                   message.analysisContext.insights.length > 0 && (
                                    <InsightsPanel insights={message.analysisContext.insights} />
                                  )}
                                  
                                  {/* Refinement Suggestions */}
                                  {message.analysisContext.suggested_refinements && 
                                   message.analysisContext.suggested_refinements.length > 0 && (
                                    <RefinementSuggestions
                                      suggestions={message.analysisContext.suggested_refinements}
                                      onSuggestionClick={handleRefinementClick}
                                    />
                                  )}
                                  
                                  {/* Data Profile Card (collapsible) */}
                                  {message.analysisContext.data_profile && (
                                    <DataProfileCard 
                                      profile={message.analysisContext.data_profile}
                                      className="mt-2"
                                    />
                                  )}
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}

                  {/* Temporary Loading Message */}
                  {isLoading && (
                    <div className="flex justify-start">
                      <div className="w-[98%]">
                        <div className="flex items-center gap-2 mb-2 text-xs text-slate-500 justify-start">
                          <Bot size={12} />
                          <span>AI Agent</span>
                        </div>
                        <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-5 backdrop-blur-sm">
                          <div className="flex items-center justify-between gap-4">
                            {steps.length > 0 ? (
                              <div className="flex items-center gap-3">
                                <Loader2 className="animate-spin text-indigo-400" size={16} />
                                <div className="text-sm text-indigo-300 font-medium">
                                  {steps[steps.length - 1].message}
                                </div>
                              </div>
                            ) : (
                              <div className="flex items-center gap-3 text-indigo-400">
                                <Loader2 className="animate-spin" size={16} />
                                <span className="font-medium tracking-wide">Starting process...</span>
                              </div>
                            )}
                            <button
                              onClick={handleStopGeneration}
                              className="inline-flex items-center gap-1.5 text-xs text-slate-300 hover:text-white bg-slate-800/60 hover:bg-slate-800 px-2.5 py-1 rounded-md border border-slate-700 transition-colors"
                            >
                              <Square size={12} />
                              Stop
                            </button>
                          </div>
                        </div>
                      </div>
                    </div>
                  )}
                  {/* Scroll target - always at bottom */}
                  <div ref={messagesEndRef} />
                </div>
              )}
            </div>
          </main>

          {/* Input Area */}
          <footer className="px-6 py-4 bg-slate-900/80 backdrop-blur border-t border-slate-800">
            <div className="w-full">
              {/* Mode Toggle - Radio Buttons */}
              <div className="flex items-center justify-center gap-6 mb-3">
                <label className="flex items-center gap-2 cursor-pointer group">
                  <input
                    type="radio"
                    name="queryMode"
                    value="generate-sql"
                    checked={queryMode === 'generate-sql'}
                    onChange={() => setQueryMode('generate-sql')}
                    className="w-4 h-4 text-indigo-600 bg-slate-800 border-slate-600 focus:ring-indigo-500 focus:ring-offset-slate-900"
                  />
                  <span className={`text-sm font-medium transition-colors ${queryMode === 'generate-sql' ? 'text-indigo-400' : 'text-slate-400 group-hover:text-slate-300'}`}>
                    ✨ Generate SQL
                  </span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer group">
                  <input
                    type="radio"
                    name="queryMode"
                    value="generate-r"
                    checked={queryMode === 'generate-r'}
                    onChange={() => setQueryMode('generate-r')}
                    className="w-4 h-4 text-orange-600 bg-slate-800 border-slate-600 focus:ring-orange-500 focus:ring-offset-slate-900"
                  />
                  <span className={`text-sm font-medium transition-colors ${queryMode === 'generate-r' ? 'text-orange-400' : 'text-slate-400 group-hover:text-slate-300'}`}>
                    📈 Generate R
                  </span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer group">
                  <input
                    type="radio"
                    name="queryMode"
                    value="generate-sas"
                    checked={queryMode === 'generate-sas'}
                    onChange={() => setQueryMode('generate-sas')}
                    className="w-4 h-4 text-blue-600 bg-slate-800 border-slate-600 focus:ring-blue-500 focus:ring-offset-slate-900"
                  />
                  <span className={`text-sm font-medium transition-colors ${queryMode === 'generate-sas' ? 'text-blue-400' : 'text-slate-400 group-hover:text-slate-300'}`}>
                    📊 Generate SAS
                  </span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer group">
                  <input
                    type="radio"
                    name="queryMode"
                    value="generate-python"
                    checked={queryMode === 'generate-python'}
                    onChange={() => setQueryMode('generate-python')}
                    className="w-4 h-4 text-yellow-500 bg-slate-800 border-slate-600 focus:ring-yellow-400 focus:ring-offset-slate-900"
                  />
                  <span className={`text-sm font-medium transition-colors ${queryMode === 'generate-python' ? 'text-yellow-400' : 'text-slate-400 group-hover:text-slate-300'}`}>
                    🐍 Generate Python
                  </span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer group">
                  <input
                    type="radio"
                    name="queryMode"
                    value="search"
                    checked={queryMode === 'search'}
                    onChange={() => setQueryMode('search')}
                    className="w-4 h-4 text-emerald-600 bg-slate-800 border-slate-600 focus:ring-emerald-500 focus:ring-offset-slate-900"
                  />
                  <span className={`text-sm font-medium transition-colors ${queryMode === 'search' ? 'text-emerald-400' : 'text-slate-400 group-hover:text-slate-300'}`}>
                    🔍 Search Objects
                  </span>
                </label>
              </div>

              {selectedObjects.length > 0 && (
                <div className="mb-3 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-200">
                  Context locked in. I’ll use these {selectedObjects.length} object{selectedObjects.length !== 1 ? 's' : ''} for the next step. What would you like me to generate?
                </div>
              )}

              <div className="relative group">
                <div className={`absolute -inset-0.5 bg-gradient-to-r ${queryMode === 'search' ? 'from-emerald-500 to-teal-600' : 'from-indigo-500 to-purple-600'} rounded-xl opacity-30 blur group-hover:opacity-50 transition duration-500`}></div>
                <div className={`relative flex items-end bg-slate-950 rounded-xl p-1 shadow-2xl ring-1 ring-slate-800 ${queryMode === 'search' ? 'focus-within:ring-emerald-500/50' : 'focus-within:ring-indigo-500/50'} transition-all`}>
                  <textarea
                    ref={textareaRef}
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && !e.shiftKey && !e.ctrlKey) {
                        e.preventDefault();
                        handleSend();
                      }
                    }}
                    placeholder={queryMode === 'search' ? 'Search for tables, columns, or values...' : 'Ask a question about your data (SQL, R, SAS, or Python)...'}
                    disabled={isLoading}
                    rows={1}
                    className="flex-1 bg-transparent border-none text-slate-200 placeholder-slate-500 px-4 py-3 focus:outline-none focus:ring-0 text-base resize-none overflow-y-auto min-h-[48px]"
                  />
                  <button
                    onClick={handleSend}
                    disabled={isLoading || !query.trim()}
                    className={`p-3 mb-0.5 ${queryMode === 'search' ? 'bg-emerald-600 hover:bg-emerald-500 shadow-emerald-500/20' : 'bg-indigo-600 hover:bg-indigo-500 shadow-indigo-500/20'} text-white rounded-lg transition-all disabled:opacity-50 shadow-lg`}
                  >
                    {isLoading ? <Loader2 className="animate-spin" size={20} /> : <Send size={20} />}
                  </button>
                </div>
              </div>
              {isLoading && (
                <div className="hidden"></div>
              )}
              <div className="text-center mt-3 text-xs text-slate-600">
                Powered by Retrieval Augmented Generation (RAG)
              </div>
            </div>
          </footer>
          {isSchemaModalOpen && (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 px-4">
              <div className="w-full max-w-3xl bg-slate-950 border border-slate-800 rounded-2xl shadow-2xl p-6 space-y-4">
                <div className="flex items-start justify-between">
                  <div>
                    <p className="text-xs uppercase tracking-[0.2em] text-slate-500 mb-1">Schema Preview</p>
                    <h3 className="text-xl font-semibold text-white">
                      {schemaPreviewName || 'Selected Schema'}
                    </h3>
                  </div>
                  <button
                    onClick={handleCloseSchemaPreview}
                    className="text-slate-400 hover:text-white transition-colors"
                    aria-label="Close schema preview"
                  >
                    <X size={20} />
                  </button>
                </div>

                <div className="max-h-[60vh] overflow-y-auto rounded-lg border border-slate-800 bg-slate-900/40 p-4 text-sm text-slate-200">
                  {isSchemaPreviewLoading ? (
                    <div className="flex items-center gap-2 text-slate-400">
                      <Loader2 className="animate-spin" size={16} />
                      Loading schema...
                    </div>
                  ) : schemaPreviewError ? (
                    <div className="text-red-300">{schemaPreviewError}</div>
                  ) : (
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm]}
                      className="prose prose-invert max-w-none"
                      components={{
                        table: ({ children }) => (
                          <table className="w-full border-collapse border border-slate-800">{children}</table>
                        ),
                        th: ({ children }) => (
                          <th className="border border-slate-800 px-3 py-2 text-left text-xs font-semibold text-slate-200">
                            {children}
                          </th>
                        ),
                        td: ({ children }) => (
                          <td className="border border-slate-800 px-3 py-2 text-xs text-slate-200">
                            {children}
                          </td>
                        ),
                      }}
                    >
                      {schemaPreviewMarkdown}
                    </ReactMarkdown>
                  )}
                </div>
              </div>
            </div>
          )}
          {toast && (
            <Toast
              message={toast.message}
              type={toast.type}
              onClose={() => setToast(null)}
            />
          )}
        </div>
      </div>
    </ErrorBoundary>
  );
}

export default App;
