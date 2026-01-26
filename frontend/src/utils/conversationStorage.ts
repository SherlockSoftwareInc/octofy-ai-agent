import type { Conversation, ChatMessage } from '../types/conversation';

const STORAGE_KEY = 'sql_agent_conversations';
const ACTIVE_CONVERSATION_KEY = 'sql_agent_active_conversation';

interface StoredConversation extends Omit<Conversation, 'messages'> {
  messages: Array<Omit<ChatMessage, 'timestamp'> & { timestamp: string }>;
}

export const conversationStorage = {
  // Load all conversations from localStorage
  loadConversations: (): Conversation[] => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (!stored) return [];
      
      const conversations: StoredConversation[] = JSON.parse(stored);
      // Convert timestamp strings back to Date objects
      return conversations.map((conv) => ({
        ...conv,
        messages: conv.messages.map((msg) => ({
          ...msg,
          timestamp: new Date(msg.timestamp),
        })),
      }));
    } catch (error) {
      console.error('Failed to load conversations:', error);
      return [];
    }
  },

  // Save all conversations to localStorage
  saveConversations: (conversations: Conversation[]): void => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(conversations));
    } catch (error) {
      console.error('Failed to save conversations:', error);
    }
  },

  // Load the active conversation ID
  loadActiveConversationId: (): string | null => {
    try {
      return localStorage.getItem(ACTIVE_CONVERSATION_KEY);
    } catch (error) {
      console.error('Failed to load active conversation ID:', error);
      return null;
    }
  },

  // Save the active conversation ID
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

  // Clear all conversation data
  clearAll: (): void => {
    try {
      localStorage.removeItem(STORAGE_KEY);
      localStorage.removeItem(ACTIVE_CONVERSATION_KEY);
    } catch (error) {
      console.error('Failed to clear conversation data:', error);
    }
  },
};

// Generate a unique ID for conversations
export function generateConversationId(): string {
  return `conv_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

// Generate a unique ID for messages
export function generateMessageId(): string {
  return `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

// Generate a title for a conversation based on the first user message
export function generateInitialTitle(firstMessage: string): string {
  // Take first 50 characters and clean up
  const title = firstMessage.slice(0, 50).trim();
  return title.length < firstMessage.length ? `${title}...` : title;
}

// Auto-generate a better title using AI (to be called after 2-3 messages)
export async function generateAutoTitle(
  messages: ChatMessage[], 
  apiGenerateSQL: typeof import('../api/client').api.generateSQL
): Promise<string | null> {
  try {
    // Get the first 2-3 messages to understand the context
    const conversationContext = messages
      .slice(0, 6) // First 3 exchanges (user + AI)
      .map(msg => `${msg.type}: ${msg.content}`)
      .join('\n');

    // Ask the LLM to generate a concise title
    const titlePrompt = `Based on this conversation, generate a short, descriptive title (max 5 words):

${conversationContext}

Respond with ONLY the title, no explanation.`;

    const response = await apiGenerateSQL(titlePrompt, undefined, undefined, undefined, true);
    
    if (response.explanation) {
      // Clean up the response
      let title = response.explanation
        .replace(/^["']|["']$/g, '') // Remove quotes
        .replace(/^Title:\s*/i, '') // Remove "Title:" prefix
        .trim();
      
      // Limit length
      if (title.length > 60) {
        title = title.slice(0, 60).trim() + '...';
      }
      
      return title || null;
    }
    
    return null;
  } catch (error) {
    console.error('Failed to generate auto-title:', error);
    return null;
  }
}
