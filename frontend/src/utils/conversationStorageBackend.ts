import type { Conversation, ChatMessage } from '../types/conversation';
import { api } from '../api/client';

// Backend conversation response structure
interface BackendConversation {
  id: number;
  user_id: number;
  title: string | null;
  messages: Array<{
    role: 'user' | 'assistant' | 'system';
    content: string;
    timestamp: string;
  }>;
  created_at: string;
  updated_at: string;
}

// Local storage keys for fallback/cache
const STORAGE_KEY = 'sql_agent_conversations';
const ACTIVE_CONVERSATION_KEY = 'sql_agent_active_conversation';

export const conversationStorageBackend = {
  // Load all conversations from backend
  loadConversations: async (): Promise<Conversation[]> => {
    try {
      const response = await api.conversations.list(0, 100);
      const backendConversations: BackendConversation[] = response.conversations.map((item: any) => {
        // Get full conversation details
        return api.conversations.get(item.id);
      });
      
      // Fetch all conversations in parallel
      const fullConversations = await Promise.all(backendConversations);
      
      // Convert backend format to frontend format
      return fullConversations.map((conv) => ({
        id: `backend_${conv.id}`,
        backendId: conv.id,
        title: conv.title || 'Untitled Conversation',
        messages: conv.messages.map((msg, idx) => ({
          id: `msg_${conv.id}_${idx}`,
          role: msg.role,
          type: (msg.role === 'user' ? 'user' : 'ai') as 'user' | 'ai',  // For backward compatibility
          content: msg.content,
          timestamp: new Date(msg.timestamp),
        })),
        createdAt: new Date(conv.created_at),
        updatedAt: new Date(conv.updated_at),
      }));
    } catch (error) {
      console.error('Failed to load conversations from backend:', error);
      // Fallback to local storage
      return conversationStorageLocal.loadConversations();
    }
  },

  // Save conversation to backend
  saveConversation: async (conversation: Conversation): Promise<Conversation> => {
    try {
      const messages = conversation.messages.map((msg) => ({
        role: (msg.role || (msg.type === 'user' ? 'user' : 'assistant')) as 'user' | 'assistant' | 'system',
        content: msg.content,
        timestamp: msg.timestamp.toISOString(),
      }));

      if (conversation.backendId) {
        // Update existing conversation
        const updated = await api.conversations.update(
          conversation.backendId,
          conversation.title,
          messages
        );
        return {
          ...conversation,
          backendId: updated.id,
          updatedAt: new Date(updated.updated_at),
        };
      } else {
        // Create new conversation
        const created = await api.conversations.create(conversation.title, messages);
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
      // Fallback to local storage
      conversationStorageLocal.saveConversation(conversation);
      return conversation;
    }
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

  // Load active conversation ID (still from localStorage for now)
  loadActiveConversationId: (): string | null => {
    return conversationStorageLocal.loadActiveConversationId();
  },

  // Save active conversation ID
  saveActiveConversationId: (id: string | null): void => {
    conversationStorageLocal.saveActiveConversationId(id);
  },
};

// Local storage fallback (original implementation)
export const conversationStorageLocal = {
  loadConversations: (): Conversation[] => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (!stored) return [];
      
      const conversations = JSON.parse(stored);
      return conversations.map((conv: any) => ({
        ...conv,
        messages: (conv.messages || []).map((msg: any) => ({
          ...msg,
          timestamp: new Date(msg.timestamp),
        })),
        createdAt: conv.createdAt ? new Date(conv.createdAt) : new Date(),
        updatedAt: conv.updatedAt ? new Date(conv.updatedAt) : new Date(),
      }));
    } catch (error) {
      console.error('Failed to load conversations from localStorage:', error);
      return [];
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
      
      localStorage.setItem(STORAGE_KEY, JSON.stringify(conversations));
    } catch (error) {
      console.error('Failed to save conversation to localStorage:', error);
    }
  },

  loadActiveConversationId: (): string | null => {
    try {
      return localStorage.getItem(ACTIVE_CONVERSATION_KEY);
    } catch (error) {
      return null;
    }
  },

  saveActiveConversationId: (id: string | null): void => {
    try {
      if (id) {
        localStorage.setItem(ACTIVE_CONVERSATION_KEY, id);
      } else {
        localStorage.removeItem(ACTIVE_CONVERSATION_KEY);
      }
    } catch (error) {
      console.error('Failed to save active conversation ID:', error);
    }
  },

  clearAll: (): void => {
    localStorage.removeItem(STORAGE_KEY);
    localStorage.removeItem(ACTIVE_CONVERSATION_KEY);
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
