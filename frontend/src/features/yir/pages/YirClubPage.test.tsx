import { screen, waitFor, within } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { Route, Routes } from 'react-router';
import { afterEach, describe, expect, it } from 'vitest';
import { clearMe, setMe } from '../../../lib/me';
import { expectChartControls, expectExplainer } from '../../../test/charts';
import { LAZY_CHART, LAZY_TEST_TIMEOUT } from '../../../test/lazyChart';
import { server } from '../../../test/msw/server';
import { renderWithProviders } from '../../../test/render';
import { YEAR_BOARD, YIR_2025, leaderboardHandler } from '../mocks';
import { YirClubPage } from './YirClubPage';

function renderYear(year: number) {
  return renderWithProviders(
    <Routes>
      <Route path="/yir/:year" element={<YirClubPage />} />
    </Routes>,
    { route: `/yir/${year}` },
  );
}

const EMPTY_YEAR = {
  ...YIR_2025,
  year: 2019,
  totals: {
    ...YIR_2025.totals,
    year: 2019,
    scored_events: 0,
    held_events: 0,
    rounds: 0,
    shooters: 0,
    clays_thrown: 0,
    clays_broken: 0,
    avg_score: null,
  },
  events: 12,
  newcomers: 0,
  perfect_rounds: 0,
  top_rounds: [],
  mean_head_count: 8,
  busiest: null,
  hardest: null,
  easiest: null,
  trophies: 0,
  previous: null,
};

afterEach(() => clearMe());

describe('YirClubPage', () => {
  it('summarises the year against the one before', async () => {
    server.use(
      http.get('*/api/yir/:year', () => HttpResponse.json(YIR_2025)),
      leaderboardHandler,
    );
    renderYear(2025);
    const glance = await screen.findByRole('region', { name: '2025 at a glance' });
    expect(within(glance).getByText('48 (±0 vs 2024)')).toBeInTheDocument();
    expect(within(glance).getByText('1,267 (+74 vs 2024)')).toBeInTheDocument();
    expect(within(glance).getByText('139 (+14 vs 2024)')).toBeInTheDocument();
    expect(within(glance).getByText('35.27 (+0.83 vs 2024)')).toBeInTheDocument();
    const highlights = screen.getByRole('region', { name: '2025 highlights' });
    expect(within(highlights).getByText('50 by Grimsby, Gregor (Aug 3)')).toBeInTheDocument();
    expect(within(highlights).getByText('Aug 17 (40 shooters)')).toBeInTheDocument();
    expect(within(highlights).getByText('Nov 16')).toBeInTheDocument();
    expect(within(highlights).getByText('612')).toBeInTheDocument();
  });

  it('shows the calendar-year boards as of Dec 31 for a past year', async () => {
    const asOf: (string | null)[] = [];
    const periods: (string | null)[] = [];
    server.use(
      http.get('*/api/yir/:year', () => HttpResponse.json(YIR_2025)),
      http.get('*/api/leaderboards', ({ request }) => {
        asOf.push(new URL(request.url).searchParams.get('as_of'));
        periods.push(new URL(request.url).searchParams.get('period'));
        return HttpResponse.json(YEAR_BOARD);
      }),
    );
    renderYear(2025);
    const most = await screen.findByRole('list', { name: 'Most Sundays' });
    const items = within(most).getAllByRole('listitem');
    expect(items).toHaveLength(5);
    expect(items[0]).toHaveTextContent('1. Hadley, Ike44');
    expect(within(items[0] as HTMLElement).getByRole('link')).toHaveAttribute(
      'href',
      '/yir/2025/shooters/59',
    );
    expect(await screen.findByRole('list', { name: 'Best average' })).toHaveTextContent('44.00');
    await waitFor(() => expect(asOf).toHaveLength(4));
    expect(new Set(asOf)).toEqual(new Set(['2025-12-31']));
    // The calendar year is the leaderboards' ytd period; season is the last 8 Sundays.
    expect(new Set(periods)).toEqual(new Set(['ytd']));
    expect(await screen.findByRole('list', { name: 'Points' })).toBeInTheDocument();
  });

  it('asks for current boards during the current year', async () => {
    const thisYear = new Date().getFullYear();
    const asOf: (string | null)[] = [];
    server.use(
      http.get('*/api/yir/:year', () => HttpResponse.json({ ...YIR_2025, year: thisYear })),
      http.get('*/api/leaderboards', ({ request }) => {
        asOf.push(new URL(request.url).searchParams.get('as_of'));
        return HttpResponse.json({ ...YEAR_BOARD, rows: [] });
      }),
    );
    renderYear(thisYear);
    await waitFor(() => expect(screen.getAllByText('Nobody qualifies yet.')).toHaveLength(4));
    expect(asOf).toEqual([null, null, null, null]);
  });

  it('sends the global round-type filter to the year boards (C10)', async () => {
    const roundTypes: string[][] = [];
    server.use(
      http.get('*/api/yir/:year', () => HttpResponse.json(YIR_2025)),
      http.get('*/api/leaderboards', ({ request }) => {
        roundTypes.push(new URL(request.url).searchParams.getAll('round_type'));
        return HttpResponse.json(YEAR_BOARD);
      }),
    );
    renderWithProviders(
      <Routes>
        <Route path="/yir/:year" element={<YirClubPage />} />
      </Routes>,
      { route: '/yir/2025?rt=super_sporting' },
    );
    await waitFor(() => expect(roundTypes).toHaveLength(4));
    expect(roundTypes).toEqual([
      ['super_sporting'],
      ['super_sporting'],
      ['super_sporting'],
      ['super_sporting'],
    ]);
  });

  it('sends the round-type filter with the year summary too (C10)', async () => {
    const roundTypes: string[][] = [];
    server.use(
      http.get('*/api/yir/:year', ({ request }) => {
        roundTypes.push(new URL(request.url).searchParams.getAll('round_type'));
        return HttpResponse.json(YIR_2025);
      }),
      leaderboardHandler,
    );
    renderWithProviders(
      <Routes>
        <Route path="/yir/:year" element={<YirClubPage />} />
      </Routes>,
      { route: '/yir/2025?rt=super_sporting' },
    );
    await screen.findByRole('region', { name: '2025 at a glance' });
    expect(roundTypes).toEqual([['super_sporting']]);
    expect(screen.queryByText(/Only these lists follow/)).not.toBeInTheDocument();
  });

  it('shows no leaders for a year the club has no scores for', async () => {
    server.use(
      http.get('*/api/yir/:year', () => HttpResponse.json({ ...YIR_2025, year: 2030 })),
      leaderboardHandler,
    );
    renderYear(2030);
    await screen.findByRole('region', { name: '2030 at a glance' });
    expect(screen.queryByRole('region', { name: '2030 leaders' })).not.toBeInTheDocument();
  });

  it(
    'every data chart exposes Table and CSV controls and an explainer',
    async () => {
      server.use(
        http.get('*/api/yir/:year', () => HttpResponse.json(YIR_2025)),
        leaderboardHandler,
      );
      renderYear(2025);
      const chart = await screen.findByRole('region', { name: 'Month by month' }, LAZY_CHART);
      expectChartControls(chart);
      await expectExplainer(chart, 'About this chart', { read: true });
    },
    LAZY_TEST_TIMEOUT,
  );

  it('explains each card in plain language', async () => {
    server.use(
      http.get('*/api/yir/:year', () => HttpResponse.json(YIR_2025)),
      leaderboardHandler,
    );
    renderYear(2025);
    for (const name of ['2025 at a glance', '2025 highlights', '2025 leaders']) {
      const card = await screen.findByRole('region', { name });
      await expectExplainer(card, 'About this card');
    }
  });

  it('links to other years and to your own year', async () => {
    setMe(307);
    server.use(
      http.get('*/api/yir/:year', () => HttpResponse.json(YIR_2025)),
      leaderboardHandler,
    );
    renderYear(2025);
    const years = await screen.findByRole('navigation', { name: 'Other years' });
    expect(within(years).getByRole('link', { name: '2025' })).toHaveAttribute(
      'aria-current',
      'page',
    );
    expect(within(years).getByRole('link', { name: '2024' })).toHaveAttribute('href', '/yir/2024');
    expect(screen.getByRole('link', { name: 'Your 2025' })).toHaveAttribute(
      'href',
      '/yir/2025/shooters/307',
    );
  });

  it('shows dashes for a year without scores', async () => {
    server.use(
      http.get('*/api/yir/:year', () => HttpResponse.json(EMPTY_YEAR)),
      leaderboardHandler,
    );
    renderYear(2019);
    const highlights = await screen.findByRole('region', { name: '2019 highlights' });
    expect(within(highlights).getAllByText('—')).toHaveLength(4);
    expect(screen.getByRole('region', { name: '2019 at a glance' })).toHaveTextContent('—');
    expect(screen.queryByRole('link', { name: /^Your/ })).not.toBeInTheDocument();
  });

  it('reports failed requests', async () => {
    server.use(
      http.get('*/api/yir/:year', () =>
        HttpResponse.json(
          { error: { code: 'internal', message: 'Internal server error' } },
          { status: 500 },
        ),
      ),
    );
    renderYear(2025);
    expect(await screen.findByRole('alert')).toHaveTextContent('Internal server error');
  });

  it('reports a failed leaderboard', async () => {
    server.use(
      http.get('*/api/yir/:year', () => HttpResponse.json(YIR_2025)),
      http.get('*/api/leaderboards', () =>
        HttpResponse.json({ error: { code: 'internal', message: 'x' } }, { status: 500 }),
      ),
    );
    renderYear(2025);
    expect(await screen.findByText('Could not load Most Sundays.')).toBeInTheDocument();
  });
});
