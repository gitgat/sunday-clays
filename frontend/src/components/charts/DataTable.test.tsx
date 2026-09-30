import { screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderWithProviders } from '../../test/render';
import { DataTable, type DataTableProps } from './DataTable';

// An event-first explore result as the API types it: the event is a 'date', so the first text
// column is the status that follows it.
const COLUMNS: DataTableProps['columns'] = [
  { key: 'event', label: 'Event', type: 'date' },
  { key: 'status', label: 'Status', type: 'string' },
  { key: 'value', label: 'Avg score', type: 'number' },
];
const ROWS: DataTableProps['rows'] = [
  { event: '2025-03-02', status: 'member', value: 38.5 },
  { event: '2025-03-09', status: 'guest', value: 31 },
];
const toEvent = (row: DataTableProps['rows'][number]) => `/events/${String(row.event)}`;

function renderTable(props: Partial<DataTableProps> = {}, route = '/explorer') {
  return renderWithProviders(
    <DataTable caption="Avg score by event" columns={COLUMNS} rows={ROWS} {...props} />,
    { route },
  );
}

function linksByRow(): (string | null)[][] {
  return within(screen.getByRole('table', { name: 'Avg score by event' }))
    .getAllByRole('row')
    .slice(1)
    .map((row) =>
      within(row)
        .queryAllByRole('link')
        .map((link) => link.getAttribute('href')),
    );
}

describe('DataTable', () => {
  it('links the first text column by default (D17)', () => {
    renderTable({ rowHref: toEvent });
    expect(screen.getByRole('link', { name: 'member' })).toHaveAttribute(
      'href',
      '/events/2025-03-02',
    );
    expect(linksByRow()).toEqual([['/events/2025-03-02'], ['/events/2025-03-09']]);
  });

  it('links the rowHrefKey column when it names one', () => {
    renderTable({ rowHref: toEvent, rowHrefKey: 'event' });
    expect(screen.getByRole('link', { name: '2025-03-02' })).toHaveAttribute(
      'href',
      '/events/2025-03-02',
    );
    expect(screen.queryByRole('link', { name: 'member' })).toBeNull();
    expect(linksByRow()).toEqual([['/events/2025-03-02'], ['/events/2025-03-09']]);
  });

  it('links nothing when no column has the rowHrefKey', () => {
    renderTable({ rowHref: toEvent, rowHrefKey: 'shooter' });
    expect(linksByRow()).toEqual([[], []]);
  });

  it('links nothing without a rowHref, whatever the rowHrefKey', () => {
    renderTable({ rowHrefKey: 'event' });
    expect(linksByRow()).toEqual([[], []]);
  });

  it('keeps the global round-type filter on a rowHrefKey link', () => {
    renderTable({ rowHref: toEvent, rowHrefKey: 'event' }, '/explorer?rt=super_sporting');
    expect(screen.getByRole('link', { name: '2025-03-09' })).toHaveAttribute(
      'href',
      '/events/2025-03-09?rt=super_sporting',
    );
  });
});
