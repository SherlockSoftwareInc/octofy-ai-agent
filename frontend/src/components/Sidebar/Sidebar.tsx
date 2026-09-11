import { useEffect, useMemo, useRef, useState } from 'react';
import {
  Plus,
  MessageSquare,
  Trash2,
  Edit2,
  Search,
  MoreVertical,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  User,
  Database,
  Loader2,
} from 'lucide-react';
import type { Conversation } from '../../types/conversation';
import type { DataSourceResponse } from '../../api/client';
import { api } from '../../api/client';
import {
  filterConversationTree,
  groupConversationsBySource,
  resolveDefaultSourceId,
  type ConversationTreeGroup,
} from '../../utils/conversationTree';

interface SidebarProps {
  conversations: Conversation[];
  activeConversationId: string | null;
  selectedSourceId?: string;
  onSelectConversation: (id: string) => void;
  onNewConversation: (sourceId: string) => void;
  onDeleteConversation: (id: string) => void;
  onRenameConversation: (id: string, newTitle: string) => void;
  onOpenProfile?: () => void;
}

export function Sidebar({
  conversations,
  activeConversationId,
  selectedSourceId,
  onSelectConversation,
  onNewConversation,
  onDeleteConversation,
  onRenameConversation,
  onOpenProfile,
}: SidebarProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState('');
  const [activeMenuId, setActiveMenuId] = useState<string | null>(null);
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [dataSources, setDataSources] = useState<DataSourceResponse[]>([]);
  const [sourcesLoading, setSourcesLoading] = useState(true);
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());
  const userCollapsedRef = useRef<Set<string>>(new Set());
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;

    const loadSources = async () => {
      setSourcesLoading(true);
      try {
        const response = await api.dataSources.getAll();
        if (!cancelled) {
          setDataSources(response.data_sources || []);
        }
      } catch (error) {
        console.error('Failed to load data sources for sidebar:', error);
        if (!cancelled) {
          setDataSources([]);
        }
      } finally {
        if (!cancelled) {
          setSourcesLoading(false);
        }
      }
    };

    loadSources();
    return () => {
      cancelled = true;
    };
  }, []);

  const groups = useMemo(
    () => groupConversationsBySource(conversations, dataSources),
    [conversations, dataSources],
  );

  const visibleGroups = useMemo(
    () => filterConversationTree(groups, searchQuery),
    [groups, searchQuery],
  );

  useEffect(() => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      let changed = false;

      for (const group of groups) {
        const shouldExpand =
          group.conversations.length > 0 ||
          group.id === selectedSourceId ||
          group.conversations.some((conv) => conv.id === activeConversationId);

        if (shouldExpand && !userCollapsedRef.current.has(group.id) && !next.has(group.id)) {
          next.add(group.id);
          changed = true;
        }
      }

      return changed ? next : prev;
    });
  }, [groups, selectedSourceId, activeConversationId]);

  const toggleExpanded = (groupId: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(groupId)) {
        next.delete(groupId);
        userCollapsedRef.current.add(groupId);
      } else {
        next.add(groupId);
        userCollapsedRef.current.delete(groupId);
      }
      return next;
    });
  };

  useEffect(() => {
    if (!searchQuery.trim()) return;
    setExpandedIds((prev) => {
      const next = new Set(prev);
      for (const group of visibleGroups) {
        next.add(group.id);
      }
      return next;
    });
  }, [searchQuery, visibleGroups]);

  useEffect(() => {
    if (!activeMenuId) return;

    const handlePointerDown = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setActiveMenuId(null);
      }
    };

    document.addEventListener('mousedown', handlePointerDown);
    return () => document.removeEventListener('mousedown', handlePointerDown);
  }, [activeMenuId]);

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

  const handleNewChat = (sourceId?: string) => {
    const resolved = (
      sourceId ||
      selectedSourceId ||
      resolveDefaultSourceId(dataSources)
    )?.trim();
    if (!resolved) return;

    setExpandedIds((prev) => {
      if (prev.has(resolved)) return prev;
      const next = new Set(prev);
      next.add(resolved);
      return next;
    });
    onNewConversation(resolved);
  };

  const renderConversation = (conv: Conversation) => {
    const isActive = conv.id === activeConversationId;
    const isEditing = editingId === conv.id;
    const showMenu = activeMenuId === conv.id;
    const messageCount = conv.messages?.length || 0;

    return (
      <div
        key={conv.id}
        role="treeitem"
        aria-selected={isActive}
        className={`group relative flex items-center gap-2 ml-3 pl-3 pr-1.5 py-1.5 rounded-md cursor-pointer border-l transition-colors ${
          isActive
            ? 'bg-indigo-600/20 border-indigo-400 text-slate-100'
            : 'border-slate-800 hover:bg-slate-800/70 hover:border-slate-600'
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
            <MessageSquare size={14} className={`flex-shrink-0 ${isActive ? 'text-indigo-300' : 'text-slate-500'}`} />
            <button
              type="button"
              className="flex-1 min-w-0 text-left"
              onClick={() => onSelectConversation(conv.id)}
            >
              <p className="text-sm text-slate-200 truncate leading-5">{conv.title}</p>
              <p className="text-[11px] text-slate-500 truncate">
                {messageCount} message{messageCount !== 1 ? 's' : ''}
              </p>
            </button>
            <div className="relative" ref={showMenu ? menuRef : undefined}>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  setActiveMenuId(showMenu ? null : conv.id);
                }}
                className={`p-1 rounded opacity-0 group-hover:opacity-100 focus:opacity-100 transition-opacity ${
                  showMenu ? 'bg-slate-700 opacity-100' : 'hover:bg-slate-700'
                }`}
                aria-label="More options"
                title="More options"
              >
                <MoreVertical size={14} className="text-slate-400" />
              </button>
              {showMenu && (
                <div className="absolute right-0 mt-1 w-40 bg-slate-800 border border-slate-700 rounded-lg shadow-xl z-50 overflow-hidden">
                  <button
                    type="button"
                    onClick={() => handleRename(conv.id, conv.title)}
                    className="w-full flex items-center gap-2 px-3 py-2 text-sm text-slate-200 hover:bg-slate-700 transition-colors"
                  >
                    <Edit2 size={14} />
                    Rename
                  </button>
                  <button
                    type="button"
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

  const renderGroup = (group: ConversationTreeGroup) => {
    const isExpanded = expandedIds.has(group.id);
    const isCurrentSource = group.id === selectedSourceId;
    const canCreateUnderGroup = !group.isUnknown;

    return (
      <div key={group.id} role="treeitem" aria-expanded={isExpanded} className="mb-1">
        <div
          className={`group flex items-center gap-1 px-1.5 py-1.5 rounded-md cursor-pointer transition-colors ${
            isCurrentSource ? 'bg-slate-800/80' : 'hover:bg-slate-800/60'
          }`}
        >
          <button
            type="button"
            onClick={() => toggleExpanded(group.id)}
            className="p-0.5 rounded text-slate-500 hover:text-slate-300 hover:bg-slate-700 flex-shrink-0"
            aria-label={isExpanded ? `Collapse ${group.name}` : `Expand ${group.name}`}
            title={isExpanded ? 'Collapse' : 'Expand'}
          >
            {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          </button>
          <button
            type="button"
            onClick={() => toggleExpanded(group.id)}
            className="flex items-center gap-2 min-w-0 flex-1 text-left"
            title={group.subtitle || group.name}
          >
            <Database
              size={15}
              className={`flex-shrink-0 ${group.isUnknown ? 'text-amber-400' : 'text-blue-400'}`}
            />
            <span className="text-sm font-medium text-slate-200 truncate">{group.name}</span>
            {group.isPrimary && (
              <span className="text-[10px] uppercase tracking-wide text-indigo-300 bg-indigo-500/15 px-1.5 py-0.5 rounded flex-shrink-0">
                Primary
              </span>
            )}
            <span className="ml-auto text-[11px] text-slate-500 tabular-nums flex-shrink-0">
              {group.conversations.length}
            </span>
          </button>
          {canCreateUnderGroup && (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                handleNewChat(group.id);
              }}
              className="p-1 rounded text-slate-500 hover:text-white hover:bg-slate-700 flex-shrink-0"
              aria-label={`New chat in ${group.name}`}
              title={`New chat in ${group.name}`}
            >
              <Plus size={14} />
            </button>
          )}
        </div>

        {isExpanded && (
          <div role="group" className="mt-0.5 mb-2 space-y-0.5">
            {group.conversations.length === 0 ? (
              <p className="ml-3 pl-3 py-1.5 text-xs text-slate-600 border-l border-slate-800">
                No chats yet
              </p>
            ) : (
              group.conversations.map((conv) => renderConversation(conv))
            )}
          </div>
        )}
      </div>
    );
  };

  const visibleConversationCount = visibleGroups.reduce(
    (sum, group) => sum + group.conversations.length,
    0,
  );

  return (
    <div
      className={`h-full bg-slate-900/50 border-r border-slate-800 flex flex-col flex-shrink-0 transition-all duration-300 ease-in-out overflow-hidden ${
        isCollapsed ? 'w-16 min-w-16' : 'w-72 min-w-72'
      }`}
    >
      <div className="p-4 border-b border-slate-800 flex items-center justify-between">
        {!isCollapsed && (
          <span className="text-sm font-semibold text-slate-400">Conversations</span>
        )}
        <button
          type="button"
          onClick={() => setIsCollapsed(!isCollapsed)}
          className="p-2 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition-colors ml-auto"
          aria-label={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          title={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {isCollapsed ? <ChevronRight size={20} /> : <ChevronLeft size={20} />}
        </button>
      </div>

      {isCollapsed && (
        <div className="p-2 flex flex-col items-center gap-2">
          <button
            type="button"
            onClick={() => handleNewChat()}
            className="p-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white transition-colors"
            aria-label="New chat"
            title="New chat"
          >
            <Plus size={18} />
          </button>
        </div>
      )}

      {!isCollapsed && (
        <>
          <div className="p-4 border-b border-slate-800">
            <button
              type="button"
              onClick={() => handleNewChat()}
              className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white font-medium rounded-lg transition-colors shadow-lg shadow-indigo-500/20"
            >
              <Plus size={18} />
              New Chat
            </button>
          </div>

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

          <div className="flex-1 overflow-y-auto p-2" role="tree" aria-label="Conversations by data source">
            {sourcesLoading ? (
              <div className="flex items-center justify-center gap-2 py-8 text-slate-500 text-sm">
                <Loader2 size={16} className="animate-spin" />
                Loading sources...
              </div>
            ) : visibleGroups.length === 0 ? (
              <div className="text-center py-8 px-4 text-slate-500 text-sm">
                <Database size={32} className="mx-auto mb-2 opacity-50" />
                <p>{searchQuery ? 'No conversations found' : 'No data sources yet'}</p>
                <p className="text-xs mt-1">
                  {searchQuery ? 'Try a different search' : 'Add a data source to start chatting'}
                </p>
              </div>
            ) : (
              visibleGroups.map((group) => renderGroup(group))
            )}
          </div>

          <div className="p-3 border-t border-slate-800 space-y-2">
            {onOpenProfile && (
              <button
                type="button"
                onClick={onOpenProfile}
                className="w-full flex items-center gap-3 px-3 py-2 hover:bg-slate-800 rounded-lg transition-colors text-slate-300 hover:text-white"
              >
                <div className="w-8 h-8 rounded-full bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center">
                  <User size={16} className="text-white" />
                </div>
                <span className="text-sm font-medium">Profile</span>
              </button>
            )}
            <div className="text-xs text-slate-600 text-center">
              {visibleConversationCount} chat{visibleConversationCount !== 1 ? 's' : ''}
              {dataSources.length > 0 ? ` · ${dataSources.length} source${dataSources.length !== 1 ? 's' : ''}` : ''}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
