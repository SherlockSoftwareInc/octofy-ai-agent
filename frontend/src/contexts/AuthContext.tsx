import React, { createContext, useContext, useState, useEffect } from 'react';
import { api } from '../api/client';

export interface User {
  id: number;
  username: string;
  email: string;
  full_name: string | null;
  role: 'admin' | 'user';
  is_active: boolean;
  api_key: string;
  created_at: string;
  last_login_at: string | null;
}

interface AuthContextType {
  user: User | null;
  apiKey: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [apiKey, setApiKey] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Load API key and user from localStorage on mount
  useEffect(() => {
    const initializeAuth = async () => {
      const storedApiKey = localStorage.getItem('api_key');
      const storedTimestamp = localStorage.getItem('api_key_timestamp');
      
      if (storedApiKey && storedTimestamp) {
        // Check if token is older than 7 days
        const tokenAge = Date.now() - parseInt(storedTimestamp);
        const sevenDaysInMs = 7 * 24 * 60 * 60 * 1000;
        
        if (tokenAge > sevenDaysInMs) {
          // Token expired, clear it
          console.log('API key expired (older than 7 days), clearing...');
          localStorage.removeItem('api_key');
          localStorage.removeItem('api_key_timestamp');
          setIsLoading(false);
          return;
        }
        
        // Token is valid (less than 7 days old), try to authenticate
        setApiKey(storedApiKey);
        try {
          const response = await api.client.get('/api/v1/auth/me', {
            headers: { 'X-API-Key': storedApiKey }
          });
          setUser(response.data);
          console.log('Auto-login successful');
        } catch (error) {
          console.error('Failed to fetch user:', error);
          // API key is invalid, clear it
          localStorage.removeItem('api_key');
          localStorage.removeItem('api_key_timestamp');
          setApiKey(null);
        }
      }
      setIsLoading(false);
    };

    initializeAuth();
  }, []);

  const login = async (username: string, password: string) => {
    try {
      const response = await api.client.post('/api/v1/auth/login', { username, password });
      const { access_token, user: userData } = response.data;
      
      // access_token is actually the user's API key
      setApiKey(access_token);
      setUser(userData);
      localStorage.setItem('api_key', access_token);
      localStorage.setItem('api_key_timestamp', Date.now().toString());
      console.log('Login successful, API key saved with timestamp');
    } catch (error: any) {
      console.error('Login failed:', error);
      throw new Error(error.response?.data?.detail || 'Login failed');
    }
  };

  const logout = () => {
    setUser(null);
    setApiKey(null);
    localStorage.removeItem('api_key');
    localStorage.removeItem('api_key_timestamp');
    // Clear user-scoped conversation cache keys
    // Remove all conversation-related localStorage entries for any user
    const keysToRemove: string[] = [];
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (key && (key.startsWith('sql_agent_conversations_') || key.startsWith('sql_agent_active_conversation_'))) {
        keysToRemove.push(key);
      }
    }
    keysToRemove.forEach(key => localStorage.removeItem(key));
    // Also clear legacy non-scoped keys
    localStorage.removeItem('sql_agent_conversations');
    localStorage.removeItem('sql_agent_active_conversation');
    localStorage.removeItem('conversations');
    localStorage.removeItem('activeConversationId');
    console.log('Logout complete, all tokens and conversation cache cleared');
  };

  const refreshUser = async () => {
    if (!apiKey) return;
    
    try {
      const response = await api.client.get('/api/v1/auth/me', {
        headers: { 'X-API-Key': apiKey }
      });
      setUser(response.data);
    } catch (error) {
      console.error('Failed to refresh user:', error);
    }
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        apiKey,
        isAuthenticated: !!user && !!apiKey,
        isLoading,
        login,
        logout,
        refreshUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
