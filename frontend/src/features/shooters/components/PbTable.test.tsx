import { screen, within } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { expectExplainer } from '../../../test/charts';
import { server } from '../../../test/msw/server';
import { renderWithProviders } from '../../../test/render';
import { hadleyRounds } from '../mocks';
import type { PersonalBest } from '../api';
import { PbTable } from './PbTable';

describe('PbTable', () => {
  it('lists the overall PB first, then each year newest first, with links to the event', () => {
    // Plan 06 PbOut: scope 'overall' (key 'all') or 'year' (key = the year).
    const pbs: PersonalBest[] = [
      { scope: 'year', key: '2024', score: 43, event_date: '2024-02-25', round_id: 5900 },
      { scope: 'overall', key: 'all', score: 45, event_date: '2022-04-03', round_id: 3850 },
      { scope: 'year', key: '2026', score: 44, event_date: '2026-02-01', round_id: 6905 },
      { scope: 'year', key: '2025', score: 44, event_date: '2025-02-09', round_id: 6412 },
    ];
    renderWithProviders(<PbTable shooterId={3} pbs={pbs} />);
    const rows = within(screen.getByRole('table', { name: 'Personal bests' }))
      .getAllByRole('row')
      .slice(1);
    expect(
      rows.map((r) =>
        within(r)
          .getAllByRole('cell')
          .map((c) => c.textContent),
      ),
    ).toEqual([
      ['Overall', '45', 'Apr 3, 2022'],
      ['2026', '44', 'Feb 1, 2026'],
      ['2025', '44', 'Feb 9, 2025'],
      ['2024', '43', 'Feb 25, 2024'],
    ]);
    expect(
      within(rows[0] as HTMLElement).getByRole('link', { name: 'Apr 3, 2022' }),
    ).toHaveAttribute('href', '/events/2022-04-03');
  });

  it('event links are visibly links with a 44 px tap target (C10)', () => {
    renderWithProviders(
      <PbTable
        shooterId={3}
        pbs={[{ scope: 'overall', key: 'all', score: 45, event_date: '2022-04-03', round_id: 1 }]}
      />,
    );
    expect(screen.getByRole('link', { name: 'Apr 3, 2022' })).toHaveClass(
      'underline',
      'min-h-11',
      'min-w-11',
    );
  });

  it('points to the splits table for PBs by season, month, round type, gauge and weather', () => {
    renderWithProviders(
      <PbTable
        shooterId={3}
        pbs={[
          { scope: 'overall', key: 'all', score: 45, event_date: '2022-04-03', round_id: 3850 },
        ]}
      />,
    );
    expect(screen.getByText(/the Best column of the Splits chart/)).toBeInTheDocument();
  });

  it('marks a best from the first 5 rounds as early, and only that one', async () => {
    const dates = ['2026-01-04', '2026-01-11', '2026-01-18', '2026-01-25', '2026-02-01'];
    server.use(
      http.get('*/api/shooters/:id/rounds', () =>
        HttpResponse.json(
          [...dates, '2026-02-08', '2026-02-15'].map((event_date, i) => ({
            ...hadleyRounds[0],
            round_id: i + 1,
            event_date,
            score: 30 + i,
          })),
        ),
      ),
    );
    renderWithProviders(
      <PbTable
        shooterId={3}
        pbs={[
          { scope: 'overall', key: 'all', score: 36, event_date: '2026-02-15', round_id: 7 },
          { scope: 'year', key: '2026', score: 34, event_date: '2026-02-01', round_id: 5 },
        ]}
      />,
    );
    // 2026-02-01 has 4 rounds before it (early); 2026-02-15 has 6.
    expect(await screen.findByText('(early)')).toBeInTheDocument();
    const rows = screen.getAllByRole('row').slice(1);
    expect(within(rows[0] as HTMLElement).queryByText('(early)')).toBeNull();
    expect(within(rows[1] as HTMLElement).getByText('(early)')).toBeInTheDocument();
    expect(screen.getByText(/a best from your first 5 rounds/)).toBeInTheDocument();
    expect(screen.queryByText(/pin on the chart/)).toBeNull();
  });

  it('holds back the early footnote until the rounds have loaded', async () => {
    server.use(http.get('*/api/shooters/:id/rounds', () => new Promise(() => {})));
    renderWithProviders(
      <PbTable
        shooterId={3}
        pbs={[
          { scope: 'overall', key: 'all', score: 45, event_date: '2022-04-03', round_id: 3850 },
        ]}
      />,
    );
    expect(screen.getByRole('table', { name: 'Personal bests' })).toBeInTheDocument();
    expect(screen.queryByText(/a best from your first 5 rounds/)).toBeNull();
  });

  it('explains itself', async () => {
    renderWithProviders(
      <PbTable
        shooterId={3}
        pbs={[
          { scope: 'overall', key: 'all', score: 45, event_date: '2022-04-03', round_id: 3850 },
        ]}
      />,
    );
    await expectExplainer(
      screen.getByRole('region', { name: 'Personal bests' }),
      'About personal bests',
      { read: true },
    );
  });

  it('says when there are no personal bests yet', () => {
    renderWithProviders(<PbTable shooterId={3} pbs={[]} />);
    expect(screen.getByText('No personal bests yet')).toBeInTheDocument();
  });

  it('keeps the round-type filter on the event links', () => {
    renderWithProviders(
      <PbTable
        shooterId={3}
        pbs={[
          { scope: 'overall', key: 'all', score: 45, event_date: '2022-04-03', round_id: 3850 },
        ]}
      />,
      { route: '/shooters/3?rt=sporting' },
    );
    expect(screen.getByRole('link', { name: 'Apr 3, 2022' })).toHaveAttribute(
      'href',
      '/events/2022-04-03?rt=sporting',
    );
  });
});
