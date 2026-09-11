import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { Conversation } from '../../types/conversation';

vi.mock('../../api/client', () => ({
  api: {
    dataSources: {
      getAll: vi.fn(),
    },
  },
}));

import { api } from '../../api/client';
import { Sidebar } from './Sidebar';

const getAll = vi.mocked(api.dataSources.getAll);

function conv(id: string, title: string, sourceId?: string): Conversation {
  return {
    id,
    title,
    lastModified: '2026-09-11T12:00:00.000Z',
    messages: [{ id: `${id}-m`, role: 'user', content: 'hi', timestamp: new Date() }],
    selectedSourceId: sourceId,
  };
}

const sources = {
  data_sources: [
    {
      source_id: 'sales',
      friendly_name: 'Sales Warehouse',
      description: '',
      keywords: [],
      server: 'localhost',
      database_name: 'Sales',
      db_type: 'mssql',
      enabled: true,
      is_primary: true,
      object_count: 10,
    },
    {
      source_id: 'hr',
      friendly_name: 'HR Database',
      description: '',
      keywords: [],
      server: 'localhost',
      database_name: 'HR',
      db_type: 'mssql',
      enabled: true,
      is_primary: false,
      object_count: 4,
    },
  ],
};

describe('Sidebar tree', () => {
  beforeEach(() => {
    getAll.mockResolvedValue(sources as never);
  });

  it('renders data sources as roots with chats as children', async () => {
    render(
      <Sidebar
        conversations={[
          conv('c1', 'Q1 revenue', 'sales'),
          conv('c2', 'Headcount', 'hr'),
          conv('c3', 'Scratch pad'),
        ]}
        activeConversationId="c1"
        selectedSourceId="sales"
        onSelectConversation={vi.fn()}
        onNewConversation={vi.fn()}
        onDeleteConversation={vi.fn()}
        onRenameConversation={vi.fn()}
      />,
    );

    await screen.findByText('Sales Warehouse');
    expect(await screen.findByText('Headcount')).toBeInTheDocument();
    expect(screen.getByText('HR Database')).toBeInTheDocument();
    expect(screen.queryByText('Unassigned')).not.toBeInTheDocument();
    expect(screen.getByText('Q1 revenue')).toBeInTheDocument();
    expect(screen.getByText('Scratch pad')).toBeInTheDocument();
    expect(screen.getByLabelText('Conversations by data source')).toBeInTheDocument();
  });

  it('creates a new chat under the hovered data source', async () => {
    const onNewConversation = vi.fn();
    const user = userEvent.setup();

    render(
      <Sidebar
        conversations={[conv('c1', 'Q1 revenue', 'sales')]}
        activeConversationId="c1"
        selectedSourceId="sales"
        onSelectConversation={vi.fn()}
        onNewConversation={onNewConversation}
        onDeleteConversation={vi.fn()}
        onRenameConversation={vi.fn()}
      />,
    );

    await screen.findByText('HR Database');
    await user.click(screen.getByLabelText('New chat in HR Database'));
    expect(onNewConversation).toHaveBeenCalledWith('hr');
  });

  it('collapses a data source so its chats are hidden', async () => {
    const user = userEvent.setup();

    render(
      <Sidebar
        conversations={[conv('c1', 'Q1 revenue', 'sales')]}
        activeConversationId="c1"
        selectedSourceId="sales"
        onSelectConversation={vi.fn()}
        onNewConversation={vi.fn()}
        onDeleteConversation={vi.fn()}
        onRenameConversation={vi.fn()}
      />,
    );

    await screen.findByText('Q1 revenue');
    await user.click(screen.getByLabelText('Collapse Sales Warehouse'));
    expect(screen.queryByText('Q1 revenue')).not.toBeInTheDocument();
  });

  it('filters the tree by conversation title', async () => {
    const user = userEvent.setup();

    render(
      <Sidebar
        conversations={[
          conv('c1', 'Q1 revenue', 'sales'),
          conv('c2', 'Headcount', 'hr'),
        ]}
        activeConversationId="c1"
        selectedSourceId="sales"
        onSelectConversation={vi.fn()}
        onNewConversation={vi.fn()}
        onDeleteConversation={vi.fn()}
        onRenameConversation={vi.fn()}
      />,
    );

    await screen.findByText('Headcount');
    await user.type(screen.getByPlaceholderText('Search conversations...'), 'headcount');

    await waitFor(() => {
      expect(screen.queryByText('Q1 revenue')).not.toBeInTheDocument();
    });
    expect(screen.getByText('Headcount')).toBeInTheDocument();
    expect(screen.getByText('HR Database')).toBeInTheDocument();
  });
});
