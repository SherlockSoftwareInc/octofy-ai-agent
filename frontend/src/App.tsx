import { useState, useEffect, useRef } from 'react';
import { Send, Loader2, Sparkles, LayoutDashboard, User, Bot, Square, Eye, X, FileText, RotateCcw, Edit } from 'lucide-react';
import { api, generatePlanningSummary } from './api/client';
import type { GenerateSQLResponse, AgentStatus, ExecutePythonResponse, ExecuteSQLResponse } from './api/client';
import { SQLResultDisplay } from './components/SQL/SQLResultDisplay';
import { AdminLayout } from './pages/Admin/AdminLayout';
import { SchemaManager } from './pages/Admin/SchemaManager';
import { FewShotManager } from './pages/Admin/FewShotManager';
import { ValueManager } from './pages/Admin/ValueManager';
import { ContributionManager } from './pages/Admin/ContributionManager';
import { Settings } from './pages/Admin/Settings';
import { DataSourcesManager } from './pages/Admin/DataSourcesManager';
import { UserManager } from './pages/Admin/UserManager';
import { Toast } from './components/Toast';
import type { ToastType } from './components/Toast';
import { ErrorBoundary } from './components/ErrorBoundary';
import { Sidebar } from './components/Sidebar/Sidebar';
import { ObjectTypeLabel } from './components/ObjectTypeLabel';
import type { Conversation, ChatMessage } from './types/conversation';
import { InsightsPanel } from './components/InsightsPanel';
import { RefinementSuggestions } from './components/RefinementSuggestions';
import { DataProfileCard } from './components/DataProfileCard';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import {
  conversationStorage,
  generateConversationId,
  generateMessageId,
  generateInitialTitle,
  generateAutoTitle
} from './utils/conversationStorage';
import { useAuth } from './contexts/AuthContext';
import { Login } from './pages/Login';
import { UserProfile } from './components/UserProfile';
import { ProtectedRoute } from './components/ProtectedRoute';

function App() {
  const { isAuthenticated, isLoading } = useAuth();
  const [showProfileModal, setShowProfileModal] = useState(false);

  // Show login page if not authenticated
  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <Loader2 className="w-8 h-8 animate-spin text-purple-600 mx-auto mb-4" />
          <p className="text-gray-600">Loading...</p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Login />;
  }

  return (
    <ProtectedRoute>
      <AuthenticatedApp 
        showProfileModal={showProfileModal}
        setShowProfileModal={setShowProfileModal}
      />
    </ProtectedRoute>
  );
}

// Separate component for authenticated app to keep state management clean
function AuthenticatedApp({ 
  showProfileModal, 
  setShowProfileModal 
}: { 
  showProfileModal: boolean; 
  setShowProfileModal: (show: boolean) => void;
}) {
  const { user } = useAuth();
  
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
  const [queryMode, setQueryMode] = useState<'plan' | 'generate-sql' | 'generate-r' | 'generate-sas' | 'generate-python' | 'code-advisor'>('plan');
  const [toast, setToast] = useState<{ message: string; type: ToastType } | null>(null);
  const [steps, setSteps] = useState<AgentStatus[]>([]);
  const abortControllerRef = useRef<AbortController | null>(null);
  const abortedRef = useRef(false);
  const [selectedObjects, setSelectedObjects] = useState<string[]>([]);
  const [planningContext, setPlanningContext] = useState<Record<string, unknown> | null>(null);
  const [planningSummary, setPlanningSummary] = useState<string | null>(null);
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

    console.log('=== LOADING CONVERSATIONS FROM STORAGE ===');
    console.log('Loaded conversations:', loadedConversations.length);
    if (loadedConversations.length > 0) {
      const firstConv = loadedConversations[0];
      console.log('First conversation messages:', firstConv.messages.length);

      // Check for messages with sqlExecutionResult
      const messagesWithSQLExecution = firstConv.messages.filter(msg => msg.sqlExecutionResult);
      console.log('Messages with sqlExecutionResult:', messagesWithSQLExecution.length);
      if (messagesWithSQLExecution.length > 0) {
        console.log('Sample message with SQL execution:', {
          id: messagesWithSQLExecution[0].id,
          hasResult: !!messagesWithSQLExecution[0].sqlExecutionResult,
          resultKeys: Object.keys(messagesWithSQLExecution[0].sqlExecutionResult || {})
        });
      }
    }
    console.log('==========================================');

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
      console.log('=== SAVING CONVERSATIONS TO STORAGE ===');
      const messagesWithSQLExecution = conversations.flatMap(c =>
        c.messages.filter(m => m.sqlExecutionResult)
      );
      console.log('Total messages with sqlExecutionResult:', messagesWithSQLExecution.length);
      if (messagesWithSQLExecution.length > 0) {
        console.log('Sample message being saved:', {
          id: messagesWithSQLExecution[0].id,
          hasResult: !!messagesWithSQLExecution[0].sqlExecutionResult,
          resultKeys: Object.keys(messagesWithSQLExecution[0].sqlExecutionResult || {})
        });
      }
      console.log('=======================================');

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
      setPlanningContext(activeConversation.planningContext || null);
      setPlanningSummary(activeConversation.planningSummary || null);
    } else {
      setSelectedObjects([]);
      setPlanningContext(null);
      setPlanningSummary(null);
    }
  }, [activeConversationId, activeConversation]);

  // Auto-scroll to bottom when conversation changes or new messages arrive
  // Track message count to only scroll on new messages, not on message updates
  const messageCountRef = useRef(0);
  useEffect(() => {
    const currentMessageCount = activeConversation?.messages.length || 0;
    // Only scroll if message count increased (new message) or conversation changed
    if (currentMessageCount > messageCountRef.current || messageCountRef.current === 0) {
      if (messagesEndRef.current) {
        messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
      }
    }
    messageCountRef.current = currentMessageCount;
  }, [activeConversationId, activeConversation?.messages.length]);

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`;
    }
  }, [query]);

  // Auto-generate planning summary when switching from plan mode to code generation
  useEffect(() => {
    const generateSummary = async () => {
      if (
        queryMode !== 'plan' &&  // Switched away from plan mode
        planningContext &&  // Have planning context
        !planningSummary &&  // Summary not yet generated
        activeConversationId
      ) {
        try {
          // Call backend to generate summary
          const summaryResponse = await generatePlanningSummary(planningContext);
          setPlanningSummary(summaryResponse.summary);

          // Add summary as AI message
          const summaryMessage: ChatMessage = {
            id: generateMessageId(),
            role: 'assistant',
            type: 'ai',
            content: summaryResponse.summary,
            timestamp: new Date(),
            queryType: 'planning_summary',
            sqlResult: {
              sql: '',
              explanation: summaryResponse.summary,
              query_type: 'planning_summary',
              objects: []
            }
          };

          const currentMessages = activeConversation?.messages || [];
          setConversations(prev =>
            prev.map(conv =>
              conv.id === activeConversationId
                ? { ...conv, messages: [...currentMessages, summaryMessage], planningSummary: summaryResponse.summary, lastModified: new Date().toISOString() }
                : conv
            )
          );

          // Set focus to textarea after planning summary is generated
          setTimeout(() => textareaRef.current?.focus(), 100);

        } catch (error) {
          console.error('Failed to generate planning summary:', error);
        }
      }
    };

    generateSummary();
  }, [queryMode, planningContext, planningSummary, activeConversationId, activeConversation?.messages]);

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
        setTimeout(() => textareaRef.current?.focus(), 0);
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
        setTimeout(() => textareaRef.current?.focus(), 0);
      }
    }
  };

  // Handle execution result updates
  const handleExecutionComplete = async (
    messageId: string,
    result: ExecutePythonResponse
  ) => {
    if (!activeConversationId) return;
    // Use functional update to ensure we work with the latest state
    setConversations(prevConversations => {
      return prevConversations.map(conv => {
        if (conv.id !== activeConversationId) return conv;

        const messages = conv.messages;
        const msgToUpdate = messages.find(msg => msg.id === messageId);

        if (!msgToUpdate) {
          // If message not found, fallback to just updating the execution result on the matching ID
          // This handles race conditions where the message might have been added but we can't find it for some reason
          const updatedMessages = messages.map(msg =>
            msg.id === messageId ? { ...msg, executionResult: result } : msg
          );
          return { ...conv, messages: updatedMessages };
        }

        // Calculate analysis context - DISABLED: Now on-demand via UI buttons
        // let analysisContext: AnalysisContext | undefined;
        // if (result.data_profile || result.insights) {
        //   analysisContext = {
        //     data_profile: result.data_profile,
        //     insights: result.insights || [],
        //     refinement_history: msgToUpdate.analysisContext?.refinement_history || [],
        //     suggested_refinements: result.suggested_refinements || []
        //   };
        // }

        const updatedMessages = messages.map(msg =>
          msg.id === messageId ? {
            ...msg,
            executionResult: result,
            // analysisContext: analysisContext  // Removed: now populated on-demand
          } : msg
        );

        return { ...conv, messages: updatedMessages };
      });
    });

    // Log for debugging
    console.log('✅ Code execution result added to message:', {
      messageId,
      hasExecutionResult: !!result,
      hasResults: !!result.results
    });

    // Note: AI Summary is now on-demand via UI buttons in SQLResultDisplay component
  };

  const handleSQLExecutionComplete = async (
    messageId: string,
    result: ExecuteSQLResponse
  ) => {
    if (!activeConversationId) return;
    // Use functional update to ensure we work with the latest state
    setConversations(prevConversations => {
      return prevConversations.map(conv => {
        if (conv.id !== activeConversationId) return conv;

        const messages = conv.messages;
        const msgToUpdate = messages.find(msg => msg.id === messageId);

        if (!msgToUpdate) {
          const updatedMessages = messages.map(msg =>
            msg.id === messageId ? { ...msg, sqlExecutionResult: result } : msg
          );
          return { ...conv, messages: updatedMessages };
        }

        // Calculate analysis context - DISABLED: Now on-demand via UI buttons
        // let analysisContext: AnalysisContext | undefined;
        // if (result.data_profile || result.insights) {
        //   analysisContext = {
        //     data_profile: result.data_profile,
        //     insights: result.insights || [],
        //     refinement_history: msgToUpdate.analysisContext?.refinement_history || [],
        //     suggested_refinements: []
        //   };
        // }

        const updatedMessages = messages.map(msg =>
          msg.id === messageId ? {
            ...msg,
            sqlExecutionResult: result,
            // analysisContext: analysisContext  // Removed: now populated on-demand
          } : msg
        );

        return { ...conv, messages: updatedMessages };
      });
    });

    console.log('✅ SQL execution result added to message:', {
      messageId,
      hasSQLExecutionResult: !!result,
      hasResults: !!result.results
    });

    // Note: AI Summary is now on-demand via UI buttons in SQLResultDisplay component
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

      // Update planning context if in plan mode
      if (queryMode === 'plan' && planningContext) {
        const updatedContext = {
          ...planningContext,
          selected_tables: nextSelected
        };
        setPlanningContext(updatedContext);
        updateConversation(activeConversationId, {
          selectedObjects: nextSelected,
          planningContext: updatedContext
        });
      } else {
        updateConversation(activeConversationId, { selectedObjects: nextSelected });
      }

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
    // Allow sending if:
    // 1. Query has content, OR
    // 2. We have a planning summary in non-plan mode, OR
    // 3. We're in plan mode and user has selected tables (table selection submission)
    const hasSelectedTables = selectedObjects.length > 0;
    const canSubmit = query.trim() || 
                      (planningSummary && queryMode !== 'plan') ||
                      (queryMode === 'plan' && hasSelectedTables);
    
    if (!canSubmit) return;

    // Create new conversation if none exists
    let conversationId = activeConversationId;
    if (!conversationId) {
      const newConv = handleNewConversation();
      conversationId = newConv.id;
    }

    if (!conversationId) return;

    // Determine user message content - use auto-generate indicator if no query but planning summary exists
    const userMessageContent = query.trim()
      ? query
      : (planningSummary ? '✨ Auto-generate from planning summary' : '');

    const userMessage: ChatMessage = {
      id: generateMessageId(),
      role: 'user',
      type: 'user',
      content: userMessageContent,
      timestamp: new Date()
    };

    // Add user message to chat history
    const currentMessages = [...chatHistory, userMessage];
    updateConversation(conversationId, { messages: currentMessages });

    // Auto-title on first message
    if (chatHistory.length === 0) {
      const title = generateInitialTitle(query || 'Auto-generated query');
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

      // NEW: Handle plan mode
      if (queryMode === 'plan') {
        result = await api.generateSQLStream(
          currentQuery,
          (status) => setSteps([status]),
          undefined,
          undefined,
          undefined,
          false,
          'plan',
          abortControllerRef.current.signal,
          undefined,
          planningContext,
          selectedObjects.length > 0 ? selectedObjects : undefined  // Pass selected tables for table selection submissions
        );

        // Update planning context from response
        if (result.context_text) {
          try {
            const updatedContext = JSON.parse(result.context_text);
            setPlanningContext(updatedContext);

            // Update conversation
            updateConversation(conversationId, {
              planningContext: updatedContext
            });
          } catch (e) {
            console.error('Failed to parse planning context:', e);
          }
        }

        // Handle AI response
        const aiMessage: ChatMessage = {
          id: generateMessageId(),
          role: 'assistant',
          type: 'ai',
          content: result.explanation || 'Planning conversation continued.',
          timestamp: new Date(),
          sqlResult: result,
          queryType: 'plan',
          sourceQuery: currentQuery
        };

        updateConversation(conversationId, {
          messages: [...currentMessages, aiMessage],
        });

      } else if (queryMode === 'generate-r') {
        // Use summary as prompt if available
        let queryToSend = currentQuery;
        if (planningSummary && !currentQuery.trim()) {
          queryToSend = planningSummary;
        } else if (planningSummary && currentQuery.trim()) {
          queryToSend = `${planningSummary}\n\nAdditional requirements:\n${currentQuery}`;
        }

        result = await api.generateRStream(queryToSend, (status) => {
          setSteps([status]);
        }, undefined, abortControllerRef.current.signal);
        // Ensure query_type is set
        if (!result.query_type) result.query_type = 'r_code';
      } else if (queryMode === 'generate-sas') {
        // Use summary as prompt if available
        let queryToSend = currentQuery;
        if (planningSummary && !currentQuery.trim()) {
          queryToSend = planningSummary;
        } else if (planningSummary && currentQuery.trim()) {
          queryToSend = `${planningSummary}\n\nAdditional requirements:\n${currentQuery}`;
        }

        result = await api.generateSASStream(queryToSend, (status) => {
          setSteps([status]);
        }, undefined, abortControllerRef.current.signal);
        if (!result.query_type) result.query_type = 'sas_code';
      } else if (queryMode === 'generate-python') {
        // Use summary as prompt if available
        let queryToSend = currentQuery;
        if (planningSummary && !currentQuery.trim()) {
          queryToSend = planningSummary;
        } else if (planningSummary && currentQuery.trim()) {
          queryToSend = `${planningSummary}\n\nAdditional requirements:\n${currentQuery}`;
        }

        result = await api.generatePythonStream(queryToSend, (status) => {
          setSteps([status]);
        }, undefined, abortControllerRef.current.signal);
        if (!result.query_type) result.query_type = 'python_code';
      } else if (queryMode === 'code-advisor') {
        // Code Advisor mode - pass conversation history for follow-up questions
        const queryHistory = chatHistory
          .map(msg => `${msg.type === 'user' ? 'User' : 'AI'}: ${msg.content}`)
          .join('\n');

        result = await api.generateCodeAdvisorStream(
          currentQuery,
          (status) => setSteps([status]),
          abortControllerRef.current.signal,
          queryHistory
        );
        if (!result.query_type) result.query_type = 'code_advisor';
      } else {
        // 'generate-sql' mode
        // Use summary as prompt if available
        let queryToSend = currentQuery;
        if (planningSummary && !currentQuery.trim()) {
          queryToSend = planningSummary;
        } else if (planningSummary && currentQuery.trim()) {
          queryToSend = `${planningSummary}\n\nAdditional requirements:\n${currentQuery}`;
        }

        // Pass accumulated query history and previous SQL
        result = await api.generateSQLStream(
          queryToSend,
          (status) => {
            setSteps([status]);
          },
          undefined,
          lastGeneratedSQL || undefined,
          queryHistory || undefined,
          false,
          'generate',
          abortControllerRef.current.signal,
          tableOverride
        );
      }

      if (result.query_type === 'plan') {
        // Already handled above - do nothing more
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
          role: 'assistant',
          type: 'ai',
          content: result.explanation || (result.query_type === 'database' ?
            'Here is the query statement you need to use to query the database:' :
            `Here is the generated ${result.query_type === 'r_code' ? 'R' : result.query_type === 'sas_code' ? 'SAS' : 'Python'} code:`),
          timestamp: new Date(),
          discoveryResult: context,
          sqlResult: result,
          queryType: normalizedQueryType,
          sourceQuery: currentQuery
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
      } else if (result.query_type === 'code_advisor') {
        // Code Advisor response - display advice with code
        const aiMessage: ChatMessage = {
          id: generateMessageId(),
          role: 'assistant',
          type: 'ai',
          content: result.explanation || 'Here is my code advice:',
          timestamp: new Date(),
          sqlResult: result,
          queryType: 'code_advisor',
          sourceQuery: currentQuery
        };

        const updatedMessages = [...currentMessages, aiMessage];
        updateConversation(conversationId, {
          messages: updatedMessages,
        });

        // Auto-generate title if needed
        if (updatedMessages.length === 4) {
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
          role: 'assistant',
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
          role: 'assistant',
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
          role: 'assistant',
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
        role: 'assistant',
        type: 'ai',
        content: errorDisplay,
        timestamp: new Date()
      };

      const updatedMessages = [...currentMessages, errorMessage];
      updateConversation(conversationId, { messages: updatedMessages });
    } finally {
      setIsLoading(false);
      abortControllerRef.current = null;
      setTimeout(() => textareaRef.current?.focus(), 0);
    }
  };

  const handleStopGeneration = () => {
    if (!isLoading || !abortControllerRef.current) return;
    abortedRef.current = true;
    abortControllerRef.current.abort();
    setSteps([]);
    // Set focus back to textarea after stopping generation
    setTimeout(() => textareaRef.current?.focus(), 0);
  };

  const navigateToAdmin = () => {
    // Only allow admin users to navigate to admin panel
    if (user?.role !== 'admin') {
      return;
    }
    window.history.pushState({}, '', '/admin');
    setCurrentRoute('admin');
  };

  // Redirect non-admin users away from admin route
  useEffect(() => {
    if (currentRoute === 'admin' && user?.role !== 'admin') {
      window.history.pushState({}, '', '/');
      setCurrentRoute('chat');
    }
  }, [currentRoute, user]);

  if (currentRoute === 'admin' && user?.role === 'admin') {
    return (
      <ErrorBoundary>
        <AdminLayout currentPage={adminPage} onNavigate={setAdminPage} isUploading={isUploadingInAdmin}>
          {adminPage === 'sources' && <DataSourcesManager />}
          {adminPage === 'schema' && <SchemaManager onUploadStateChange={setIsUploadingInAdmin} />}
          {adminPage === 'fewshot' && <FewShotManager onUploadStateChange={setIsUploadingInAdmin} />}
          {adminPage === 'contributions' && <ContributionManager onUploadStateChange={setIsUploadingInAdmin} />}
          {adminPage === 'values' && <ValueManager onUploadStateChange={setIsUploadingInAdmin} />}
          {adminPage === 'users' && <UserManager />}
          {adminPage === 'settings' && <Settings />}
        </AdminLayout>
      </ErrorBoundary>
    );
  }

  return (
    <ErrorBoundary>
      <div className="flex h-screen w-screen bg-slate-950 text-slate-200 font-sans selection:bg-indigo-500/30 overflow-hidden">
        {/* Sidebar */}
        <Sidebar
          conversations={conversations}
          activeConversationId={activeConversationId}
          onSelectConversation={handleSelectConversation}
          onNewConversation={handleNewConversation}
          onDeleteConversation={handleDeleteConversation}
          onRenameConversation={handleRenameConversation}
          onOpenProfile={() => setShowProfileModal(true)}
        />

        {/* Main Chat Area */}
        <div className="flex flex-col flex-1 h-screen min-w-0 overflow-x-auto">
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
                {user?.role === 'admin' && (
                  <button
                    onClick={navigateToAdmin}
                    className="flex items-center gap-2 text-sm text-slate-400 hover:text-white transition-colors px-3 py-1.5 rounded-md hover:bg-slate-800"
                  >
                    <LayoutDashboard size={16} /> Admin
                  </button>
                )}
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
                    {['What was the total revenue generated by each product category in 1997?',
                      'Which customer orders had a total amount exceeding the average order value?',
                      'What is the quarterly breakdown of sales subtotals based on shipping dates?',
                      'Which products are currently active and "federated" across our systems?',
                      'Which products have been discontinued, and what are their details?',
                      'Which products have a unit price that is higher than the average price of all products?',
                      'How many customers are associated with each specific demographic category?',
                      'Can we get a list of all business contacts (customers and suppliers) grouped by the city they are located in?',
                      'What are the primary contact details (name, phone, type) for our base company contacts?',
                      'What is the departmental hierarchy, and who are the managers for each department?',
                      'Which employees are assigned to which specific sales territories?',
                      'What are the geographical regions covered by our sales territories?',
                      'Can we see a list of employees including their supplementary info like photo paths and extensions?',
                      'Which suppliers provide products for our "Active" product list?',
	                    'Find top selling products'].map(q => (
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
                              <p className="text-slate-200 leading-relaxed whitespace-pre-wrap break-words">
                                {message.content}
                              </p>
                            </div>
                          )}

                          {/* AI Message */}
                          {message.type === 'ai' && (
                            <div className="space-y-4">
                              {/* Hide raw content for search results and code advisor since we display formatted content */}
                              {message.queryType !== 'search' && message.queryType !== 'code_advisor' && (
                                <div className="prose prose-invert max-w-none">
                                  {(() => {
                                    // Pre-process content to extract code blocks
                                    const content = message.content;
                                    // Debug: Log raw content
                                    console.log('=== DEBUG: Raw content ===');
                                    console.log('Content length:', content.length);
                                    console.log('First 200 chars:', content.substring(0, 200));
                                    console.log('Contains ```:', content.includes('```'));
                                    
                                    // More flexible regex: allow optional whitespace after language identifier
                                    const codeBlockRegex = /```(\w+)?[\s\n]*([\s\S]*?)```/g;
                                    const parts: Array<{ type: 'text' | 'code'; content: string; language?: string }> = [];
                                    let lastIndex = 0;
                                    let match;

                                    while ((match = codeBlockRegex.exec(content)) !== null) {
                                      console.log('=== Found code block ===');
                                      console.log('Language:', match[1]);
                                      console.log('Code preview:', match[2]?.substring(0, 100));
                                      // Add text before code block
                                      if (match.index > lastIndex) {
                                        parts.push({
                                          type: 'text',
                                          content: content.substring(lastIndex, match.index)
                                        });
                                      }
                                      
                                      // Add code block
                                      parts.push({
                                        type: 'code',
                                        content: match[2],
                                        language: match[1] || 'text'
                                      });
                                      
                                      lastIndex = match.index + match[0].length;
                                    }
                                    
                                    // Add remaining text
                                    if (lastIndex < content.length) {
                                      parts.push({
                                        type: 'text',
                                        content: content.substring(lastIndex)
                                      });
                                    }

                                    return (
                                      <>
                                        {parts.map((part, idx) => {
                                          if (part.type === 'code') {
                                            return (
                                              <div key={idx} className="my-4 rounded-xl border border-slate-700 bg-slate-900 overflow-hidden">
                                                <div className="flex items-center justify-between px-4 py-2 border-b border-slate-700 bg-slate-800/50">
                                                  <div className="flex items-center gap-2">
                                                    <div className="w-2 h-2 rounded-full bg-emerald-500"></div>
                                                    <span className="text-xs font-semibold text-slate-300 tracking-wider uppercase">
                                                      {part.language?.toUpperCase() || 'CODE'}
                                                    </span>
                                                  </div>
                                                  <button
                                                    onClick={() => {
                                                      navigator.clipboard.writeText(part.content);
                                                      setToast({ message: 'Code copied to clipboard!', type: 'success' });
                                                    }}
                                                    className="flex items-center gap-1.5 px-3 py-1 text-xs text-slate-300 hover:text-white bg-slate-700 hover:bg-slate-600 rounded-md transition-colors"
                                                  >
                                                    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-1M8 5a2 2 0 002 2h2a2 2 0 002-2M8 5a2 2 0 012-2h2a2 2 0 012 2m0 0h2a2 2 0 012 2v3m2 4H10m0 0l3-3m-3 3l3 3" />
                                                    </svg>
                                                    Copy
                                                  </button>
                                                </div>
                                                <div className="text-sm">
                                                  <SyntaxHighlighter
                                                    language={part.language || 'text'}
                                                    style={vscDarkPlus}
                                                    customStyle={{ margin: 0, padding: '1rem', background: 'transparent' }}
                                                  >
                                                    {part.content}
                                                  </SyntaxHighlighter>
                                                </div>
                                              </div>
                                            );
                                          } else {
                                            // Render text parts with ReactMarkdown (excluding code blocks)
                                            return (
                                              <ReactMarkdown
                                                key={idx}
                                                remarkPlugins={[remarkGfm]}
                                                components={{
                                                  code({ children }: React.ComponentPropsWithoutRef<'code'>) {
                                                    // Render inline code as plain text
                                                    return <span>{children}</span>;
                                                  },
                                                  h1: ({ children }) => <h1 className="text-2xl font-bold text-slate-100 mt-6 mb-4">{children}</h1>,
                                                  h2: ({ children }) => <h2 className="text-lg font-semibold text-slate-100 mt-6 mb-3 border-b border-slate-700 pb-1">{children}</h2>,
                                                  h3: ({ children }) => <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-400 mt-5 mb-2">{children}</h3>,
                                                  p: ({ children }) => <p className="text-slate-200 leading-relaxed mb-4">{children}</p>,
                                                  ul: ({ children }) => <ul className="list-disc list-inside space-y-1 text-slate-200 mb-4">{children}</ul>,
                                                  ol: ({ children }) => <ol className="list-decimal list-inside space-y-1 text-slate-200 mb-4">{children}</ol>,
                                                  blockquote: ({ children }) => <blockquote className="border-l-4 border-indigo-500/60 pl-4 text-slate-300 italic my-4">{children}</blockquote>,
                                                  table: ({ children }) => <table className="w-full border-collapse border border-slate-700 my-4">{children}</table>,
                                                  th: ({ children }) => <th className="border border-slate-700 px-3 py-2 bg-slate-800 text-left text-xs font-semibold text-slate-200">{children}</th>,
                                                  td: ({ children }) => <td className="border border-slate-700 px-3 py-2 text-xs text-slate-200">{children}</td>,
                                                }}
                                              >
                                                {part.content}
                                              </ReactMarkdown>
                                            );
                                          }
                                        })}
                                      </>
                                    );
                                  })()}
                                </div>
                              )}

                              {/* Plan Mode and Search Results Grid */}
                              {(message.queryType === 'plan' || message.queryType === 'search') && message.sqlResult?.explanation && (
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
                                          type: obj.type ?? null,
                                          autoChecked: (obj as { auto_checked?: boolean }).auto_checked || false
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
                                            type: null,
                                            autoChecked: false
                                          };
                                        });
                                      })();

                                    if (parsedObjects.length > 0) {
                                      const themeColor = message.queryType === 'plan' ? 'amber' : 'emerald';
                                      const hasAutoChecked = parsedObjects.some(obj => obj.autoChecked);

                                      return (
                                        <>
                                          {hasAutoChecked && (
                                            <div className={`mb-2 text-xs text-${themeColor}-300 italic`}>
                                              ✨ Essential tables have been pre-selected. You can adjust the selection below.
                                            </div>
                                          )}
                                          <div className={`flex items-center gap-2 mb-3 text-sm font-medium text-${themeColor}-400`}>
                                            <div className={`w-2 h-2 bg-${themeColor}-500 rounded-full`}></div>
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
                                                  className={`h-4 w-4 rounded border-slate-600 bg-slate-800 text-${themeColor}-500 focus:ring-${themeColor}-500 ${obj.autoChecked ? `border-${themeColor}-400` : ''}`}
                                                  aria-label={`Select ${obj.key}`}
                                                />
                                                <ObjectTypeLabel type={obj.type} />
                                                <div className={`flex items-center gap-2 text-sm text-${themeColor}-200`}>
                                                  <span className="font-mono">[{obj.schema}].[{obj.name}]</span>
                                                  {obj.autoChecked && (
                                                    <span className={`ml-2 text-xs text-${themeColor}-400`}>
                                                      (Essential)
                                                    </span>
                                                  )}
                                                  <button
                                                    type="button"
                                                    onClick={() => handleViewSchema(obj.key)}
                                                    className={`inline-flex items-center text-slate-400 hover:text-${themeColor}-200 transition-colors`}
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
                                        </ul>
                                      </div>
                                    );
                                  })()}
                                </div>
                              )}

                              {/* Planning Summary Card */}
                              {message.queryType === 'planning_summary' && (
                                <div className="mt-3 rounded-lg border-2 border-amber-500/40 bg-gradient-to-br from-amber-950/30 to-orange-950/20 p-4 shadow-lg">
                                  <div className="flex items-center gap-2 mb-3 text-amber-300 font-semibold">
                                    <FileText size={18} />
                                    <span>Planning Summary</span>
                                  </div>

                                  <div className="prose prose-sm prose-invert max-w-none text-slate-200">
                                    <ReactMarkdown>{message.content}</ReactMarkdown>
                                  </div>

                                  <div className="flex gap-2 mt-4 pt-3 border-t border-amber-500/20">
                                    <button
                                      onClick={() => {
                                        // Clear planning state
                                        setPlanningContext(null);
                                        setPlanningSummary(null);
                                        setSelectedObjects([]);
                                        if (activeConversationId) {
                                          updateConversation(activeConversationId, {
                                            planningContext: null,
                                            planningSummary: undefined,
                                            selectedObjects: []
                                          });
                                        }
                                      }}
                                      className="px-3 py-1.5 text-xs rounded-md bg-slate-700 hover:bg-slate-600 text-slate-200 transition-colors flex items-center gap-1"
                                    >
                                      <RotateCcw size={12} />
                                      Start Over
                                    </button>

                                    <button
                                      onClick={() => setQueryMode('plan')}
                                      className="px-3 py-1.5 text-xs rounded-md bg-amber-600 hover:bg-amber-500 text-white transition-colors flex items-center gap-1"
                                    >
                                      <Edit size={12} />
                                      Back to Plan
                                    </button>
                                  </div>
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
                              {message.sqlResult && (message.queryType === 'database' || message.queryType === 'r_code' || message.queryType === 'sas_code' || message.queryType === 'python_code') && (message.sqlResult.sql || message.sqlResult.explanation) && (
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
                                      pythonSummary={message.pythonSummary || ''}
                                      sqlSummary={message.sqlSummary || ''}
                                      textareaRef={textareaRef}
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
                              )}

                              {/* Code Advisor display */}
                              {message.queryType === 'code_advisor' && (
                                <div className="mt-3 space-y-4">
                                  {(() => {
                                    // Pre-process content to extract code blocks (same logic as AI messages)
                                    const content = message.sqlResult?.explanation || message.content || '';
                                    console.log('=== CODE ADVISOR DEBUG ===');
                                    console.log('Content:', content.substring(0, 200));
                                    console.log('Contains ```:', content.includes('```'));
                                    
                                    const codeBlockRegex = /```(\w+)?[\s\n]*([\s\S]*?)```/g;
                                    const parts: Array<{ type: 'text' | 'code'; content: string; language?: string }> = [];
                                    let lastIndex = 0;
                                    let match;

                                    while ((match = codeBlockRegex.exec(content)) !== null) {
                                      console.log('Found code block:', match[1], match[2]?.substring(0, 50));
                                      // Add text before code block
                                      if (match.index > lastIndex) {
                                        parts.push({
                                          type: 'text',
                                          content: content.substring(lastIndex, match.index)
                                        });
                                      }
                                      
                                      // Add code block
                                      parts.push({
                                        type: 'code',
                                        content: match[2],
                                        language: match[1] || 'text'
                                      });
                                      
                                      lastIndex = match.index + match[0].length;
                                    }
                                    
                                    // Add remaining text
                                    if (lastIndex < content.length) {
                                      parts.push({
                                        type: 'text',
                                        content: content.substring(lastIndex)
                                      });
                                    }

                                    console.log('Total parts:', parts.length, parts.map(p => p.type));

                                    return (
                                      <>
                                        {parts.map((part, idx) => {
                                          if (part.type === 'code') {
                                            return (
                                              <div key={idx} className="my-4 rounded-xl border border-slate-700 bg-slate-900 overflow-hidden">
                                                <div className="flex items-center justify-between px-4 py-2 border-b border-slate-700 bg-slate-800/50">
                                                  <div className="flex items-center gap-2">
                                                    <div className="w-2 h-2 rounded-full bg-emerald-500"></div>
                                                    <span className="text-xs font-semibold text-slate-300 tracking-wider uppercase">
                                                      {part.language?.toUpperCase() || 'CODE'}
                                                    </span>
                                                  </div>
                                                  <button
                                                    onClick={() => {
                                                      navigator.clipboard.writeText(part.content);
                                                      setToast({ message: 'Code copied to clipboard!', type: 'success' });
                                                    }}
                                                    className="flex items-center gap-1.5 px-3 py-1 text-xs text-slate-300 hover:text-white bg-slate-700 hover:bg-slate-600 rounded-md transition-colors"
                                                  >
                                                    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-1M8 5a2 2 0 002 2h2a2 2 0 002-2M8 5a2 2 0 012-2h2a2 2 0 012 2m0 0h2a2 2 0 012 2v3m2 4H10m0 0l3-3m-3 3l3 3" />
                                                    </svg>
                                                    Copy
                                                  </button>
                                                </div>
                                                <div className="text-sm">
                                                  <SyntaxHighlighter
                                                    language={part.language || 'text'}
                                                    style={vscDarkPlus}
                                                    customStyle={{ margin: 0, padding: '1rem', background: 'transparent' }}
                                                  >
                                                    {part.content}
                                                  </SyntaxHighlighter>
                                                </div>
                                              </div>
                                            );
                                          } else {
                                            // Render text parts with ReactMarkdown
                                            return (
                                              <ReactMarkdown
                                                key={idx}
                                                remarkPlugins={[remarkGfm]}
                                                className="prose prose-invert max-w-none"
                                                components={{
                                                  code({ children }: React.ComponentPropsWithoutRef<'code'>) {
                                                    // Inline code as plain span
                                                    return <span>{children}</span>;
                                                  },
                                                  h2: ({ children }) => <h2 className="text-lg font-semibold text-slate-100 mt-6 mb-3 border-b border-slate-700 pb-1">{children}</h2>,
                                                  h3: ({ children }) => <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-400 mt-5 mb-2">{children}</h3>,
                                                  p: ({ children }) => <p className="text-slate-200 leading-relaxed mb-4">{children}</p>,
                                                  ul: ({ children }) => <ul className="list-disc list-inside space-y-1 text-slate-200 mb-4">{children}</ul>,
                                                  ol: ({ children }) => <ol className="list-decimal list-inside space-y-1 text-slate-200 mb-4">{children}</ol>,
                                                  blockquote: ({ children }) => <blockquote className="border-l-4 border-indigo-500/60 pl-4 text-slate-300 italic my-4">{children}</blockquote>,
                                                }}
                                              >
                                                {part.content}
                                              </ReactMarkdown>
                                            );
                                          }
                                        })}
                                      </>
                                    );
                                  })()}
                                </div>
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
                {/* 1. Plan Mode - FIRST */}
                <label className="flex items-center gap-2 cursor-pointer group">
                  <input
                    type="radio"
                    name="queryMode"
                    value="plan"
                    checked={queryMode === 'plan'}
                    onChange={() => {
                      setQueryMode('plan');
                      setPlanningSummary(null);
                    }}
                    className="w-4 h-4 text-amber-600 bg-slate-800 border-slate-600 focus:ring-amber-500 focus:ring-offset-slate-900"
                  />
                  <span className={`text-sm font-medium transition-colors ${queryMode === 'plan' ? 'text-amber-400' : 'text-slate-400 group-hover:text-slate-300'}`}>
                    📋 Plan
                  </span>
                </label>

                {/* 2. Generate SQL */}
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

                {/* 3. Generate R */}
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

                {/* 4. Generate SAS */}
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

                {/* 5. Generate Python */}
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

                {/* 6. Code Advisor */}
                <label className="flex items-center gap-2 cursor-pointer group">
                  <input
                    type="radio"
                    name="queryMode"
                    value="code-advisor"
                    checked={queryMode === 'code-advisor'}
                    onChange={() => setQueryMode('code-advisor')}
                    className="w-4 h-4 text-purple-600 bg-slate-800 border-slate-600 focus:ring-purple-500 focus:ring-offset-slate-900"
                  />
                  <span className={`text-sm font-medium transition-colors ${queryMode === 'code-advisor' ? 'text-purple-400' : 'text-slate-400 group-hover:text-slate-300'}`}>
                    🤖 Code Advisor
                  </span>
                </label>
              </div>

              {/* Planning summary ready banner */}
              {queryMode !== 'plan' && planningSummary && (
                <div className="mb-3 rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-200">
                  📋 I have your planning summary ready. Click below to generate code, or add additional requirements first.
                </div>
              )}

              {/* Selected objects banner */}
              {selectedObjects.length > 0 && queryMode !== 'plan' && !planningSummary && (
                <div className="mb-3 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-200">
                  Context locked in. I'll use these {selectedObjects.length} object{selectedObjects.length !== 1 ? 's' : ''} for the next step. What would you like me to generate?
                </div>
              )}

              <div className="relative group">
                <div className={`absolute -inset-0.5 bg-gradient-to-r ${queryMode === 'plan' ? 'from-amber-500 to-orange-600' : 'from-indigo-500 to-purple-600'} rounded-xl opacity-30 blur group-hover:opacity-50 transition duration-500`}></div>
                <div className={`relative flex items-end bg-slate-950 rounded-xl p-1 shadow-2xl ring-1 ring-slate-800 ${queryMode === 'plan' ? 'focus-within:ring-amber-500/50' : 'focus-within:ring-indigo-500/50'} transition-all`}>
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
                    placeholder={
                      queryMode === 'plan'
                        ? 'Describe your analysis goal or ask about available data...'
                        : queryMode === 'code-advisor'
                          ? 'Paste your SQL, R, SAS, or Python code here for advice... (e.g., "Review this query", "Optimize this code", "Fix this bug")'
                          : planningSummary
                            ? 'Add additional requirements (optional)...'
                            : 'Ask a question about your data (SQL, R, SAS, or Python)...'
                    }
                    disabled={isLoading}
                    rows={1}
                    className="flex-1 bg-transparent border-none text-slate-200 placeholder-slate-500 px-4 py-3 focus:outline-none focus:ring-0 text-base resize-none overflow-y-auto min-h-[48px]"
                  />
                  <button
                    onClick={handleSend}
                    disabled={isLoading || (queryMode !== 'plan' && !planningSummary && !query.trim())}
                    className={`p-3 mb-0.5 ${queryMode === 'plan' ? 'bg-amber-600 hover:bg-amber-500 shadow-amber-500/20' : 'bg-indigo-600 hover:bg-indigo-500 shadow-indigo-500/20'} text-white rounded-lg transition-all disabled:opacity-50 shadow-lg`}
                  >
                    {isLoading ? (
                      <Loader2 className="animate-spin" size={20} />
                    ) : planningSummary && queryMode !== 'plan' ? (
                      <span className="flex items-center gap-1 text-sm px-2">
                        ✨ {query.trim() ? 'Generate' : 'Auto-Generate'}
                      </span>
                    ) : (
                      <Send size={20} />
                    )}
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
          {/* User Profile Modal */}
          {showProfileModal && (
            <UserProfile onClose={() => setShowProfileModal(false)} />
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
