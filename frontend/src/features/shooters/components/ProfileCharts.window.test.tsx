import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { delay, http, HttpResponse } from 'msw';
import { beforeEach, describe, expect, it } from 'vitest';
import { LAZY_CHART, LAZY_TEST_TIMEOUT } from '../../../test/lazyChart';
import { openFullscreen } from '../../../test/charts';
import { server } from '../../../test/msw/server';
import { renderWithProviders } from '../../../test/render';
import { stubViewport } from '../../../test/viewport';
import {
  clubDistribution,
  hadleyInsights,
  hadleyRating,
  hadleyRounds,
  hadleySplitsByYear,
} from '../mocks';
import { ProfileCharts } from './ProfileCharts';

const splitRequests: URLSearchParams[] = [];
const distributionRequests: URLSearchParams[] = [];

describe('ProfileCharts follow the time window', { timeout: LAZY_TEST_TIMEOUT }, () => {
  beforeEach(() => {
    splitRequests.length = 0;
    distributionRequests.length = 0;
    server.use(
      http.get('*/api/shooters/:id/rounds', () =>
        HttpResponse.json([
          ...hadleyRounds,
          { ...hadleyRounds[0], round_id: 1, event_date: '2025-11-09', score: 41 },
        ]),
      ),
      http.get('*/api/shooters/:id/rating', () => HttpResponse.json(hadleyRating)),
      http.get('*/api/shooters/:id/insights', () => HttpResponse.json(hadleyInsights)),
      http.get('*/api/shooters/:id/splits', ({ request }) => {
        splitRequests.push(new URL(request.url).searchParams);
        return HttpResponse.json(hadleySplitsByYear);
      }),
      http.get('*/api/club/distribution', ({ request }) => {
        distributionRequests.push(new URL(request.url).searchParams);
        return HttpResponse.json(clubDistribution);
      }),
    );
  });

  it('asks for splits and the club distribution over the window', async () => {
    renderWithProviders(<ProfileCharts shooterId={3} />, { route: '/shooters/3' });
    await screen.findByText('Splits by Year', {}, LAZY_CHART);
    await waitFor(() => expect(distributionRequests.length).toBeGreaterThan(0));
    for (const q of [splitRequests.at(-1), distributionRequests.at(-1)]) {
      expect(q?.get('since')).toBe('2026-08-03');
      expect(q?.get('as_of')).toBe('2026-09-27');
    }
  });

  it('names the window in the splits and distribution tags, not their subtitles', async () => {
    renderWithProviders(<ProfileCharts shooterId={3} />, { route: '/shooters/3' });
    const splits = await screen.findByRole('region', { name: 'Splits by Year' }, LAZY_CHART);
    expect(within(splits).getByText('Last 8 weeks · Aug 3 – Sep 27')).toBeVisible();
    expect(within(splits).queryByText(/the last 8 weeks/)).toBeNull();
    const dist = await screen.findByRole(
      'region',
      { name: 'Score distribution vs club' },
      LAZY_CHART,
    );
    expect(within(dist).getByText('Last 8 weeks · Aug 3 – Sep 27')).toBeVisible();
    expect(within(dist).queryByText(/the last 8 weeks/)).toBeNull();
  });

  it('fullscreen splits and distribution ask for every round, not just the window', async () => {
    stubViewport('desktop');
    const user = userEvent.setup();
    renderWithProviders(<ProfileCharts shooterId={3} />, { route: '/shooters/3' });
    const splits = await screen.findByRole('region', { name: 'Splits by Year' }, LAZY_CHART);
    await openFullscreen(user, splits, 'Splits by Year');
    await waitFor(() => expect(splitRequests.some((q) => !q.has('since'))).toBe(true));
    await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: /close/i }));
    const dist = await screen.findByRole('region', { name: 'Score distribution vs club' });
    await openFullscreen(user, dist, 'Score distribution vs club');
    await waitFor(() => expect(distributionRequests.some((q) => !q.has('since'))).toBe(true));
  });

  it('says so when the window holds none of the shooter’s rounds, naming the period', async () => {
    renderWithProviders(<ProfileCharts shooterId={3} />, {
      route: '/shooters/3?w=2020-01-01..2020-02-01',
    });
    const message = await screen.findByText(
      'No rounds in Jan 1, 2020 – Feb 1, 2020',
      {},
      LAZY_CHART,
    );
    const dist = message.closest('section') as HTMLElement;
    expect(within(dist).getByRole('heading', { name: 'Score distribution vs club' })).toBeVisible();
    expect(within(dist).getByText(/Pick 12M or All/)).toBeVisible();
  });

  it('opens the attendance calendar on the year the window ends in', async () => {
    renderWithProviders(<ProfileCharts shooterId={3} />, {
      route: '/shooters/3?w=2025-01-01..2025-12-31',
    });
    await screen.findByRole('img', { name: 'Attendance calendar for 2025' }, LAZY_CHART);
    expect(screen.getByRole('button', { name: '2025' })).toHaveAttribute('aria-pressed', 'true');
  });

  it('opens on the latest year they shot when the window ends in a later year', async () => {
    renderWithProviders(<ProfileCharts shooterId={3} />, { route: '/shooters/3?w=all' });
    await screen.findByRole('img', { name: 'Attendance calendar for 2026' }, LAZY_CHART);
  });

  it('opens on the latest year at or before the window end when they skipped that year', async () => {
    renderWithProviders(<ProfileCharts shooterId={3} />, {
      route: '/shooters/3?w=2024-01-01..2024-12-31',
    });
    // They shot in 2025 and 2026 only: nothing at or before 2024, so the newest year opens.
    await screen.findByRole('img', { name: 'Attendance calendar for 2026' }, LAZY_CHART);
  });
  it('keeps the loading placeholder until the window resolves, so no all-time chart flashes', async () => {
    let roundsServed = false;
    server.use(
      http.get('*/api/meta', async () => {
        await delay('infinite');
        return new HttpResponse(null, { status: 500 });
      }),
      http.get('*/api/shooters/:id/rounds', () => {
        roundsServed = true;
        return HttpResponse.json(hadleyRounds);
      }),
    );
    renderWithProviders(<ProfileCharts shooterId={3} />, { route: '/shooters/3' });
    await waitFor(() => expect(roundsServed).toBe(true));
    await new Promise((resolve) => setTimeout(resolve, 100));
    // Each chart is still its loading card: a skeleton, no chart controls.
    for (const name of ['Rating', 'Scores over time', 'Finishes', 'Attendance calendar']) {
      const card = screen.getByRole('region', { name });
      expect(within(card).getByRole('status')).toBeInTheDocument();
      expect(within(card).queryByRole('button', { name: 'Table' })).not.toBeInTheDocument();
    }
    expect(screen.queryByRole('img', { name: /Attendance calendar/ })).not.toBeInTheDocument();
  });

  it('still shows the charts, unzoomed, when the latest Sunday lookup fails', async () => {
    server.use(http.get('*/api/meta', () => new HttpResponse(null, { status: 500 })));
    renderWithProviders(<ProfileCharts shooterId={3} />, { route: '/shooters/3' });
    expect(await screen.findByRole('region', { name: 'Finishes' }, LAZY_CHART)).toBeVisible();
  });

  it('says "No rounds in <period>. Last shot <date>." instead of drawing all-time data', async () => {
    const user = userEvent.setup();
    const { router } = renderWithProviders(<ProfileCharts shooterId={3} />, {
      route: '/shooters/3?w=2027-01-01..2027-02-01',
    });
    for (const title of ['Rating', 'Scores over time', 'Finishes']) {
      const card = () => screen.getByRole('region', { name: title });
      await waitFor(
        () =>
          expect(within(card()).getByText('No rounds in Jan 1, 2027 – Feb 1, 2027.')).toBeVisible(),
        LAZY_CHART,
      );
      const region = card();
      expect(within(region).getByText(/^Last shot \w{3} \d{1,2}, 2026\.$/)).toBeVisible();
      expect(within(region).queryByRole('img')).toBeNull();
      // Table, CSV and Fullscreen stay reachable for every round.
      expect(within(region).getByRole('button', { name: 'Fullscreen' })).toBeVisible();
      expect(within(region).getByRole('button', { name: 'CSV' })).toBeVisible();
    }
    const rating = screen.getByRole('region', { name: 'Rating' });
    await user.click(within(rating).getByRole('button', { name: 'Show all time' }));
    expect(router.state.location.search).toContain('w=all');
    expect(await screen.findByRole('img', { name: /Rating over time/ }, LAZY_CHART)).toBeVisible();
  });

  it('trims the Table of a windowed chart to the window, with the note', async () => {
    renderWithProviders(<ProfileCharts shooterId={3} />, {
      route: '/shooters/3?w=2026-09-01..2026-09-30&rating=table',
    });
    // header + 2026-09-06, 09-13, 09-27
    await waitFor(
      () =>
        expect(
          within(screen.getByRole('region', { name: 'Rating' })).getAllByRole('row'),
        ).toHaveLength(4),
      LAZY_CHART,
    );
    const rating = screen.getByRole('region', { name: 'Rating' });
    expect(
      within(rating).getByText(
        'Showing the time window. Open fullscreen or download CSV for every Sunday.',
      ),
    ).toBeVisible();
  });
});
