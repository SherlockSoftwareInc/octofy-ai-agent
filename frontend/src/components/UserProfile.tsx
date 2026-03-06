import React, { useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { User, Mail, LogOut, Lock, Eye, EyeOff, Check, Copy } from 'lucide-react';
import { api } from '../api/client';

export const UserProfile: React.FC<{ onClose: () => void }> = ({ onClose }) => {
  const { user, apiKey, logout } = useAuth();
  const [showChangePassword, setShowChangePassword] = useState(false);
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [isChangingPassword, setIsChangingPassword] = useState(false);
  const [passwordError, setPasswordError] = useState('');
  const [passwordSuccess, setPasswordSuccess] = useState(false);
  const [apiKeyCopyStatus, setApiKeyCopyStatus] = useState<'idle' | 'success' | 'error'>('idle');

  if (!user) return null;

  const keyToDisplay = apiKey || user.api_key || '';
  const maskedApiKey = keyToDisplay
    ? `****${keyToDisplay.slice(-4)}`
    : 'Not available';

  const handleCopyApiKey = async () => {
    if (!keyToDisplay) {
      setApiKeyCopyStatus('error');
      setTimeout(() => setApiKeyCopyStatus('idle'), 2000);
      return;
    }

    try {
      await navigator.clipboard.writeText(keyToDisplay);
      setApiKeyCopyStatus('success');
      setTimeout(() => setApiKeyCopyStatus('idle'), 2000);
    } catch {
      setApiKeyCopyStatus('error');
      setTimeout(() => setApiKeyCopyStatus('idle'), 2000);
    }
  };

  const handleChangePassword = async () => {
    setPasswordError('');
    setPasswordSuccess(false);

    if (newPassword.length < 6) {
      setPasswordError('Password must be at least 6 characters');
      return;
    }
    if (newPassword !== confirmPassword) {
      setPasswordError('Passwords do not match');
      return;
    }

    setIsChangingPassword(true);
    try {
      await api.client.put('/api/v1/users/me', { password: newPassword });
      setPasswordSuccess(true);
      setNewPassword('');
      setConfirmPassword('');
      setTimeout(() => {
        setShowChangePassword(false);
        setPasswordSuccess(false);
      }, 2000);
    } catch (error) {
      console.error('Failed to change password:', error);
      setPasswordError('Failed to change password');
    } finally {
      setIsChangingPassword(false);
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

          <div className="flex items-center space-x-3 p-3 bg-gray-50 rounded-lg">
            <Lock className="w-5 h-5 text-gray-400" />
            <div className="flex-1 min-w-0">
              <p className="text-xs text-gray-500 uppercase font-medium">API key</p>
              <p className="text-sm font-medium text-gray-900 font-mono">{maskedApiKey}</p>
              {apiKeyCopyStatus === 'success' && (
                <p className="text-xs text-green-600">Copied to clipboard</p>
              )}
              {apiKeyCopyStatus === 'error' && (
                <p className="text-xs text-red-600">Failed to copy API key</p>
              )}
            </div>
            <button
              onClick={handleCopyApiKey}
              className="p-2 bg-gray-200 hover:bg-gray-300 text-gray-700 rounded-lg transition-colors"
              title="Copy API key"
            >
              <Copy className="w-4 h-4" />
            </button>
          </div>

          {/* Change Password */}
          <div className="border-t pt-4">
            {!showChangePassword ? (
              <button
                onClick={() => setShowChangePassword(true)}
                className="w-full flex items-center space-x-3 p-3 bg-gray-50 hover:bg-gray-100 rounded-lg transition-colors"
              >
                <Lock className="w-5 h-5 text-gray-400" />
                <span className="text-sm font-medium text-gray-900">Change Password</span>
              </button>
            ) : (
              <div className="space-y-3">
                <div className="flex items-center space-x-2 mb-2">
                  <Lock className="w-4 h-4 text-gray-400" />
                  <p className="text-xs text-gray-500 uppercase font-medium">Change Password</p>
                </div>

                {/* New Password */}
                <div className="relative">
                  <input
                    type={showNewPassword ? 'text' : 'password'}
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    placeholder="New password (min 6 characters)"
                    className="w-full px-3 py-2 pr-10 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                  />
                  <button
                    type="button"
                    onClick={() => setShowNewPassword(!showNewPassword)}
                    className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-gray-400 hover:text-gray-600"
                  >
                    {showNewPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>

                {/* Confirm Password */}
                <div className="relative">
                  <input
                    type={showConfirmPassword ? 'text' : 'password'}
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    placeholder="Confirm new password"
                    className="w-full px-3 py-2 pr-10 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                  />
                  <button
                    type="button"
                    onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                    className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-gray-400 hover:text-gray-600"
                  >
                    {showConfirmPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>

                {passwordError && (
                  <p className="text-xs text-red-600">{passwordError}</p>
                )}
                {passwordSuccess && (
                  <p className="text-xs text-green-600 flex items-center space-x-1">
                    <Check className="w-3 h-3" />
                    <span>Password changed successfully</span>
                  </p>
                )}

                <div className="flex space-x-2">
                  <button
                    onClick={handleChangePassword}
                    disabled={isChangingPassword || !newPassword || !confirmPassword}
                    className="flex-1 py-2 px-3 bg-purple-600 hover:bg-purple-700 text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-50"
                  >
                    {isChangingPassword ? 'Saving...' : 'Save Password'}
                  </button>
                  <button
                    onClick={() => {
                      setShowChangePassword(false);
                      setNewPassword('');
                      setConfirmPassword('');
                      setPasswordError('');
                      setPasswordSuccess(false);
                    }}
                    className="py-2 px-3 bg-gray-200 hover:bg-gray-300 text-gray-700 text-sm font-medium rounded-lg transition-colors"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}
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
