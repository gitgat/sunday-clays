import { act, fireEvent, screen, waitFor, within } from '@testing-library/react';
import { getInstanceByDom } from 'echarts/core';
import { delay, http, HttpResponse } from 'msw';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { captureCsv, expectChartControls, expectExplainer } from '../../test/charts';
import { server } from '../../test/msw/server';
import { renderWithProviders } from '../../test/render';
import { ChartCard, type ChartCardProps } from './ChartCard';
import type * as Explore from './explore';
import {
  allHistorySpec,
  buildExploreOption,
  querySpec,
  type QueryResult,
  type QuerySpec,
} from './explore';

// The real builder, wrapped so a test can count how often a card rebuilds its chart option.
vi.mock('./explore', async (importOriginal) => {
  const actual = await importOriginal<typeof Explore>();
  return { ...actual, buildExploreOption: vi.fn(actual.buildExploreOption) };
});

function result(spec: QuerySpec): QueryResult {
  const dim = spec.group_by[0] ?? 'year';
  return {
    columns: [
      { key: dim, label: dim, type: 'string' },
      { key: 'value', label: 'Value', type: 'number' },
      { key: 'n', label: 'n', type: 'int' },
    ],
    rows: [
      { [dim]: 'a', value: 1, n: 1 },
      { [dim]: 'b', value: 2, n: 2 },
    ],
    n_rounds: 3,
    truncated: false,
  };
}

function captureExplore(): QuerySpec[] {
  const seen: QuerySpec[] = [];
  server.use(
    http.post('/api/explore', async ({ request }) => {
      const spec = (await request.json()) as QuerySpec;
      seen.push(spec);
      return HttpResponse.json(result(spec));
    }),
  );
  return seen;
}

const BASE: ChartCardProps = {
  title: 'Turnout vs weather',
  spec: querySpec({ metric: 'attendance', group_by: ['condition'] }),
  chartTypes: ['bar', 'line'],
  allowedGroupBy: ['condition', 'temp_band'],
  urlKey: 'turnout',
};

describe('ChartCard', () => {
  it('queries /api/explore with the spec and renders the result in a ChartFrame', async () => {
    const seen = captureExplore();
    renderWithProviders(<ChartCard {...BASE} />);
    await screen.findByRole('img', { name: 'Turnout vs weather' });
    const region = screen.getByRole('region', { name: 'Turnout vs weather' });
    expect(within(region).getByRole('img', { name: 'Turnout vs weather' })).toBeInTheDocument();
    expectChartControls(region);
    expect(seen[0]).toEqual(BASE.spec);
  });

  it('merges the global round-type filter unless the card sets its own', async () => {
    const seen = captureExplore();
    renderWithProviders(<ChartCard {...BASE} />, { route: '/?rt=sporting' });
    await screen.findByRole('img', { name: 'Turnout vs weather' });
    expect(seen[0]?.filters.round_types).toEqual(['sporting']);

    const own = querySpec({
      metric: 'attendance',
      group_by: ['condition'],
      filters: { round_types: ['super_sporting'] },
    });
    renderWithProviders(<ChartCard {...BASE} urlKey="own" spec={own} />, {
      route: '/?rt=sporting',
    });
    expect(await screen.findByText('Round type: Super Sporting')).toBeInTheDocument();
    expect(seen.at(-1)?.filters.round_types).toEqual(['super_sporting']);
  });

  it('switches group-by, metric, chart type and best-round-only through URL-backed chips', async () => {
    const seen = captureExplore();
    const { user, router } = renderWithProviders(
      <ChartCard
        {...BASE}
        spec={querySpec({ metric: 'score', group_by: ['condition'] })}
        allowedMetrics={['score', 'adjusted']}
      />,
    );
    await screen.findByRole('img', { name: 'Turnout vs weather' });
    await user.click(screen.getByRole('button', { name: 'By temperature' }));
    await user.click(screen.getByRole('button', { name: 'Adjusted score' }));
    await user.click(screen.getByRole('button', { name: 'Line' }));
    await user.click(screen.getByRole('button', { name: 'Best round only' }));
    expect(router.state.location.search).toBe(
      '?turnout.g=temp_band&turnout.m=adjusted&turnout.t=line&turnout.b=1',
    );
    const last = seen.at(-1);
    expect(last?.group_by).toEqual(['temp_band']);
    expect(last?.metric).toBe('adjusted');
    expect(last?.filters.best_round_only).toBe(true);
    const chart = getInstanceByDom(screen.getByRole('img', { name: 'Turnout vs weather' }));
    expect((chart?.getOption() as { series: { type: string }[] }).series[0]?.type).toBe('line');
  });

  it('keeps drawing the previous result while a new grouping loads', async () => {
    let calls = 0;
    let release = () => {};
    const held = new Promise<void>((resolve) => {
      release = resolve;
    });
    server.use(
      http.post('/api/explore', async ({ request }) => {
        calls += 1;
        const spec = (await request.json()) as QuerySpec;
        if (calls > 1) await held; // the second (temperature) answer waits for release()
        return HttpResponse.json(result(spec));
      }),
    );
    const { user } = renderWithProviders(<ChartCard {...BASE} />);
    await screen.findByRole('img', { name: 'Turnout vs weather' });
    await user.click(screen.getByRole('button', { name: 'By temperature' }));
    // The condition-grouped result is still on screen, drawn with its own grouping.
    expect(screen.getByRole('img', { name: 'Turnout vs weather' })).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Table' }));
    expect(screen.getAllByRole('columnheader').map((h) => h.textContent)).toEqual([
      'condition',
      'Value',
      'n',
    ]);
    release();
    expect(await screen.findByRole('columnheader', { name: 'temp_band' })).toBeInTheDocument();
  });

  it('drills by the grouping on screen while a new grouping loads', async () => {
    let calls = 0;
    let release = () => {};
    const held = new Promise<void>((resolve) => {
      release = resolve;
    });
    server.use(
      http.post('/api/explore', async ({ request }) => {
        calls += 1;
        const spec = (await request.json()) as QuerySpec;
        if (calls > 1) await held;
        return HttpResponse.json(result(spec));
      }),
    );
    const { user, router } = renderWithProviders(
      <ChartCard {...BASE} drill={(row) => `/x?c=${String(row.condition)}`} />,
    );
    await screen.findByRole('img', { name: 'Turnout vs weather' });
    await user.click(screen.getByRole('button', { name: 'By temperature' }));
    // Still the condition-grouped chart: bar 'b' is the row whose condition is 'b'.
    getInstanceByDom(screen.getByRole('img', { name: 'Turnout vs weather' }))?.trigger('click', {
      name: 'b',
      seriesName: 'Value',
    } as never);
    expect(router.state.location.pathname + router.state.location.search).toBe('/x?c=b');
    release();
  });

  it('leaves out the date chips when the dates come from the time window', async () => {
    captureExplore();
    const spec = querySpec({
      metric: 'attendance',
      group_by: ['condition'],
      filters: { date_from: '2026-06-28', date_to: '2026-09-27', statuses: ['member'] },
    });
    renderWithProviders(<ChartCard {...BASE} spec={spec} datesFromWindow />);
    // Other filters still show; the window's own dates are the tag beside the title instead.
    expect(await screen.findByText('Status: member')).toBeInTheDocument();
    expect(screen.queryByText(/^From |^To /)).toBeNull();
  });

  it('describes its own filters as chips', async () => {
    captureExplore();
    const spec = querySpec({
      metric: 'score',
      group_by: ['year'],
      filters: {
        date_from: '2025-01-01',
        date_to: '2025-12-31',
        statuses: ['member'],
        gauges: ['unspecified'],
        shooter_ids: [1, 2],
        min_rounds: 5,
        temp_f: [40, 70],
        gust_mph: [0, 10],
        precip_in: [0, 0.02],
      },
    });
    renderWithProviders(
      <ChartCard {...BASE} allowedGroupBy={undefined} chartTypes={['bar']} spec={spec} />,
    );
    for (const text of [
      'From 2025-01-01',
      'To 2025-12-31',
      'Status: member',
      'Gauge: unspecified',
      '2 shooter(s)',
      '≥5 rounds',
      '40–70 °F',
      'Gusts 0–10 mph',
      'Rain 0–0.02 in',
    ]) {
      expect(await screen.findByText(text)).toBeInTheDocument();
    }
    expect(screen.queryByRole('button', { name: 'Bar' })).toBeNull();
  });

  it('shows a loading skeleton, then an empty state when nothing matches', async () => {
    server.use(
      http.post('/api/explore', async () => {
        await delay(20);
        return HttpResponse.json({ columns: [], rows: [], n_rounds: 0, truncated: false });
      }),
    );
    renderWithProviders(<ChartCard {...BASE} />);
    expect(screen.getByRole('status', { name: 'Loading Turnout vs weather' })).toBeInTheDocument();
    expect(
      await screen.findByRole('heading', { name: 'No data for these filters' }),
    ).toBeInTheDocument();
  });

  it("shows the server's invalid_query message and retries", async () => {
    let calls = 0;
    server.use(
      http.post('/api/explore', async ({ request }) => {
        calls += 1;
        const spec = (await request.json()) as QuerySpec;
        return calls === 1
          ? HttpResponse.json(
              {
                error: {
                  code: 'invalid_query',
                  message: 'Grouping by station needs the Hit % metric',
                },
              },
              { status: 400 },
            )
          : HttpResponse.json(result(spec));
      }),
    );
    const { user } = renderWithProviders(<ChartCard {...BASE} />);
    expect(
      await screen.findByText('Grouping by station needs the Hit % metric'),
    ).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Try again' }));
    expect(await screen.findByRole('img', { name: 'Turnout vs weather' })).toBeInTheDocument();
  });

  it('keeps its chips on an error so a bad choice can be undone', async () => {
    server.use(
      http.post('/api/explore', async ({ request }) => {
        const spec = (await request.json()) as QuerySpec;
        return spec.group_by[0] === 'temp_band'
          ? HttpResponse.json(
              { error: { code: 'invalid_query', message: 'No weather for these events' } },
              { status: 400 },
            )
          : HttpResponse.json(result(spec));
      }),
    );
    const { user } = renderWithProviders(<ChartCard {...BASE} />);
    await screen.findByRole('img', { name: 'Turnout vs weather' });
    await user.click(screen.getByRole('button', { name: 'By temperature' }));
    expect(await screen.findByText('No weather for these events')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'By conditions' }));
    expect(await screen.findByRole('img', { name: 'Turnout vs weather' })).toBeInTheDocument();
  });

  it('drills from a table row link and from a clicked bar', async () => {
    captureExplore();
    const { user, router } = renderWithProviders(
      <ChartCard {...BASE} drill={(row) => `/events?c=${String(row.condition)}`} />,
    );
    await screen.findByRole('img', { name: 'Turnout vs weather' });
    await user.click(screen.getByRole('button', { name: 'Table' }));
    expect(screen.getByRole('link', { name: 'a' })).toHaveAttribute('href', '/events?c=a');
    await user.click(screen.getByRole('button', { name: 'Table' }));
    const img = await screen.findByRole('img', { name: 'Turnout vs weather' });
    getInstanceByDom(img)?.trigger('click', { name: 'b', seriesName: 'Value' } as never);
    expect(router.state.location.pathname + router.state.location.search).toBe('/events?c=b');
  });

  it('draws one total bar when the card has no grouping', async () => {
    const seen: QuerySpec[] = [];
    server.use(
      http.post('/api/explore', async ({ request }) => {
        seen.push((await request.json()) as QuerySpec);
        return HttpResponse.json({
          columns: [
            { key: 'value', label: 'Rounds', type: 'int' },
            { key: 'n', label: 'n', type: 'int' },
          ],
          rows: [{ value: 7480, n: 7480 }],
          n_rounds: 7480,
          truncated: false,
        });
      }),
    );
    renderWithProviders(
      <ChartCard
        title="Rounds shot"
        spec={querySpec({ metric: 'rounds' })}
        chartTypes={['line']}
        urlKey="total"
      />,
    );
    const img = await screen.findByRole('img', { name: 'Rounds shot' });
    const option = getInstanceByDom(img)?.getOption() as {
      xAxis: { data: string[] }[];
      series: { type: string; data: number[] }[];
    };
    expect(option.xAxis[0]?.data).toEqual(['All']);
    expect(option.series[0]?.data).toEqual([7480]);
    expect(seen[0]?.group_by).toEqual([]);
    expect(screen.queryByRole('button', { name: /^By / })).toBeNull();
  });

  it('draws bars when the card offers no chart type', async () => {
    captureExplore();
    renderWithProviders(<ChartCard {...BASE} chartTypes={[]} />);
    const img = await screen.findByRole('img', { name: 'Turnout vs weather' });
    const option = getInstanceByDom(img)?.getOption() as { series: { type: string }[] };
    expect(option.series[0]?.type).toBe('bar');
    expect(screen.queryByRole('button', { name: 'Bar' })).toBeNull();
  });

  it('ignores clicks that match no row', async () => {
    captureExplore();
    const { router } = renderWithProviders(<ChartCard {...BASE} drill={() => '/elsewhere'} />);
    const img = await screen.findByRole('img', { name: 'Turnout vs weather' });
    getInstanceByDom(img)?.trigger('click', { name: 'zzz' } as never);
    expect(router.state.location.pathname).toBe('/');
  });

  it('offers no "Best round only" chip on an attendance card and never sends the flag', async () => {
    const seen = captureExplore();
    renderWithProviders(<ChartCard {...BASE} />, { route: '/?turnout.b=1' });
    await screen.findByRole('img', { name: 'Turnout vs weather' });
    expect(screen.queryByRole('button', { name: 'Best round only' })).toBeNull();
    expect(seen.map((s) => s.filters.best_round_only)).toEqual([false]);
  });

  it('drops best-round-only while attendance is the metric and restores it after', async () => {
    const seen = captureExplore();
    const { user } = renderWithProviders(
      <ChartCard
        {...BASE}
        spec={querySpec({ metric: 'score', group_by: ['condition'] })}
        allowedMetrics={['score', 'attendance']}
      />,
      { route: '/?turnout.b=1' },
    );
    await screen.findByRole('img', { name: 'Turnout vs weather' });
    expect(seen.at(-1)?.filters.best_round_only).toBe(true);
    await user.click(screen.getByRole('button', { name: 'Attendance' }));
    await waitFor(() => expect(seen.at(-1)?.metric).toBe('attendance'));
    expect(seen.at(-1)?.filters.best_round_only).toBe(false);
    expect(screen.queryByRole('button', { name: 'Best round only' })).toBeNull();
    await user.click(screen.getByRole('button', { name: 'Score' }));
    expect(screen.getByRole('button', { name: 'Best round only' })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
    expect(seen.filter((s) => s.metric === 'attendance' && s.filters.best_round_only)).toEqual([]);
  });

  it('keeps the global round-type filter when it drills (C10: the filter is global)', async () => {
    captureExplore();
    const { user, router } = renderWithProviders(
      <ChartCard {...BASE} drill={(row) => `/events?c=${String(row.condition)}`} />,
      { route: '/?rt=sporting' },
    );
    await screen.findByRole('img', { name: 'Turnout vs weather' });
    await user.click(screen.getByRole('button', { name: 'Table' }));
    expect(screen.getByRole('link', { name: 'a' })).toHaveAttribute(
      'href',
      '/events?c=a&rt=sporting',
    );
    await user.click(screen.getByRole('button', { name: 'Table' }));
    const img = await screen.findByRole('img', { name: 'Turnout vs weather' });
    getInstanceByDom(img)?.trigger('click', { name: 'b', seriesName: 'Value' } as never);
    expect(router.state.location.pathname + router.state.location.search).toBe(
      '/events?c=b&rt=sporting',
    );
  });

  it('drills from a clicked heatmap cell', async () => {
    server.use(
      http.post('/api/explore', () =>
        HttpResponse.json({
          columns: [
            { key: 'condition', label: 'Conditions', type: 'string' },
            { key: 'temp_band', label: 'Temperature', type: 'string' },
            { key: 'value', label: 'Attendance', type: 'number' },
            { key: 'n', label: 'n', type: 'int' },
          ],
          rows: [
            { condition: 'dry', temp_band: 'cold', value: 20, n: 2 },
            { condition: 'dry', temp_band: 'warm', value: 30, n: 3 },
            { condition: 'wet', temp_band: 'cold', value: 10, n: 1 },
          ],
          n_rounds: 6,
          truncated: false,
        } satisfies QueryResult),
      ),
    );
    const { router } = renderWithProviders(
      <ChartCard
        {...BASE}
        spec={querySpec({ metric: 'attendance', group_by: ['condition', 'temp_band'] })}
        chartTypes={['heatmap']}
        drill={(row) => `/events?c=${String(row.condition)}&t=${String(row.temp_band)}`}
      />,
    );
    const img = await screen.findByRole('img', { name: 'Turnout vs weather' });
    // Temperature bands run across (x: cold, warm), conditions down (y: dry, wet).
    getInstanceByDom(img)?.trigger('click', {
      seriesType: 'heatmap',
      seriesName: 'Attendance',
      value: [1, 0, 30],
    } as never);
    expect(router.state.location.pathname + router.state.location.search).toBe(
      '/events?c=dry&t=warm',
    );
  });

  it('builds its chart option once per result, not on every URL change', async () => {
    captureExplore();
    const { router } = renderWithProviders(<ChartCard {...BASE} />);
    await screen.findByRole('img', { name: 'Turnout vs weather' });
    const build = vi.mocked(buildExploreOption);
    build.mockClear();
    await act(() => router.navigate('/?elsewhere=1'));
    await act(() => router.navigate('/?elsewhere=2'));
    expect(router.state.location.search).toBe('?elsewhere=2');
    expect(build).not.toHaveBeenCalled();
  });

  it('notes a truncated result, still charting, tabling and exporting every returned row', async () => {
    server.use(
      http.post('/api/explore', async ({ request }) =>
        HttpResponse.json({ ...result((await request.json()) as QuerySpec), truncated: true }),
      ),
    );
    const { user } = renderWithProviders(<ChartCard {...BASE} />);
    expect(await screen.findByText('Showing the first 2 rows')).toBeInTheDocument();
    expect(screen.getByRole('img', { name: 'Turnout vs weather' })).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Table' }));
    expect(screen.getAllByRole('row')).toHaveLength(3);
    expect(screen.getByText('Showing the first 2 rows')).toBeInTheDocument();
  });

  it('shows no truncation note for a complete result', async () => {
    captureExplore();
    renderWithProviders(<ChartCard {...BASE} />);
    await screen.findByRole('img', { name: 'Turnout vs weather' });
    expect(screen.queryByText(/^Showing the first/)).toBeNull();
  });

  it('falls back to the spec defaults for hand-edited card keys', async () => {
    const seen = captureExplore();
    const spec = querySpec({ metric: 'score', group_by: ['condition'] });
    renderWithProviders(
      <ChartCard {...BASE} spec={spec} allowedMetrics={['score', 'adjusted']} />,
      { route: '/?turnout.m=bogus&turnout.g=zzz&turnout.t=abc&turnout.b=x' },
    );
    const img = await screen.findByRole('img', { name: 'Turnout vs weather' });
    expect(seen).toEqual([spec]);
    expect(
      (getInstanceByDom(img)?.getOption() as { series: { type: string }[] }).series[0]?.type,
    ).toBe('bar');
    for (const name of ['Score', 'By conditions', 'Bar']) {
      expect(screen.getByRole('button', { name })).toHaveAttribute('aria-pressed', 'true');
    }
    expect(screen.getByRole('button', { name: 'Best round only' })).toHaveAttribute(
      'aria-pressed',
      'false',
    );
  });

  it('passes its explainer to the frame', async () => {
    captureExplore();
    renderWithProviders(
      <ChartCard
        {...BASE}
        explainer={{ what: 'Turnout by weather.', computed: ['Count of shooters.'] }}
      />,
    );
    await screen.findByRole('img', { name: 'Turnout vs weather' });
    await expectExplainer(screen.getByRole('region', { name: 'Turnout vs weather' }), undefined, {
      read: false,
    });
  });
});

describe('ChartCard fullSpec', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  const FULL_ROWS = [
    { condition: 'a', value: 1, n: 1 },
    { condition: 'b', value: 2, n: 2 },
    { condition: 'c', value: 3, n: 3 },
  ];

  /** Every request's spec; the all-history one (limit 5000) answers with three rows. */
  function captureFull(truncated = false): QuerySpec[] {
    const seen: QuerySpec[] = [];
    server.use(
      http.post('/api/explore', async ({ request }) => {
        const spec = (await request.json()) as QuerySpec;
        seen.push(spec);
        const base = result(spec);
        return HttpResponse.json(
          spec.limit === 5000 ? { ...base, rows: FULL_ROWS, truncated } : base,
        );
      }),
    );
    return seen;
  }

  const spec = querySpec({
    metric: 'attendance',
    group_by: ['condition'],
    filters: { date_from: '2026-06-28', date_to: '2026-09-27' },
  });

  it('fetches every row only when fullscreen opens, and shows them in the dialog table', async () => {
    const seen = captureFull();
    const { user, router } = renderWithProviders(
      <ChartCard {...BASE} spec={spec} fullSpec={allHistorySpec} />,
    );
    await screen.findByRole('img', { name: 'Turnout vs weather' });
    fireEvent.scroll(globalThis.window);
    expect(seen).toHaveLength(1);
    await user.click(screen.getByRole('button', { name: 'Fullscreen' }));
    expect(router.state.location.search).toBe('?turnout.v=full');
    const dialog = screen.getByRole('dialog', { name: 'Turnout vs weather' });
    await waitFor(() => expect(seen).toHaveLength(2));
    expect(seen[1]?.limit).toBe(5000);
    expect(seen[1]?.filters.date_from).toBeNull();
    expect(seen[1]?.filters.date_to).toBeNull();
    await user.click(screen.getByRole('button', { name: 'Table' }));
    await waitFor(() => expect(within(dialog).getAllByRole('row')).toHaveLength(4));
    expect(within(dialog).queryByText(/Showing the first/)).toBeNull();
  });

  it('says so in the dialog when the full result is cut short', async () => {
    captureFull(true);
    const { user } = renderWithProviders(<ChartCard {...BASE} fullSpec={allHistorySpec} />);
    await screen.findByRole('img', { name: 'Turnout vs weather' });
    await user.click(screen.getByRole('button', { name: 'Fullscreen' }));
    const dialog = screen.getByRole('dialog', { name: 'Turnout vs weather' });
    expect(await within(dialog).findByText('Showing the first 3 rows')).toBeVisible();
  });

  it('downloads the full spec rows as CSV', async () => {
    const seen = captureFull();
    const csv = captureCsv();
    const { user } = renderWithProviders(<ChartCard {...BASE} fullSpec={allHistorySpec} />);
    await screen.findByRole('img', { name: 'Turnout vs weather' });
    await user.click(screen.getByRole('button', { name: 'CSV' }));
    await waitFor(() => expect(csv.names).toEqual(['turnout.csv']));
    expect(seen.at(-1)?.limit).toBe(5000);
    expect(seen.at(-1)?.filters.date_from).toBeNull();
    expect(seen.at(-1)?.filters.date_to).toBeNull();
    expect((await csv.text()).trimEnd().split('\r\n')).toHaveLength(4);
  });

  it('makes no second request for CSV without fullSpec', async () => {
    const seen = captureFull();
    const csv = captureCsv();
    const { user } = renderWithProviders(<ChartCard {...BASE} />);
    await screen.findByRole('img', { name: 'Turnout vs weather' });
    await user.click(screen.getByRole('button', { name: 'CSV' }));
    await waitFor(() => expect(csv.names).toHaveLength(1));
    expect(seen).toHaveLength(1);
  });
});
