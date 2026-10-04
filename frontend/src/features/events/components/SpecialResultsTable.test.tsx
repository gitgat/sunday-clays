import { screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderWithProviders } from '../../../test/render';
import type { EventResult } from '../api';
import { specialDetail } from '../mocks';
import { SpecialResultsTable } from './SpecialResultsTable';

describe('SpecialResultsTable', () => {
  it('lists every shooter best first, out of the shoot’s own total, with no rank or rating', () => {
    renderWithProviders(<SpecialResultsTable results={specialDetail.results} targetTotal={60} />);
    const table = screen.getByRole('table', { name: 'Results' });
    expect(
      within(table)
        .getAllByRole('columnheader')
        .map((h) => h.textContent),
    ).toEqual(['Shooter', 'Score (of 60)']);
    const rows = within(table)
      .getAllByRole('row')
      .slice(1)
      .map((r) =>
        within(r)
          .getAllByRole('cell')
          .map((c) => c.textContent),
      );
    expect(rows).toEqual([
      ['Hadley, Ike', '55'],
      ['Kaplan, Noel', '51'],
      ['Kim, Pat', '39'],
    ]);
  });

  it('heads the score column with the shoot’s own total', () => {
    renderWithProviders(<SpecialResultsTable results={specialDetail.results} targetTotal={75} />);
    expect(screen.getByRole('columnheader', { name: 'Score (of 75)' })).toBeVisible();
  });

  it('breaks a tie by name and keeps the round-type filter on profile links', () => {
    const [first, second] = specialDetail.results as [EventResult, EventResult];
    renderWithProviders(
      <SpecialResultsTable
        results={[
          { ...first, display_name: 'Zed, Al', score: 40 },
          { ...second, display_name: 'Ace, Amy', score: 40 },
        ]}
        targetTotal={60}
      />,
      { route: '/events/2026-09-20?rt=sporting' },
    );
    const links = within(screen.getByRole('table', { name: 'Results' })).getAllByRole('link');
    expect(links.map((l) => l.textContent)).toEqual(['Ace, Amy', 'Zed, Al']);
    expect(links[0]).toHaveAttribute('href', `/shooters/${second.shooter_id}?rt=sporting`);
  });

  it('breaks a tie on score and name by the round order', () => {
    const [first, second] = specialDetail.results as [EventResult, EventResult];
    renderWithProviders(
      <SpecialResultsTable
        results={[
          { ...first, display_name: 'Ace, Amy', score: 40, ordinal: 2, round_id: 701 },
          { ...second, display_name: 'Ace, Amy', score: 40, ordinal: 1, round_id: 702 },
        ]}
        targetTotal={60}
      />,
    );
    const rows = within(screen.getByRole('table', { name: 'Results' }))
      .getAllByRole('row')
      .slice(1);
    expect(rows).toHaveLength(2);
    expect(rows[0]).toHaveTextContent('Ace, Amy');
  });
});
