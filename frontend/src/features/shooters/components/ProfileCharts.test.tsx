import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import { http, HttpResponse } from 'msw';
import { getInstanceByDom } from 'echarts/core';
import type { EChartsOption } from 'echarts';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  captureCsv,
  chartOptionIn,
  expectChartControls,
  expectExplainer,
  openFullscreen,
} from '../../../test/charts';
import { eventSummaries } from '../../events/mocks';
import { LAZY_CHART, LAZY_TEST_TIMEOUT } from '../../../test/lazyChart';
import { server } from '../../../test/msw/server';
import { renderWithProviders } from '../../../test/render';
import { stubViewport } from '../../../test/viewport';
import {
  clubDistribution,
  hadleyInsights,
  hadleyRating,
  hadleyRounds,
  hadleySpecials,
  hadleySplitsByGauge,
  hadleySplitsByYear,
} from '../mocks';
import { isFinish } from '../charts';
import { ProfileCharts } from './ProfileCharts';

async function openTable(user: ReturnType<typeof userEvent.setup>, title: string) {
  const button = await waitFor(() =>
    within(screen.getByRole('region', { name: title })).getByRole('button', { name: 'Table' }),
  );
  await user.click(button);
  return screen.getByRole('table', { name: title });
}

async function openTableFor(title: string) {
  await userEvent.click(
    within(screen.getByRole('region', { name: title })).getByRole('button', { name: 'Table' }),
  );
  return screen.getByRole('table', { name: title });
}

/** The chart's card once its chart (not the loading placeholder) is on screen. */
async function loadedRegion(title: string) {
  await waitFor(
    () =>
      within(screen.getByRole('region', { name: title })).getByRole('button', { name: 'Table' }),
    LAZY_CHART,
  );
  return screen.getByRole('region', { name: title });
}

/** How each Sunday of `hadleyRounds` played (the Explorer's `difficulty` grouped by event). */
const difficultyByEvent = {
  columns: [
    { key: 'event', label: 'Event', type: 'date' },
    { key: 'value', label: 'How the day played (avg)', type: 'number' },
  ],
  rows: [
    { event: '2026-08-16', value: 1.24 },
    { event: '2026-08-23', value: -0.5 },
    { event: '2026-09-06', value: 0.4 },
  ],
  n_rounds: 0,
  truncated: false,
};

const splitRequests: URLSearchParams[] = [];
const roundRequests: URLSearchParams[] = [];

describe('ProfileCharts', () => {
  beforeEach(() => {
    splitRequests.length = 0;
    roundRequests.length = 0;
    server.use(
      http.get('*/api/shooters/:id/rounds', ({ request }) => {
        roundRequests.push(new URL(request.url).searchParams);
        return HttpResponse.json([
          ...hadleyRounds,
          { ...hadleyRounds[0], round_id: 1, event_date: '2025-11-09', score: 41 },
        ]);
      }),
      http.get('*/api/shooters/:id/rating', () => HttpResponse.json(hadleyRating)),
      http.get('*/api/shooters/:id/insights', () => HttpResponse.json(hadleyInsights)),
      http.get('*/api/shooters/:id/splits', ({ request }) => {
        const params = new URL(request.url).searchParams;
        splitRequests.push(params);
        return HttpResponse.json(
          params.get('by') === 'gauge' ? hadleySplitsByGauge : hadleySplitsByYear,
        );
      }),
      http.get('*/api/club/distribution', () => HttpResponse.json(clubDistribution)),
      http.post('*/api/explore', () => HttpResponse.json(difficultyByEvent)),
    );
  });

  it(
    'every data chart exposes Table and CSV controls',
    async () => {
      renderWithProviders(<ProfileCharts shooterId={3} />, { route: '/shooters/3' });
      await waitFor(
        () => expect(screen.getAllByRole('button', { name: /csv/i })).toHaveLength(8),
        LAZY_CHART,
      );
      expect(screen.getAllByRole('button', { name: /table/i })).toHaveLength(8);
      for (const title of [
        'Rating',
        'Scores over time',
        'Finishes',
        'Score distribution vs club',
        'Learning curve vs club',
        'Splits by Year',
        'Tough days',
        'Attendance calendar 2026',
      ]) {
        // getAll: a ChartFrame data table may repeat a title as a column header (e.g. "Rating").
        expect(screen.getAllByText(title, { exact: true }).length).toBeGreaterThan(0);
      }
    },
    LAZY_TEST_TIMEOUT,
  );

  it(
    'every chart explains itself, says which window it covers and which round types it uses',
    async () => {
      renderWithProviders(<ProfileCharts shooterId={3} />, { route: '/shooters/3?w=6m' });
      await waitFor(
        () => expect(screen.getAllByRole('button', { name: 'About this chart' })).toHaveLength(8),
        LAZY_CHART,
      );
      const tags: Record<string, string> = {
        Rating: 'Last 6 months',
        'Scores over time': 'Last 6 months',
        Finishes: 'Last 6 months',
        'Score distribution vs club': 'Last 6 months',
        'Learning curve vs club': 'All time',
        'Splits by Year': 'Last 6 months',
        'Tough days': 'Last 6 months',
        'Attendance calendar 2026': 'All time',
      };
      for (const [title, tag] of Object.entries(tags)) {
        const region = screen.getByRole('region', { name: title });
        expect(
          within(region).getByText(tag === 'All time' ? tag : new RegExp(`^${tag}( · .+)?$`)),
        ).toBeVisible();
        await expectExplainer(region, undefined, { read: true });
      }
      // Rating and the learning curve ignore the round-type filter, and say so.
      for (const title of ['Rating', 'Learning curve vs club']) {
        const region = screen.getByRole('region', { name: title });
        expect(within(region).getByText('All round types')).toBeVisible();
      }
      expect(screen.getAllByText('All round types')).toHaveLength(2);
    },
    LAZY_TEST_TIMEOUT,
  );

  it(
    'opens the rating and scores charts zoomed to the time window, keeping all history',
    async () => {
      renderWithProviders(<ProfileCharts shooterId={3} />, { route: '/shooters/3' });
      const trend = await screen.findByRole(
        'img',
        { name: /Scores and scores against the day/ },
        LAZY_CHART,
      );
      const zoom = (getInstanceByDom(trend)?.getOption() as { dataZoom: { startValue: number }[] })
        .dataZoom;
      // The 2025-11-09 round is older than 3 months before the latest scored Sunday: index 0, cropped out.
      expect(zoom[0]?.startValue).toBe(1);
      const table = await openTableFor('Scores over time');
      expect(within(table).getAllByRole('row').length).toBeGreaterThan(6);
    },
    LAZY_TEST_TIMEOUT,
  );

  it(
    'switching the split chip requests that split and retitles the chart',
    async () => {
      const user = userEvent.setup();
      renderWithProviders(<ProfileCharts shooterId={3} />, { route: '/shooters/3' });
      await screen.findByText('Splits by Year', {}, LAZY_CHART);
      await user.click(screen.getByRole('button', { name: 'Gauge' }));
      expect(await screen.findByText('Splits by Gauge', {}, LAZY_CHART)).toBeInTheDocument();
      expect(splitRequests.at(-1)?.get('by')).toBe('gauge');
    },
    LAZY_TEST_TIMEOUT,
  );

  it(
    'labels the winter-to-fall split "Time of year"',
    async () => {
      const user = userEvent.setup();
      renderWithProviders(<ProfileCharts shooterId={3} />, { route: '/shooters/3' });
      await screen.findByText('Splits by Year', {}, LAZY_CHART);
      await user.click(screen.getByRole('button', { name: 'Time of year' }));
      expect(await screen.findByText('Splits by Time of year', {}, LAZY_CHART)).toBeInTheDocument();
      expect(splitRequests.at(-1)?.get('by')).toBe('season');
      expect(screen.queryByRole('button', { name: 'Season' })).toBeNull();
    },
    LAZY_TEST_TIMEOUT,
  );

  it(
    'keeps the chips mounted and the old split on screen while the next split loads',
    async () => {
      const user = userEvent.setup();
      let release: () => void = () => {};
      const gate = new Promise<void>((resolve) => {
        release = resolve;
      });
      server.use(
        http.get('*/api/shooters/:id/splits', async ({ request }) => {
          if (new URL(request.url).searchParams.get('by') === 'gauge') await gate;
          return HttpResponse.json(
            new URL(request.url).searchParams.get('by') === 'gauge'
              ? hadleySplitsByGauge
              : hadleySplitsByYear,
          );
        }),
      );
      renderWithProviders(<ProfileCharts shooterId={3} />, { route: '/shooters/3' });
      await screen.findByText('Splits by Year', {}, LAZY_CHART);
      const chip = screen.getByRole('button', { name: 'Gauge' });
      await user.click(chip);
      expect(chip).toHaveAttribute('aria-pressed', 'true');
      expect(screen.getByRole('button', { name: 'Gauge' })).toBe(chip);
      expect(screen.getByText('Splits by Year')).toBeInTheDocument();
      release();
      expect(await screen.findByText('Splits by Gauge', {}, LAZY_CHART)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Gauge' })).toBe(chip);
    },
    LAZY_TEST_TIMEOUT,
  );

  it(
    'never shows another shooter’s splits while a new profile loads',
    async () => {
      let release: () => void = () => {};
      const gate = new Promise<void>((resolve) => {
        release = resolve;
      });
      server.use(
        http.get('*/api/shooters/:id/splits', async ({ params }) => {
          if (params.id === '4') await gate;
          return HttpResponse.json(hadleySplitsByYear);
        }),
      );
      function Switcher() {
        const [id, setId] = useState(3);
        return (
          <>
            <button type="button" onClick={() => setId(4)}>
              Next shooter
            </button>
            <ProfileCharts shooterId={id} />
          </>
        );
      }
      const { user } = renderWithProviders(<Switcher />, { route: '/shooters/3' });
      await screen.findByText('Splits by Year', {}, LAZY_CHART);
      await user.click(screen.getByRole('button', { name: 'Next shooter' }));
      expect(screen.queryByText('Splits by Year')).not.toBeInTheDocument();
      release();
      expect(await screen.findByText('Splits by Year', {}, LAZY_CHART)).toBeInTheDocument();
    },
    LAZY_TEST_TIMEOUT,
  );

  it('keeps the Split by chips inside the Splits card', async () => {
    renderWithProviders(<ProfileCharts shooterId={3} />, { route: '/shooters/3' });
    const region = await screen.findByRole('region', { name: 'Splits by Year' });
    expect(within(region).getByRole('group', { name: 'Split by' })).toBeInTheDocument();
  });

  it('an unknown split in the URL falls back to year', async () => {
    renderWithProviders(<ProfileCharts shooterId={3} />, { route: '/shooters/3?split=bogus' });
    expect(await screen.findByText('Splits by Year')).toBeInTheDocument();
    expect(splitRequests.at(-1)?.get('by')).toBe('year');
  });

  it('the attendance calendar switches between the years the shooter attended', async () => {
    const user = userEvent.setup();
    renderWithProviders(<ProfileCharts shooterId={3} />, { route: '/shooters/3' });
    // The year chips are re-created when the held Sundays arrive: click the loaded chart's chip.
    await screen.findByRole('img', { name: 'Attendance calendar for 2026' }, LAZY_CHART);
    await user.click(screen.getByRole('button', { name: '2025' }));
    expect(await screen.findByText('Attendance calendar 2025')).toBeInTheDocument();
  });

  it("the calendar's Table view keeps the chosen year (year and view use different URL keys)", async () => {
    const user = userEvent.setup();
    const { router } = renderWithProviders(<ProfileCharts shooterId={3} />, {
      route: '/shooters/3',
    });
    await screen.findByRole('img', { name: 'Attendance calendar for 2026' }, LAZY_CHART);
    await user.click(screen.getByRole('button', { name: '2025' }));
    const calendar = await screen.findByRole('region', { name: 'Attendance calendar 2025' });
    await user.click(within(calendar).getByRole('button', { name: 'Table' }));
    expect(screen.getByRole('region', { name: 'Attendance calendar 2025' })).toBeInTheDocument();
    const table = screen.getByRole('table', { name: 'Attendance calendar 2025' });
    // Header + the one 2025 date (2025-11-09, best score 41).
    expect(within(table).getAllByRole('row')).toHaveLength(2);
    expect(within(table).getByText('41')).toBeInTheDocument();
    const params = new URLSearchParams(router.state.location.search);
    expect(params.get('calYear')).toBe('2025');
    expect(params.get('cal')).toBe('table');
  });

  it('appends the global round-type filter to the rounds and splits requests', async () => {
    renderWithProviders(<ProfileCharts shooterId={3} />, { route: '/shooters/3?rt=sporting' });
    await screen.findByText('Splits by Year');
    await waitFor(() => expect(roundRequests.at(-1)?.getAll('round_type')).toEqual(['sporting']));
    expect(splitRequests.at(-1)?.getAll('round_type')).toEqual(['sporting']);
  });

  it(
    'names the hidden club points in the learning curve subtitle',
    async () => {
      server.use(
        http.get('*/api/shooters/:id/insights', () =>
          HttpResponse.json({
            ...hadleyInsights,
            learning_curve: [{ k: 40, value: 1, club_median: 4, n_club: 2 }],
          }),
        ),
      );
      renderWithProviders(<ProfileCharts shooterId={3} />, { route: '/shooters/3' });
      expect(
        await screen.findByText(/not enough rounds yet/, undefined, LAZY_CHART),
      ).toBeInTheDocument();
    },
    LAZY_TEST_TIMEOUT,
  );

  it('shows empty states for a shooter with no rating, rounds or learning curve yet', async () => {
    server.use(
      http.get('*/api/shooters/:id/rounds', () => HttpResponse.json([])),
      http.get('*/api/shooters/:id/rating', () =>
        HttpResponse.json({
          ...hadleyRating,
          points: [],
          current_mu: null,
          peak_mu: null,
          peak_date: null,
        }),
      ),
      http.get('*/api/shooters/:id/insights', () =>
        HttpResponse.json({ ...hadleyInsights, learning_curve: [] }),
      ),
      http.get('*/api/shooters/:id/splits', () => HttpResponse.json([])),
    );
    renderWithProviders(<ProfileCharts shooterId={3} />, { route: '/shooters/3' });
    expect(await screen.findByText('No rating yet')).toBeInTheDocument();
    // Scores over time, the distribution and tough days; the calendar counts Sundays shot.
    expect(await screen.findAllByText('No rounds yet')).toHaveLength(3);
    expect(screen.getByText('No Sundays shot yet')).toBeInTheDocument();
    expect(screen.getByText('Not enough Sundays for a learning curve')).toBeInTheDocument();
    expect(
      screen.getByText(/No rounds in the last 8 weeks \(Aug 3 – Sep 27\)\. Pick 12M or All/),
    ).toBeInTheDocument();
    // An empty split must not strand the shooter: the chips stay so another split can be picked.
    expect(screen.getByRole('group', { name: 'Split by' })).toBeInTheDocument();
  });

  it('shows the club distribution failure inside the distribution card', async () => {
    server.use(
      http.get('*/api/club/distribution', () =>
        HttpResponse.json(
          { error: { code: 'internal', message: 'Internal server error' } },
          { status: 500 },
        ),
      ),
    );
    renderWithProviders(<ProfileCharts shooterId={3} />, { route: '/shooters/3' });
    expect(await screen.findByText("Couldn't load score distribution vs club")).toBeInTheDocument();
  });

  it('links the table rows of the rating, scores and calendar charts to their event, keeping the round-type filter', async () => {
    const user = userEvent.setup();
    renderWithProviders(<ProfileCharts shooterId={3} />, {
      route: '/shooters/3?rt=sporting',
    });
    const linkIn = async (title: string, date: string) => {
      // The titled card is a skeleton until its data and the chart chunk arrive; its Table button marks the chart.
      const table = await waitFor(() =>
        within(screen.getByRole('region', { name: title })).getByRole('button', { name: 'Table' }),
      );
      await user.click(table);
      return within(screen.getByRole('region', { name: title })).getByRole('link', {
        name: date,
      });
    };
    expect(await linkIn('Rating', '2026-08-16')).toHaveAttribute(
      'href',
      '/events/2026-08-16?rt=sporting',
    );
    expect(await linkIn('Scores over time', '2026-09-27')).toHaveAttribute(
      'href',
      '/events/2026-09-27?rt=sporting',
    );
    expect(await linkIn('Attendance calendar 2026', '2026-09-13')).toHaveAttribute(
      'href',
      '/events/2026-09-13?rt=sporting',
    );
  });

  describe('attendance calendar', () => {
    const held = (dates: string[]) =>
      dates.map((event_date) => ({ ...eventSummaries[0], event_date, results_complete: true }));

    it('lists every held Sunday the shooter skipped as missed, even before their first shoot, and only Sundays', async () => {
      const user = userEvent.setup();
      server.use(
        http.get('*/api/events', () =>
          HttpResponse.json([
            ...held(['2026-01-04', '2026-08-09', '2026-08-16', '2026-09-20']),
            { ...eventSummaries[0], event_date: '2026-08-02', results_complete: false },
          ]),
        ),
      );
      renderWithProviders(<ProfileCharts shooterId={3} />, { route: '/shooters/3' });
      const table = await openTable(user, 'Attendance calendar 2026');
      const rows = within(table)
        .getAllByRole('row')
        .slice(1)
        .map((r) =>
          within(r)
            .getAllByRole('cell')
            .map((c) => c.textContent),
        );
      expect(rows.map((r) => r.slice(0, 2))).toEqual([
        ['2026-01-04', 'missed'],
        ['2026-08-09', 'missed'],
        ['2026-08-16', 'shot'],
        ['2026-08-23', 'shot'],
        ['2026-08-30', 'shot'],
        ['2026-09-06', 'shot'],
        ['2026-09-13', 'shot'],
        ['2026-09-20', 'missed'],
        ['2026-09-27', 'shot'],
      ]);
      for (const [date] of rows) expect(new Date(`${String(date)}T00:00:00Z`).getUTCDay()).toBe(0);
    });

    it.each(['mobile', 'desktop'] as const)(
      'names the chart and gives it the same height on a %s viewport',
      async (viewport) => {
        stubViewport(viewport);
        renderWithProviders(<ProfileCharts shooterId={3} />, { route: '/shooters/3' });
        const calendar = await screen.findByRole(
          'img',
          { name: 'Attendance calendar for 2026' },
          LAZY_CHART,
        );
        expect(calendar.style.height).toBe('440px');
      },
    );

    it('explains itself and says it covers all time', async () => {
      renderWithProviders(<ProfileCharts shooterId={3} />, { route: '/shooters/3?w=6m' });
      await screen.findByRole('img', { name: 'Attendance calendar for 2026' }, LAZY_CHART);
      const region = screen.getByRole('region', { name: 'Attendance calendar 2026' });
      expect(within(region).getByText('All time')).toBeVisible();
      await expectExplainer(region, undefined, { read: true });
    });

    it('opens a clicked shot Sunday, keeping the round-type filter and window, and ignores a missed one', async () => {
      const { router } = renderWithProviders(<ProfileCharts shooterId={3} />, {
        route: '/shooters/3?rt=sporting&w=6m',
      });
      const el = await screen.findByRole(
        'img',
        { name: 'Attendance calendar for 2026' },
        LAZY_CHART,
      );
      const chart = getInstanceByDom(el);
      chart?.trigger('click', { seriesName: 'Missed', data: { date: '2026-08-09' } } as never);
      expect(router.state.location.pathname).toBe('/shooters/3');
      const shot = chart?.getOption() as { series: { name: string; data: { date: string }[] }[] };
      const date = shot.series.find((s) => s.name === 'Shot')?.data[0]?.date as string;
      // ECharts routes a real click to the item; drive the handler as it would.
      chart?.trigger('click', { seriesName: 'Shot', data: { date } } as never);
      await waitFor(() => expect(router.state.location.pathname).toBe(`/events/${date}`));
      expect(router.state.location.search).toBe('?rt=sporting&w=6m');
    });

    it('says so when the held Sundays cannot be loaded', async () => {
      server.use(
        http.get('*/api/events', () =>
          HttpResponse.json({ error: { code: 'x', message: 'nope' } }, { status: 500 }),
        ),
      );
      renderWithProviders(<ProfileCharts shooterId={3} />, { route: '/shooters/3' });
      expect(await screen.findByText("Couldn't load attendance calendar 2026")).toBeInTheDocument();
    });

    const special = (event_date: string) => ({
      ...eventSummaries[0],
      event_date,
      results_complete: true,
      kind: 'special' as const,
      label: '3-Bird Shoot',
      target_total: 60,
    });

    async function calendarRows(user: ReturnType<typeof userEvent.setup>) {
      const table = await openTable(user, 'Attendance calendar 2026');
      return within(table)
        .getAllByRole('row')
        .slice(1)
        .map((r) =>
          within(r)
            .getAllByRole('cell')
            .map((c) => c.textContent)
            .slice(0, 2),
        );
    }

    it('shows a special shoot the shooter came to as special, not missed', async () => {
      const user = userEvent.setup();
      server.use(
        http.get('*/api/events', () =>
          HttpResponse.json([...held(['2026-09-13', '2026-09-27']), special('2026-09-20')]),
        ),
        http.get('*/api/shooters/:id/special', () => HttpResponse.json(hadleySpecials)),
      );
      renderWithProviders(<ProfileCharts shooterId={3} />, { route: '/shooters/3' });
      const rows = await calendarRows(user);
      expect(rows).toContainEqual(['2026-09-20', 'special']);
      expect(rows).not.toContainEqual(['2026-09-20', 'missed']);
    });

    it('never counts a special shoot the shooter skipped as missed', async () => {
      const user = userEvent.setup();
      server.use(
        http.get('*/api/events', () =>
          HttpResponse.json([...held(['2026-09-13']), special('2026-09-20')]),
        ),
      );
      renderWithProviders(<ProfileCharts shooterId={3} />, { route: '/shooters/3' });
      const rows = await calendarRows(user);
      expect(rows.map(([date]) => date)).not.toContain('2026-09-20');
    });

    it('a shooter with only a special shoot still gets a calendar', async () => {
      const user = userEvent.setup();
      server.use(
        http.get('*/api/shooters/:id/rounds', () => HttpResponse.json([])),
        http.get('*/api/events', () => HttpResponse.json([special('2026-09-20')])),
        http.get('*/api/shooters/:id/special', () => HttpResponse.json(hadleySpecials)),
      );
      renderWithProviders(<ProfileCharts shooterId={340} />, { route: '/shooters/340' });
      expect(await calendarRows(user)).toEqual([['2026-09-20', 'special']]);
      expect(screen.queryByText('No Sundays shot yet')).not.toBeInTheDocument();
    });

    it('counts a special shoot in Sundays shot per month', async () => {
      const user = userEvent.setup();
      server.use(http.get('*/api/shooters/:id/special', () => HttpResponse.json(hadleySpecials)));
      renderWithProviders(<ProfileCharts shooterId={3} />, {
        route: '/shooters/3?cal.view=month',
      });
      const table = await openTable(user, 'Sundays shot per month');
      const september = within(table).getByRole('row', { name: /2026-09/ });
      expect(
        within(september)
          .getAllByRole('cell')
          .map((c) => c.textContent),
      ).toEqual(['2026-09', '4']);
    });

    it('opens a clicked special shoot', async () => {
      server.use(
        http.get('*/api/events', () =>
          HttpResponse.json([...held(['2026-09-13']), special('2026-09-20')]),
        ),
        http.get('*/api/shooters/:id/special', () => HttpResponse.json(hadleySpecials)),
      );
      const { router } = renderWithProviders(<ProfileCharts shooterId={3} />, {
        route: '/shooters/3',
      });
      const el = await screen.findByRole(
        'img',
        { name: 'Attendance calendar for 2026' },
        LAZY_CHART,
      );
      getInstanceByDom(el)?.trigger('click', {
        seriesName: 'Special',
        data: { date: '2026-09-20' },
      } as never);
      await waitFor(() => expect(router.state.location.pathname).toBe('/events/2026-09-20'));
    });
  });

  it(
    'draws the line an insight asks for, and lets the reader pick another',
    async () => {
      const user = userEvent.setup();
      renderWithProviders(<ProfileCharts shooterId={3} />, {
        route: '/shooters/3?trend.line=roll10',
      });
      const region = await loadedRegion('Scores over time');
      expect(within(region).getByRole('button', { name: '10-Sunday average' })).toHaveAttribute(
        'aria-pressed',
        'true',
      );
      await user.click(within(region).getByRole('button', { name: 'Table' }));
      expect(
        within(region).getByRole('columnheader', { name: '10-Sunday average' }),
      ).toBeInTheDocument();
      await user.click(within(region).getByRole('button', { name: 'No line' }));
      expect(within(region).queryByRole('columnheader', { name: '10-Sunday average' })).toBeNull();
      await expectExplainer(region);
    },
    LAZY_TEST_TIMEOUT,
  );

  it(
    'draws the 20-Sunday line over all time',
    async () => {
      renderWithProviders(<ProfileCharts shooterId={3} />, {
        route: '/shooters/3?w=all&trend.line=roll20',
      });
      const region = await loadedRegion('Scores over time');
      expect(within(region).getByRole('button', { name: '20-Sunday average' })).toHaveAttribute(
        'aria-pressed',
        'true',
      );
      await loadedRegion('Finishes');
    },
    LAZY_TEST_TIMEOUT,
  );

  it(
    'still draws the charts, unwindowed, while the newest score date is unknown',
    async () => {
      server.use(http.get('*/api/meta', () => new HttpResponse(null, { status: 500 })));
      renderWithProviders(<ProfileCharts shooterId={3} />, { route: '/shooters/3' });
      await loadedRegion('Finishes');
      await loadedRegion('Rating');
      const trend = await screen.findByRole(
        'img',
        { name: /Scores and scores against the day/ },
        LAZY_CHART,
      );
      const zoom = (getInstanceByDom(trend)?.getOption() as { dataZoom: { startValue?: number }[] })
        .dataZoom;
      expect(zoom[0]?.startValue ?? 0).toBe(0);
    },
    LAZY_TEST_TIMEOUT,
  );

  it(
    'falls back to no line for an unknown trend.line',
    async () => {
      renderWithProviders(<ProfileCharts shooterId={3} />, {
        route: '/shooters/3?trend.line=bogus',
      });
      const region = await loadedRegion('Scores over time');
      expect(within(region).getByRole('button', { name: 'No line' })).toHaveAttribute(
        'aria-pressed',
        'true',
      );
    },
    LAZY_TEST_TIMEOUT,
  );

  it(
    'shows each Sunday finish with its explainer',
    async () => {
      renderWithProviders(<ProfileCharts shooterId={3} />, { route: '/shooters/3' });
      const region = await loadedRegion('Finishes');
      expectChartControls(region);
      await expectExplainer(region, 'About this chart', { read: true });
    },
    LAZY_TEST_TIMEOUT,
  );

  describe('full data in fullscreen and the CSV', () => {
    afterEach(() => vi.restoreAllMocks());
    beforeEach(() => {
      // An older point, so the rating's window start differs from its first point.
      server.use(
        http.get('*/api/shooters/:id/rating', () =>
          HttpResponse.json({
            ...hadleyRating,
            points: [
              { event_date: '2025-01-05', mu: 30, var: 4, lo: 26, hi: 34 },
              ...hadleyRating.points,
            ],
          }),
        ),
      );
    });
    const startOf = (o: EChartsOption) =>
      (o as { dataZoom: { startValue?: number }[] }).dataZoom[0]?.startValue ?? 0;
    // hadleyRounds plus the one 2025 round the beforeEach adds.
    const ROUNDS = hadleyRounds.length + 1;
    // The top-level beforeEach also adds a clone of hadleyRounds[0].
    const finishRounds = [...hadleyRounds, hadleyRounds[0]].filter((r) => r && isFinish(r)).length;

    it.each([
      ['Rating', /Rating over time/],
      ['Scores over time', /Scores and scores against the day/],
      ['Finishes', /Place on each Sunday/],
    ])(
      '%s opens on the window inline and on all its history in fullscreen',
      async (title, name) => {
        stubViewport('desktop');
        const user = userEvent.setup();
        renderWithProviders(<ProfileCharts shooterId={3} />, { route: '/shooters/3' });
        const region = await loadedRegion(title);
        const inline = startOf(chartOptionIn(region, name));
        const dialog = await openFullscreen(user, region, title);
        const zoom = (chartOptionIn(dialog, name) as { dataZoom: unknown[] }).dataZoom;
        expect(zoom).toHaveLength(2);
        expect(inline).toBeGreaterThan(0);
        // The live option resolves "no window" to the first point (index 0), not to a later start.
        expect(startOf(chartOptionIn(dialog, name))).toBe(0);
      },
      LAZY_TEST_TIMEOUT,
    );

    it.each([
      ['Rating', 'rating', () => hadleyRating.points.length + 1],
      ['Scores over time', 'trend', () => ROUNDS],
      ['Finishes', 'finishes', () => finishRounds],
    ])(
      'the %s fullscreen table and the CSV hold every row',
      async (title, key, count) => {
        stubViewport('desktop');
        const csv = captureCsv();
        const user = userEvent.setup();
        renderWithProviders(<ProfileCharts shooterId={3} />, {
          route: `/shooters/3?${key}=table`,
        });
        const region = await loadedRegion(title);
        await user.click(within(region).getByRole('button', { name: 'CSV' }));
        expect((await csv.text()).trimEnd().split('\r\n')).toHaveLength(count() + 1);
        const dialog = await openFullscreen(user, region, title);
        expect(within(dialog).getAllByRole('row')).toHaveLength(count() + 1);
        expect(within(dialog).getByRole('button', { name: 'CSV' })).toBeInTheDocument();
      },
      LAZY_TEST_TIMEOUT,
    );

    describe('attendance calendar', () => {
      const held = (dates: string[]) =>
        dates.map((event_date) => ({ ...eventSummaries[0], event_date, results_complete: true }));
      const shot2026 = new Set(
        hadleyRounds.filter((r) => r.event_date.startsWith('2026')).map((r) => r.event_date),
      );
      const requestedYears: string[] = [];

      beforeEach(() => {
        requestedYears.length = 0;
        server.use(
          http.get('*/api/events', ({ request }) => {
            const params = new URL(request.url).searchParams;
            const year = params.get('year') as string;
            requestedYears.push(year);
            return HttpResponse.json(
              year === '2026' ? held(['2026-01-04']) : held(['2025-11-02', '2025-11-09']),
            );
          }),
        );
      });

      it(
        'lists every year in the fullscreen table and the CSV, and only the chosen year inline',
        async () => {
          stubViewport('desktop');
          const csv = captureCsv();
          const user = userEvent.setup();
          renderWithProviders(<ProfileCharts shooterId={3} />, {
            route: '/shooters/3?cal=table',
          });
          await screen.findByRole('table', { name: 'Attendance calendar 2026' }, LAZY_CHART);
          const region = screen.getByRole('region', { name: 'Attendance calendar 2026' });
          const inlineRows = within(region).getAllByRole('row').length - 1;
          // 2026: the shot Sundays plus the missed 2026-01-04. 2025: the shot 2025-11-09 plus the missed 2025-11-02.
          expect(inlineRows).toBe(shot2026.size + 1);
          await user.click(within(region).getByRole('button', { name: 'CSV' }));
          await waitFor(() => expect(csv.names).toHaveLength(1));
          const lines = (await csv.text()).trimEnd().split('\r\n');
          expect(lines).toHaveLength(1 + shot2026.size + 1 + 2);
          // Oldest year first, so the export reads chronologically.
          expect(lines[1]).toContain('2025');
          expect(lines.at(-1)).toContain('2026');
          expect(requestedYears).toEqual(expect.arrayContaining(['2025', '2026']));
          // The page already holds 2026, so the CSV reuses it instead of asking again.
          expect(requestedYears.filter((y) => y === '2026')).toHaveLength(1);
          const dialog = await openFullscreen(user, region, 'Attendance calendar 2026');
          await waitFor(() =>
            expect(within(dialog).getAllByRole('row')).toHaveLength(lines.length),
          );
          expect(within(dialog).getByText(/Every year you shot/)).toBeVisible();
          expect(csv.names).toHaveLength(1);
        },
        LAZY_TEST_TIMEOUT,
      );

      it(
        'keeps the fullscreen chart on the chosen year',
        async () => {
          stubViewport('desktop');
          const user = userEvent.setup();
          renderWithProviders(<ProfileCharts shooterId={3} />, { route: '/shooters/3' });
          await screen.findByRole('img', { name: 'Attendance calendar for 2026' }, LAZY_CHART);
          const region = screen.getByRole('region', { name: 'Attendance calendar 2026' });
          const dialog = await openFullscreen(user, region, 'Attendance calendar 2026');
          expect(
            within(dialog).getByRole('img', { name: 'Attendance calendar for 2026' }),
          ).toBeInTheDocument();
        },
        LAZY_TEST_TIMEOUT,
      );

      it(
        'says so when the CSV cannot load every year',
        async () => {
          const csv = captureCsv();
          const user = userEvent.setup();
          renderWithProviders(<ProfileCharts shooterId={3} />, { route: '/shooters/3' });
          await screen.findByRole('img', { name: 'Attendance calendar for 2026' }, LAZY_CHART);
          server.use(
            http.get('*/api/events', ({ request }) =>
              new URL(request.url).searchParams.get('year') === '2025'
                ? HttpResponse.json({ error: { code: 'x', message: 'no' } }, { status: 500 })
                : HttpResponse.json(held(['2026-01-04'])),
            ),
          );
          const region = screen.getByRole('region', { name: 'Attendance calendar 2026' });
          await user.click(within(region).getByRole('button', { name: 'CSV' }));
          expect(await within(region).findByRole('alert')).toHaveTextContent(
            "Couldn't download every row. Try again.",
          );
          expect(csv.names).toEqual([]);
        },
        LAZY_TEST_TIMEOUT,
      );
    });
  });
  it(
    'tough days: each best round against the field by how the day played',
    async () => {
      const user = userEvent.setup();
      renderWithProviders(<ProfileCharts shooterId={3} />, {
        route: '/shooters/3?w=6m&tough-days.hl=2026-08-16',
      });
      const region = await loadedRegion('Tough days');
      expectChartControls(region);
      expect(within(region).getByText('Showing what the insight points to.')).toBeInTheDocument();
      await expectExplainer(region, 'About this chart', { read: true });
      await user.click(within(region).getByRole('button', { name: 'Table' }));
      const rows = within(within(region).getByRole('table')).getAllByRole('row').slice(1);
      const cells = rows.map((r) =>
        within(r)
          .getAllByRole('cell')
          .map((c) => c.textContent),
      );
      expect(cells.map((c) => c[0])).toEqual(['2026-08-16', '2026-08-23', '2026-09-06']);
      expect(
        cells.map((c) => [Number(c[1]?.replace('−', '-')), Number(c[2]?.replace('−', '-'))]),
      ).toEqual([
        [1.2, 2],
        [-0.5, 3],
        [0.4, -3],
      ]);
    },
    LAZY_TEST_TIMEOUT,
  );

  it(
    'tough days shows the Sundays an insight link points to, even outside the header window',
    async () => {
      server.use(
        http.post('*/api/explore', () =>
          HttpResponse.json({
            ...difficultyByEvent,
            rows: [...difficultyByEvent.rows, { event: '2025-11-09', value: 0.8 }],
          }),
        ),
      );
      const user = userEvent.setup();
      renderWithProviders(<ProfileCharts shooterId={3} />, {
        route:
          '/shooters/3?tough-days.hl=2025-11-09&tough-days.from=2025-01-01&tough-days.to=2025-12-31',
      });
      const region = await loadedRegion('Tough days');
      await user.click(within(region).getByRole('button', { name: 'Table' }));
      const table = within(region).getByRole('table');
      expect(within(table).getByText('2025-11-09')).toBeInTheDocument();
      expect(within(table).queryByText('2026-08-16')).toBeNull();
    },
    LAZY_TEST_TIMEOUT,
  );

  it(
    'the month view opens on the year the window ends in, not just the window',
    async () => {
      renderWithProviders(<ProfileCharts shooterId={3} />, {
        route: '/shooters/3?cal.view=month',
      });
      const region = await loadedRegion('Sundays shot per month');
      const zoom = (chartOptionIn(region) as { dataZoom: { startValue?: number }[] }).dataZoom;
      // Nov 2025 is index 0 and Jan 2026 index 2: the 2026 year, not the last 8 weeks.
      expect(zoom[0]?.startValue).toBe(2);
    },
    LAZY_TEST_TIMEOUT,
  );

  it(
    'the month view shows every month on All time',
    async () => {
      renderWithProviders(<ProfileCharts shooterId={3} />, {
        route: '/shooters/3?cal.view=month&w=all',
      });
      const region = await loadedRegion('Sundays shot per month');
      const zoom = (chartOptionIn(region) as { dataZoom: { startValue?: number }[] }).dataZoom;
      expect(zoom.every((z) => z.startValue === undefined || z.startValue === 0)).toBe(true);
    },
    LAZY_TEST_TIMEOUT,
  );

  it(
    'tough days follows the window inline, while fullscreen and the CSV keep every Sunday',
    async () => {
      const csv = captureCsv();
      const user = userEvent.setup();
      renderWithProviders(<ProfileCharts shooterId={3} />, {
        route: '/shooters/3?w=2026-09-01..2026-09-30',
      });
      const region = await loadedRegion('Tough days');
      await user.click(within(region).getByRole('button', { name: 'Table' }));
      expect(within(within(region).getByRole('table')).getAllByRole('row')).toHaveLength(2);
      await user.click(within(region).getByRole('button', { name: 'CSV' }));
      await waitFor(() => expect(csv.names).toHaveLength(1));
      expect((await csv.text()).trim().split(/\r?\n/)).toHaveLength(4);
    },
    LAZY_TEST_TIMEOUT,
  );

  it(
    'tough days says which window came up empty',
    async () => {
      renderWithProviders(<ProfileCharts shooterId={3} />, {
        route: '/shooters/3?w=2020-01-01..2020-03-01',
      });
      expect(
        await screen.findByText('No Sundays with field results in Jan 1, 2020 – Mar 1, 2020'),
      ).toBeInTheDocument();
    },
    LAZY_TEST_TIMEOUT,
  );

  it('tough days says so when no Sunday has field results', async () => {
    server.use(
      http.post('*/api/explore', () => HttpResponse.json({ ...difficultyByEvent, rows: [] })),
    );
    renderWithProviders(<ProfileCharts shooterId={3} />, { route: '/shooters/3' });
    expect(await screen.findByText('No Sundays with field results yet')).toBeInTheDocument();
  });

  it(
    'calendar by month: Sundays per month, chosen by the link',
    async () => {
      const user = userEvent.setup();
      renderWithProviders(<ProfileCharts shooterId={3} />, {
        route: '/shooters/3?cal.view=month&cal.hl=2026-08',
      });
      const region = await loadedRegion('Sundays shot per month');
      expect(within(region).getByRole('button', { name: 'By month' })).toHaveAttribute(
        'aria-pressed',
        'true',
      );
      expect(within(region).getByText('Showing what the insight points to.')).toBeInTheDocument();
      await expectExplainer(region, 'About this chart', { read: true });
      await user.click(within(region).getByRole('button', { name: 'By year' }));
      expect(await loadedRegion('Attendance calendar 2026')).toBeInTheDocument();
    },
    LAZY_TEST_TIMEOUT,
  );

  it(
    'calendar by month lists every month, empty ones too, and the CSV has them all',
    async () => {
      const csv = captureCsv();
      const user = userEvent.setup();
      renderWithProviders(<ProfileCharts shooterId={3} />, {
        route: '/shooters/3?cal.view=month&w=all',
      });
      const region = await loadedRegion('Sundays shot per month');
      await user.click(within(region).getByRole('button', { name: 'CSV' }));
      await waitFor(() => expect(csv.names).toHaveLength(1));
      const lines = (await csv.text()).trim().split(/\r?\n/);
      // Nov 2025 to Sep 2026: 11 months, 8 of them with no Sunday shot.
      expect(lines).toHaveLength(12);
      expect(lines.filter((l) => /,"?0"?$/.test(l))).toHaveLength(8);
    },
    LAZY_TEST_TIMEOUT,
  );

  it(
    "the calendar opens on the year of an insight link's dates",
    async () => {
      renderWithProviders(<ProfileCharts shooterId={3} />, {
        route: '/shooters/3?cal.hl=2025-11-09&cal.from=2025-01-01&cal.to=2025-12-31',
      });
      expect(await loadedRegion('Attendance calendar 2025')).toBeInTheDocument();
    },
    LAZY_TEST_TIMEOUT,
  );
});
