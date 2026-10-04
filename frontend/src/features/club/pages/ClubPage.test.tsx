import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import { expectChartControls, expectExplainer } from '../../../test/charts';
import { server } from '../../../test/msw/server';
import { renderWithProviders } from '../../../test/render';
import { distributionModel } from '../charts';
import type * as Charts from '../charts';
import {
  clubAttendance,
  clubCohorts,
  clubConversion,
  clubDistribution,
  clubFirstRounds,
  clubParity,
  clubRegulars,
  clubSummary,
  clubTrends,
} from '../mocks';
import { ClubPage } from './ClubPage';

// The real model, wrapped so a test can count how often the (costliest) chart model is built.
vi.mock('../charts', async (importOriginal) => {
  const actual = await importOriginal<typeof Charts>();
  return { ...actual, distributionModel: vi.fn(actual.distributionModel) };
});

/** Every data chart on the page, by the title of its ChartFrame / ChartCard. */
const CHART_TITLES = [
  'Attendance per Sunday',
  'Shooters and Sundays per year',
  'Seasonality',
  'Turnout vs weather',
  'Score distribution by year',
  'Median and top score',
  'Difficulty by Sunday',
  'Newcomers per year',
  'Newcomer retention',
  'First rounds',
  'Rounds by member status',
  'Guest → member conversion',
  'How open is the competition?',
];

/** A complete C9 QueryResult for the turnout card (POST /api/explore is the explorer feature's endpoint). */
const exploreResult = {
  columns: [
    { key: 'condition', label: 'Condition', type: 'string' },
    { key: 'value', label: 'Attendance (avg)', type: 'number' },
  ],
  rows: [
    { condition: 'clear', value: 24.1 },
    { condition: 'rain', value: 17.5 },
  ],
  n_rounds: 0,
  truncated: false,
};

/**
 * Waits that need many charts on screen: thirteen ECharts inits behind lazy chunks can take over
 * the default 1 s when the whole suite runs with coverage on a busy machine.
 */
const SETTLED = { timeout: 5000 };

const summaryRequests: URLSearchParams[] = [];
const distributionRequests: URLSearchParams[] = [];
const firstRoundRequests: URLSearchParams[] = [];
const serverError = () =>
  HttpResponse.json(
    { error: { code: 'internal', message: 'Internal server error' } },
    { status: 500 },
  );

// Thirteen charts behind lazy chunks: the SETTLED waits below must fit inside the test's own timeout.
describe('ClubPage', { timeout: 15_000 }, () => {
  // The page loads its charts (and ECharts) lazily: load those chunks once up front, so a
  // cold import under a busy test run never eats the waitFor budget of the first test.
  beforeAll(async () => {
    await Promise.all([
      import('../components/ClubCharts'),
      import('../components/TurnoutWeatherCard'),
    ]);
  });

  beforeEach(() => {
    summaryRequests.length = 0;
    distributionRequests.length = 0;
    firstRoundRequests.length = 0;
    server.use(
      http.get('*/api/club/summary', ({ request }) => {
        summaryRequests.push(new URL(request.url).searchParams);
        return HttpResponse.json(clubSummary);
      }),
      http.get('*/api/club/attendance', () => HttpResponse.json(clubAttendance)),
      http.get('*/api/club/cohorts', () => HttpResponse.json(clubCohorts)),
      http.get('*/api/club/distribution', ({ request }) => {
        distributionRequests.push(new URL(request.url).searchParams);
        return HttpResponse.json(clubDistribution);
      }),
      http.get('*/api/club/first-rounds', ({ request }) => {
        firstRoundRequests.push(new URL(request.url).searchParams);
        return HttpResponse.json(clubFirstRounds);
      }),
      http.get('*/api/club/regulars', () => HttpResponse.json(clubRegulars)),
      http.get('*/api/club/conversion', () => HttpResponse.json(clubConversion)),
      http.get('*/api/club/parity', () => HttpResponse.json(clubParity)),
      http.get('*/api/club/trends', () => HttpResponse.json(clubTrends)),
      http.post('*/api/explore', () => HttpResponse.json(exploreResult)),
    );
  });

  it('every data chart exposes Table and CSV controls', async () => {
    renderWithProviders(<ClubPage />, { route: '/club' });
    await waitFor(
      () => expect(screen.getAllByRole('button', { name: /csv/i })).toHaveLength(14),
      SETTLED,
    );
    expect(screen.getAllByRole('button', { name: /table/i })).toHaveLength(14);
    for (const title of CHART_TITLES) {
      expectChartControls(screen.getByRole('region', { name: title }));
    }
  });

  it('explains every chart, stat and regulars list in plain words', async () => {
    renderWithProviders(<ClubPage />, { route: '/club' });
    await waitFor(
      () => expect(screen.getAllByRole('button', { name: 'CSV' })).toHaveLength(14),
      SETTLED,
    );
    for (const title of CHART_TITLES) {
      await expectExplainer(screen.getByRole('region', { name: title }), 'About this chart', {
        read: true,
      });
    }
    // Each stat carries its own "?"; the five headline numbers follow the time window.
    for (const stat of [
      'Sundays with full results',
      'Shooters',
      'Rounds',
      'Clays broken',
      'First scored Sunday',
    ]) {
      expect(await screen.findByRole('button', { name: `About ${stat}` })).toBeInTheDocument();
    }
    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: 'About Sundays with full results' }));
    expect(screen.getByText(/Sundays with only a head count/)).toBeVisible();
    await screen.findByText('Core regulars (2)');
    await expectExplainer(
      screen.getByRole('region', { name: 'Core regulars' }),
      'About Core regulars',
      { read: true },
    );
    await expectExplainer(
      screen.getByRole('region', { name: 'Lapsed regulars' }),
      'About Lapsed regulars',
      { read: true },
    );
  });

  it('tags each chart with the dates it covers', async () => {
    renderWithProviders(<ClubPage />, { route: '/club' });
    await waitFor(
      () => expect(screen.getAllByRole('button', { name: 'CSV' })).toHaveLength(14),
      SETTLED,
    );
    // Time series and the turnout card follow the window; the per-year and all-history charts do not.
    for (const title of [
      'Attendance per Sunday',
      'Median and top score',
      'Difficulty by Sunday',
      'Turnout vs weather',
    ]) {
      expect(
        within(screen.getByRole('region', { name: title })).getByText(/^Last 8 weeks( · .+)?$/),
      ).toBeVisible();
    }
    for (const title of ['Seasonality', 'Score distribution by year', 'Newcomer retention']) {
      expect(
        within(screen.getByRole('region', { name: title })).getByText('All time'),
      ).toBeVisible();
    }
  });

  it('says "all years" on the year-by-year charts, which the time window does not move', async () => {
    renderWithProviders(<ClubPage />, { route: '/club' });
    await waitFor(
      () => expect(screen.getAllByRole('button', { name: 'CSV' })).toHaveLength(14),
      SETTLED,
    );
    for (const title of ['Seasonality', 'Newcomer retention', 'How open is the competition?']) {
      const region = screen.getByRole('region', { name: title });
      expect(within(region).getByText(/ · all years/)).toBeVisible();
    }
    const windowed = screen.getByRole('region', { name: 'Attendance per Sunday' });
    expect(within(windowed).queryByText(/ · all years/)).toBeNull();
  });

  it('a view toggle on one chart does not rebuild the other charts', async () => {
    // Every URL change re-renders the round-type-aware charts; their models must stay put.
    const { user } = renderWithProviders(<ClubPage />, { route: '/club' });
    await waitFor(
      () => expect(screen.getAllByRole('button', { name: 'CSV' })).toHaveLength(14),
      SETTLED,
    );
    const builds = vi.mocked(distributionModel).mock.calls.length;
    const parity = screen.getByRole('region', { name: 'How open is the competition?' });
    await user.click(within(parity).getByRole('button', { name: 'Table' }));
    expect(
      await screen.findByRole('table', { name: 'How open is the competition?' }),
    ).toBeInTheDocument();
    expect(vi.mocked(distributionModel).mock.calls.length).toBe(builds);
  });

  it('nests every chart title under its section heading', async () => {
    renderWithProviders(<ClubPage />, { route: '/club' });
    for (const section of [
      'Attendance',
      'Scores',
      'Membership',
      "Year by year (every year; the time window doesn't apply)",
    ]) {
      expect(screen.getByRole('heading', { level: 2, name: section })).toBeInTheDocument();
    }
    // While loading, the placeholder card is not a second region called "Attendance".
    expect(screen.getAllByRole('region', { name: 'Attendance' })).toHaveLength(1);
    await waitFor(
      () => expect(screen.getAllByRole('button', { name: /csv/i })).toHaveLength(14),
      SETTLED,
    );
    for (const title of CHART_TITLES) {
      expect(screen.getByRole('heading', { level: 3, name: title })).toBeInTheDocument();
    }
    expect(screen.getAllByRole('region', { name: 'Attendance' })).toHaveLength(1);
  });

  it('says which charts the round-type filter does not apply to', async () => {
    renderWithProviders(<ClubPage />, { route: '/club?rt=super_sporting' });
    await waitFor(
      () => expect(screen.getAllByRole('button', { name: /csv/i })).toHaveLength(14),
      SETTLED,
    );
    for (const title of [
      'How open is the competition?',
      'Attendance per Sunday',
      'Newcomer retention',
    ]) {
      expect(screen.getByRole('region', { name: title })).toHaveTextContent('all round types');
    }
    expect(screen.getByRole('region', { name: 'Regulars' })).toHaveTextContent('all round types');
    // These four take the filter (summary, distribution, the explorer).
    for (const title of [
      'Score distribution by year',
      'Rounds by member status',
      'Turnout vs weather',
    ]) {
      expect(screen.getByRole('region', { name: title })).not.toHaveTextContent('all round types');
    }
  });

  it('adds no filter note without a round-type filter', async () => {
    renderWithProviders(<ClubPage />, { route: '/club' });
    await waitFor(
      () => expect(screen.getAllByRole('button', { name: /csv/i })).toHaveLength(14),
      SETTLED,
    );
    expect(screen.queryByText(/all round types/i)).not.toBeInTheDocument();
  });

  it('shows the summary header', async () => {
    renderWithProviders(<ClubPage />, { route: '/club' });
    expect(screen.getByRole('heading', { level: 1, name: 'Club' })).toBeInTheDocument();
    expect(await screen.findByText('310')).toBeInTheDocument();
    expect(screen.getByText('7,480')).toBeInTheDocument();
    expect(screen.getByText('261,461')).toBeInTheDocument();
    expect(screen.getByText('Jan 5, 2020')).toBeInTheDocument();
  });

  it('appends the global round-type filter to the summary and distribution requests', async () => {
    renderWithProviders(<ClubPage />, { route: '/club?rt=super_sporting' });
    await screen.findByText('310');
    await waitFor(() =>
      expect(distributionRequests.at(-1)?.getAll('round_type')).toEqual(['super_sporting']),
    );
    expect(summaryRequests.at(-1)?.getAll('round_type')).toEqual(['super_sporting']);
  });

  it('a failing endpoint only affects its own chart', async () => {
    server.use(http.get('*/api/club/conversion', serverError));
    renderWithProviders(<ClubPage />, { route: '/club' });
    expect(
      await screen.findByText("Couldn't load guest → member conversion", {}, SETTLED),
    ).toBeInTheDocument();
    await waitFor(
      () => expect(screen.getAllByRole('button', { name: /csv/i })).toHaveLength(13),
      SETTLED,
    );
  });

  it('a failing summary hides the header stats and the member chart but keeps the rest', async () => {
    server.use(http.get('*/api/club/summary', serverError));
    renderWithProviders(<ClubPage />, { route: '/club' });
    expect(
      await screen.findByText("Couldn't load rounds by member status", {}, SETTLED),
    ).toBeInTheDocument();
    expect(screen.queryByText('7,480')).not.toBeInTheDocument();
    expect(await screen.findByText('Attendance per Sunday', {}, SETTLED)).toBeInTheDocument();
  });

  it('shows empty states before any events exist', async () => {
    server.use(
      http.get('*/api/club/summary', () =>
        HttpResponse.json({
          ...clubSummary,
          first_event: null,
          last_event: null,
          n_events: 0,
          n_scored_events: 0,
          n_held_events: 0,
          n_rounds: 0,
          n_shooters: 0,
          avg_score: null,
          median_score: null,
          top_score: null,
          n_perfect: 0,
          clays_thrown: 0,
          clays_broken: 0,
          avg_head_count: null,
          shooters_by_status: {},
          status_by_year: [],
        }),
      ),
      http.get('*/api/club/attendance', () => HttpResponse.json([])),
      http.get('*/api/club/cohorts', () => HttpResponse.json([])),
      http.get('*/api/club/distribution', () => HttpResponse.json([])),
      http.get('*/api/club/first-rounds', () =>
        HttpResponse.json({ n: 0, median: null, counts: Array<number>(51).fill(0) }),
      ),
      http.get('*/api/club/conversion', () => HttpResponse.json([])),
      http.get('*/api/club/parity', () => HttpResponse.json([])),
      http.get('*/api/club/trends', () =>
        HttpResponse.json({
          as_of: '2026-09-27',
          years: [],
          events: [],
          months: Array.from({ length: 12 }, (_, i) => ({
            month: i + 1,
            n_events: 0,
            mean_head_count: null,
            mean_median: null,
          })),
        }),
      ),
    );
    renderWithProviders(<ClubPage />, { route: '/club' });
    expect(await screen.findByText('No Sundays yet', {}, SETTLED)).toBeInTheDocument();
    // The slots settle as their own queries resolve, so wait for all eleven.
    await waitFor(() => expect(screen.getAllByText('No data yet')).toHaveLength(11), SETTLED);
    // An empty window says so in plain words, naming the period.
    expect(
      screen.getByText(/No scored Sundays in the last 8 weeks \(Aug 3 – Sep 27\)\./),
    ).toBeInTheDocument();
  });

  it('first rounds: the window by default, the insight window and highlight from a link', async () => {
    renderWithProviders(<ClubPage />, {
      route: '/club?first-rounds.hl=38&first-rounds.from=2016-01-01&first-rounds.to=2026-09-13',
    });
    await waitFor(() => expect(firstRoundRequests.length).toBeGreaterThan(0), SETTLED);
    expect(Object.fromEntries(firstRoundRequests.at(-1) ?? [])).toEqual({
      from: '2016-01-01',
      to: '2026-09-13',
    });
    // The lazy chart replaces its placeholder card: find the loaded frame by its chip.
    const chip = await screen.findByText('Showing what the insight points to.', {}, SETTLED);
    const region = screen.getByRole('region', { name: 'First rounds' });
    expect(region).toContainElement(chip);
    expect(region).toHaveAttribute('id', 'chart-first-rounds');
    // The card says which dates the linked view covers, not just "all time".
    expect(
      within(region).getByText(/First Sundays in Jan 1, 2016 – Sep 13, 2026/),
    ).toBeInTheDocument();
    expect(within(region).getByRole('button', { name: 'About this chart' })).toBeInTheDocument();
  });

  it('first rounds without a link asks for the time window and names its dates', async () => {
    renderWithProviders(<ClubPage />, { route: '/club' });
    await waitFor(() => expect(firstRoundRequests.length).toBeGreaterThan(0), SETTLED);
    expect(Object.fromEntries(firstRoundRequests.at(-1) ?? [])).toEqual({
      from: '2026-08-03',
      to: '2026-09-27',
    });
    const region = await screen.findByRole('region', { name: 'First rounds' }, SETTLED);
    expect(await within(region).findByText(/^First Sundays in the window: /)).toBeInTheDocument();
    // The dates are in the tag, once.
    expect(within(region).getAllByText(/Aug 3 – Sep 27/)).toHaveLength(1);
  });

  it('headline numbers follow the window: tagged with its dates, and asked for it', async () => {
    renderWithProviders(<ClubPage />, { route: '/club?w=12m' });
    expect(
      await screen.findByText('Last 12 months · Sep 28, 2025 – Sep 27, 2026', { selector: 'p' }),
    ).toBeVisible();
    await waitFor(() =>
      expect(
        summaryRequests.some(
          (q) => q.get('since') === '2025-09-28' && q.get('as_of') === '2026-09-27',
        ),
      ).toBe(true),
    );
    // The year-by-year status table is asked for without a window.
    await waitFor(
      () => expect(summaryRequests.some((q) => !q.has('since') && !q.has('as_of'))).toBe(true),
      SETTLED,
    );
  });

  it('shows a dash when a window has rounds but no first Sunday date', async () => {
    server.use(
      http.get('*/api/club/summary', () =>
        HttpResponse.json({ ...clubSummary, first_event: null }),
      ),
    );
    renderWithProviders(<ClubPage />, { route: '/club' });
    expect(await screen.findByText('—')).toBeInTheDocument();
  });

  it('shows the year-by-year section under its own heading', async () => {
    renderWithProviders(<ClubPage />, { route: '/club' });
    const heading = screen.getByRole('heading', {
      level: 2,
      name: "Year by year (every year; the time window doesn't apply)",
    });
    const section = heading.closest('section') as HTMLElement;
    for (const title of ['Newcomers per year', 'Rounds by member status', 'Seasonality']) {
      expect(await within(section).findByRole('heading', { name: title }, SETTLED)).toBeVisible();
    }
    expect(within(section).queryByRole('heading', { name: 'First rounds' })).toBeNull();
  });
});
