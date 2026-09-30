import { screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderWithProviders } from '../../../test/render';
import { scoresPreview, stalePreview, stationsPreview } from '../mocks';
import { DiffSummary } from './DiffSummary';

describe('DiffSummary', () => {
  it('lists removed events prominently for a stale scores file', () => {
    renderWithProviders(<DiffSummary diff={stalePreview.diff} />);
    const removals = screen.getByRole('region', { name: 'Removals' });
    expect(
      within(removals).getByText(/missing 2 events and 36 rows that are live now/),
    ).toBeInTheDocument();
    expect(
      within(within(removals).getByRole('list', { name: 'Removed events' }))
        .getAllByRole('listitem')
        .map((li) => li.textContent),
    ).toEqual(['Sep 13, 2026', 'Sep 27, 2026']);
  });

  it('shows additions, new names and possible duplicates without a removals box', () => {
    renderWithProviders(<DiffSummary diff={scoresPreview.diff} />);
    expect(screen.queryByRole('region', { name: 'Removals' })).not.toBeInTheDocument();
    expect(screen.getByText('Oct 4, 2026')).toBeInTheDocument();
    expect(screen.getByText('New names (1)')).toBeInTheDocument();
    expect(screen.getByText('Hamond, Bennett ↔ Hammond, Bennett')).toBeInTheDocument();
  });

  it('summarizes a long list of added events with a count and an expandable list', () => {
    const dates = Array.from({ length: 6 }, (_, i) => `2026-01-${String(i + 4).padStart(2, '0')}`);
    renderWithProviders(<DiffSummary diff={{ ...scoresPreview.diff, events_added: dates }} />);
    expect(screen.getByText('6 events')).toBeInTheDocument();
    expect(screen.getByText(/Jan 4, 2026, Jan 5, 2026/)).toBeInTheDocument();
  });

  it('shows added, replaced and unchanged weeks and skipped tabs for a stations file', () => {
    renderWithProviders(<DiffSummary diff={stationsPreview.diff} />);
    expect(screen.getByText('Weeks replaced')).toBeInTheDocument();
    expect(screen.getByText('Sep 6, 2026')).toBeInTheDocument();
    expect(screen.getByText('Skipped tabs: 9 20 26')).toBeInTheDocument();
  });

  it('flags removed rows even when no whole event disappears', () => {
    renderWithProviders(<DiffSummary diff={{ ...scoresPreview.diff, rows_removed: 3 }} />);
    expect(screen.getByRole('region', { name: 'Removals' })).toHaveTextContent(
      'missing 0 events and 3 rows',
    );
    expect(screen.queryByRole('list', { name: 'Removed events' })).not.toBeInTheDocument();
  });
});
