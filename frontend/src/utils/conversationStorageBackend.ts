import type { Conversation, ChatMessage } from '../types/conversation';
import { api } from '../api/client';

// Backend conversation response structure (now stores rich message data)
interface BackendConversation {
  id: number;
  user_id: number;
  title: string | null;
  messages: Array<Record<string, unknown>>;
  extra_data?: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

// Local storage keys for fallback/cache (user-scoped)
const STORAGE_KEY_PREFIX = 'sql_agent_conversations_';
const ACTIVE_KEY_PREFIX = 'sql_agent_active_conversation_';

function getUserStorageKey(): string {
  const apiKey = localStorage.getItem('api_key');
  // Use a hash of the API key as the user scope (or 'anonymous' if not logged in)
  const userScope = apiKey ? apiKey.substring(0, 12) : 'anonymous';
  return userScope;
}

function getStorageKey(): string {
  return `${STORAGE_KEY_PREFIX}${getUserStorageKey()}`;
}

function getActiveKey(): string {
  return `${ACTIVE_KEY_PREFIX}${getUserStorageKey()}`;
}

/**
 * Serialize a ChatMessage for backend storage.
 * Preserves all fields including rich data (sqlResult, executionResult, etc.)
 */
function serializeMessage(msg: ChatMessage): Record<string, unknown> {
  const serialized: Record<string, unknown> = { ...msg };
  // Convert Date to ISO string for JSON serialization
  if (msg.timestamp instanceof Date) {
    serialized.timestamp = msg.timestamp.toISOString();
  }
  // Ensure role is set (backward compat from type field)
  if (!serialized.role && msg.type) {
    serialized.role = msg.type === 'user' ? 'user' : 'assistant';
  }
  return serialized;
}

/**
 * Deserialize a backend message dict back to ChatMessage.
 */
function deserializeMessage(msg: Record<string, unknown>, convId: number, idx: number): ChatMessage {
  return {
    ...msg,
    id: (msg.id as string) || `msg_${convId}_${idx}`,
    role: (msg.role as ChatMessage['role']) || 'assistant',
    type: msg.type as ChatMessage['type'] || ((msg.role === 'user' ? 'user' : 'ai') as 'user' | 'ai'),
    content: (msg.content as string) || '',
    timestamp: msg.timestamp ? new Date(msg.timestamp as string) : new Date(),
  } as ChatMessage;
}

/**
 * Extract conversation metadata for backend storage.
 */
function extractMetadata(conversation: Conversation): Record<string, unknown> {
  const metadata: Record<string, unknown> = {};
  if (conversation.lastGeneratedSQL) metadata.lastGeneratedSQL = conversation.lastGeneratedSQL;
  if (conversation.queryHistory) metadata.queryHistory = conversation.queryHistory;
  if (conversation.selectedObjects) metadata.selectedObjects = conversation.selectedObjects;
  if (conversation.planningContext) metadata.planningContext = conversation.planningContext;
  if (conversation.planningSummary) metadata.planningSummary = conversation.planningSummary;
  return metadata;
}

export const conversationStorageBackend = {
  // Load all conversations from backend
  loadConversations: async (): Promise<Conversation[]> => {
    try {
      const response = await api.conversations.list(0, 100);
      
      if (!response.conversations || response.conversations.length === 0) {
        return [];
      }
      
      // Fetch full conversation details in parallel
      const fullConversations: BackendConversation[] = await Promise.all(
        response.conversations.map((item: { id: number }) => api.conversations.get(item.id))
      );
      
      // Convert backend format to frontend format, preserving all rich data
      return fullConversations.map((conv) => {
        const extraData = conv.extra_data || {};
        return {
          id: `backend_${conv.id}`,
          backendId: conv.id,
          title: conv.title || 'Untitled Conversation',
          messages: (conv.messages || []).map((msg, idx) => deserializeMessage(msg, conv.id, idx)),
          createdAt: new Date(conv.created_at),
          updatedAt: new Date(conv.updated_at),
          lastGeneratedSQL: extraData.lastGeneratedSQL as string | undefined,
          queryHistory: extraData.queryHistory as string | undefined,
          selectedObjects: extraData.selectedObjects as string[] | undefined,
          planningContext: extraData.planningContext as Record<string, unknown> | undefined,
          planningSummary: extraData.planningSummary as string | undefined,
        };
      });
    } catch (error) {
      console.error('Failed to load conversations from backend:', error);
      // Fallback to user-scoped local storage
      return conversationStorageLocal.loadConversations();
    }
  },

  // Save/sync a single conversation to backend
  saveConversation: async (conversation: Conversation): Promise<Conversation> => {
    try {
      const messages = conversation.messages.map(serializeMessage);
      const metadata = extractMetadata(conversation);

      if (conversation.backendId) {
        // Update existing conversation
        const updated = await api.conversations.update(
          conversation.backendId,
          conversation.title,
          messages,
          metadata
        );
        return {
          ...conversation,
          backendId: updated.id,
          updatedAt: new Date(updated.updated_at),
        };
      } else {
        // Create new conversation
        const created = await api.conversations.create(conversation.title, messages, metadata);
        return {
          ...conversation,
          id: `backend_${created.id}`,
          backendId: created.id,
          createdAt: new Date(created.created_at),
          updatedAt: new Date(created.updated_at),
        };
      }
    } catch (error) {
      console.error('Failed to save conversation to backend:', error);
      // Fallback: save to user-scoped local storage
      conversationStorageLocal.saveConversation(conversation);
      return conversation;
    }
  },

  // Save all conversations (batch operation for compatibility with old interface)
  saveConversations: async (conversations: Conversation[]): Promise<void> => {
    // Also save to user-scoped localStorage as cache
    conversationStorageLocal.saveConversations(conversations);
  },

  // Delete conversation from backend
  deleteConversation: async (conversation: Conversation): Promise<void> => {
    try {
      if (conversation.backendId) {
        await api.conversations.delete(conversation.backendId);
      }
    } catch (error) {
      console.error('Failed to delete conversation from backend:', error);
    }
  },

  // Load active conversation ID (user-scoped localStorage)
  loadActiveConversationId: (): string | null => {
    return conversationStorageLocal.loadActiveConversationId();
  },

  // Save active conversation ID (user-scoped localStorage)
  saveActiveConversationId: (id: string | null): void => {
    conversationStorageLocal.saveActiveConversationId(id);
  },

  // Clear all conversation data
  clearAll: (): void => {
    conversationStorageLocal.clearAll();
  },
};

// Local storage fallback (user-scoped)
export const conversationStorageLocal = {
  loadConversations: (): Conversation[] => {
    try {
      const stored = localStorage.getItem(getStorageKey());
      if (!stored) return [];
      
      const conversations = JSON.parse(stored);
      return conversations.map((conv: Record<string, unknown>) => ({
        ...conv,
        messages: ((conv.messages as Array<Record<string, unknown>>) || []).map((msg: Record<string, unknown>) => ({
          ...msg,
          timestamp: new Date(msg.timestamp as string),
        })),
        createdAt: conv.createdAt ? new Date(conv.createdAt as string) : new Date(),
        updatedAt: conv.updatedAt ? new Date(conv.updatedAt as string) : new Date(),
      }));
    } catch (error) {
      console.error('Failed to load conversations from localStorage:', error);
      return [];
    }
  },

  saveConversations: (conversations: Conversation[]): void => {
    try {
      localStorage.setItem(getStorageKey(), JSON.stringify(conversations));
    } catch (error) {
      console.error('Failed to save conversations to localStorage:', error);
    }
  },

  saveConversation: (conversation: Conversation): void => {
    try {
      const conversations = conversationStorageLocal.loadConversations();
      const index = conversations.findIndex((c) => c.id === conversation.id);
      
      if (index >= 0) {
        conversations[index] = conversation;
      } else {
        conversations.push(conversation);
      }
      
      localStorage.setItem(getStorageKey(), JSON.stringify(conversations));
    } catch (error) {
      console.error('Failed to save conversation to localStorage:', error);
    }
  },

  loadActiveConversationId: (): string | null => {
    try {
      return localStorage.getItem(getActiveKey());
    } catch (error) {
      return null;
    }
  },

  saveActiveConversationId: (id: string | null): void => {
    try {
      if (id) {
        localStorage.setItem(getActiveKey(), id);
      } else {
        localStorage.removeItem(getActiveKey());
      }
    } catch (error) {
      console.error('Failed to save active conversation ID:', error);
    }
  },

  clearAll: (): void => {
    localStorage.removeItem(getStorageKey());
    localStorage.removeItem(getActiveKey());
  },
};

// Export the backend version as default
export const conversationStorage = conversationStorageBackend;

// Helper functions (keep original implementations)
export function generateConversationId(): string {
  return `conv_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

export function generateMessageId(): string {
  return `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

export function generateInitialTitle(query: string): string {
  return query.length > 50 ? query.substring(0, 50) + '...' : query;
}

export function generateAutoTitle(messages: ChatMessage[]): string {
  const firstUserMessage = messages.find((msg) => msg.role === 'user');
  if (firstUserMessage) {
    return generateInitialTitle(firstUserMessage.content);
  }
  return 'New Conversation';
}
