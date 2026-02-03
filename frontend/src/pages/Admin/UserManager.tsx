import { useState, useEffect } from 'react';
import {
    Users, Plus, Edit2, Trash2, Search, Key, Activity,
    CheckCircle, XCircle, MessageSquare, Zap, Clock,
    TrendingUp, AlertCircle, RefreshCw, X, Shield, User as UserIcon
} from 'lucide-react';
import { api } from '../../api/client';
import type { UserResponse, UserStatistics, UserActivity, AdminUserCreate, AdminUserUpdate } from '../../api/client';

interface UserWithStats extends UserResponse {
    conversationCount?: number;
    totalActivities?: number;
}

export const UserManager = () => {
    const [users, setUsers] = useState<UserWithStats[]>([]);
    const [loading, setLoading] = useState(true);
    const [searchQuery, setSearchQuery] = useState('');
    const [selectedUser, setSelectedUser] = useState<UserResponse | null>(null);
    const [userStats, setUserStats] = useState<UserStatistics | null>(null);
    const [userActivities, setUserActivities] = useState<UserActivity[]>([]);
    const [showAddModal, setShowAddModal] = useState(false);
    const [showEditModal, setShowEditModal] = useState(false);
    const [showStatsModal, setShowStatsModal] = useState(false);
    const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState<string | null>(null);

    // Form state
    const [formData, setFormData] = useState<AdminUserCreate | AdminUserUpdate>({
        username: '',
        email: '',
        full_name: '',
        password: '',
        role: 'user'
    });

    useEffect(() => {
        loadUsers();
    }, []);

    const loadUsers = async () => {
        try {
            setLoading(true);
            const response = await api.users.list(0, 100);
            setUsers(response.users);
            setError(null);
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to load users');
        } finally {
            setLoading(false);
        }
    };

    const loadUserStats = async (userId: number) => {
        try {
            const stats = await api.users.getStats(userId, 30);
            setUserStats(stats);
            
            // Load recent activities
            const activities = await api.users.getActivities(userId, 0, 20);
            setUserActivities(activities.activities);
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to load user statistics');
        }
    };

    const handleAddUser = async () => {
        try {
            await api.users.create(formData as AdminUserCreate);
            setSuccess('User created successfully');
            setShowAddModal(false);
            resetForm();
            loadUsers();
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to create user');
        }
    };

    const handleUpdateUser = async () => {
        if (!selectedUser) return;
        
        try {
            await api.users.update(selectedUser.id, formData as AdminUserUpdate);
            setSuccess('User updated successfully');
            setShowEditModal(false);
            resetForm();
            loadUsers();
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to update user');
        }
    };

    const handleDeleteUser = async () => {
        if (!selectedUser) return;
        
        try {
            await api.users.delete(selectedUser.id);
            setSuccess('User deleted successfully');
            setShowDeleteConfirm(false);
            setSelectedUser(null);
            loadUsers();
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to delete user');
        }
    };

    const handleRegenerateApiKey = async (userId: number) => {
        try {
            const response = await api.users.regenerateApiKey(userId);
            setSuccess(`New API key generated: ${response.api_key}`);
            loadUsers();
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to regenerate API key');
        }
    };

    const openEditModal = (user: UserResponse) => {
        setSelectedUser(user);
        setFormData({
            email: user.email || '',
            full_name: user.full_name || '',
            role: user.role,
            is_active: user.is_active
        });
        setShowEditModal(true);
    };

    const openStatsModal = (user: UserResponse) => {
        setSelectedUser(user);
        setShowStatsModal(true);
        loadUserStats(user.id);
    };

    const resetForm = () => {
        setFormData({
            username: '',
            email: '',
            full_name: '',
            password: '',
            role: 'user'
        });
        setSelectedUser(null);
    };

    const filteredUsers = users.filter(user =>
        user.username.toLowerCase().includes(searchQuery.toLowerCase()) ||
        user.email?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        user.full_name?.toLowerCase().includes(searchQuery.toLowerCase())
    );

    const getActivityTypeLabel = (type: string) => {
        const labels: Record<string, string> = {
            sql_generated: 'SQL Generated',
            sql_executed: 'SQL Executed',
            python_executed: 'Python Executed',
            r_generated: 'R Generated',
            sas_generated: 'SAS Generated',
            conversation_created: 'Conversation Created',
            login: 'Login'
        };
        return labels[type] || type;
    };

    const getActivityTypeColor = (type: string) => {
        const colors: Record<string, string> = {
            sql_generated: 'bg-blue-500/20 text-blue-300',
            sql_executed: 'bg-green-500/20 text-green-300',
            python_executed: 'bg-yellow-500/20 text-yellow-300',
            r_generated: 'bg-purple-500/20 text-purple-300',
            sas_generated: 'bg-orange-500/20 text-orange-300',
            conversation_created: 'bg-cyan-500/20 text-cyan-300',
            login: 'bg-gray-500/20 text-gray-300'
        };
        return colors[type] || 'bg-slate-500/20 text-slate-300';
    };

    return (
        <div className="h-full flex flex-col bg-slate-950">
            {/* Header */}
            <div className="border-b border-slate-800 bg-slate-900/50 p-6">
                <div className="flex items-center justify-between">
                    <div>
                        <h1 className="text-2xl font-bold text-white flex items-center gap-3">
                            <Users className="text-cyan-400" size={32} />
                            User Management
                        </h1>
                        <p className="text-slate-400 mt-1">Manage users, roles, and view activity statistics</p>
                    </div>
                    <button
                        onClick={() => setShowAddModal(true)}
                        className="flex items-center gap-2 bg-cyan-600 hover:bg-cyan-700 text-white px-4 py-2 rounded-lg transition-colors"
                    >
                        <Plus size={20} />
                        Add User
                    </button>
                </div>

                {/* Search */}
                <div className="mt-4 relative">
                    <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-slate-400" size={20} />
                    <input
                        type="text"
                        placeholder="Search users by username, email, or name..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        className="w-full pl-10 pr-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-white placeholder-slate-400 focus:outline-none focus:border-cyan-500"
                    />
                </div>
            </div>

            {/* Notifications */}
            {error && (
                <div className="mx-6 mt-4 p-4 bg-red-500/10 border border-red-500/50 rounded-lg flex items-center gap-3 text-red-300">
                    <AlertCircle size={20} />
                    <span>{error}</span>
                    <button onClick={() => setError(null)} className="ml-auto">
                        <X size={20} />
                    </button>
                </div>
            )}

            {success && (
                <div className="mx-6 mt-4 p-4 bg-green-500/10 border border-green-500/50 rounded-lg flex items-center gap-3 text-green-300">
                    <CheckCircle size={20} />
                    <span>{success}</span>
                    <button onClick={() => setSuccess(null)} className="ml-auto">
                        <X size={20} />
                    </button>
                </div>
            )}

            {/* User Table */}
            <div className="flex-1 overflow-auto p-6">
                {loading ? (
                    <div className="flex items-center justify-center h-64">
                        <RefreshCw className="animate-spin text-cyan-400" size={32} />
                    </div>
                ) : (
                    <div className="bg-slate-900 rounded-lg border border-slate-800 overflow-hidden">
                        <table className="w-full">
                            <thead className="bg-slate-800/50">
                                <tr>
                                    <th className="px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">User</th>
                                    <th className="px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">Role</th>
                                    <th className="px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">Status</th>
                                    <th className="px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">Created</th>
                                    <th className="px-6 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">Last Login</th>
                                    <th className="px-6 py-3 text-right text-xs font-medium text-slate-400 uppercase tracking-wider">Actions</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-800">
                                {filteredUsers.map((user) => (
                                    <tr key={user.id} className="hover:bg-slate-800/30 transition-colors">
                                        <td className="px-6 py-4">
                                            <div>
                                                <div className="font-medium text-white">{user.username}</div>
                                                <div className="text-sm text-slate-400">{user.email || 'No email'}</div>
                                                {user.full_name && <div className="text-xs text-slate-500">{user.full_name}</div>}
                                            </div>
                                        </td>
                                        <td className="px-6 py-4">
                                            <span className={`inline-flex items-center gap-1 px-2 py-1 rounded text-xs font-medium ${
                                                user.role === 'admin' 
                                                    ? 'bg-red-500/20 text-red-300' 
                                                    : 'bg-blue-500/20 text-blue-300'
                                            }`}>
                                                {user.role === 'admin' ? <Shield size={12} /> : <UserIcon size={12} />}
                                                {user.role}
                                            </span>
                                        </td>
                                        <td className="px-6 py-4">
                                            <span className={`inline-flex items-center gap-1 px-2 py-1 rounded text-xs font-medium ${
                                                user.is_active 
                                                    ? 'bg-green-500/20 text-green-300' 
                                                    : 'bg-gray-500/20 text-gray-300'
                                            }`}>
                                                {user.is_active ? <CheckCircle size={12} /> : <XCircle size={12} />}
                                                {user.is_active ? 'Active' : 'Inactive'}
                                            </span>
                                        </td>
                                        <td className="px-6 py-4 text-sm text-slate-300">
                                            {new Date(user.created_at).toLocaleDateString()}
                                        </td>
                                        <td className="px-6 py-4 text-sm text-slate-300">
                                            {user.last_login_at ? new Date(user.last_login_at).toLocaleDateString() : 'Never'}
                                        </td>
                                        <td className="px-6 py-4 text-right">
                                            <div className="flex items-center gap-2 justify-end">
                                                <button
                                                    onClick={() => openStatsModal(user)}
                                                    className="p-2 text-cyan-400 hover:bg-cyan-500/10 rounded transition-colors"
                                                    title="View Statistics"
                                                >
                                                    <Activity size={16} />
                                                </button>
                                                <button
                                                    onClick={() => openEditModal(user)}
                                                    className="p-2 text-blue-400 hover:bg-blue-500/10 rounded transition-colors"
                                                    title="Edit User"
                                                >
                                                    <Edit2 size={16} />
                                                </button>
                                                <button
                                                    onClick={() => {
                                                        if (window.confirm('Regenerate API key for this user?')) {
                                                            handleRegenerateApiKey(user.id);
                                                        }
                                                    }}
                                                    className="p-2 text-yellow-400 hover:bg-yellow-500/10 rounded transition-colors"
                                                    title="Regenerate API Key"
                                                >
                                                    <Key size={16} />
                                                </button>
                                                <button
                                                    onClick={() => {
                                                        setSelectedUser(user);
                                                        setShowDeleteConfirm(true);
                                                    }}
                                                    className="p-2 text-red-400 hover:bg-red-500/10 rounded transition-colors"
                                                    title="Delete User"
                                                >
                                                    <Trash2 size={16} />
                                                </button>
                                            </div>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>

                        {filteredUsers.length === 0 && (
                            <div className="text-center py-12 text-slate-400">
                                {searchQuery ? 'No users found matching your search' : 'No users found'}
                            </div>
                        )}
                    </div>
                )}
            </div>

            {/* Add User Modal */}
            {showAddModal && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
                    <div className="bg-slate-900 rounded-lg border border-slate-800 w-full max-w-md">
                        <div className="p-6 border-b border-slate-800">
                            <h2 className="text-xl font-bold text-white">Add New User</h2>
                        </div>
                        <div className="p-6 space-y-4">
                            <div>
                                <label className="block text-sm font-medium text-slate-300 mb-1">Username *</label>
                                <input
                                    type="text"
                                    value={(formData as AdminUserCreate).username || ''}
                                    onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                                    className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded text-white focus:outline-none focus:border-cyan-500"
                                />
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-slate-300 mb-1">Email</label>
                                <input
                                    type="email"
                                    value={formData.email || ''}
                                    onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                                    className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded text-white focus:outline-none focus:border-cyan-500"
                                />
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-slate-300 mb-1">Full Name</label>
                                <input
                                    type="text"
                                    value={formData.full_name || ''}
                                    onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
                                    className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded text-white focus:outline-none focus:border-cyan-500"
                                />
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-slate-300 mb-1">Password *</label>
                                <input
                                    type="password"
                                    value={(formData as AdminUserCreate).password || ''}
                                    onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                                    className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded text-white focus:outline-none focus:border-cyan-500"
                                />
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-slate-300 mb-1">Role</label>
                                <select
                                    value={formData.role}
                                    onChange={(e) => setFormData({ ...formData, role: e.target.value as 'admin' | 'user' })}
                                    className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded text-white focus:outline-none focus:border-cyan-500"
                                >
                                    <option value="user">User</option>
                                    <option value="admin">Admin</option>
                                </select>
                            </div>
                        </div>
                        <div className="p-6 border-t border-slate-800 flex justify-end gap-3">
                            <button
                                onClick={() => {
                                    setShowAddModal(false);
                                    resetForm();
                                }}
                                className="px-4 py-2 text-slate-300 hover:text-white transition-colors"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={handleAddUser}
                                className="px-4 py-2 bg-cyan-600 hover:bg-cyan-700 text-white rounded transition-colors"
                            >
                                Create User
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Edit User Modal */}
            {showEditModal && selectedUser && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
                    <div className="bg-slate-900 rounded-lg border border-slate-800 w-full max-w-md">
                        <div className="p-6 border-b border-slate-800">
                            <h2 className="text-xl font-bold text-white">Edit User: {selectedUser.username}</h2>
                        </div>
                        <div className="p-6 space-y-4">
                            <div>
                                <label className="block text-sm font-medium text-slate-300 mb-1">Email</label>
                                <input
                                    type="email"
                                    value={formData.email || ''}
                                    onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                                    className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded text-white focus:outline-none focus:border-cyan-500"
                                />
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-slate-300 mb-1">Full Name</label>
                                <input
                                    type="text"
                                    value={formData.full_name || ''}
                                    onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
                                    className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded text-white focus:outline-none focus:border-cyan-500"
                                />
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-slate-300 mb-1">New Password (leave blank to keep current)</label>
                                <input
                                    type="password"
                                    value={(formData as AdminUserUpdate).password || ''}
                                    onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                                    className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded text-white focus:outline-none focus:border-cyan-500"
                                />
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-slate-300 mb-1">Role</label>
                                <select
                                    value={formData.role}
                                    onChange={(e) => setFormData({ ...formData, role: e.target.value as 'admin' | 'user' })}
                                    className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded text-white focus:outline-none focus:border-cyan-500"
                                >
                                    <option value="user">User</option>
                                    <option value="admin">Admin</option>
                                </select>
                            </div>
                            <div className="flex items-center gap-2">
                                <input
                                    type="checkbox"
                                    checked={(formData as AdminUserUpdate).is_active !== false}
                                    onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                                    className="w-4 h-4"
                                />
                                <label className="text-sm text-slate-300">Active</label>
                            </div>
                        </div>
                        <div className="p-6 border-t border-slate-800 flex justify-end gap-3">
                            <button
                                onClick={() => {
                                    setShowEditModal(false);
                                    resetForm();
                                }}
                                className="px-4 py-2 text-slate-300 hover:text-white transition-colors"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={handleUpdateUser}
                                className="px-4 py-2 bg-cyan-600 hover:bg-cyan-700 text-white rounded transition-colors"
                            >
                                Update User
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Stats Modal */}
            {showStatsModal && selectedUser && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4 overflow-y-auto">
                    <div className="bg-slate-900 rounded-lg border border-slate-800 w-full max-w-4xl my-8">
                        <div className="p-6 border-b border-slate-800 flex justify-between items-center">
                            <div>
                                <h2 className="text-xl font-bold text-white">User Statistics: {selectedUser.username}</h2>
                                <p className="text-slate-400 text-sm mt-1">Activity overview for the last 30 days</p>
                            </div>
                            <button
                                onClick={() => setShowStatsModal(false)}
                                className="text-slate-400 hover:text-white transition-colors"
                            >
                                <X size={24} />
                            </button>
                        </div>

                        {userStats ? (
                            <div className="p-6 space-y-6">
                                {/* Stats Grid */}
                                <div className="grid grid-cols-4 gap-4">
                                    <div className="bg-slate-800/50 rounded-lg p-4 border border-slate-700">
                                        <div className="flex items-center gap-2 text-slate-400 text-sm mb-1">
                                            <Activity size={16} />
                                            Total Activities
                                        </div>
                                        <div className="text-2xl font-bold text-white">{userStats.total_activities}</div>
                                    </div>
                                    <div className="bg-slate-800/50 rounded-lg p-4 border border-slate-700">
                                        <div className="flex items-center gap-2 text-slate-400 text-sm mb-1">
                                            <MessageSquare size={16} />
                                            Conversations
                                        </div>
                                        <div className="text-2xl font-bold text-white">{userStats.conversation_count}</div>
                                    </div>
                                    <div className="bg-slate-800/50 rounded-lg p-4 border border-slate-700">
                                        <div className="flex items-center gap-2 text-slate-400 text-sm mb-1">
                                            <Zap size={16} />
                                            Tokens Used
                                        </div>
                                        <div className="text-2xl font-bold text-white">{userStats.total_tokens_used.toLocaleString()}</div>
                                    </div>
                                    <div className="bg-slate-800/50 rounded-lg p-4 border border-slate-700">
                                        <div className="flex items-center gap-2 text-slate-400 text-sm mb-1">
                                            <TrendingUp size={16} />
                                            Success Rate
                                        </div>
                                        <div className="text-2xl font-bold text-white">{userStats.success_rate}%</div>
                                    </div>
                                </div>

                                {/* Activity Breakdown */}
                                <div className="bg-slate-800/50 rounded-lg p-4 border border-slate-700">
                                    <h3 className="text-lg font-semibold text-white mb-3">Activity Breakdown</h3>
                                    <div className="grid grid-cols-2 gap-3">
                                        {Object.entries(userStats.activities_by_type).map(([type, count]) => (
                                            <div key={type} className="flex items-center justify-between">
                                                <span className={`px-2 py-1 rounded text-xs font-medium ${getActivityTypeColor(type)}`}>
                                                    {getActivityTypeLabel(type)}
                                                </span>
                                                <span className="text-white font-medium">{count}</span>
                                            </div>
                                        ))}
                                    </div>
                                </div>

                                {/* Recent Activities */}
                                <div className="bg-slate-800/50 rounded-lg p-4 border border-slate-700">
                                    <h3 className="text-lg font-semibold text-white mb-3">Recent Activities</h3>
                                    <div className="space-y-2 max-h-64 overflow-y-auto">
                                        {userActivities.map((activity) => (
                                            <div
                                                key={activity.id}
                                                className="flex items-center justify-between p-2 bg-slate-900/50 rounded border border-slate-700"
                                            >
                                                <div className="flex items-center gap-3">
                                                    <span className={`px-2 py-1 rounded text-xs ${getActivityTypeColor(activity.activity_type)}`}>
                                                        {getActivityTypeLabel(activity.activity_type)}
                                                    </span>
                                                    <span className={`text-xs ${activity.success ? 'text-green-400' : 'text-red-400'}`}>
                                                        {activity.success ? <CheckCircle size={14} /> : <XCircle size={14} />}
                                                    </span>
                                                    {activity.tokens_used && (
                                                        <span className="text-xs text-slate-400">{activity.tokens_used} tokens</span>
                                                    )}
                                                    {activity.execution_time && (
                                                        <span className="text-xs text-slate-400 flex items-center gap-1">
                                                            <Clock size={12} />
                                                            {activity.execution_time.toFixed(2)}s
                                                        </span>
                                                    )}
                                                </div>
                                                <span className="text-xs text-slate-400">
                                                    {new Date(activity.created_at).toLocaleString()}
                                                </span>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            </div>
                        ) : (
                            <div className="p-12 flex items-center justify-center">
                                <RefreshCw className="animate-spin text-cyan-400" size={32} />
                            </div>
                        )}
                    </div>
                </div>
            )}

            {/* Delete Confirmation */}
            {showDeleteConfirm && selectedUser && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
                    <div className="bg-slate-900 rounded-lg border border-slate-800 w-full max-w-md">
                        <div className="p-6">
                            <h2 className="text-xl font-bold text-white mb-4">Delete User</h2>
                            <p className="text-slate-300 mb-6">
                                Are you sure you want to delete <strong>{selectedUser.username}</strong>? 
                                This action cannot be undone and will delete all associated conversations and activities.
                            </p>
                            <div className="flex justify-end gap-3">
                                <button
                                    onClick={() => setShowDeleteConfirm(false)}
                                    className="px-4 py-2 text-slate-300 hover:text-white transition-colors"
                                >
                                    Cancel
                                </button>
                                <button
                                    onClick={handleDeleteUser}
                                    className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded transition-colors"
                                >
                                    Delete User
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};
