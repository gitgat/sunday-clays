import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { delay, http, HttpResponse } from 'msw';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { server } from '../../../test/msw/server';
import {
  captureCsv,
  chartOptionIn,
  expectChartControls,
  expectExplainer,
  openFullscreen,
} from '../../../test/charts';
import { LAZY_CHART, LAZY_TEST_TIMEOUT } from '../../../test/lazyChart';
import { renderWithProviders } from '../../../test/render';
import type { LeaderboardOut } from '../api';
import { leaderboardFixture, moversFixture } from '../mocks';
import { LeaderboardsPage } from './LeaderboardsPage';

function captureRequests(body: LeaderboardOut = leaderboardFixture): URL[] {
  const seen: URL[] = [];
  server.use(
    http.get('*/api/leaderboards', ({ request }) => {
      seen.push(new URL(request.url));
      const params = new URL(request.url).searchParams;
      return HttpResponse.json({
        ...body,
        since: params.get('since'),
        start: params.get('since') ?? body.start,
        end: params.get('as_of') ?? body.end,
      });
    }),
  );
  return seen;
}

function lastRequest(seen: URL[]): URLSearchParams {
  const last = seen.at(-1);
  if (last === undefined) throw new Error('no /api/leaderboards request yet');
  return last.searchParams;
}

async function standingsRows(): Promise<HTMLElement[]> {
  const table = await screen.findByRole('table', { name: 'Leaderboard standings' });
  return within(table).getAllByRole('row').slice(1);
}

function cellTexts(row: HTMLElement | undefined): (string | null)[] {
  if (row === undefined) throw new Error('row missing');
  return within(row)
    .getAllByRole('cell')
    .map((cell) => cell.textContent);
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe('LeaderboardsPage', () => {
  it('lists standings with shared ranks, and formatted values, with no class badges', async () => {
    renderWithProviders(<LeaderboardsPage />, { route: '/leaderboards' });
    const rows = await standingsRows();
    expect(rows.map((row) => cellTexts(row)[0])).toEqual(['1', '2', '2']);
    expect(cellTexts(rows[0])).toEqual(['1', 'Ace, Amy', '45.02', '12']);
    expect(screen.queryByLabelText(/^Class/)).toBeNull();
    expect(screen.queryByText(/classes/i)).toBeNull();
    expect(screen.getByRole('link', { name: /Ace, Amy/ })).toHaveAttribute('href', '/shooters/7');
  });

  it('shows the biggest rating gains under the standings, following the header window and board date', async () => {
    const seen: URLSearchParams[] = [];
    server.use(
      http.get('*/api/leaderboards/movers', ({ request }) => {
        seen.push(new URL(request.url).searchParams);
        return HttpResponse.json(moversFixture);
      }),
    );
    renderWithProviders(<LeaderboardsPage />, { route: '/leaderboards?as_of=2026-09-13' });
    const region = await screen.findByRole('region', { name: 'Biggest rating gains' });
    expect(region).toBeInTheDocument();
    expect(seen.at(-1)?.get('as_of')).toBe('2026-09-13');
    expect(within(region).queryByText(/rank|place/i)).toBeNull();
  });

  it('has no period buttons or start date of its own: the header window is the only date control', async () => {
    renderWithProviders(<LeaderboardsPage />, { route: '/leaderboards' });
    await standingsRows();
    expect(screen.queryByRole('group', { name: 'Period' })).toBeNull();
    expect(screen.queryByLabelText('Start date')).toBeNull();
    expect(screen.queryByRole('button', { name: 'Custom' })).toBeNull();
    expect(screen.queryByText('Time machine')).toBeNull();
  });

  it('sends metric, gauge and status from the controls', async () => {
    const seen = captureRequests();
    const user = userEvent.setup();
    renderWithProviders(<LeaderboardsPage />, { route: '/leaderboards' });
    await standingsRows();
    expect(lastRequest(seen).get('metric')).toBe('avg_score');
    await user.click(screen.getByRole('button', { name: 'Wins' }));
    await user.selectOptions(screen.getByLabelText('Gauge'), 'Not recorded');
    await user.selectOptions(screen.getByLabelText('Shooters'), 'Members');
    await waitFor(() => {
      expect(lastRequest(seen).get('status')).toBe('member');
    });
    const params = lastRequest(seen);
    expect(params.get('metric')).toBe('wins');
    expect(params.get('gauge')).toBe('unspecified');
  });

  it('offers the measures as chips, and as a select for phones', async () => {
    const seen = captureRequests();
    const user = userEvent.setup();
    renderWithProviders(<LeaderboardsPage />, { route: '/leaderboards' });
    await standingsRows();
    const chips = screen.getByRole('group', { name: 'Measure' });
    expect(chips).toHaveClass('hidden', 'sm:flex');
    expect(
      within(chips)
        .getAllByRole('button')
        .map((b) => b.textContent),
    ).toEqual([
      'Average',
      'Avg vs field',
      'Best round',
      'Wins',
      'Podiums',
      'Sundays shot',
      'Rounds',
      'Rating gain',
      'Points',
    ]);
    const select = screen.getByRole('combobox', { name: 'Measure' });
    expect(select.closest('label')).toHaveClass('sm:hidden');
    await user.selectOptions(select, 'Podiums');
    await waitFor(() => {
      expect(lastRequest(seen).get('metric')).toBe('podiums');
    });
  });

  describe('the header window becomes the board', () => {
    it.each([
      ['/leaderboards', 'season', null],
      ['/leaderboards?w=12m', 'rolling_12', null],
      ['/leaderboards?w=ytd', 'ytd', null],
      ['/leaderboards?w=all', 'all_time', null],
      ['/leaderboards?w=3m', 'season', '2026-06-28'],
      ['/leaderboards?w=6m', 'season', '2026-03-28'],
    ])('%s asks for period %s and since %s', async (route, period, since) => {
      const seen = captureRequests();
      renderWithProviders(<LeaderboardsPage />, { route });
      await standingsRows();
      const params = lastRequest(seen);
      expect(params.get('period')).toBe(period);
      expect(params.get('since')).toBe(since);
      expect(params.get('as_of')).toBeNull();
    });

    it('sends a Custom window as since and as_of, and hides the board-as-of control', async () => {
      const seen = captureRequests();
      renderWithProviders(<LeaderboardsPage />, {
        route: '/leaderboards?w=2026-06-01..2026-09-13&as_of=2026-09-06',
      });
      await standingsRows();
      const params = lastRequest(seen);
      expect(params.get('since')).toBe('2026-06-01');
      expect(params.get('as_of')).toBe('2026-09-13');
      expect(screen.queryByLabelText('Board as of')).toBeNull();
    });

    it('a Custom window from Jan 1 is asked for as a start date and the server treats it as YTD', async () => {
      const seen = captureRequests({ ...leaderboardFixture, period: 'ytd', start: '2026-01-01' });
      renderWithProviders(<LeaderboardsPage />, {
        route: '/leaderboards?w=2026-01-01..2026-09-27',
      });
      await standingsRows();
      expect(lastRequest(seen).get('since')).toBe('2026-01-01');
      expect(screen.getByText('Jan 1 – Sep 27')).toBeInTheDocument();
    });

    it('waits for the latest Sunday before it asks for a 3M board', async () => {
      server.use(http.get('*/api/meta', () => new Promise(() => undefined)));
      const seen = captureRequests();
      renderWithProviders(<LeaderboardsPage />, { route: '/leaderboards?w=3m' });
      await new Promise((resolve) => setTimeout(resolve, 50));
      expect(seen).toHaveLength(0);
      expect(screen.getByRole('status', { name: /./ })).toBeInTheDocument();
    });
  });

  describe('the period and its dates above the chart and table', () => {
    it.each([
      ['/leaderboards', 'Last 8 weeks · Aug 3 – Sep 27'],
      ['/leaderboards?w=12m', 'Last 12 months · Aug 3 – Sep 27'],
      ['/leaderboards?w=2026-06-01..2026-09-13', 'Jun 1 – Sep 13'],
    ])('%s reads "%s"', async (route, tag) => {
      captureRequests();
      renderWithProviders(<LeaderboardsPage />, { route });
      await standingsRows();
      // The charts' scope tags name the same dates as the line above them.
      expect(screen.getAllByText(tag).length).toBeGreaterThan(0);
    });

    it('names the board-as-of date in the tag', async () => {
      captureRequests();
      renderWithProviders(<LeaderboardsPage />, { route: '/leaderboards?as_of=2026-09-13' });
      await standingsRows();
      expect(
        screen.getByText('Last 8 weeks as of Sep 13, 2026 · Aug 3 – Sep 13'),
      ).toBeInTheDocument();
    });

    it('spells out both years when the dates cross a year end, and starts All time on the first Sunday', async () => {
      captureRequests({ ...leaderboardFixture, start: '2025-09-29', period: 'rolling_12' });
      renderWithProviders(<LeaderboardsPage />, { route: '/leaderboards?w=12m' });
      await standingsRows();
      expect(screen.getByText('Last 12 months · Sep 29, 2025 – Sep 27, 2026')).toBeInTheDocument();
    });

    it('starts an All time board on the first scored Sunday', async () => {
      captureRequests({ ...leaderboardFixture, start: null, period: 'all_time' });
      renderWithProviders(<LeaderboardsPage />, { route: '/leaderboards?w=all' });
      await standingsRows();
      expect(screen.getByText('All time · Sep 6 – Sep 27')).toBeInTheDocument();
    });

    it('tags the chart with the window it follows, not All time', async () => {
      renderWithProviders(<LeaderboardsPage />, { route: '/leaderboards?w=6m' });
      await standingsRows();
      const region = await screen.findByRole('region', { name: /^Top 3 · / });
      const user = userEvent.setup();
      await user.click(within(region).getByRole('button', { name: 'About this chart' }));
      expect(within(region).getByText(/^Last 6 months( · .+)?$/)).toBeVisible();
      expect(within(region).queryByText('All time')).toBeNull();
    });
  });

  describe('thin and empty windows', () => {
    it('says so, naming the period, and widens to 12M in one tap', async () => {
      captureRequests({ ...leaderboardFixture, event_dates: ['2026-09-13', '2026-09-27'] });
      const user = userEvent.setup();
      const { router } = renderWithProviders(<LeaderboardsPage />, { route: '/leaderboards' });
      await standingsRows();
      expect(screen.getByText('Only 2 Sundays in the last 8 weeks.')).toBeInTheDocument();
      const widen = screen.getByRole('group', { name: 'Widen the window' });
      await user.click(within(widen).getByRole('button', { name: '12M' }));
      expect(router.state.location.search).toBe('?w=12m');
    });

    it('offers All from a 12M window and nothing from All time', async () => {
      captureRequests({ ...leaderboardFixture, event_dates: ['2026-09-27'] });
      const user = userEvent.setup();
      const { router } = renderWithProviders(<LeaderboardsPage />, {
        route: '/leaderboards?w=12m',
      });
      await standingsRows();
      expect(screen.getByText('Only 1 Sunday in the last 12 months.')).toBeInTheDocument();
      const widen = screen.getByRole('group', { name: 'Widen the window' });
      expect(within(widen).queryByRole('button', { name: '12M' })).toBeNull();
      await user.click(within(widen).getByRole('button', { name: 'All' }));
      expect(router.state.location.search).toBe('?w=all');
    });

    it('does not nudge a window with enough Sundays', async () => {
      captureRequests({
        ...leaderboardFixture,
        event_dates: ['2026-08-09', '2026-08-16', '2026-09-06', '2026-09-13', '2026-09-27'],
      });
      renderWithProviders(<LeaderboardsPage />, { route: '/leaderboards' });
      await standingsRows();
      expect(screen.queryByRole('group', { name: 'Widen the window' })).toBeNull();
    });

    it('shows an empty state naming the period, with the widen buttons', async () => {
      captureRequests({ ...leaderboardFixture, rows: [], n_eligible: 0 });
      renderWithProviders(<LeaderboardsPage />, { route: '/leaderboards' });
      expect(await screen.findByText('No one qualifies in the last 8 weeks')).toBeInTheDocument();
      expect(screen.getByText('Needs ≥5 rounds · 0 qualify')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '12M' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'All' })).toBeInTheDocument();
    });

    it('says there are no Sundays at all when the window holds none', async () => {
      captureRequests({ ...leaderboardFixture, rows: [], n_eligible: 0, event_dates: [] });
      renderWithProviders(<LeaderboardsPage />, { route: '/leaderboards?w=6m' });
      expect(
        await screen.findByText('No Sundays with scores in the last 6 months'),
      ).toBeInTheDocument();
    });

    it('dates an empty All time board on its end when there is no first Sunday', async () => {
      captureRequests({
        ...leaderboardFixture,
        rows: [],
        n_eligible: 0,
        event_dates: [],
        start: null,
      });
      renderWithProviders(<LeaderboardsPage />, { route: '/leaderboards?w=all' });
      expect(await screen.findByText('No Sundays with scores in all time')).toBeInTheDocument();
      expect(screen.getByText('All time · Sep 27 – Sep 27')).toBeInTheDocument();
      expect(screen.queryByRole('group', { name: 'Widen the window' })).toBeNull();
    });

    it('never falls back to all-time data under a windowed tag', async () => {
      const seen = captureRequests({ ...leaderboardFixture, rows: [], n_eligible: 0 });
      renderWithProviders(<LeaderboardsPage />, { route: '/leaderboards' });
      await screen.findByText('No one qualifies in the last 8 weeks');
      expect(seen.every((url) => url.searchParams.get('period') !== 'all_time')).toBe(true);
    });
  });

  describe('old URLs convert once into the window', () => {
    it.each([
      ['?period=season', '', 'season', null],
      ['?period=rolling_12', '?w=12m', 'rolling_12', null],
      ['?period=ytd', '?w=ytd', 'ytd', null],
      ['?period=all_time', '?w=all', 'all_time', null],
      [
        '?period=custom&since=2026-06-01&as_of=2026-09-13',
        '?w=2026-06-01..2026-09-13',
        'season',
        '2026-06-01',
      ],
      ['?period=custom', '?w=2026-01-01..2026-09-27', 'season', '2026-01-01'],
      ['?since=2026-06-01', '', 'season', null],
      [
        '?period=ytd&metric=wins&as_of=2026-09-13',
        '?metric=wins&as_of=2026-09-13&w=ytd',
        'ytd',
        null,
      ],
    ])('%s becomes "%s"', async (old, search, period, since) => {
      const seen = captureRequests();
      const { router } = renderWithProviders(<LeaderboardsPage />, {
        route: `/leaderboards${old}`,
      });
      await standingsRows();
      expect(router.state.location.search).toBe(search);
      const params = lastRequest(seen);
      expect(params.get('period')).toBe(period);
      expect(params.get('since')).toBe(since);
      // The first request is already the converted one: the old URL never asks for the wrong window.
      expect(new Set(seen.map((url) => url.search)).size).toBe(1);
    });

    it('an explicit w beats an old period, which is still removed', async () => {
      const { router } = renderWithProviders(<LeaderboardsPage />, {
        route: '/leaderboards?w=6m&period=ytd&since=2026-01-01',
      });
      await standingsRows();
      expect(router.state.location.search).toBe('?w=6m');
    });

    it('a reversed custom range is dropped, leaving the default window', async () => {
      const { router } = renderWithProviders(<LeaderboardsPage />, {
        route: '/leaderboards?period=custom&since=2026-09-27&as_of=2026-09-13',
      });
      await standingsRows();
      expect(router.state.location.search).toBe('?as_of=2026-09-13');
    });

    it('waits for the latest Sunday to fill in a custom end date', async () => {
      server.use(http.get('*/api/meta', () => new Promise(() => undefined)));
      const seen = captureRequests();
      const { router } = renderWithProviders(<LeaderboardsPage />, {
        route: '/leaderboards?period=custom&since=2026-06-01',
      });
      await new Promise((resolve) => setTimeout(resolve, 50));
      expect(seen).toHaveLength(0);
      expect(router.state.location.search).toBe('?period=custom&since=2026-06-01');
    });

    it.each(['rating', 'most_improved'])('metric=%s becomes rating_gain', async (metric) => {
      const seen = captureRequests({ ...leaderboardFixture, metric: 'rating_gain' });
      const { router } = renderWithProviders(<LeaderboardsPage />, {
        route: `/leaderboards?metric=${metric}`,
      });
      await standingsRows();
      expect(router.state.location.search).toBe('?metric=rating_gain');
      expect(lastRequest(seen).get('metric')).toBe('rating_gain');
    });
  });

  it('forwards the global round-type filter', async () => {
    const seen = captureRequests();
    renderWithProviders(<LeaderboardsPage />, { route: '/leaderboards?rt=super_sporting' });
    await standingsRows();
    expect(lastRequest(seen).getAll('round_type')).toEqual(['super_sporting']);
  });

  it('keeps the round-type filter on shooter links', async () => {
    renderWithProviders(<LeaderboardsPage />, { route: '/leaderboards?rt=super_sporting' });
    expect(await screen.findByRole('link', { name: /Ace, Amy/ })).toHaveAttribute(
      'href',
      '/shooters/7?rt=super_sporting',
    );
  });

  it('shows the minimum-rounds note, and hides it when one round is enough', async () => {
    const { unmount } = renderWithProviders(<LeaderboardsPage />, { route: '/leaderboards' });
    expect(await screen.findByText('Needs ≥5 rounds · 3 qualify')).toBeInTheDocument();
    unmount();
    captureRequests({ ...leaderboardFixture, min_rounds_applied: 1 });
    renderWithProviders(<LeaderboardsPage />, { route: '/leaderboards?metric=wins' });
    await standingsRows();
    expect(screen.queryByText(/^Needs ≥/)).toBeNull();
  });

  describe('Board as of', () => {
    it('steps a Sunday back, and forward again to the latest board', async () => {
      const seen = captureRequests();
      const user = userEvent.setup();
      const { router } = renderWithProviders(<LeaderboardsPage />, { route: '/leaderboards' });
      await standingsRows();
      await user.click(screen.getByRole('button', { name: 'Previous Sunday' }));
      await waitFor(() => {
        expect(lastRequest(seen).get('as_of')).toBe('2026-09-13');
      });
      expect(router.state.location.search).toBe('?as_of=2026-09-13');
      await user.click(screen.getByRole('button', { name: 'Next Sunday' }));
      await waitFor(() => {
        expect(lastRequest(seen).get('as_of')).toBeNull();
      });
      expect(router.state.location.search).toBe('');
    });

    it('moves to an earlier event with the slider, and back with Latest', async () => {
      const seen = captureRequests();
      const user = userEvent.setup();
      renderWithProviders(<LeaderboardsPage />, { route: '/leaderboards' });
      await standingsRows();
      fireEvent.change(screen.getByLabelText('Board as of'), { target: { value: '0' } });
      await waitFor(() => {
        expect(lastRequest(seen).get('as_of')).toBe('2026-09-06');
      });
      expect(screen.getByText('Sep 6, 2026', { selector: 'output' })).toBeInTheDocument();
      await user.click(screen.getByRole('button', { name: 'Latest' }));
      await waitFor(() => {
        expect(lastRequest(seen).get('as_of')).toBeNull();
      });
    });

    it('moves only the end: a 3M board counts three months back from the chosen date', async () => {
      const seen = captureRequests();
      renderWithProviders(<LeaderboardsPage />, { route: '/leaderboards?w=3m&as_of=2026-09-13' });
      await standingsRows();
      expect(lastRequest(seen).get('since')).toBe('2026-06-14');
      expect(lastRequest(seen).get('as_of')).toBe('2026-09-13');
    });
  });

  it('explains that rating gain ignores round-type and gauge filters', async () => {
    renderWithProviders(<LeaderboardsPage />, {
      route: '/leaderboards?metric=rating_gain&gauge=SxS',
    });
    expect(
      await screen.findByText('Rating gain ignores the round-type and gauge filters.'),
    ).toBeInTheDocument();
  });

  it('explains the note for a round-type filter alone, and not for other measures', async () => {
    const { unmount } = renderWithProviders(<LeaderboardsPage />, {
      route: '/leaderboards?metric=rating_gain&rt=super_sporting',
    });
    expect(
      await screen.findByText('Rating gain ignores the round-type and gauge filters.'),
    ).toBeInTheDocument();
    unmount();
    renderWithProviders(<LeaderboardsPage />, { route: '/leaderboards?rt=super_sporting' });
    await standingsRows();
    expect(screen.queryByText('Rating gain ignores the round-type and gauge filters.')).toBeNull();
  });

  it('shows an error state when the API fails', async () => {
    server.use(http.get('*/api/leaderboards', () => new HttpResponse(null, { status: 500 })));
    renderWithProviders(<LeaderboardsPage />, { route: '/leaderboards' });
    expect(await screen.findByText('Leaderboard unavailable')).toBeInTheDocument();
  });

  it('keeps the previous board under its own label and format while a new metric loads', async () => {
    server.use(
      http.get('*/api/leaderboards', async ({ request }) => {
        if (new URL(request.url).searchParams.get('metric') === 'wins') {
          await delay(150);
          return HttpResponse.json({ ...leaderboardFixture, metric: 'wins' });
        }
        return HttpResponse.json(leaderboardFixture);
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<LeaderboardsPage />, { route: '/leaderboards' });
    await standingsRows();
    await user.click(screen.getByRole('button', { name: 'Wins' }));
    const table = screen.getByRole('table', { name: 'Leaderboard standings' });
    expect(within(table).getByRole('columnheader', { name: 'Average' })).toBeInTheDocument();
    expect(within(table).getByText('45.02')).toBeInTheDocument();
    expect(screen.getByRole('region', { name: 'Top 3 · Average' })).toBeInTheDocument();
    // The table remounts on the new board, so look it up again.
    expect(
      await screen.findByRole('columnheader', { name: 'Wins' }, { timeout: 5000 }),
    ).toBeInTheDocument();
    const wins = screen.getByRole('table', { name: 'Leaderboard standings' });
    expect(within(wins).getAllByText('45').length).toBeGreaterThan(0);
  });

  it('never asks for classes', async () => {
    const paths: string[] = [];
    server.events.on('request:start', ({ request }) => {
      paths.push(new URL(request.url).pathname);
    });
    renderWithProviders(<LeaderboardsPage />, { route: '/leaderboards?as_of=2026-09-06' });
    await standingsRows();
    expect(paths).toContain('/api/leaderboards');
    expect(paths).not.toContain('/api/classes');
  });

  it.each([
    ['season_points', 'Sundays'],
    ['events', 'Sundays'],
    ['avg_score', 'Rounds'],
    ['wins', 'Rounds'],
    ['rating_gain', 'Rounds'],
  ])('labels the count column of %s "%s"', async (metric, label) => {
    captureRequests({ ...leaderboardFixture, metric } as LeaderboardOut);
    renderWithProviders(<LeaderboardsPage />, { route: `/leaderboards?metric=${metric}` });
    await standingsRows();
    const table = screen.getByRole('table', { name: 'Leaderboard standings' });
    const headers = within(table).getAllByRole('columnheader');
    expect(headers.at(-1)).toHaveTextContent(label);
  });

  it('every data chart exposes Table and CSV controls', async () => {
    renderWithProviders(<LeaderboardsPage />, { route: '/leaderboards' });
    await standingsRows();
    expectChartControls(await screen.findByRole('region', { name: 'Top 3 · Average' }));
  });

  it('explains the chart for the chosen measure and period', async () => {
    renderWithProviders(<LeaderboardsPage />, { route: '/leaderboards?metric=season_points' });
    await standingsRows();
    const region = await screen.findByRole('region', { name: /^Top 3 · / });
    await expectExplainer(region, 'About this chart', { read: true });
  });

  it('names the CSV after the measure and the dates it covers', async () => {
    const csv = captureCsv();
    const user = userEvent.setup();
    renderWithProviders(<LeaderboardsPage />, {
      route: '/leaderboards?w=2026-06-01..2026-09-13',
    });
    await standingsRows();
    const region = await screen.findByRole('region', { name: /^Top 3 · / });
    await user.click(within(region).getByRole('button', { name: 'CSV' }));
    expect(csv.names).toEqual(['leaderboard-avg_score-2026-06-01-to-2026-09-13.csv']);
  });

  it('explains a board that runs from a start date', async () => {
    const user = userEvent.setup();
    renderWithProviders(<LeaderboardsPage />, { route: '/leaderboards?w=6m' });
    await standingsRows();
    const region = await screen.findByRole('region', { name: /^Top 3 · / });
    await user.click(within(region).getByRole('button', { name: 'About this chart' }));
    expect(within(region).getByText(/from the start of your time window/)).toBeVisible();
    expect(within(region).getByText(/40% of the Sundays with scores in your dates/)).toBeVisible();
  });

  describe('the standings table', () => {
    const many: LeaderboardOut = {
      ...leaderboardFixture,
      n_eligible: 13,
      rows: Array.from({ length: 13 }, (_, i) => ({
        rank: i < 9 ? i + 1 : 10,
        shooter_id: 200 + i,
        display_name: `Shooter ${String(i + 1).padStart(2, '0')}`,
        status: 'member' as const,
        value: i < 9 ? 45 - i : 36,
        n_rounds: 12,
      })),
    };

    it('shows ten rows, the tie the cut leaves out, and every row after Show all', async () => {
      captureRequests(many);
      const user = userEvent.setup();
      renderWithProviders(<LeaderboardsPage />, { route: '/leaderboards' });
      expect(await standingsRows()).toHaveLength(10);
      expect(screen.getByText('3 more tied at 36.00')).toBeInTheDocument();
      await user.click(screen.getByRole('button', { name: 'Show all 13' }));
      expect(await standingsRows()).toHaveLength(13);
      expect(screen.queryByRole('button', { name: /Show all/ })).toBeNull();
    });

    it('collapses the list again when the measure changes', async () => {
      server.use(
        http.get('*/api/leaderboards', ({ request }) =>
          HttpResponse.json({
            ...many,
            metric: new URL(request.url).searchParams.get('metric') ?? many.metric,
          }),
        ),
      );
      const user = userEvent.setup();
      renderWithProviders(<LeaderboardsPage />, { route: '/leaderboards' });
      await standingsRows();
      await user.click(screen.getByRole('button', { name: 'Show all 13' }));
      expect(await standingsRows()).toHaveLength(13);
      await user.click(screen.getByRole('button', { name: 'Wins' }));
      await waitFor(async () => {
        expect(await standingsRows()).toHaveLength(10);
      });
    });

    it('gives no Show all for ten or fewer, and no tie note when the cut is between values', async () => {
      renderWithProviders(<LeaderboardsPage />, { route: '/leaderboards' });
      await standingsRows();
      expect(screen.queryByRole('button', { name: /Show all/ })).toBeNull();
    });

    it('says nothing about ties when the tenth row stands alone', async () => {
      captureRequests({
        ...many,
        rows: many.rows.map((row, i) => ({ ...row, value: 50 - i, rank: i + 1 })),
      });
      renderWithProviders(<LeaderboardsPage />, { route: '/leaderboards' });
      await standingsRows();
      expect(screen.queryByText(/more tied at/)).toBeNull();
      expect(screen.getByRole('button', { name: 'Show all 13' })).toBeInTheDocument();
    });
  });

  describe('full data in fullscreen and CSV', () => {
    /** Fourteen shooters: the card draws ten, fullscreen and the CSV hold all of them. */
    const fourteen: LeaderboardOut = {
      ...leaderboardFixture,
      n_eligible: 14,
      rows: Array.from({ length: 14 }, (_, i) => ({
        rank: i + 1,
        shooter_id: 100 + i,
        display_name: `Shooter ${String(i + 1).padStart(2, '0')}`,
        status: 'member' as const,
        value: 45 - i / 2,
        n_rounds: 12,
      })),
    };
    const rowCount = (el: HTMLElement) => within(el).getAllByRole('row').length;

    it(
      'the fullscreen table and CSV list everyone; the card keeps the top ten',
      async () => {
        captureRequests(fourteen);
        const csv = captureCsv();
        const { user } = renderWithProviders(<LeaderboardsPage />, {
          route: '/leaderboards?lb-chart=table',
        });
        const card = await screen.findByRole('region', { name: 'Top 10 · Average' });
        expect(rowCount(card)).toBe(1 + 10);
        const dialog = await openFullscreen(user, card, 'Top 10 · Average');
        expect(within(dialog).getByText('Everyone in the standings.')).toBeInTheDocument();
        expect(rowCount(dialog)).toBe(1 + 14);
        await user.click(within(card).getByRole('button', { name: 'CSV' }));
        await waitFor(() =>
          expect(csv.names).toEqual(['leaderboard-avg_score-2026-08-03-to-2026-09-27.csv']),
        );
        expect((await csv.text()).trimEnd().split('\r\n')).toHaveLength(1 + 14);
      },
      LAZY_TEST_TIMEOUT,
    );

    it(
      'fullscreen draws a bar for everyone, tall enough for each label',
      async () => {
        captureRequests(fourteen);
        const { user } = renderWithProviders(<LeaderboardsPage />, { route: '/leaderboards' });
        const card = await screen.findByRole('region', { name: 'Top 10 · Average' });
        const bars = (o: ReturnType<typeof chartOptionIn>) =>
          ((o.yAxis as { data: string[] }[])[0] as { data: string[] }).data.length;
        await within(card).findByRole('img', { name: /leaders/ }, LAZY_CHART);
        expect(bars(chartOptionIn(card, /leaders/))).toBe(10);
        const dialog = await openFullscreen(user, card, 'Top 10 · Average');
        await within(dialog).findByRole('img', { name: /leaders/ }, LAZY_CHART);
        await waitFor(() => expect(bars(chartOptionIn(dialog, /leaders/))).toBe(14));
        expect(dialog.querySelector('[role="img"]')).toHaveStyle({ height: `${80 + 28 * 14}px` });
      },
      LAZY_TEST_TIMEOUT,
    );
  });
});

describe('LeaderboardsPage insight targets', () => {
  it('rings the board row an insight points to', async () => {
    renderWithProviders(<LeaderboardsPage />, { route: '/leaderboards?lb-board.hl=s:3' });
    const rows = await standingsRows();
    expect(rows.map((r) => r.getAttribute('aria-current'))).toEqual([null, 'true', null]);
    expect(
      screen.getByRole('table', { name: 'Leaderboard standings' }).closest('section'),
    ).toHaveAttribute('id', 'chart-lb-board');
  });
});
