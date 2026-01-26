import { useState } from 'react';
import { Plus, MessageSquare, Trash2, Edit2, Search, Calendar, Clock, MoreVertical } from 'lucide-react';
import type { Conversation } from '../../types/conversation';

interface SidebarProps {
  conversations: Conversation[];
  activeConversationId: string | null;
  onSelectConversation: (id: string) => void;
  onNewConversation: () => void;
  onDeleteConversation: (id: string) => void;
  onRenameConversation: (id: string, newTitle: string) => void;
}

export function Sidebar({
  conversations,
  activeConversationId,
  onSelectConversation,
  onNewConversation,
  onDeleteConversation,
  onRenameConversation,
}: SidebarProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState('');
  const [activeMenuId, setActiveMenuId] = useState<string | null>(null);

  // Filter conversations by search query
  const filteredConversations = conversations.filter(conv =>
    conv.title.toLowerCase().includes(searchQuery.toLowerCase())
  );

  // Group conversations by time
  const groupedConversations = {
    today: [] as Conversation[],
    yesterday: [] as Conversation[],
    previous7Days: [] as Conversation[],
    previous30Days: [] as Conversation[],
    older: [] as Conversation[],
  };

  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);
  const sevenDaysAgo = new Date(today);
  sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7);
  const thirtyDaysAgo = new Date(today);
  thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);

  filteredConversations.forEach(conv => {
    const convDate = new Date(conv.lastModified);
    if (convDate >= today) {
      groupedConversations.today.push(conv);
    } else if (convDate >= yesterday) {
      groupedConversations.yesterday.push(conv);
    } else if (convDate >= sevenDaysAgo) {
      groupedConversations.previous7Days.push(conv);
    } else if (convDate >= thirtyDaysAgo) {
      groupedConversations.previous30Days.push(conv);
    } else {
      groupedConversations.older.push(conv);
    }
  });

  const handleRename = (id: string, currentTitle: string) => {
    setEditingId(id);
    setEditTitle(currentTitle);
    setActiveMenuId(null);
  };

  const handleSaveRename = (id: string) => {
    if (editTitle.trim()) {
      onRenameConversation(id, editTitle.trim());
    }
    setEditingId(null);
    setEditTitle('');
  };

  const renderConversation = (conv: Conversation) => {
    const isActive = conv.id === activeConversationId;
    const isEditing = editingId === conv.id;
    const showMenu = activeMenuId === conv.id;

    return (
      <div
        key={conv.id}
        className={`group relative flex items-center gap-2 px-3 py-2.5 rounded-lg cursor-pointer transition-all ${
          isActive
            ? 'bg-indigo-600/20 border border-indigo-500/30'
            : 'hover:bg-slate-800 border border-transparent'
        }`}
      >
        {isEditing ? (
          <input
            type="text"
            value={editTitle}
            onChange={(e) => setEditTitle(e.target.value)}
            onBlur={() => handleSaveRename(conv.id)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleSaveRename(conv.id);
              if (e.key === 'Escape') {
                setEditingId(null);
                setEditTitle('');
              }
            }}
            className="flex-1 bg-slate-900 text-slate-200 text-sm px-2 py-1 rounded border border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            autoFocus
            aria-label="Rename conversation"
            title="Rename conversation"
          />
        ) : (
          <>
            <MessageSquare size={16} className="text-slate-400 flex-shrink-0" />
            <div
              className="flex-1 min-w-0"
              onClick={() => onSelectConversation(conv.id)}
            >
              <p className="text-sm text-slate-200 truncate">{conv.title}</p>
              <p className="text-xs text-slate-500 truncate">
                {conv.messages.length} message{conv.messages.length !== 1 ? 's' : ''}
              </p>
            </div>
            <div className="relative">
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setActiveMenuId(showMenu ? null : conv.id);
                }}
                className={`p-1 rounded opacity-0 group-hover:opacity-100 transition-opacity ${
                  showMenu ? 'bg-slate-700' : 'hover:bg-slate-700'
                }`}
                aria-label="More options"
                title="More options"
              >
                <MoreVertical size={14} className="text-slate-400" />
              </button>
              {showMenu && (
                <div className="absolute right-0 mt-1 w-40 bg-slate-800 border border-slate-700 rounded-lg shadow-xl z-50 overflow-hidden">
                  <button
                    onClick={() => handleRename(conv.id, conv.title)}
                    className="w-full flex items-center gap-2 px-3 py-2 text-sm text-slate-200 hover:bg-slate-700 transition-colors"
                  >
                    <Edit2 size={14} />
                    Rename
                  </button>
                  <button
                    onClick={() => {
                      onDeleteConversation(conv.id);
                      setActiveMenuId(null);
                    }}
                    className="w-full flex items-center gap-2 px-3 py-2 text-sm text-red-400 hover:bg-slate-700 transition-colors"
                  >
                    <Trash2 size={14} />
                    Delete
                  </button>
                </div>
              )}
            </div>
          </>
        )}
      </div>
    );
  };

  const renderGroup = (title: string, icon: React.ReactNode, convs: Conversation[]) => {
    if (convs.length === 0) return null;

    return (
      <div className="mb-4">
        <div className="flex items-center gap-2 px-3 py-2 text-xs font-semibold text-slate-500 uppercase tracking-wider">
          {icon}
          <span>{title}</span>
        </div>
        <div className="space-y-1">
          {convs.map(conv => renderConversation(conv))}
        </div>
      </div>
    );
  };

  return (
    <div className="w-72 h-full bg-slate-900/50 border-r border-slate-800 flex flex-col">
      {/* Header */}
      <div className="p-4 border-b border-slate-800">
        <button
          onClick={onNewConversation}
          className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white font-medium rounded-lg transition-colors shadow-lg shadow-indigo-500/20"
        >
          <Plus size={18} />
          New Chat
        </button>
      </div>

      {/* Search */}
      <div className="p-4 border-b border-slate-800">
        <div className="relative">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search conversations..."
            className="w-full pl-9 pr-3 py-2 bg-slate-800/50 text-slate-200 text-sm placeholder-slate-500 rounded-lg border border-slate-700 focus:outline-none focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500"
          />
        </div>
      </div>

      {/* Conversation List */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {filteredConversations.length === 0 ? (
          <div className="text-center py-8 px-4 text-slate-500 text-sm">
            <MessageSquare size={32} className="mx-auto mb-2 opacity-50" />
            <p>{searchQuery ? 'No conversations found' : 'No conversations yet'}</p>
            <p className="text-xs mt-1">Start a new chat to begin</p>
          </div>
        ) : (
          <>
            {renderGroup('Today', <Clock size={12} />, groupedConversations.today)}
            {renderGroup('Yesterday', <Calendar size={12} />, groupedConversations.yesterday)}
            {renderGroup('Previous 7 Days', <Calendar size={12} />, groupedConversations.previous7Days)}
            {renderGroup('Previous 30 Days', <Calendar size={12} />, groupedConversations.previous30Days)}
            {renderGroup('Older', <Calendar size={12} />, groupedConversations.older)}
          </>
        )}
      </div>

      {/* Footer */}
      <div className="p-3 border-t border-slate-800">
        <div className="text-xs text-slate-600 text-center">
          {conversations.length} conversation{conversations.length !== 1 ? 's' : ''}
        </div>
      </div>
    </div>
  );
}
