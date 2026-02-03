import React, { useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { User, Mail, Key, Shield, LogOut, Copy, Check, RefreshCw } from 'lucide-react';
import { api } from '../api/client';

export const UserProfile: React.FC<{ onClose: () => void }> = ({ onClose }) => {
  const { user, logout, refreshUser } = useAuth();
  const [copiedApiKey, setCopiedApiKey] = useState(false);
  const [isRegenerating, setIsRegenerating] = useState(false);

  if (!user) return null;

  const handleCopyApiKey = () => {
    navigator.clipboard.writeText(user.api_key);
    setCopiedApiKey(true);
    setTimeout(() => setCopiedApiKey(false), 2000);
  };

  const handleRegenerateApiKey = async () => {
    if (!confirm('Are you sure you want to regenerate your API key? The old key will stop working.')) {
      return;
    }

    setIsRegenerating(true);
    try {
      const response = await api.client.post('/api/v1/users/me/regenerate-api-key');
      const newApiKey = response.data.api_key;
      
      // Update localStorage with new API key and reset timestamp
      localStorage.setItem('api_key', newApiKey);
      localStorage.setItem('api_key_timestamp', Date.now().toString());
      
      // Refresh user data
      await refreshUser();
    } catch (error) {
      console.error('Failed to regenerate API key:', error);
      alert('Failed to regenerate API key');
    } finally {
      setIsRegenerating(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-white rounded-xl shadow-2xl max-w-md w-full mx-4" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="bg-gradient-to-r from-purple-600 to-pink-600 p-6 rounded-t-xl">
          <div className="flex items-center space-x-3">
            <div className="w-16 h-16 rounded-full bg-white/20 backdrop-blur-sm flex items-center justify-center">
              <User className="w-8 h-8 text-white" />
            </div>
            <div className="flex-1">
              <h2 className="text-xl font-bold text-white">{user.full_name || user.username}</h2>
              <p className="text-purple-100 text-sm">@{user.username}</p>
            </div>
          </div>
        </div>

        {/* Content */}
        <div className="p-6 space-y-4">
          {/* Email */}
          <div className="flex items-center space-x-3 p-3 bg-gray-50 rounded-lg">
            <Mail className="w-5 h-5 text-gray-400" />
            <div className="flex-1">
              <p className="text-xs text-gray-500 uppercase font-medium">Email</p>
              <p className="text-sm font-medium text-gray-900">{user.email}</p>
            </div>
          </div>

          {/* Role */}
          <div className="flex items-center space-x-3 p-3 bg-gray-50 rounded-lg">
            <Shield className="w-5 h-5 text-gray-400" />
            <div className="flex-1">
              <p className="text-xs text-gray-500 uppercase font-medium">Role</p>
              <span className={`inline-flex items-center px-2 py-1 text-xs font-medium rounded ${
                user.role === 'admin' 
                  ? 'bg-purple-100 text-purple-800' 
                  : 'bg-blue-100 text-blue-800'
              }`}>
                {user.role}
              </span>
            </div>
          </div>

          {/* API Key */}
          <div className="border-t pt-4">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center space-x-2">
                <Key className="w-4 h-4 text-gray-400" />
                <p className="text-xs text-gray-500 uppercase font-medium">API Key</p>
              </div>
              <button
                onClick={handleRegenerateApiKey}
                disabled={isRegenerating}
                className="text-xs text-purple-600 hover:text-purple-700 font-medium flex items-center space-x-1 disabled:opacity-50"
              >
                <RefreshCw className={`w-3 h-3 ${isRegenerating ? 'animate-spin' : ''}`} />
                <span>Regenerate</span>
              </button>
            </div>
            <div className="flex items-center space-x-2">
              <code className="flex-1 px-3 py-2 bg-gray-900 text-gray-100 text-xs rounded font-mono truncate">
                {user.api_key}
              </code>
              <button
                onClick={handleCopyApiKey}
                className="p-2 hover:bg-gray-100 rounded transition-colors"
                title="Copy API Key"
              >
                {copiedApiKey ? (
                  <Check className="w-4 h-4 text-green-600" />
                ) : (
                  <Copy className="w-4 h-4 text-gray-600" />
                )}
              </button>
            </div>
            <p className="text-xs text-gray-500 mt-2">
              Use this key to authenticate API requests
            </p>
          </div>
        </div>

        {/* Footer */}
        <div className="p-6 bg-gray-50 rounded-b-xl flex space-x-3">
          <button
            onClick={logout}
            className="flex-1 py-2 px-4 bg-red-600 hover:bg-red-700 text-white font-medium rounded-lg transition-colors flex items-center justify-center space-x-2"
          >
            <LogOut className="w-4 h-4" />
            <span>Logout</span>
          </button>
          <button
            onClick={onClose}
            className="flex-1 py-2 px-4 bg-gray-200 hover:bg-gray-300 text-gray-800 font-medium rounded-lg transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
