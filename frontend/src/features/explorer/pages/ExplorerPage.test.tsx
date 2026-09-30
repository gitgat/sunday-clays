import { act, fireEvent, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { delay, http, HttpResponse } from 'msw';
import { getInstanceByDom } from 'echarts/core';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type * as Explore from '../../../components/charts/explore';
import { buildExploreOption, type QuerySpec } from '../../../components/charts/explore';
import {
  captureCsv,
  expectChartControls,
  expectExplainer,
  openFullscreen,
} from '../../../test/charts';
import { server } from '../../../test/msw/server';
import { renderRoute, renderWithProviders, type ProvidersResult } from '../../../test/render';
import { stubViewport } from '../../../test/viewport';
import { SETTLE_MS } from '../components/FilterControls';
import { fakeExploreResult } from '../mocks';
import { ExplorerPage } from './ExplorerPage';

// The real builder, wrapped so a test can count how often the page rebuilds its chart option.
vi.mock('../../../components/charts/explore', async (importOriginal) => {
  const actual = await importOriginal<typeof Explore>();
  return { ...actual, buildExploreOption: vi.fn(actual.buildExploreOption) };
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

function captureSpecs(): QuerySpec[] {
  const seen: QuerySpec[] = [];
  server.use(
    http.post('/api/explore', async ({ request }) => {
      const spec = (await request.json()) as QuerySpec;
      seen.push(spec);
      return HttpResponse.json(fakeExploreResult(spec));
    }),
  );
  return seen;
}

function renderPage(route = '/explorer') {
  return renderWithProviders(<ExplorerPage />, { route, path: '/explorer' });
}

/** Every query string the page writes from now on, in order (one entry per navigation). */
function urlWrites(router: ProvidersResult['router']): string[] {
  const writes: string[] = [];
  let lastKey = router.state.location.key;
  router.subscribe((state) => {
    if (state.location.key === lastKey) return;
    lastKey = state.location.key;
    writes.push(state.location.search);
  });
  return writes;
}

/** Fakes only setTimeout, the clock sliders settle on; msw, React and ECharts keep real time. */
function fakeSettleClock() {
  vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] });
}

async function tick(ms: number) {
  await act(async () => {
    vi.advanceTimersByTime(ms);
  });
}

/** Runs what the fake clock still holds (React Query's notify batches), then real time again. */
function realClock() {
  act(() => {
    vi.runOnlyPendingTimers();
  });
  vi.useRealTimers();
}

describe('ExplorerPage', () => {
  it('runs the default query (average score by year) and shows it with Table and CSV controls', async () => {
    const seen = captureSpecs();
    renderPage();
    const chart = await screen.findByRole('img', { name: 'Value by Sunday' });
    expect(chart).toBeInTheDocument();
    expectChartControls(screen.getByRole('region', { name: 'Value by Sunday' }));
    expect(screen.getByText('Based on 10 rounds')).toBeInTheDocument();
    expect(seen[0]).toEqual({
      metric: 'score',
      agg: 'avg',
      group_by: ['event'],
      sort: 'key_asc',
      limit: 500,
      // The time window (anchor = the latest scored Sunday) fills the dates the URL leaves empty.
      filters: {
        date_from: '2026-08-03',
        date_to: '2026-09-27',
        shooter_ids: [],
        round_types: [],
        statuses: [],
        gauges: [],
        temp_f: null,
        gust_mph: null,
        precip_in: null,
        min_rounds: 0,
        best_round_only: false,
        min_score: null,
        ytd: null,
      },
    });
  });

  it('follows the time window, All time included', async () => {
    const all = captureSpecs();
    renderPage('/explorer?w=all');
    await screen.findByRole('img', { name: /^Value by / });
    expect(all[0]?.filters).toMatchObject({ date_from: null, date_to: '2026-09-27' });
    expect(screen.getByText('Based on 10 rounds')).toBeInTheDocument();
  });

  it('has no From and To boxes: the time window is the only date control', async () => {
    captureSpecs();
    renderPage();
    await screen.findByRole('img', { name: 'Value by Sunday' });
    await userEvent.setup().click(screen.getByText('Filters'));
    expect(screen.queryByLabelText('From')).toBeNull();
    expect(screen.queryByLabelText('To')).toBeNull();
  });

  it('turns an old From and To link into a Custom window, once, and drops them from the URL', async () => {
    const seen = captureSpecs();
    const { router } = renderPage('/explorer?from=2025-01-01&to=2025-06-29&m=rounds');
    await waitFor(() =>
      expect(Object.fromEntries(new URLSearchParams(router.state.location.search))).toEqual({
        m: 'rounds',
        w: '2025-01-01..2025-06-29',
      }),
    );
    await screen.findByText(/Jan 1, 2025 – Jun 29, 2025/);
    // One query, for the converted dates: never one for the header window first.
    expect(seen).toHaveLength(1);
    expect(seen[0]?.filters).toMatchObject({ date_from: '2025-01-01', date_to: '2025-06-29' });
  });

  it('fills a missing end of an old link from the first or latest scored Sunday', async () => {
    server.use(
      http.get('*/api/meta', () =>
        HttpResponse.json({ first_score_date: '2019-01-06', last_score_date: '2026-09-27' }),
      ),
    );
    const seen = captureSpecs();
    const { router } = renderPage('/explorer?from=2025-01-01');
    await waitFor(() => expect(router.state.location.search).toBe('?w=2025-01-01..2026-09-27'));
    await screen.findByRole('img', { name: /^Value by / });
    expect(seen.at(-1)?.filters).toMatchObject({ date_from: '2025-01-01', date_to: '2026-09-27' });
    const later = renderPage('/explorer?to=2020-12-27');
    await waitFor(() =>
      expect(later.router.state.location.search).toBe('?w=2019-01-06..2020-12-27'),
    );
  });

  it('drops old From and To values that are empty, reversed or impossible, keeping the window', async () => {
    const seen = captureSpecs();
    const { router } = renderPage('/explorer?from=2026-02-30&to=&w=3m');
    await waitFor(() => expect(router.state.location.search).toBe('?w=3m'));
    await screen.findByRole('img', { name: /^Value by / });
    expect(seen.at(-1)?.filters).toMatchObject({ date_from: '2026-06-28', date_to: '2026-09-27' });
    const reversed = renderPage('/explorer?from=2026-05-01&to=2026-01-01');
    await waitFor(() => expect(reversed.router.state.location.search).toBe(''));
  });

  it('opens on Sunday for a window of fewer than 12 Sundays, and on Year otherwise', async () => {
    server.use(
      http.get('*/api/meta', () =>
        HttpResponse.json({ first_score_date: '2019-01-06', last_score_date: '2026-09-27' }),
      ),
    );
    const seen = captureSpecs();
    const first = renderPage();
    await screen.findByRole('img', { name: 'Value by Sunday' });
    expect(seen.at(-1)?.group_by).toEqual(['event']);
    first.unmount();
    renderPage('/explorer?w=12m');
    await screen.findByRole('img', { name: 'Value by year' });
    expect(seen.at(-1)?.group_by).toEqual(['year']);
  });

  it('measures an All window from the first scored Sunday, and an unknown start opens on Year', async () => {
    server.use(
      http.get('*/api/meta', () =>
        HttpResponse.json({ first_score_date: '2026-08-02', last_score_date: '2026-09-27' }),
      ),
    );
    const seen = captureSpecs();
    const short = renderPage('/explorer?w=all');
    await screen.findByRole('img', { name: 'Value by Sunday' });
    expect(seen.at(-1)?.group_by).toEqual(['event']);
    short.unmount();
    server.use(http.get('*/api/meta', () => HttpResponse.json({ last_score_date: '2026-09-27' })));
    renderPage('/explorer?w=all');
    await screen.findByRole('img', { name: 'Value by year' });
  });

  it('keeps an explicit grouping over the window default', async () => {
    const seen = captureSpecs();
    const { user, router } = renderPage('/explorer?g=year');
    await screen.findByRole('img', { name: 'Value by year' });
    expect(seen.at(-1)?.group_by).toEqual(['year']);
    await user.selectOptions(screen.getByLabelText('Group by'), 'Sunday');
    // Sunday is the default on this short window, so the URL is back to bare.
    expect(router.state.location.search).toBe('');
  });

  it('nudges a thin window that is split by anything but time, with 12M and All', async () => {
    captureSpecs();
    const { user, router } = renderPage('/explorer?g=temp_band&w=8w');
    expect(
      await screen.findByText(
        /Only 4 Sundays in the last 8 weeks\. Comparing groups needs more; try a longer window\./,
      ),
    ).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Show the last 12 months' }));
    expect(new URLSearchParams(router.state.location.search).get('w')).toBe('12m');
  });

  it('does not claim "No Sundays" when the events request fails', async () => {
    captureSpecs();
    server.use(http.get('*/api/events', () => HttpResponse.json({}, { status: 500 })));
    renderPage('/explorer?g=temp_band&w=8w');
    await screen.findByRole('img', { name: /Value by/ });
    expect(screen.queryByText(/No Sundays/)).toBeNull();
    expect(screen.queryByText(/Comparing groups needs more/)).toBeNull();
  });

  it('does not nudge a split by Sunday or month', async () => {
    captureSpecs();
    renderPage('/explorer?g=month');
    await screen.findByRole('img', { name: 'Value by month' });
    expect(screen.queryByText(/Comparing groups needs more/)).toBeNull();
  });

  it('keeps describing the result on screen until the new one lands', async () => {
    let release = () => {};
    const gate = new Promise<void>((r) => {
      release = r;
    });
    let calls = 0;
    server.use(
      http.post('/api/explore', async ({ request }) => {
        const spec = (await request.json()) as QuerySpec;
        calls += 1;
        if (calls > 1) await gate;
        return HttpResponse.json(fakeExploreResult(spec));
      }),
    );
    const { router } = renderPage();
    await screen.findByText('Based on 10 rounds');
    await act(() => router.navigate('/explorer?w=all'));
    await waitFor(() => expect(calls).toBe(2));
    // The old numbers are still drawn, but they no longer cover the window on screen, so they
    // carry no window tag rather than the wrong one.
    expect(screen.getByText('Based on 10 rounds')).toBeInTheDocument();
    release();
    await screen.findByText('Based on 10 rounds');
    expect(screen.queryByText(/Last 8 weeks/)).toBeNull();
  });

  it('explains the result and the query choices in plain words', async () => {
    const user = userEvent.setup();
    renderPage('/explorer?m=residual');
    const region = await screen.findByRole('region', { name: 'Value by Sunday' });
    await expectExplainer(region, 'About this chart', { read: true });
    await user.click(within(region).getByRole('button', { name: 'About this chart' }));
    expect(
      within(region).getByText(/Vs expected = actual score minus expected score/),
    ).toBeVisible();
    expect(within(region).getByText(/^Last 8 weeks( · .+)?$/, { selector: 'span' })).toBeVisible();
    await user.click(screen.getByRole('button', { name: 'About these choices' }));
    expect(screen.getByText(/winter Dec to Feb/)).toBeVisible();
  });

  it('offers no Class grouping and calls the residual metric Vs expected', async () => {
    renderPage();
    await screen.findByRole('img', { name: 'Value by Sunday' });
    const groupBy = screen.getByLabelText('Group by');
    expect(within(groupBy).queryByRole('option', { name: 'Class' })).toBeNull();
    expect(within(groupBy).getByRole('option', { name: 'Sunday' })).toBeInTheDocument();
    expect(
      within(screen.getByLabelText('Metric')).getByRole('option', { name: 'Vs expected' }),
    ).toBeInTheDocument();
  });

  it('shows no window tag or date note when nothing is scored yet', async () => {
    server.use(http.get('*/api/meta', () => HttpResponse.json({ last_score_date: null })));
    const seen = captureSpecs();
    renderPage();
    // Nothing is scored, so the window has no dates and the grouping stays Year.
    await screen.findByRole('img', { name: 'Value by year' });
    expect(seen[0]?.filters).toMatchObject({ date_from: null, date_to: null });
    expect(screen.getByText('Based on 10 rounds')).toBeInTheDocument();
    const region = screen.getByRole('region', { name: 'Value by year' });
    expect(within(region).getByText('All time')).toBeInTheDocument();
  });

  it('has no subtitle for an attendance result when nothing is scored yet (no window tag)', async () => {
    server.use(http.get('*/api/meta', () => HttpResponse.json({ last_score_date: null })));
    renderPage('/explorer?m=attendance');
    const region = await screen.findByRole('region', { name: 'Value by year' });
    expect(within(region).queryByText(/Based on|Last 8 weeks/)).toBeNull();
  });

  it('leaves the round count out of an attendance result', async () => {
    renderPage('/explorer?m=attendance');
    await screen.findByRole('img', { name: 'Value by Sunday' });
    expect(screen.queryByText(/Based on/)).toBeNull();
    // The window's dates are in the scope tag, never repeated in the subtitle.
    expect(screen.queryByText(/^Last 8 weeks/, { selector: 'p' })).toBeNull();
  });

  it('is served at /explorer in the app shell, drawn from the default explore mock', async () => {
    stubViewport('desktop');
    renderRoute('/explorer?rt=sporting');
    expect(await screen.findByRole('heading', { level: 1, name: 'Explorer' })).toBeInTheDocument();
    // The shell's <main id="main"> is the only one: pages never render their own (D15).
    expect(screen.getByRole('main')).toHaveAttribute('id', 'main');
    expect(await screen.findByRole('img', { name: 'Value by Sunday' })).toBeInTheDocument();
    expect(
      within(screen.getByRole('navigation', { name: 'Main' })).getByRole('link', {
        name: 'Explorer',
      }),
    ).toHaveAttribute('href', '/explorer?rt=sporting');
  });

  it('restores a shared URL into the query and the controls', async () => {
    const seen = captureSpecs();
    renderPage(
      '/explorer?m=rounds&g=status,year&st=member&ga=unspecified&sh=3,4&t=40..70&gu=0..10&p=0..0.02&mr=5&best=1&s=value_desc&from=2025-01-01&to=2025-12-31&rt=sporting&c=line',
    );
    await screen.findByRole('img', { name: 'Value by status and year' });
    expect(seen[0]).toMatchObject({
      metric: 'rounds',
      group_by: ['status', 'year'],
      sort: 'value_desc',
      filters: {
        date_from: '2025-01-01',
        date_to: '2025-12-31',
        shooter_ids: [3, 4],
        round_types: ['sporting'],
        statuses: ['member'],
        gauges: ['unspecified'],
        temp_f: [40, 70],
        gust_mph: [0, 10],
        precip_in: [0, 0.02],
        min_rounds: 5,
        best_round_only: true,
      },
    });
    expect(screen.getByLabelText('Metric')).toHaveValue('rounds');
    expect(screen.queryByLabelText('Aggregate')).toBeNull();
    expect(screen.getByText('Filters (8)')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Line' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByText('2 shooters')).toBeInTheDocument();
  });

  it('falls back to safe defaults for hand-edited, malformed parameters', async () => {
    const seen = captureSpecs();
    renderPage(
      '/explorer?m=bogus&a=nope&g=year,year,shooter,class&t=abc&mr=-3&from=2026-02-30&sh=x&c=pie',
    );
    await screen.findByRole('img', { name: 'Value by year and shooter' });
    expect(seen[0]).toMatchObject({
      metric: 'score',
      agg: 'avg',
      group_by: ['year', 'shooter'],
      filters: { temp_f: null, min_rounds: 0, date_from: '2026-08-03', shooter_ids: [] },
    });
  });

  it('drops shooter ids that are not positive ids of at most 9 digits, never sending them', async () => {
    const seen = captureSpecs();
    const huge = '9'.repeat(400);
    renderPage(
      `/explorer?sh=0,3,-4,1e3,007,999999999,1000000000,99999999999999999999999,${huge},2.5`,
    );
    await screen.findByRole('img', { name: 'Value by Sunday' });
    expect(seen[0]?.filters.shooter_ids).toEqual([3, 999999999]);
    expect(screen.getByText('2 shooters')).toBeInTheDocument();
  });

  it('reads a shooter filter of only out-of-range ids as no filter', async () => {
    const seen = captureSpecs();
    renderPage(`/explorer?sh=99999999999999999999999,${'9'.repeat(400)}`);
    await screen.findByRole('img', { name: 'Value by Sunday' });
    expect(seen[0]?.filters.shooter_ids).toEqual([]);
    expect(screen.getByText('Filters')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Clear shooter filter' })).toBeNull();
  });

  it('reads empty parameters as no filter', async () => {
    const seen = captureSpecs();
    renderPage('/explorer?from=&to=&t=&sh=&st=');
    await screen.findByRole('img', { name: 'Value by Sunday' });
    expect(seen[0]?.filters).toMatchObject({
      date_from: '2026-08-03',
      date_to: '2026-09-27',
      temp_f: null,
      shooter_ids: [],
      statuses: [],
    });
    expect(screen.getByText('Filters')).toBeInTheDocument();
  });

  it('writes every control change to the URL', async () => {
    const seen = captureSpecs();
    const { user, router } = renderPage();
    await screen.findByRole('img', { name: 'Value by Sunday' });
    await user.selectOptions(screen.getByLabelText('Aggregate'), 'Median');
    await user.selectOptions(screen.getByLabelText('Group by'), 'Gauge');
    await user.selectOptions(screen.getByLabelText('Then by'), 'Status');
    await user.selectOptions(screen.getByLabelText('Sort'), 'Value, highest first');
    await user.click(screen.getByRole('button', { name: 'Heatmap' }));
    await user.click(screen.getByText('Filters'));
    await user.click(
      within(screen.getByRole('group', { name: 'Status' })).getByRole('button', { name: 'Guest' }),
    );
    await user.click(
      within(screen.getByRole('group', { name: 'Gauge' })).getByRole('button', {
        name: 'Not recorded',
      }),
    );
    // Sliders write once they settle (SETTLE_MS), not on every step.
    fakeSettleClock();
    fireEvent.change(screen.getByLabelText('Temperature minimum'), { target: { value: '40' } });
    await tick(SETTLE_MS);
    fireEvent.change(screen.getByLabelText('Minimum rounds per shooter'), {
      target: { value: '10' },
    });
    await tick(SETTLE_MS);
    realClock();
    await user.click(screen.getByRole('switch', { name: 'Best round only' }));
    await user.selectOptions(screen.getByLabelText('Metric'), 'Rounds');
    const params = new URLSearchParams(router.state.location.search);
    expect(Object.fromEntries(params)).toEqual({
      a: 'median',
      g: 'gauge,status',
      s: 'value_desc',
      c: 'heatmap',
      st: 'guest',
      ga: 'unspecified',
      t: '40..110',
      mr: '10',
      best: '1',
      m: 'rounds',
    });
    await screen.findByRole('img', { name: 'Value by gauge and status' });
    expect(seen.at(-1)).toMatchObject({ metric: 'rounds', group_by: ['gauge', 'status'] });
  });

  it('removes filters again: full-range sliders, toggled chips and the shooter chip', async () => {
    captureSpecs();
    const { user, router } = renderPage('/explorer?t=40..110&st=guest&sh=3');
    await screen.findByRole('img', { name: 'Value by Sunday' });
    fakeSettleClock();
    fireEvent.change(screen.getByLabelText('Temperature minimum'), { target: { value: '0' } });
    await tick(SETTLE_MS);
    realClock();
    await user.click(
      within(screen.getByRole('group', { name: 'Status' })).getByRole('button', { name: 'Guest' }),
    );
    await user.click(screen.getByRole('button', { name: 'Clear shooter filter' }));
    expect(router.state.location.search).toBe('');
  });

  it('writes a Then by picked without a Group by', async () => {
    captureSpecs();
    const { user, router } = renderPage('/explorer?g=');
    await screen.findByRole('img', { name: 'Value' });
    await user.selectOptions(screen.getByLabelText('Then by'), 'Year');
    expect(Object.fromEntries(new URLSearchParams(router.state.location.search))).toEqual({
      g: 'year',
    });
    await screen.findByRole('img', { name: 'Value by year' });
  });

  it('clears the grouping with None', async () => {
    const seen = captureSpecs();
    const { user } = renderPage('/explorer?g=year,status');
    await screen.findByRole('img', { name: 'Value by year and status' });
    await user.selectOptions(screen.getByLabelText('Then by'), 'None');
    await user.selectOptions(screen.getByLabelText('Group by'), 'None');
    expect(await screen.findByRole('img', { name: 'Value' })).toBeInTheDocument();
    expect(seen.at(-1)?.group_by).toEqual([]);
  });

  it('never writes a dim twice when Group by takes the Then by choice', async () => {
    const seen = captureSpecs();
    const { user, router } = renderPage('/explorer?g=gauge,status');
    await screen.findByRole('img', { name: 'Value by gauge and status' });
    await user.selectOptions(screen.getByLabelText('Group by'), 'Status');
    expect(router.state.location.search).toBe('?g=status');
    await screen.findByRole('img', { name: 'Value by status' });
    expect(seen.at(-1)?.group_by).toEqual(['status']);
  });

  it("shows the server's explanation when a combination is invalid", async () => {
    server.use(
      http.post('/api/explore', () =>
        HttpResponse.json(
          {
            error: { code: 'invalid_query', message: 'Grouping by station needs the Hit % metric' },
          },
          { status: 400 },
        ),
      ),
    );
    renderPage('/explorer?g=station');
    expect(
      await screen.findByRole('heading', { name: "This query can't run" }),
    ).toBeInTheDocument();
    expect(screen.getByText('Grouping by station needs the Hit % metric')).toBeInTheDocument();
  });

  it('runs the query again after a failure', async () => {
    captureSpecs();
    server.use(
      http.post(
        '/api/explore',
        () =>
          HttpResponse.json(
            { error: { code: 'internal', message: 'Server error. Try again shortly.' } },
            { status: 500 },
          ),
        { once: true },
      ),
    );
    const { user } = renderPage();
    expect(await screen.findByText('Server error. Try again shortly.')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Try again' }));
    expect(await screen.findByRole('img', { name: 'Value by Sunday' })).toBeInTheDocument();
  });

  it('titles a result that carries no value column "Value"', async () => {
    server.use(
      http.post('/api/explore', () =>
        HttpResponse.json({ columns: [], rows: [], n_rounds: 0, truncated: false }),
      ),
    );
    renderPage('/explorer?g=');
    expect(await screen.findByRole('region', { name: 'Value' })).toHaveTextContent(
      'No data for these filters',
    );
  });

  it('shows loading, empty and truncated states', async () => {
    server.use(
      http.post('/api/explore', async () => {
        await delay(20);
        return HttpResponse.json({
          columns: [{ key: 'value', label: 'Wins', type: 'int' }],
          rows: [],
          n_rounds: 0,
          truncated: false,
        });
      }),
    );
    renderPage();
    expect(screen.getByRole('status', { name: 'Running query' })).toBeInTheDocument();
    expect(
      await screen.findByRole('heading', { name: 'No data for these filters' }),
    ).toBeInTheDocument();
  });

  it('notes a truncated result', async () => {
    server.use(
      http.post('/api/explore', async ({ request }) =>
        HttpResponse.json({
          ...fakeExploreResult((await request.json()) as QuerySpec),
          n_rounds: 7480,
          truncated: true,
        }),
      ),
    );
    renderPage();
    expect(
      await screen.findByText('Based on 7,480 rounds · showing the first 2 rows'),
    ).toBeInTheDocument();
  });

  it('links shooter rows to profiles from the table', async () => {
    captureSpecs();
    renderPage('/explorer?g=shooter&v=table');
    expect(await screen.findByRole('link', { name: 'A' })).toHaveAttribute('href', '/shooters/3');
  });

  it('links event rows to event pages from the table', async () => {
    captureSpecs();
    renderPage('/explorer?g=event&v=table');
    expect(await screen.findByRole('link', { name: 'B' })).toHaveAttribute('href', '/events/B');
  });

  it('puts the event link on the event cell when a text column follows it', async () => {
    server.use(
      http.post('/api/explore', () =>
        HttpResponse.json({
          columns: [
            { key: 'event', label: 'Event', type: 'date' },
            { key: 'status', label: 'Status', type: 'string' },
            { key: 'value', label: 'Avg score', type: 'number' },
            { key: 'n', label: 'n', type: 'int' },
          ],
          rows: [{ event: '2025-03-02', status: 'member', value: 38.5, n: 12 }],
          n_rounds: 12,
          truncated: false,
        }),
      ),
    );
    renderPage('/explorer?g=event,status&v=table');
    expect(await screen.findByRole('link', { name: '2025-03-02' })).toHaveAttribute(
      'href',
      '/events/2025-03-02',
    );
    expect(screen.queryByRole('link', { name: 'member' })).toBeNull();
  });

  it('builds its chart option once per result, not on every re-render or URL change', async () => {
    captureSpecs();
    const { user, router } = renderPage('/explorer?g=year');
    await screen.findByRole('img', { name: 'Value by year' });
    const build = vi.mocked(buildExploreOption);
    build.mockClear();
    await user.click(screen.getByText('Filters'));
    await act(() => router.navigate('/explorer?g=year&elsewhere=1'));
    expect(router.state.location.search).toBe('?g=year&elsewhere=1');
    expect(build).not.toHaveBeenCalled();
  });

  it('writes a slider drag to the URL and runs one query once it settles, not one per step', async () => {
    const seen = captureSpecs();
    const { user, router } = renderPage();
    await screen.findByRole('img', { name: 'Value by Sunday' });
    await user.click(screen.getByText('Filters'));
    const writes = urlWrites(router);
    fakeSettleClock();
    const slider = screen.getByLabelText('Temperature minimum');
    for (let t = 1; t <= 30; t += 1) {
      if (t > 1) await tick(40); // pointer moves a step every 40 ms
      fireEvent.change(slider, { target: { value: String(t) } });
    }
    // The thumb and its readout follow the drag at once...
    expect(slider).toHaveValue('30');
    expect(slider).toHaveAttribute('aria-valuetext', '30 °F');
    expect(screen.getByText('30 °F – 110 °F')).toBeInTheDocument();
    // ...but the URL and the server see nothing until it has rested for SETTLE_MS.
    await tick(SETTLE_MS - 1);
    expect(writes).toEqual([]);
    await tick(1);
    expect(writes).toEqual(['?t=30..110']);
    realClock();
    await waitFor(() => expect(seen).toHaveLength(2));
    expect(seen[1]?.filters.temp_f).toEqual([30, 110]);
    expect(screen.getByText('Filters (1)')).toBeInTheDocument();
  });

  it('commits keyboard steps the same way: once they pause, and again after the next pause', async () => {
    const seen = captureSpecs();
    const { user, router } = renderPage();
    await screen.findByRole('img', { name: 'Value by Sunday' });
    await user.click(screen.getByText('Filters'));
    const writes = urlWrites(router);
    fakeSettleClock();
    const slider = screen.getByLabelText('Minimum rounds per shooter');
    // A native slider moves one step and fires a change event per arrow key press.
    for (const value of ['1', '2', '3']) {
      fireEvent.change(slider, { target: { value } });
      await tick(SETTLE_MS - 100); // presses 200 ms apart
    }
    expect(slider).toHaveValue('3');
    expect(writes).toEqual([]);
    await tick(100);
    expect(writes).toEqual(['?mr=3']);
    fireEvent.change(slider, { target: { value: '4' } });
    await tick(SETTLE_MS);
    expect(writes).toEqual(['?mr=3', '?mr=4']);
    expect(slider).toHaveValue('4');
    realClock();
    await waitFor(() => expect(seen.at(-1)?.filters.min_rounds).toBe(4));
    expect(seen.map((spec) => spec.filters.min_rounds)).toEqual([0, 3, 4]);
  });

  it('keeps a filter picked while a slider settles', async () => {
    captureSpecs();
    const { user, router } = renderPage();
    await screen.findByRole('img', { name: 'Value by Sunday' });
    await user.click(screen.getByText('Filters'));
    fakeSettleClock();
    fireEvent.change(screen.getByLabelText('Wind gust maximum'), { target: { value: '20' } });
    fireEvent.click(
      within(screen.getByRole('group', { name: 'Status' })).getByRole('button', { name: 'Guest' }),
    );
    await tick(0);
    expect(router.state.location.search).toBe('?st=guest');
    await tick(SETTLE_MS);
    expect(Object.fromEntries(new URLSearchParams(router.state.location.search))).toEqual({
      st: 'guest',
      gu: '0..20',
    });
    realClock();
  });

  it('writes a settled value again when another write lands before it renders', async () => {
    captureSpecs();
    const { user, router } = renderPage();
    await screen.findByRole('img', { name: 'Value by Sunday' });
    await user.click(screen.getByText('Filters'));
    const writes = urlWrites(router);
    fakeSettleClock();
    // Both settle in one tick, so the second setter writes over the URL it last rendered: t is lost.
    fireEvent.change(screen.getByLabelText('Temperature minimum'), { target: { value: '40' } });
    fireEvent.change(screen.getByLabelText('Minimum rounds per shooter'), {
      target: { value: '10' },
    });
    await tick(SETTLE_MS);
    expect(writes).toEqual(['?t=40..110', '?mr=10']);
    expect(screen.getByLabelText('Temperature minimum')).toHaveValue('40');
    // The temperature slider still differs from the URL, so it writes again once settled.
    await tick(SETTLE_MS - 1);
    expect(writes).toHaveLength(2);
    await tick(1);
    expect(writes).toEqual(['?t=40..110', '?mr=10', '?mr=10&t=40..110']);
    await tick(SETTLE_MS);
    expect(writes).toHaveLength(3);
    realClock();
  });

  it('writes nothing when a slider comes back to where it started', async () => {
    const seen = captureSpecs();
    const { router } = renderPage('/explorer?gu=0..30');
    await screen.findByRole('img', { name: 'Value by Sunday' });
    const writes = urlWrites(router);
    fakeSettleClock();
    const gust = screen.getByLabelText('Wind gust maximum');
    fireEvent.change(gust, { target: { value: '35' } });
    fireEvent.change(gust, { target: { value: '30' } });
    const rounds = screen.getByLabelText('Minimum rounds per shooter');
    fireEvent.change(rounds, { target: { value: '5' } });
    fireEvent.change(rounds, { target: { value: '0' } });
    await tick(SETTLE_MS);
    await act(() => router.navigate('/explorer?gu=0..30&st=guest', { replace: true }));
    await tick(SETTLE_MS);
    expect(writes).toEqual(['?gu=0..30&st=guest']);
    realClock();
    await waitFor(() => expect(seen).toHaveLength(2));
  });

  it('drops an unsettled slider value when the URL changes from elsewhere (Back, a link)', async () => {
    captureSpecs();
    const { router } = renderPage('/explorer?p=0..1');
    await screen.findByRole('img', { name: 'Value by Sunday' });
    fakeSettleClock();
    const slider = screen.getByLabelText('Rain maximum');
    fireEvent.change(slider, { target: { value: '0.5' } });
    expect(slider).toHaveValue('0.5');
    await act(() => router.navigate('/explorer?p=0..0.25'));
    expect(slider).toHaveValue('0.25');
    await tick(SETTLE_MS);
    expect(router.state.location.search).toBe('?p=0..0.25');
    expect(slider).toHaveValue('0.25');
    realClock();
  });

  it.each([
    ['Temperature minimum', '40', '?t=40..110', '/explorer', ''],
    ['Minimum rounds per shooter', '10', '?mr=10', '/explorer?rt=sporting', '?rt=sporting'],
  ])(
    'forgets a settled %s, so a link that drops it never brings it back',
    async (label, moved, settled, link, landed) => {
      captureSpecs();
      const { router } = renderPage();
      await screen.findByRole('img', { name: 'Value by Sunday' });
      fakeSettleClock();
      const slider = screen.getByLabelText(label);
      fireEvent.change(slider, { target: { value: moved } });
      await tick(SETTLE_MS);
      expect(router.state.location.search).toBe(settled);
      // A link to the page without the key (a PUSH; the page stays mounted) brings back its default.
      await act(() => router.navigate(link));
      expect(slider).toHaveValue('0');
      await tick(SETTLE_MS);
      expect(router.state.location.search).toBe(landed);
      expect(slider).toHaveValue('0');
      realClock();
    },
  );

  it('forgets an unsettled slider value for good, so Back to where it started keeps that URL', async () => {
    captureSpecs();
    const { router } = renderPage('/explorer?mr=3');
    await screen.findByRole('img', { name: 'Value by Sunday' });
    fakeSettleClock();
    const slider = screen.getByLabelText('Minimum rounds per shooter');
    fireEvent.change(slider, { target: { value: '5' } });
    await act(() => router.navigate('/explorer?mr=4'));
    await tick(SETTLE_MS);
    expect(router.state.location.search).toBe('?mr=4');
    await act(() => router.navigate(-1));
    expect(router.state.location.search).toBe('?mr=3');
    expect(slider).toHaveValue('3');
    await tick(SETTLE_MS);
    expect(router.state.location.search).toBe('?mr=3');
    expect(slider).toHaveValue('3');
    realClock();
  });

  it('keeps the Filters panel open when the last filter is cleared', async () => {
    captureSpecs();
    const { user } = renderPage('/explorer?st=guest');
    await screen.findByRole('img', { name: 'Value by Sunday' });
    expect(screen.getByText('Filters (1)').closest('details')).toHaveAttribute('open');
    await user.click(
      within(screen.getByRole('group', { name: 'Status' })).getByRole('button', { name: 'Guest' }),
    );
    expect(screen.getByText('Filters').closest('details')).toHaveAttribute('open');
  });

  it.each([
    ['/explorer?m=rounds&g=year', 'Value by year', 'explorer-rounds-by-year.csv'],
    ['/explorer?m=rounds&g=', 'Value', 'explorer-rounds.csv'],
  ])('names the CSV of %s after the query', async (route, chartName, filename) => {
    captureSpecs();
    const names: string[] = [];
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (
      this: HTMLAnchorElement,
    ) {
      names.push(this.download);
    });
    const { user } = renderPage(route);
    await screen.findByRole('img', { name: chartName });
    await user.click(screen.getByRole('button', { name: 'CSV' }));
    expect(names).toEqual([filename]);
  });

  describe('insight links (Plan 12)', () => {
    it('sends the minimum score and year-to-date cut, shown as removable filters', async () => {
      const seen = captureSpecs();
      const { user } = renderPage('/explorer?m=score&a=count&g=year&ms=40&ytd=09-27');
      await screen.findByRole('img', { name: 'Value by year' });
      expect(seen[0]?.filters).toMatchObject({ min_score: 40, ytd: '09-27' });
      await user.click(screen.getByRole('button', { name: 'Clear minimum score' }));
      await waitFor(() => expect(seen.at(-1)?.filters.min_score).toBeNull());
      expect(screen.getByText('Each year to Sep 27')).toBeInTheDocument();
      await user.click(screen.getByRole('button', { name: 'Clear year to date' }));
      await waitFor(() => expect(seen.at(-1)?.filters.ytd).toBeNull());
      expect(screen.queryByText('Each year to Sep 27')).toBeNull();
    });

    it.each(['99', 'abc', '-1'])('ignores an unusable minimum score (%s)', async (bad) => {
      const seen = captureSpecs();
      renderPage(`/explorer?m=score&a=count&g=year&ms=${bad}`);
      await screen.findByRole('img', { name: 'Value by year' });
      expect(seen[0]?.filters.min_score).toBeNull();
      expect(screen.queryByRole('button', { name: 'Clear minimum score' })).toBeNull();
    });

    it('runs the compare query and draws it as a dashed "Everyone" line', async () => {
      const seen = captureSpecs();
      const { user, router } = renderPage(
        '/explorer?m=score&a=avg&g=year&sh=3&best=1&cmp.m=adjusted',
      );
      await screen.findByRole('img', { name: 'Value by year' });
      await waitFor(() => expect(seen).toHaveLength(2));
      const compare = seen.find((spec) => spec.metric === 'adjusted');
      expect(compare?.filters).toMatchObject({ shooter_ids: [], best_round_only: false });
      expect(seen.find((spec) => spec.metric === 'score')?.filters.shooter_ids).toEqual([3]);
      await user.click(await screen.findByRole('button', { name: 'Stop comparing' }));
      expect(router.state.location.search).not.toContain('cmp.');
    });

    it('shows no round count for how the day played, a Sunday total', async () => {
      captureSpecs();
      renderPage('/explorer?m=difficulty&g=event');
      await screen.findByRole('button', { name: 'CSV' });
      expect(screen.queryByText(/Based on/)).toBeNull();
    });

    it('shows the "Dashed line" chip only once the compare result is in', async () => {
      server.use(
        http.post('/api/explore', async ({ request }) => {
          const spec = (await request.json()) as QuerySpec;
          if (spec.metric === 'adjusted') return new HttpResponse(null, { status: 500 });
          return HttpResponse.json(fakeExploreResult(spec));
        }),
      );
      renderPage('/explorer?m=score&a=avg&g=year&cmp.m=adjusted');
      await screen.findByRole('img', { name: 'Value by year' });
      expect(screen.queryByRole('button', { name: 'Stop comparing' })).toBeNull();
    });

    it('highlights the linked shooter and draws the reference line', async () => {
      captureSpecs();
      renderPage('/explorer?m=residual&a=max&g=shooter&v.hl=s:4&v.ref=0');
      const region = await screen.findByRole('region', { name: 'Value by shooter' });
      expect(within(region).getByText('Showing what the insight points to.')).toBeInTheDocument();
      const chart = getInstanceByDom(within(region).getByRole('img', { name: 'Value by shooter' }));
      const [bars] = (chart?.getOption() as { series: { data: unknown[]; markLine?: unknown }[] })
        .series;
      // Shooter 4 is row 'B' of the fake result: only that bar is ringed.
      expect(bars?.data[0]).toBe(36);
      expect(bars?.data[1]).toMatchObject({ value: 34, itemStyle: { borderWidth: 3 } });
      expect(bars?.markLine).toMatchObject({ data: [{ xAxis: 0 }] });
    });
  });
});

describe('ExplorerPage fullscreen and CSV', () => {
  /** 2 rows when the page asks for its 500 limit, 4 when fullscreen asks for every row. */
  function serveByLimit(seen: QuerySpec[], truncatedAt5000 = false) {
    server.use(
      http.post('/api/explore', async ({ request }) => {
        const spec = (await request.json()) as QuerySpec;
        seen.push(spec);
        const base = fakeExploreResult(spec);
        if (spec.limit !== 5000) return HttpResponse.json(base);
        const first = spec.group_by[0] ?? 'year';
        const extra = ['C', 'D'].map((k, i) => ({ [first]: k, value: 30 - i, n: 2 }));
        return HttpResponse.json({
          ...base,
          rows: [...base.rows, ...extra],
          truncated: truncatedAt5000,
        });
      }),
    );
  }

  it('fullscreen and CSV ask for every row and every date; the card keeps the window', async () => {
    const seen: QuerySpec[] = [];
    serveByLimit(seen);
    const csv = captureCsv();
    const { user } = renderPage('/explorer?v=table');
    const region = await screen.findByRole('region', { name: 'Value by Sunday' });
    expect(within(region).getAllByRole('row')).toHaveLength(1 + 2);
    const dialog = await openFullscreen(user, region, 'Value by Sunday');
    expect(
      await within(dialog).findByText('Every Sunday on record, not just the time window.'),
    ).toBeInTheDocument();
    expect(within(dialog).getAllByRole('row')).toHaveLength(1 + 4);
    const full = seen.find((spec) => spec.limit === 5000);
    expect(full?.filters.date_from).toBeNull();
    expect(full?.filters.date_to).toBeNull();
    await user.click(within(region).getByRole('button', { name: 'CSV' }));
    await waitFor(() => expect(csv.names).toEqual(['explorer-score-by-event.csv']));
    expect((await csv.text()).trimEnd().split('\r\n')).toHaveLength(1 + 4);
    expect(seen.filter((spec) => spec.limit === 5000)).toHaveLength(1);
  });

  it('CSV alone fetches the full rows', async () => {
    const seen: QuerySpec[] = [];
    serveByLimit(seen);
    const csv = captureCsv();
    const { user } = renderPage();
    const region = await screen.findByRole('region', { name: 'Value by Sunday' });
    await user.click(within(region).getByRole('button', { name: 'CSV' }));
    await waitFor(() => expect(csv.names).toHaveLength(1));
    expect((await csv.text()).trimEnd().split('\r\n')).toHaveLength(1 + 4);
  });

  it('lifts a Custom window in fullscreen too: every Sunday, not just the chosen dates', async () => {
    const seen: QuerySpec[] = [];
    serveByLimit(seen);
    const { user } = renderPage('/explorer?w=2026-01-01..2026-03-01');
    const region = await screen.findByRole('region', { name: 'Value by Sunday' });
    expect(seen[0]?.filters).toMatchObject({ date_from: '2026-01-01', date_to: '2026-03-01' });
    const dialog = await openFullscreen(user, region, 'Value by Sunday');
    await waitFor(() => expect(seen.some((spec) => spec.limit === 5000)).toBe(true));
    const full = seen.find((spec) => spec.limit === 5000);
    expect(full?.filters).toMatchObject({ date_from: null, date_to: null });
    expect(
      await within(dialog).findByText('Every Sunday on record, not just the time window.'),
    ).toBeInTheDocument();
  });

  it('has no note in fullscreen when All time is chosen and nothing was cut off', async () => {
    const seen: QuerySpec[] = [];
    serveByLimit(seen);
    const { user } = renderPage('/explorer?w=all&v=table');
    const region = await screen.findByRole('region', { name: 'Value by year' });
    const dialog = await openFullscreen(user, region, 'Value by year');
    await waitFor(() => expect(within(dialog).getAllByRole('row')).toHaveLength(1 + 4));
    expect(within(dialog).queryByText(/Every Sunday on record/)).toBeNull();
    expect(within(dialog).queryByText(/Showing the first/)).toBeNull();
  });

  it('says when even the full result was cut off', async () => {
    const seen: QuerySpec[] = [];
    serveByLimit(seen, true);
    const { user } = renderPage();
    const region = await screen.findByRole('region', { name: 'Value by Sunday' });
    const dialog = await openFullscreen(user, region, 'Value by Sunday');
    expect(
      await within(dialog).findByText(
        'Every Sunday on record, not just the time window. Showing the first 4 rows.',
      ),
    ).toBeInTheDocument();
  });

  it('drops the window sentence when the time window is already all history', async () => {
    const seen: QuerySpec[] = [];
    serveByLimit(seen, true);
    const { user } = renderPage('/explorer?w=all');
    const region = await screen.findByRole('region', { name: 'Value by year' });
    const dialog = await openFullscreen(user, region, 'Value by year');
    expect(await within(dialog).findByText('Showing the first 4 rows.')).toBeInTheDocument();
    expect(within(dialog).queryByText(/Every Sunday on record/)).toBeNull();
  });

  it('follows the result on screen, not a newer spec still loading', async () => {
    const seen: QuerySpec[] = [];
    let release = () => {};
    const gate = new Promise<void>((r) => {
      release = r;
    });
    server.use(
      http.post('/api/explore', async ({ request }) => {
        const spec = (await request.json()) as QuerySpec;
        seen.push(spec);
        if (spec.limit !== 5000 && spec.filters.date_from === '2026-01-01') await gate;
        return HttpResponse.json(fakeExploreResult(spec));
      }),
    );
    const { user, router } = renderPage();
    const region = await screen.findByRole('region', { name: 'Value by Sunday' });
    await act(async () => {
      await router.navigate('/explorer?w=2026-01-01..2026-03-01');
    });
    await waitFor(() => expect(seen.some((s) => s.filters.date_from === '2026-01-01')).toBe(true));
    await openFullscreen(user, region, 'Value by Sunday');
    await waitFor(() => expect(seen.some((s) => s.limit === 5000)).toBe(true));
    const full = seen.find((s) => s.limit === 5000);
    expect(full?.filters.date_from).toBeNull();
    release();
  });

  it('fetches the compare line with the same dates and limit', async () => {
    const seen: QuerySpec[] = [];
    serveByLimit(seen);
    const { user } = renderPage('/explorer?m=score&a=avg&g=year&cmp.m=adjusted');
    const region = await screen.findByRole('region', { name: 'Value by year' });
    await openFullscreen(user, region, 'Value by year');
    await waitFor(() => expect(seen.filter((spec) => spec.limit === 5000)).toHaveLength(2));
    const compare = seen.find((spec) => spec.limit === 5000 && spec.metric === 'adjusted');
    expect(compare?.filters.date_from).toBeNull();
    expect(compare?.filters.date_to).toBeNull();
  });
});
