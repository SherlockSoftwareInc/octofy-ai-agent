import type { Conversation } from '../types/conversation';

export interface ConversationTreeSource {
  source_id: string;
  friendly_name: string;
  database_name?: string;
  is_primary?: boolean;
}

export interface ConversationTreeGroup {
  id: string;
  name: string;
  subtitle?: string;
  isPrimary: boolean;
  isUnknown: boolean;
  conversations: Conversation[];
}

function sortConversations(conversations: Conversation[]): Conversation[] {
  return [...conversations].sort((a, b) => {
    const aTime = new Date(a.lastModified || a.updatedAt || 0).getTime();
    const bTime = new Date(b.lastModified || b.updatedAt || 0).getTime();
    return bTime - aTime;
  });
}

export function resolveDefaultSourceId(
  dataSources: ConversationTreeSource[],
): string | undefined {
  const primary = dataSources.find((source) => source.is_primary);
  return primary?.source_id || dataSources[0]?.source_id;
}

export function assignMissingSourceIds(
  conversations: Conversation[],
  fallbackSourceId: string,
): { conversations: Conversation[]; changedIds: string[] } {
  const changedIds: string[] = [];
  const assigned = conversations.map((conversation) => {
    if (conversation.selectedSourceId?.trim()) return conversation;
    changedIds.push(conversation.id);
    return { ...conversation, selectedSourceId: fallbackSourceId };
  });
  return { conversations: assigned, changedIds };
}

/**
 * Group conversations under data-source roots. Every chat must belong to a
 * source: missing source_id is assigned to the primary (or first) source.
 */
export function groupConversationsBySource(
  conversations: Conversation[],
  dataSources: ConversationTreeSource[],
): ConversationTreeGroup[] {
  const sortedSources = [...dataSources].sort((a, b) => {
    if (a.is_primary && !b.is_primary) return -1;
    if (!a.is_primary && b.is_primary) return 1;
    return a.friendly_name.localeCompare(b.friendly_name);
  });

  const groupsById = new Map<string, ConversationTreeGroup>();

  for (const source of sortedSources) {
    groupsById.set(source.source_id, {
      id: source.source_id,
      name: source.friendly_name,
      subtitle: source.database_name,
      isPrimary: Boolean(source.is_primary),
      isUnknown: false,
      conversations: [],
    });
  }

  const unknownGroups = new Map<string, ConversationTreeGroup>();
  const fallbackSourceId = resolveDefaultSourceId(sortedSources);

  for (const conversation of conversations) {
    const sourceId = conversation.selectedSourceId?.trim() || fallbackSourceId;
    if (!sourceId) continue;

    const known = groupsById.get(sourceId);
    if (known) {
      known.conversations.push(conversation);
      continue;
    }

    let unknown = unknownGroups.get(sourceId);
    if (!unknown) {
      unknown = {
        id: sourceId,
        name: sourceId,
        subtitle: 'Unknown source',
        isPrimary: false,
        isUnknown: true,
        conversations: [],
      };
      unknownGroups.set(sourceId, unknown);
    }
    unknown.conversations.push(conversation);
  }

  const groups = [
    ...sortedSources.map((source) => groupsById.get(source.source_id)!),
    ...unknownGroups.values(),
  ];

  return groups.map((group) => ({
    ...group,
    conversations: sortConversations(group.conversations),
  }));
}

export function filterConversationTree(
  groups: ConversationTreeGroup[],
  searchQuery: string,
): ConversationTreeGroup[] {
  const query = searchQuery.trim().toLowerCase();
  if (!query) return groups;

  return groups
    .map((group) => {
      const sourceMatches =
        group.name.toLowerCase().includes(query) ||
        (group.subtitle?.toLowerCase().includes(query) ?? false);

      if (sourceMatches) return group;

      const matchingConversations = group.conversations.filter((conv) =>
        conv.title.toLowerCase().includes(query),
      );

      if (matchingConversations.length === 0) return null;

      return { ...group, conversations: matchingConversations };
    })
    .filter((group): group is ConversationTreeGroup => group !== null);
}
