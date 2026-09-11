import { describe, expect, it } from 'vitest';
import type { Conversation } from '../types/conversation';
import {
  assignMissingSourceIds,
  filterConversationTree,
  groupConversationsBySource,
  resolveDefaultSourceId,
} from './conversationTree';

function conv(
  id: string,
  title: string,
  sourceId?: string,
  lastModified = '2026-09-11T10:00:00.000Z',
): Conversation {
  return {
    id,
    title,
    lastModified,
    messages: [],
    selectedSourceId: sourceId,
  };
}

const sources = [
  { source_id: 'hr', friendly_name: 'HR Database', database_name: 'HR', is_primary: false },
  { source_id: 'sales', friendly_name: 'Sales Warehouse', database_name: 'Sales', is_primary: true },
];

describe('groupConversationsBySource', () => {
  it('puts the primary data source first and lists chats under their source', () => {
    const groups = groupConversationsBySource(
      [
        conv('1', 'Top customers', 'sales'),
        conv('2', 'Open roles', 'hr'),
        conv('3', 'Revenue', 'sales', '2026-09-11T12:00:00.000Z'),
      ],
      sources,
    );

    expect(groups.map((g) => g.id)).toEqual(['sales', 'hr']);
    expect(groups[0].isPrimary).toBe(true);
    expect(groups[0].conversations.map((c) => c.id)).toEqual(['3', '1']);
    expect(groups[1].conversations.map((c) => c.title)).toEqual(['Open roles']);
  });

  it('keeps empty data sources as roots and assigns chats without a source to the primary', () => {
    const groups = groupConversationsBySource(
      [conv('1', 'Scratch pad')],
      sources,
    );

    expect(groups.map((g) => g.id)).toEqual(['sales', 'hr']);
    expect(groups.some((g) => g.name === 'Unassigned')).toBe(false);
    expect(groups[0].conversations[0].title).toBe('Scratch pad');
    expect(groups[1].conversations).toHaveLength(0);
  });

  it('groups chats whose source no longer exists under an unknown root', () => {
    const groups = groupConversationsBySource(
      [conv('1', 'Legacy chat', 'retired-source')],
      sources,
    );

    const unknown = groups.find((g) => g.id === 'retired-source');
    expect(unknown?.isUnknown).toBe(true);
    expect(unknown?.conversations).toHaveLength(1);
  });
});

describe('filterConversationTree', () => {
  const groups = groupConversationsBySource(
    [
      conv('1', 'Q1 revenue', 'sales'),
      conv('2', 'Headcount', 'hr'),
    ],
    sources,
  );

  it('keeps a source and all of its chats when the source name matches', () => {
    const filtered = filterConversationTree(groups, 'warehouse');
    expect(filtered).toHaveLength(1);
    expect(filtered[0].id).toBe('sales');
    expect(filtered[0].conversations).toHaveLength(1);
  });

  it('shows only matching chats when the query hits a title', () => {
    const filtered = filterConversationTree(groups, 'headcount');
    expect(filtered.map((g) => g.id)).toEqual(['hr']);
    expect(filtered[0].conversations.map((c) => c.title)).toEqual(['Headcount']);
  });

  it('returns the original tree when the query is empty', () => {
    expect(filterConversationTree(groups, '   ')).toEqual(groups);
  });
});

describe('assignMissingSourceIds', () => {
  it('uses the primary source as the default fallback', () => {
    expect(resolveDefaultSourceId(sources)).toBe('sales');
  });

  it('stamps a fallback source onto chats that are missing one', () => {
    const result = assignMissingSourceIds(
      [conv('1', 'Scratch pad'), conv('2', 'Q1 revenue', 'hr')],
      'sales',
    );

    expect(result.changedIds).toEqual(['1']);
    expect(result.conversations[0].selectedSourceId).toBe('sales');
    expect(result.conversations[1].selectedSourceId).toBe('hr');
  });
});
