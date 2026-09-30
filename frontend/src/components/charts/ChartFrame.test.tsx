import { screen, waitFor, within } from '@testing-library/react';
import type { EChartsOption } from 'echarts';
import { getInstanceByDom } from 'echarts/core';
import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  captureCsv,
  chartOptionIn,
  expectChartControls,
  expectExplainer,
  openFullscreen,
} from '../../test/charts';
import { renderWithProviders } from '../../test/render';
import { stubViewport } from '../../test/viewport';
import { ChartFrame, type ChartFrameProps } from './ChartFrame';
import type { ChartFull, Explainer, TabularData } from './types';

const DATA: TabularData = {
  columns: [
    { key: 'year', label: 'Year', type: 'int' },
    { key: 'value', label: 'Avg score', type: 'number' },
    { key: 'note', label: 'Note', type: 'string' },
  ],
  rows: [
    { year: 2025, value: 35.2668, note: '=cmd' },
    { year: 2026, value: null, note: 'ok' },
  ],
};
const OPTION: EChartsOption = {
  xAxis: { type: 'category', data: ['2025', '2026'] },
  yAxis: { type: 'value' },
  series: [{ type: 'bar', data: [35.27, null] }],
};

function renderFrame(props: Partial<ChartFrameProps> = {}, route = '/club') {
  return renderWithProviders(
    <ChartFrame
      title="Average score by year"
      option={OPTION}
      columns={DATA.columns}
      rows={DATA.rows}
      csvName="avg-by-year"
      ariaLabel="Average score by year chart"
      urlKey="avg"
      {...props}
    />,
    { route },
  );
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe('ChartFrame', () => {
  it('renders the chart in a titled card with Table, CSV and Fullscreen controls', () => {
    renderFrame({ subtitle: 'Since 2020', actions: <button type="button">Extra</button> });
    const region = screen.getByRole('region', { name: 'Average score by year' });
    expectChartControls(region);
    expect(within(region).getByRole('button', { name: 'Fullscreen' })).toBeInTheDocument();
    expect(within(region).getByRole('button', { name: 'Extra' })).toBeInTheDocument();
    expect(within(region).getByText('Since 2020')).toBeInTheDocument();
    expect(
      within(region).getByRole('img', { name: 'Average score by year chart' }),
    ).toBeInTheDocument();
  });

  it('adds x zoom to cartesian charts by default and honours an explicit mode', () => {
    renderFrame();
    const chart = getInstanceByDom(
      screen.getByRole('img', { name: 'Average score by year chart' }),
    );
    expect((chart?.getOption() as { dataZoom?: unknown[] }).dataZoom).toHaveLength(2);
  });

  it('zooms horizontal bars along their categories (y), not their values', () => {
    renderFrame({
      option: {
        xAxis: { type: 'value' },
        yAxis: { type: 'category', data: ['2025', '2026'] },
        series: [{ type: 'bar', data: [35.27, null] }],
      },
    });
    const chart = getInstanceByDom(
      screen.getByRole('img', { name: 'Average score by year chart' }),
    );
    const { dataZoom } = chart?.getOption() as {
      dataZoom: { type: string; xAxisIndex?: unknown; yAxisIndex?: unknown }[];
    };
    // Both zooms bind the category (y) axis only; an unbound dataZoom would take the x axis.
    expect(dataZoom.map((d) => [d.type, d.xAxisIndex, d.yAxisIndex])).toEqual([
      ['inside', undefined, 0],
      ['slider', undefined, 0],
    ]);
  });

  it('keeps zoom off when asked', () => {
    renderFrame({ zoom: 'none' });
    const chart = getInstanceByDom(
      screen.getByRole('img', { name: 'Average score by year chart' }),
    );
    expect((chart?.getOption() as { dataZoom?: unknown[] }).dataZoom ?? []).toHaveLength(0);
  });

  it('toggles a table of the exact rows and remembers it in the URL', async () => {
    const { user, router } = renderFrame();
    await user.click(screen.getByRole('button', { name: 'Table' }));
    expect(router.state.location.search).toBe('?avg=table');
    expect(screen.getByRole('button', { name: 'Table' })).toHaveAttribute('aria-pressed', 'true');
    const table = screen.getByRole('table', { name: 'Average score by year' });
    expect(
      within(table)
        .getAllByRole('columnheader')
        .map((h) => h.textContent),
    ).toEqual(['Year', 'Avg score', 'Note']);
    expect(
      within(table)
        .getAllByRole('row')
        .slice(1)
        .map((r) => r.textContent),
    ).toEqual(['202535.27=cmd', '2026—ok']);
    expect(screen.queryByRole('img')).toBeNull();
    await user.click(screen.getByRole('button', { name: 'Table' }));
    expect(router.state.location.search).toBe('');
  });

  it('opens the table directly from a shared URL, linking the first text column', () => {
    renderFrame({ rowHref: (row) => `/club?year=${String(row.year)}` }, '/club?avg=table');
    expect(screen.getByRole('link', { name: '=cmd' })).toHaveAttribute('href', '/club?year=2025');
  });

  it('keeps the global round-type filter on drill links (C10: the filter is global)', () => {
    renderFrame(
      { rowHref: (row) => `/club?year=${String(row.year)}` },
      '/club?avg=table&rt=super_sporting',
    );
    expect(screen.getByRole('link', { name: '=cmd' })).toHaveAttribute(
      'href',
      '/club?year=2025&rt=super_sporting',
    );
  });

  it('lets keyboard users reach and scroll the table', async () => {
    const { user } = renderFrame({}, '/club?avg=table');
    const scroller = screen.getByRole('region', { name: 'Average score by year table' });
    expect(within(scroller).getByRole('table')).toBeInTheDocument();
    screen.getByRole('button', { name: 'Fullscreen' }).focus();
    await user.tab();
    expect(scroller).toHaveFocus();
  });

  it('links the first column when the table has no text column', () => {
    renderFrame(
      {
        columns: DATA.columns.slice(0, 2),
        rows: DATA.rows,
        rowHref: (row) => `/club?year=${String(row.year)}`,
      },
      '/club?avg=table',
    );
    expect(screen.getByRole('link', { name: '2026' })).toHaveAttribute('href', '/club?year=2026');
  });

  it('puts the drill link on the rowHrefKey column instead of the first text column', () => {
    renderFrame(
      { rowHref: (row) => `/club?year=${String(row.year)}`, rowHrefKey: 'year' },
      '/club?avg=table',
    );
    expect(screen.getByRole('link', { name: '2025' })).toHaveAttribute('href', '/club?year=2025');
    expect(screen.getByRole('link', { name: '2026' })).toHaveAttribute('href', '/club?year=2026');
    expect(screen.queryByRole('link', { name: '=cmd' })).toBeNull();
  });

  it('links no cell when no column has the rowHrefKey', () => {
    renderFrame(
      { rowHref: (row) => `/club?year=${String(row.year)}`, rowHrefKey: 'event' },
      '/club?avg=table',
    );
    expect(screen.getByRole('table', { name: 'Average score by year' })).toBeInTheDocument();
    expect(screen.queryAllByRole('link')).toEqual([]);
  });

  it('downloads the rows as CSV', async () => {
    const csv = captureCsv();
    const { user } = renderFrame();
    await user.click(screen.getByRole('button', { name: 'CSV' }));
    expect(csv.names).toEqual(['avg-by-year.csv']);
    expect(await csv.text()).toBe("Year,Avg score,Note\r\n2025,35.2668,'=cmd\r\n2026,,ok\r\n");
  });

  it('opens fullscreen as a centered dialog on desktop and closes it', async () => {
    stubViewport('desktop');
    const { user, router } = renderFrame();
    await user.click(screen.getByRole('button', { name: 'Fullscreen' }));
    const dialog = screen.getByRole('dialog', { name: 'Average score by year' });
    expect(
      within(dialog).getByRole('img', { name: 'Average score by year chart' }),
    ).toBeInTheDocument();
    expect(router.state.location.search).toBe('?avg=full');
    await user.click(within(dialog).getByRole('button', { name: 'Close' }));
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(router.state.location.search).toBe('');
  });

  it('hides the Fullscreen control when fullscreen is false, even for a shared ?full link', () => {
    renderFrame({ fullscreen: false }, '/club?avg=full');
    const region = screen.getByRole('region', { name: 'Average score by year' });
    expect(within(region).queryByRole('button', { name: 'Fullscreen' })).toBeNull();
    expect(screen.queryByRole('dialog')).toBeNull();
    expectChartControls(region);
  });

  it('shows the table inside the fullscreen sheet on mobile when both are on', () => {
    stubViewport('mobile');
    renderFrame({}, '/club?avg=table,full');
    const dialog = screen.getByRole('dialog', { name: 'Average score by year' });
    expect(within(dialog).getByRole('table')).toBeInTheDocument();
  });

  it("keeps a chart's zoom when another frame's Table toggle changes the URL", async () => {
    const frame = (key: string) => (
      <ChartFrame
        title={`Frame ${key}`}
        option={OPTION}
        columns={DATA.columns}
        rows={DATA.rows}
        csvName={key}
        ariaLabel={`Chart ${key}`}
        urlKey={key}
      />
    );
    const { user } = renderWithProviders(
      <>
        {frame('a')}
        {frame('b')}
      </>,
    );
    const chartA = getInstanceByDom(screen.getByRole('img', { name: 'Chart a' }));
    chartA?.dispatchAction({ type: 'dataZoom', start: 50, end: 100 });
    await user.click(
      within(screen.getByRole('region', { name: 'Frame b' })).getByRole('button', {
        name: 'Table',
      }),
    );
    const option = chartA?.getOption() as { dataZoom: { start: number }[] };
    expect(option.dataZoom[0]?.start).toBe(50);
  });

  it('forwards chart clicks to onEvents', () => {
    const click = vi.fn();
    renderFrame({ onEvents: { click } });
    getInstanceByDom(screen.getByRole('img', { name: 'Average score by year chart' }))?.trigger(
      'click',
      { dataIndex: 0 } as never,
    );
    expect(click).toHaveBeenCalledTimes(1);
  });

  describe('explainer', () => {
    const EXPLAINER: Explainer = {
      what: 'Your average score each year.',
      read: ['Higher is better.'],
      computed: ['Total targets hit divided by rounds shot.'],
      scope: 'windowed',
    };

    it('has no disclosure or scope tag without an explainer', () => {
      renderFrame();
      expect(screen.queryByRole('button', { name: 'About this chart' })).toBeNull();
      expect(screen.queryByText('Last 3 months')).toBeNull();
    });

    it('opens and closes the three-part panel from the About this chart button', async () => {
      renderFrame({ explainer: EXPLAINER });
      await expectExplainer(
        screen.getByRole('region', { name: 'Average score by year' }),
        undefined,
        {
          read: true,
        },
      );
    });

    it('keeps the panel state out of the URL', async () => {
      const { user, router } = renderFrame({ explainer: EXPLAINER });
      await user.click(screen.getByRole('button', { name: 'About this chart' }));
      expect(router.state.location.search).toBe('');
    });

    it('tags the chart with the active window, or All time', () => {
      const { unmount } = renderFrame({ explainer: EXPLAINER }, '/club?w=12m');
      expect(screen.getByText('Last 12 months')).toBeVisible();
      unmount();
      renderFrame({ explainer: { ...EXPLAINER, scope: 'all-time' } }, '/club?w=12m');
      expect(screen.getByText('All time')).toBeVisible();
    });

    it('shows no tag when the explainer has no scope', () => {
      renderFrame({ explainer: { what: EXPLAINER.what, computed: EXPLAINER.computed } });
      expect(screen.getByRole('button', { name: 'About this chart' })).toBeVisible();
      expect(screen.queryByText('Last 3 months')).toBeNull();
      expect(screen.queryByText('All time')).toBeNull();
    });

    it('offers the panel in the fullscreen view too', async () => {
      stubViewport('desktop');
      const { user } = renderFrame({ explainer: EXPLAINER }, '/club?avg=full');
      const dialog = screen.getByRole('dialog', { name: 'Average score by year' });
      await user.click(within(dialog).getByRole('button', { name: 'About this chart' }));
      expect(within(dialog).getByRole('heading', { name: 'What this shows' })).toBeVisible();
      expect(within(dialog).getByText('Your average score each year.')).toBeVisible();
    });

    it('keeps the panel state when going fullscreen', async () => {
      stubViewport('desktop');
      const { user } = renderFrame({ explainer: EXPLAINER });
      await user.click(screen.getByRole('button', { name: 'About this chart' }));
      await user.click(screen.getByRole('button', { name: 'Fullscreen' }));
      const dialog = screen.getByRole('dialog', { name: 'Average score by year' });
      expect(within(dialog).getByRole('heading', { name: 'What this shows' })).toBeVisible();
    });
  });

  it('keeps an initial date window set by zoomToWindow on the zoom it adds', () => {
    renderFrame({
      option: {
        xAxis: { type: 'time' },
        yAxis: { type: 'value' },
        series: [
          {
            type: 'line',
            data: [
              ['2026-01-04', 1],
              ['2026-10-04', 2],
            ],
          },
        ],
        dataZoom: [{ type: 'inside', startValue: '2026-06-28', endValue: '2026-09-27' }],
      },
    });
    const chart = getInstanceByDom(
      screen.getByRole('img', { name: 'Average score by year chart' }),
    );
    const { dataZoom } = chart?.getOption() as { dataZoom: { startValue: number }[] };
    // ECharts reads a date string as local time.
    const start = new Date(2026, 5, 28).getTime();
    expect(dataZoom.map((d) => d.startValue)).toEqual([start, start]);
  });

  describe('insight targets (Plan 12)', () => {
    it('is the anchor chart-{urlKey}, focusable for a link', () => {
      renderFrame();
      const region = screen.getByRole('region', { name: 'Average score by year' });
      expect(region).toHaveAttribute('id', 'chart-avg');
      expect(region).toHaveAttribute('tabindex', '-1');
    });

    it('highlights the linked point and offers the whole chart back', async () => {
      const { user, router } = renderFrame({}, '/club?avg.hl=2026&avg.ref=30#chart-avg');
      const region = screen.getByRole('region', { name: 'Average score by year' });
      expect(within(region).getByText('Showing what the insight points to.')).toBeInTheDocument();
      expect(region).toHaveFocus();
      await user.click(within(region).getByRole('button', { name: 'Show the whole chart' }));
      expect(router.state.location.search).toBe('');
      expect(within(region).queryByText('Showing what the insight points to.')).toBeNull();
    });
  });

  describe('the time window (DF-1)', () => {
    const COLS = [
      { key: 'day', label: 'Sunday', type: 'date' as const },
      { key: 'v', label: 'Score', type: 'number' as const },
    ];
    const POINTS: [string, number][] = [
      ['2024-01-07', 3],
      ['2025-01-05', 4],
      ['2026-06-28', 1],
      ['2026-09-27', 2],
    ];
    const ROWS = POINTS.map(([day, v]) => ({ day, v }));
    const OPTION_OF = (points: [string, number][]): EChartsOption => ({
      xAxis: { type: 'time' },
      yAxis: { type: 'value' },
      series: [{ type: 'line', data: points }],
    });
    const WINDOW = { from: '2026-06-28', to: '2026-09-27' };
    const base = { option: OPTION_OF(POINTS), columns: COLS, rows: ROWS, window: WINDOW };
    const region = () => screen.getByRole('region', { name: 'Average score by year' });
    const NOTE = 'Showing the time window. Open fullscreen or download CSV for every Sunday.';

    it('lists only the window in the inline Table, with a note; fullscreen and CSV list every row', async () => {
      stubViewport('desktop');
      const csv = captureCsv();
      const { user } = renderFrame(base, '/club?avg=table');
      // header + the two Sundays inside the window
      expect(within(region()).getAllByRole('row')).toHaveLength(3);
      expect(within(region()).getByText(NOTE)).toBeVisible();
      await user.click(within(region()).getByRole('button', { name: 'CSV' }));
      expect((await csv.text()).trimEnd().split('\r\n')).toHaveLength(5);
      await user.click(within(region()).getByRole('button', { name: 'Fullscreen' }));
      const dialog = screen.getByRole('dialog', { name: 'Average score by year' });
      expect(within(dialog).getAllByRole('row')).toHaveLength(5);
      expect(within(dialog).queryByText(NOTE)).toBeNull();
    });

    it('adds no note when the window holds every row', () => {
      renderFrame({ ...base, window: { from: '2024-01-01', to: '2026-09-27' } }, '/club?avg=table');
      expect(within(region()).getAllByRole('row')).toHaveLength(5);
      expect(within(region()).queryByText(NOTE)).toBeNull();
    });

    it('trims by windowKey, and leaves rows without full dates alone', () => {
      renderFrame(
        {
          ...base,
          columns: [{ key: 'other', label: 'Other', type: 'string' as const }, ...COLS],
          rows: ROWS.map((r) => ({ other: 'x', ...r })),
          windowKey: 'day',
        },
        '/club?avg=table',
      );
      expect(within(region()).getAllByRole('row')).toHaveLength(3);
    });

    it('does not trim rows with a missing date', () => {
      renderFrame({ ...base, rows: [...ROWS, { day: null, v: 9 }] }, '/club?avg=table');
      expect(within(region()).getAllByRole('row')).toHaveLength(6);
    });

    it('does not trim rows whose dates are months', () => {
      renderFrame(
        {
          ...base,
          rows: [
            { day: '2026-01', v: 1 },
            { day: '2026-09', v: 2 },
          ],
        },
        '/club?avg=table',
      );
      expect(within(region()).getAllByRole('row')).toHaveLength(3);
      expect(within(region()).queryByText(NOTE)).toBeNull();
    });

    describe('with no rows in the window', () => {
      const EMPTY = { ...base, window: { from: '2026-10-01', to: '2026-12-01' } };

      it('says so, names the last row, and never draws all-time data under the window tag', () => {
        renderFrame(EMPTY, '/club?w=2026-10-01..2026-12-01');
        expect(
          within(region()).getByText('No Sundays in Oct 1, 2026 – Dec 1, 2026.'),
        ).toBeVisible();
        expect(within(region()).getByText('Latest Sunday Sep 27, 2026.')).toBeVisible();
        expect(within(region()).queryByRole('img')).toBeNull();
      });

      it('keeps Table, CSV and Fullscreen reachable, and Fullscreen shows every row', async () => {
        stubViewport('desktop');
        const { user } = renderFrame(EMPTY, '/club?w=3m');
        expectChartControls(region());
        expect(
          within(region()).getByText('No Sundays in the last 3 months (Oct 1 – Dec 1).'),
        ).toBeVisible();
        await user.click(within(region()).getByRole('button', { name: 'Table' }));
        // still the message, not an empty table
        expect(within(region()).queryByRole('table')).toBeNull();
        await user.click(within(region()).getByRole('button', { name: 'Fullscreen' }));
        const dialog = screen.getByRole('dialog', { name: 'Average score by year' });
        expect(within(dialog).getAllByRole('row')).toHaveLength(5);
      });

      it('"Show all time" widens the header window and is left out on All time', async () => {
        const { user, router } = renderFrame(
          { ...EMPTY, emptyWindow: { none: 'No rounds', last: 'Last shot' } },
          '/club?w=3m',
        );
        expect(within(region()).getByText(/^No rounds in the last 3 months/)).toBeVisible();
        expect(within(region()).getByText('Last shot Sep 27, 2026.')).toBeVisible();
        await user.click(within(region()).getByRole('button', { name: 'Show all time' }));
        expect(router.state.location.search).toBe('?w=all');
      });

      it('has no last-row line when nothing precedes the window', () => {
        renderFrame({ ...EMPTY, window: { from: '2020-01-01', to: '2020-12-31' } });
        expect(within(region()).getByText(/^No Sundays in/)).toBeVisible();
        expect(within(region()).queryByText(/^Latest Sunday/)).toBeNull();
      });

      it('offers no button on All time', () => {
        renderFrame({ ...EMPTY, window: { from: null, to: '2020-01-01' } }, '/club?w=all');
        expect(within(region()).queryByRole('button', { name: 'Show all time' })).toBeNull();
      });

      it('offers 12M and All in one tap each, and only the ones that widen', async () => {
        const { user, router, unmount } = renderFrame(EMPTY, '/club?w=3m');
        await user.click(within(region()).getByRole('button', { name: 'Show the last 12 months' }));
        expect(router.state.location.search).toBe('?w=12m');
        unmount();
        renderFrame(EMPTY, '/club?w=12m');
        expect(
          within(region()).queryByRole('button', { name: 'Show the last 12 months' }),
        ).toBeNull();
        expect(within(region()).getByRole('button', { name: 'Show all time' })).toBeVisible();
      });

      it('lists the insight link’s rows in the Table when its dates are outside the window', () => {
        // The chart zooms to the insight's dates, so the Table must agree with it.
        renderFrame(base, '/club?avg=table&avg.from=2024-01-01&avg.to=2025-12-31');
        // header + 2024-01-07 and 2025-01-05
        expect(within(region()).getAllByRole('row')).toHaveLength(3);
        expect(within(region()).getByText('2024-01-07')).toBeVisible();
        expect(within(region()).getByText('2025-01-05')).toBeVisible();
        expect(within(region()).queryByText('2026-09-27')).toBeNull();
        expect(within(region()).queryByText(/^No Sundays in/)).toBeNull();
      });

      it('lets an insight link win: its dates never read as an empty window', () => {
        renderFrame(EMPTY, '/club?avg.from=2026-06-28&avg.to=2026-09-27');
        expect(within(region()).queryByText(/^No Sundays in/)).toBeNull();
        expect(within(region()).getByRole('img')).toBeInTheDocument();
      });
    });

    it('a frame without a window keeps every row and never says empty', () => {
      renderFrame({ ...base, window: null, rows: [] }, '/club?avg=table');
      expect(within(region()).queryByText(/^No Sundays in/)).toBeNull();
    });
  });

  describe('full data', () => {
    const TIME_OPTION = (points: [string, number][]): EChartsOption => ({
      xAxis: { type: 'time' },
      yAxis: { type: 'value' },
      series: [{ type: 'line', data: points }],
    });
    const INLINE_POINTS: [string, number][] = [
      ['2026-06-28', 1],
      ['2026-09-27', 2],
    ];
    const FULL_POINTS: [string, number][] = [
      ['2024-01-07', 3],
      ['2025-01-05', 4],
      ['2026-01-04', 5],
      ['2026-06-28', 1],
      ['2026-09-27', 2],
    ];
    const COLS = [
      { key: 'day', label: 'Sunday', type: 'date' as const },
      { key: 'v', label: 'Score', type: 'number' as const },
    ];
    const rowsOf = (points: [string, number][]) => points.map(([day, v]) => ({ day, v }));
    const WINDOW = { from: '2026-06-28', to: '2026-09-27' };
    const FULL: ChartFull = {
      option: TIME_OPTION(FULL_POINTS),
      columns: [...COLS, { key: 'extra', label: 'Extra', type: 'string' as const }],
      rows: FULL_POINTS.map(([day, v]) => ({ day, v, extra: 'x' })),
    };
    const base = {
      option: TIME_OPTION(INLINE_POINTS),
      columns: COLS,
      rows: rowsOf(INLINE_POINTS),
    };
    const region = () => screen.getByRole('region', { name: 'Average score by year' });
    const seriesLen = (o: EChartsOption) =>
      ((o.series as { data: unknown[] }[])[0] as { data: unknown[] }).data.length;
    const zoomOf = (o: EChartsOption) => (o as { dataZoom: { startValue?: number }[] }).dataZoom;

    it('zooms the inline chart to the window but opens fullscreen on the whole axis', async () => {
      stubViewport('desktop');
      const { user } = renderFrame({ ...base, option: TIME_OPTION(FULL_POINTS), window: WINDOW });
      const start = new Date(2026, 5, 28).getTime();
      expect(zoomOf(chartOptionIn(region())).map((d) => d.startValue)).toEqual([start, start]);
      const dialog = await openFullscreen(user, region(), 'Average score by year');
      const zoom = zoomOf(chartOptionIn(dialog));
      expect(zoom).toHaveLength(2);
      // getOption reports the resolved range: the first Sunday, not the window's start.
      const first = new Date(2024, 0, 7).getTime();
      expect(zoom.map((d) => d.startValue)).toEqual([first, first]);
    });

    it('lets an insight window win over window, inline and in fullscreen', () => {
      stubViewport('desktop');
      const url = '/club?avg.from=2026-08-01&avg.to=2026-09-01';
      const start = new Date(2026, 7, 1).getTime();
      const { unmount } = renderFrame({ ...base, window: WINDOW }, url);
      expect(zoomOf(chartOptionIn(region())).map((d) => d.startValue)).toEqual([start, start]);
      unmount();
      renderFrame({ ...base, window: WINDOW }, `${url}&avg=full`);
      const dialog = screen.getByRole('dialog', { name: 'Average score by year' });
      expect(zoomOf(chartOptionIn(dialog)).map((d) => d.startValue)).toEqual([start, start]);
    });

    it('shows the full rows in the fullscreen table and the CSV, the inline rows inline', async () => {
      stubViewport('desktop');
      const csv = captureCsv();
      const { user } = renderFrame({ ...base, full: FULL }, '/club?avg=table');
      expect(within(region()).getAllByRole('row')).toHaveLength(3);
      await user.click(within(region()).getByRole('button', { name: 'CSV' }));
      const lines = (await csv.text()).trimEnd().split('\r\n');
      expect(lines).toHaveLength(6);
      expect(lines[0]).toBe('Sunday,Score,Extra');
      await user.click(within(region()).getByRole('button', { name: 'Fullscreen' }));
      const dialog = screen.getByRole('dialog', { name: 'Average score by year' });
      expect(within(dialog).getAllByRole('row')).toHaveLength(6);
    });

    it('draws full.option in fullscreen', async () => {
      stubViewport('desktop');
      const { user } = renderFrame({ ...base, full: FULL });
      expect(seriesLen(chartOptionIn(region()))).toBe(2);
      const dialog = await openFullscreen(user, region(), 'Average score by year');
      expect(seriesLen(chartOptionIn(dialog))).toBe(5);
    });

    it('sizes the fullscreen chart from full.height', () => {
      stubViewport('desktop');
      renderFrame({ ...base, full: { height: 900 } }, '/club?avg=full');
      const dialog = screen.getByRole('dialog', { name: 'Average score by year' });
      expect(within(dialog).getByRole('img')).toHaveStyle({ height: '900px' });
    });

    it('maps insight keys with the inline rows inline and the full rows in fullscreen', () => {
      stubViewport('desktop');
      const hlLabels = vi.fn<NonNullable<ChartFrameProps['hlLabels']>>((keys) => [...keys]);
      renderFrame({ ...base, full: FULL, hlLabels }, '/club?avg.hl=2024-01-07&avg=full');
      const lengths = hlLabels.mock.calls.map(([, rows]) => rows.length);
      expect(lengths).toContain(2);
      expect(lengths).toContain(5);
    });

    it('keeps the 70dvh fullscreen height by default', () => {
      stubViewport('desktop');
      renderFrame(base, '/club?avg=full');
      const dialog = screen.getByRole('dialog', { name: 'Average score by year' });
      expect(within(dialog).getByRole('img')).toHaveStyle({ height: '70dvh' });
    });

    it('shows full.note in fullscreen only', () => {
      stubViewport('desktop');
      renderFrame({ ...base, full: { note: 'Every Sunday since 2024' } }, '/club?avg=full');
      const dialog = screen.getByRole('dialog', { name: 'Average score by year' });
      expect(within(dialog).getByText('Every Sunday since 2024')).toBeVisible();
      expect(within(region()).queryByText('Every Sunday since 2024')).toBeNull();
    });

    describe('scope tag', () => {
      const WINDOWED: Explainer = { what: 'w', computed: ['c'], scope: 'windowed' };

      it('turns All time in fullscreen only when the chart has full data', async () => {
        stubViewport('desktop');
        const { user } = renderFrame(
          { ...base, explainer: WINDOWED, window: WINDOW },
          '/club?w=3m',
        );
        expect(within(region()).getByText('Last 3 months')).toBeVisible();
        const dialog = await openFullscreen(user, region(), 'Average score by year');
        expect(within(dialog).getByText('All time')).toBeVisible();
      });

      it('lets full.scope override', () => {
        stubViewport('desktop');
        renderFrame(
          { ...base, explainer: WINDOWED, window: WINDOW, full: { scope: 'windowed' } },
          '/club?w=3m&avg=full',
        );
        const dialog = screen.getByRole('dialog', { name: 'Average score by year' });
        expect(within(dialog).getByText('Last 3 months')).toBeVisible();
      });

      it('keeps a windowed tag in fullscreen when nothing is full', () => {
        stubViewport('desktop');
        renderFrame({ ...base, explainer: WINDOWED }, '/club?w=3m&avg=full');
        const dialog = screen.getByRole('dialog', { name: 'Average score by year' });
        expect(within(dialog).getByText('Last 3 months')).toBeVisible();
      });

      it('shows no tag for an explainer with no scope', () => {
        stubViewport('desktop');
        renderFrame(
          {
            ...base,
            explainer: { what: 'w', computed: ['c'] },
            fullQuery: { queryKey: ['scope-none'], queryFn: () => Promise.resolve({}) },
          },
          '/club?avg=full',
        );
        const dialog = screen.getByRole('dialog', { name: 'Average score by year' });
        expect(within(dialog).queryByText('All time')).toBeNull();
        expect(within(dialog).queryByText(/Last \d+ months/)).toBeNull();
      });

      it('keeps an all-time tag in fullscreen', () => {
        stubViewport('desktop');
        renderFrame(
          { ...base, explainer: { ...WINDOWED, scope: 'all-time' }, full: FULL },
          '/club?avg=full',
        );
        const dialog = screen.getByRole('dialog', { name: 'Average score by year' });
        expect(within(dialog).getByText('All time')).toBeVisible();
      });
    });

    describe('fullQuery', () => {
      const query = (queryFn: () => Promise<ChartFull>, key = 'q') => ({
        queryKey: [key],
        queryFn,
      });

      it('fetches only once fullscreen opens, showing a status meanwhile', async () => {
        stubViewport('desktop');
        let release: (v: ChartFull) => void = () => {};
        const queryFn = vi.fn(
          () =>
            new Promise<ChartFull>((resolve) => {
              release = resolve;
            }),
        );
        const { user } = renderFrame({ ...base, fullQuery: query(queryFn) }, '/club?avg=table');
        expect(queryFn).not.toHaveBeenCalled();
        const dialog = await openFullscreen(user, region(), 'Average score by year');
        expect(queryFn).toHaveBeenCalledTimes(1);
        expect(within(dialog).getByRole('status')).toHaveTextContent('Loading every row…');
        expect(within(dialog).getAllByRole('row')).toHaveLength(3);
        release(FULL);
        await waitFor(() => expect(within(dialog).getAllByRole('row')).toHaveLength(6));
        expect(within(dialog).queryByRole('status')).toBeNull();
      });

      it('shows the inline data, an alert and Try again when the fetch fails', async () => {
        stubViewport('desktop');
        const queryFn = vi
          .fn<() => Promise<ChartFull>>()
          .mockRejectedValueOnce(new Error('boom'))
          .mockResolvedValueOnce(FULL);
        const { user } = renderFrame({ ...base, fullQuery: query(queryFn) }, '/club?avg=full');
        const dialog = screen.getByRole('dialog', { name: 'Average score by year' });
        expect(await within(dialog).findByRole('alert')).toHaveTextContent(
          "Couldn't load the full data. Showing the chart as it is on the page.",
        );
        expect(within(dialog).getByRole('img')).toBeInTheDocument();
        await user.click(within(dialog).getByRole('button', { name: 'Try again' }));
        expect(queryFn).toHaveBeenCalledTimes(2);
        await waitFor(() => expect(within(dialog).queryByRole('alert')).toBeNull());
        expect(seriesLen(chartOptionIn(dialog))).toBe(5);
      });

      it('CSV awaits the fetch (busy meanwhile), then reuses the cache', async () => {
        const csv = captureCsv();
        let release: (v: ChartFull) => void = () => {};
        const queryFn = vi.fn(
          () =>
            new Promise<ChartFull>((resolve) => {
              release = resolve;
            }),
        );
        const { user } = renderFrame({ ...base, fullQuery: query(queryFn) });
        const button = within(region()).getByRole('button', { name: 'CSV' });
        await user.click(button);
        expect(button).toHaveAttribute('aria-busy', 'true');
        expect(button).toHaveAttribute('aria-disabled', 'true');
        expect(button).toBeEnabled();
        expect(csv.names).toEqual([]);
        release(FULL);
        await waitFor(() => expect(csv.names).toEqual(['avg-by-year.csv']));
        expect((await csv.text()).trimEnd().split('\r\n')).toHaveLength(6);
        await waitFor(() => expect(button).not.toHaveAttribute('aria-disabled'));
        expect(button).not.toHaveAttribute('aria-busy');
        await user.click(button);
        await waitFor(() => expect(csv.names).toHaveLength(2));
        expect(queryFn).toHaveBeenCalledTimes(1);
      });

      it('CSV failure shows an alert, downloads nothing, and clears on the next success', async () => {
        const csv = captureCsv();
        const queryFn = vi
          .fn<() => Promise<ChartFull>>()
          .mockRejectedValueOnce(new Error('boom'))
          .mockResolvedValueOnce(FULL);
        const { user } = renderFrame({ ...base, fullQuery: query(queryFn) });
        const button = within(region()).getByRole('button', { name: 'CSV' });
        await user.click(button);
        expect(await within(region()).findByRole('alert')).toHaveTextContent(
          "Couldn't download every row. Try again.",
        );
        expect(csv.names).toEqual([]);
        await user.click(button);
        await waitFor(() => expect(csv.names).toHaveLength(1));
        expect(within(region()).queryByRole('alert')).toBeNull();
      });

      it('CSV falls back to the inline columns and rows when the fetch has none', async () => {
        const csv = captureCsv();
        const { user } = renderFrame({
          ...base,
          fullQuery: query(() => Promise.resolve({ note: 'n' })),
        });
        await user.click(within(region()).getByRole('button', { name: 'CSV' }));
        await waitFor(() => expect(csv.names).toHaveLength(1));
        expect((await csv.text()).trimEnd().split('\r\n')).toEqual([
          'Sunday,Score',
          '2026-06-28,1',
          '2026-09-27,2',
        ]);
      });

      it('merges the fetched fields over the static full data', async () => {
        stubViewport('desktop');
        const fetched: ChartFull = { rows: rowsOf(FULL_POINTS), columns: COLS };
        const { user } = renderFrame(
          {
            ...base,
            full: { note: 'Static note', rows: [{ day: '2020-01-05', v: 9 }] },
            fullQuery: query(() => Promise.resolve(fetched)),
          },
          '/club?avg=table',
        );
        const dialog = await openFullscreen(user, region(), 'Average score by year');
        await waitFor(() => expect(within(dialog).getAllByRole('row')).toHaveLength(6));
        expect(within(dialog).getByText('Static note')).toBeVisible();
        expect(within(dialog).queryByText('2020-01-05')).toBeNull();
      });

      it('has a CSV button inside the fullscreen sheet that exports the full rows', async () => {
        stubViewport('desktop');
        const csv = captureCsv();
        const queryFn = vi.fn(() => Promise.resolve(FULL));
        const { user } = renderFrame({ ...base, fullQuery: query(queryFn) }, '/club?avg=full');
        const dialog = screen.getByRole('dialog', { name: 'Average score by year' });
        await waitFor(() => expect(queryFn).toHaveBeenCalledTimes(1));
        await user.click(within(dialog).getByRole('button', { name: 'CSV' }));
        await waitFor(() => expect(csv.names).toEqual(['avg-by-year.csv']));
        const lines = (await csv.text()).trimEnd().split('\r\n');
        expect(lines).toHaveLength(6);
        expect(lines[0]).toBe('Sunday,Score,Extra');
        expect(queryFn).toHaveBeenCalledTimes(1);
      });

      it('shows the busy state on the fullscreen CSV button while the rows load', async () => {
        stubViewport('desktop');
        captureCsv();
        let release: (v: ChartFull) => void = () => {};
        const queryFn = vi.fn(
          () =>
            new Promise<ChartFull>((resolve) => {
              release = resolve;
            }),
        );
        const { user } = renderFrame({ ...base, fullQuery: query(queryFn) }, '/club?avg=full');
        const dialog = screen.getByRole('dialog', { name: 'Average score by year' });
        const button = within(dialog).getByRole('button', { name: 'CSV' });
        await user.click(button);
        expect(button).toHaveAttribute('aria-busy', 'true');
        expect(button).toHaveAttribute('aria-disabled', 'true');
        release(FULL);
        await waitFor(() => expect(button).not.toHaveAttribute('aria-busy'));
      });

      it('shows a CSV failure inside the fullscreen sheet, above the sheet content', async () => {
        stubViewport('desktop');
        const csv = captureCsv();
        const queryFn = vi.fn<() => Promise<ChartFull>>().mockRejectedValue(new Error('boom'));
        const { user } = renderFrame({ ...base, fullQuery: query(queryFn) }, '/club?avg=full');
        const dialog = screen.getByRole('dialog', { name: 'Average score by year' });
        // Both the load alert and the download alert are in the dialog once CSV fails.
        await within(dialog).findByText(/Couldn't load the full data/);
        await user.click(within(dialog).getByRole('button', { name: 'CSV' }));
        expect(
          await within(dialog).findByText("Couldn't download every row. Try again."),
        ).toBeVisible();
        expect(csv.names).toEqual([]);
      });
    });

    it('has a CSV button inside a fullscreen sheet with static full data', async () => {
      stubViewport('desktop');
      const csv = captureCsv();
      const { user } = renderFrame({ ...base, full: FULL }, '/club?avg=full');
      const dialog = screen.getByRole('dialog', { name: 'Average score by year' });
      await user.click(within(dialog).getByRole('button', { name: 'CSV' }));
      expect((await csv.text()).trimEnd().split('\r\n')).toHaveLength(6);
    });

    it('leaves defaults unchanged without the new props', async () => {
      stubViewport('desktop');
      const csv = captureCsv();
      const { user } = renderFrame();
      const inline = zoomOf(chartOptionIn(region()));
      await user.click(within(region()).getByRole('button', { name: 'CSV' }));
      expect(await csv.text()).toBe("Year,Avg score,Note\r\n2025,35.2668,'=cmd\r\n2026,,ok\r\n");
      const dialog = await openFullscreen(user, region(), 'Average score by year');
      expect(zoomOf(chartOptionIn(dialog))).toEqual(inline);
    });
  });
});
