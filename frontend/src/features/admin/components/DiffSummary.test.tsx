import { screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderWithProviders } from '../../../test/render';
import { scoresPreview, specialPreview, stalePreview, stationsPreview } from '../mocks';
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

  describe('a special-shoot workbook (Plan 17)', () => {
    function row(label: string) {
      return screen.getByText(label, { selector: 'dt' }).nextElementSibling?.textContent;
    }

    it('shows the Sunday, its name, targets and stations, shooters and what it replaces', () => {
      renderWithProviders(<DiffSummary diff={specialPreview.diff} />);
      expect(row('Sunday')).toBe('Sep 20, 2026');
      expect(row('Special shoot')).toBe('3-Bird Shoot');
      expect(row('Targets')).toBe('60 (10 stations)');
      expect(row('Shooters')).toBe('5');
      expect(row('Replaces')).toBe('—');
      expect(screen.queryByRole('note')).not.toBeInTheDocument();
      expect(screen.queryByText('Rows added')).not.toBeInTheDocument();
    });

    it('lists new names and possible duplicates as the scores preview does', () => {
      renderWithProviders(<DiffSummary diff={specialPreview.diff} />);
      expect(screen.getByText('New names (1)')).toBeInTheDocument();
      expect(screen.getByText('Kim, Pat ↔ Kimm, Pat')).toBeInTheDocument();
    });

    it('names the live import it replaces and warns about weekly rows on that Sunday', () => {
      renderWithProviders(
        <DiffSummary
          diff={{ ...specialPreview.diff, replaces_import: 12, regular_rows_on_date: 3 } as never}
        />,
      );
      expect(row('Replaces')).toBe('Import #12');
      expect(screen.getByRole('note')).toHaveTextContent(
        'The scores workbook has 3 rows on Sep 20, 2026. While this special shoot is live they are left out, and rolling it back brings them back.',
      );
    });

    it('says one row in the singular', () => {
      renderWithProviders(
        <DiffSummary diff={{ ...specialPreview.diff, regular_rows_on_date: 1 } as never} />,
      );
      expect(screen.getByRole('note')).toHaveTextContent('has 1 row on Sep 20, 2026.');
    });
  });
});
