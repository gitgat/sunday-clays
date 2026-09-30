import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { server } from '../../../test/msw/server';
import { renderWithProviders } from '../../../test/render';
import { hadleyInsights } from '../mocks';
import { InsightsCard, milestoneText, rustText } from './InsightsCard';

describe('insight text helpers', () => {
  it.each([
    [{ effect: -2.1, n: 4, club_effect: -1.3 }, '−2.1 after 3+ weeks off (4 rounds; club −1.3)'],
    [{ effect: 0.4, n: 3, club_effect: null }, '+0.4 after 3+ weeks off (3 rounds; club —)'],
    [{ effect: 0.4, n: 2, club_effect: null }, 'Not enough rounds yet (2 rounds after a break)'],
    [{ effect: null, n: 1, club_effect: null }, 'Not enough rounds yet (1 round after a break)'],
    [{ effect: null, n: 0, club_effect: -1.3 }, 'No 3-week breaks yet'],
  ])('rustText %#', (rust, want) => {
    expect(rustText(rust)).toBe(want);
  });

  it.each([
    [
      { next_events: 50, events_to_go: 6, weekly_rate: 0.9, projected_date: '2026-11-08' },
      '50 Sundays — 6 to go, projected Nov 8, 2026',
    ],
    [
      { next_events: 10, events_to_go: 2, weekly_rate: 0, projected_date: null },
      '10 Sundays — 2 to go',
    ],
    [
      { next_events: 1, events_to_go: 1, weekly_rate: 0, projected_date: null },
      '1 Sunday — 1 to go',
    ],
    [
      { next_events: null, events_to_go: null, weekly_rate: 0.81, projected_date: null },
      'All milestones reached',
    ],
  ])('milestoneText %#', (milestone, want) => {
    expect(milestoneText(milestone)).toBe(want);
  });
});

describe('InsightsCard', () => {
  it('says what date it is as of and that the time filter does not change it', async () => {
    server.use(http.get('*/api/shooters/:id/insights', () => HttpResponse.json(hadleyInsights)));
    renderWithProviders(<InsightsCard shooterId={3} />);
    expect(
      await screen.findByText('As of Sep 27, 2026 · not affected by the time filter'),
    ).toBeVisible();
  });

  it('shows floor/ceiling, bad-day rate, form, rust, wins, percentile, peak and the next milestone', async () => {
    server.use(http.get('*/api/shooters/:id/insights', () => HttpResponse.json(hadleyInsights)));
    renderWithProviders(<InsightsCard shooterId={3} />);
    expect(await screen.findByText('30.9 / 40.0')).toBeInTheDocument();
    expect(screen.getByText('18%')).toBeInTheDocument();
    expect(screen.getByText('Hot (+3.4)')).toBeInTheDocument();
    expect(screen.getByText('2 / 14')).toBeInTheDocument();
    expect(screen.getByText('49%')).toBeInTheDocument();
    expect(screen.getByText('38.2')).toBeInTheDocument();
    expect(screen.getByText('Reached Jun 11, 2023')).toBeInTheDocument();
    expect(screen.getByText('All milestones reached')).toBeInTheDocument();
    // Short values fill the two-column phone grid first; the long Rust and Next milestone texts come last and span
    // the full width below lg, so no value wraps to three lines at 390px.
    expect(screen.getAllByRole('term').map((t) => t.textContent?.replace(/\?$/, ''))).toEqual([
      'Low end / High end',
      'Bad-day rate',
      'Form',
      'Wins / podiums',
      'Field beaten (avg)',
      'Peak rating',
      'Rust',
      'Next milestone',
    ]);
    expect(screen.getByText('All round types')).toBeInTheDocument();
  });

  it('omits the next-milestone projection for a deceased shooter', async () => {
    server.use(
      http.get('*/api/shooters/:id/insights', () =>
        HttpResponse.json({
          ...hadleyInsights,
          milestone: {
            next_events: 25,
            events_to_go: 14,
            weekly_rate: 0.2,
            projected_date: '2027-10-03',
          },
        }),
      ),
    );
    renderWithProviders(<InsightsCard shooterId={41} deceased />);
    const card = await screen.findByRole('region', { name: 'Stats' });
    expect(await within(card).findByText('2 / 14')).toBeInTheDocument();
    expect(within(card).queryByText('Next milestone')).not.toBeInTheDocument();
    expect(within(card).queryByText(/to go/)).not.toBeInTheDocument();
  });

  it('projects the next Sunday milestone from the attendance rate', async () => {
    server.use(
      http.get('*/api/shooters/:id/insights', () =>
        HttpResponse.json({
          ...hadleyInsights,
          milestone: {
            next_events: 50,
            events_to_go: 6,
            weekly_rate: 0.9,
            projected_date: '2026-11-08',
          },
        }),
      ),
    );
    renderWithProviders(<InsightsCard shooterId={3} />);
    expect(
      await screen.findByText('50 Sundays — 6 to go, projected Nov 8, 2026'),
    ).toBeInTheDocument();
  });

  it('shows dashes for a newcomer without enough rounds', async () => {
    server.use(
      http.get('*/api/shooters/:id/insights', () =>
        HttpResponse.json({
          ...hadleyInsights,
          floor: null,
          ceiling: null,
          recent_n: 3,
          bad_day_rate: null,
          form: null,
          form_label: null,
          avg_percentile: null,
          peak_mu: null,
          peak_date: null,
        }),
      ),
    );
    renderWithProviders(<InsightsCard shooterId={3} />);
    expect(await screen.findByText('2 / 14')).toBeInTheDocument();
    expect(screen.getAllByText('—')).toHaveLength(5);
    expect(screen.queryByText(/^Reached/)).not.toBeInTheDocument();
  });

  it('shows "not enough rounds yet" for a low end and high end from fewer than 8 rounds', async () => {
    server.use(
      http.get('*/api/shooters/:id/insights', () =>
        HttpResponse.json({ ...hadleyInsights, floor: 30, ceiling: 41, recent_n: 7 }),
      ),
    );
    renderWithProviders(<InsightsCard shooterId={3} />);
    expect(await screen.findByText('Not enough rounds yet')).toBeInTheDocument();
    expect(screen.queryByText('30.0 / 41.0')).not.toBeInTheDocument();
  });

  it('shows the low end and high end from 8 rounds', async () => {
    server.use(
      http.get('*/api/shooters/:id/insights', () =>
        HttpResponse.json({ ...hadleyInsights, floor: 30, ceiling: 41, recent_n: 8 }),
      ),
    );
    renderWithProviders(<InsightsCard shooterId={3} />);
    expect(await screen.findByText('30.0 / 41.0')).toBeInTheDocument();
  });

  it('opens a plain-language explanation for a stat', async () => {
    server.use(http.get('*/api/shooters/:id/insights', () => HttpResponse.json(hadleyInsights)));
    renderWithProviders(<InsightsCard shooterId={3} />);
    await screen.findByText('2 / 14');
    const toggle = screen.getByRole('button', { name: 'About Rust' });
    await userEvent.click(toggle);
    expect(screen.getByRole('heading', { name: 'What this shows' })).toBeVisible();
    expect(screen.getByText(/28 or more days/)).toBeVisible();
    // The item takes the whole row while its panel is open.
    expect(toggle.closest('dt')?.parentElement).toHaveClass('col-span-2');
  });

  it('says insights are unavailable when the request fails', async () => {
    server.use(
      http.get('*/api/shooters/:id/insights', () =>
        HttpResponse.json(
          { error: { code: 'internal', message: 'Internal server error' } },
          { status: 500 },
        ),
      ),
    );
    renderWithProviders(<InsightsCard shooterId={3} />);
    expect(await screen.findByText('Insights unavailable right now.')).toBeInTheDocument();
  });
});
