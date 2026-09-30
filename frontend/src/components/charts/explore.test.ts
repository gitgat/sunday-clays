import type { BarSeriesOption, HeatmapSeriesOption, LineSeriesOption } from 'echarts';
import { describe, expect, it } from 'vitest';
import {
  DIM_LABELS,
  EXPLORE_MAX_LIMIT,
  METRICS,
  allHistorySpec,
  allRowsSpec,
  bestRoundApplies,
  buildExploreOption,
  querySpec,
  rowForClick,
  toTabular,
  type QueryResult,
} from './explore';
import type { TabularData } from './types';

const BY_YEAR_STATUS: QueryResult = {
  columns: [
    { key: 'year', label: 'Year', type: 'int' },
    { key: 'status', label: 'Status', type: 'string' },
    { key: 'value', label: 'Rounds', type: 'int' },
    { key: 'n', label: 'n', type: 'int' },
  ],
  rows: [
    { year: 2025, status: 'member', value: 1200, n: 1200 },
    { year: 2025, status: null, value: 67, n: 67 },
    { year: 2026, status: 'member', value: 950, n: 950 },
  ],
  n_rounds: 2217,
  truncated: false,
};

it('names the winter-to-fall dimension "Time of year", not "Season"', () => {
  expect(DIM_LABELS.season).toBe('Time of year');
});

describe('querySpec', () => {
  it('fills server defaults and merges partial filters', () => {
    expect(
      querySpec({ metric: 'score', group_by: ['year'], filters: { best_round_only: true } }),
    ).toEqual({
      metric: 'score',
      agg: 'avg',
      group_by: ['year'],
      sort: 'key_asc',
      limit: 500,
      filters: {
        best_round_only: true,
        gauges: [],
        min_rounds: 0,
        round_types: [],
        shooter_ids: [],
        statuses: [],
      },
    });
  });
});

describe('bestRoundApplies', () => {
  it('is false for the Sunday totals, which the explorer engine rejects with best_round_only', () => {
    expect(METRICS.filter((m) => !bestRoundApplies(m))).toEqual(['attendance', 'difficulty']);
  });
});

describe('buildExploreOption', () => {
  const data = toTabular(BY_YEAR_STATUS);

  it('adapts a QueryResult to TabularData', () => {
    expect(data.columns.map((c) => c.key)).toEqual(['year', 'status', 'value', 'n']);
    expect(data.rows).toBe(BY_YEAR_STATUS.rows);
  });

  it('draws bars by the first dim with one series per second-dim value', () => {
    const o = buildExploreOption(data, ['year', 'status'], 'bar');
    expect(o.xAxis).toMatchObject({ type: 'category', data: ['2025', '2026'] });
    expect((o.series as BarSeriesOption[]).map((s) => [s.name, s.data])).toEqual([
      ['member', [1200, 950]],
      ['—', [67, null]],
    ]);
  });

  it('draws horizontal bars for shooters and lines when asked', () => {
    const shooters: TabularData = {
      columns: [
        { key: 'shooter_id', label: 'Shooter ID', type: 'int' },
        { key: 'shooter', label: 'Shooter', type: 'string' },
        { key: 'value', label: 'Avg score', type: 'number' },
      ],
      rows: [{ shooter_id: 3, shooter: 'Slocum, Cy', value: 42 }],
    };
    expect(buildExploreOption(shooters, ['shooter'], 'bar').yAxis).toMatchObject({
      type: 'category',
      data: ['Slocum, Cy'],
    });
    const line = buildExploreOption(data, ['year'], 'line');
    expect((line.series as LineSeriesOption[])[0]?.type).toBe('line');
  });

  it('draws a heatmap for two dims and falls back to bars with one', () => {
    const heat = buildExploreOption(data, ['year', 'status'], 'heatmap');
    expect((heat.series as HeatmapSeriesOption[])[0]?.type).toBe('heatmap');
    expect(heat.yAxis).toMatchObject({ data: ['2025', '2026'] });
    expect(
      (buildExploreOption(data, ['year'], 'heatmap').series as BarSeriesOption[])[0]?.type,
    ).toBe('bar');
  });

  it('charts averages to 2 dp (cell labels, tooltips), leaving counts and the raw rows alone', () => {
    const avg: TabularData = {
      columns: [
        { key: 'season', label: 'Season', type: 'string' },
        { key: 'year', label: 'Year', type: 'int' },
        { key: 'value', label: 'Avg score', type: 'number' },
        { key: 'n', label: 'n', type: 'int' },
      ],
      rows: [
        { season: 'winter', year: 2020, value: 33.243902439024396, n: 41 },
        { season: 'spring', year: 2020, value: null, n: 0 },
        { season: 'winter', year: 2021, value: -0.006, n: 7 },
      ],
    };
    const heat = buildExploreOption(avg, ['season', 'year'], 'heatmap');
    expect((heat.series as HeatmapSeriesOption[])[0]?.data).toEqual([
      [0, 0, 33.24],
      [1, 0, -0.01],
    ]);
    const bars = buildExploreOption(avg, ['year', 'season'], 'bar');
    expect((bars.series as BarSeriesOption[]).map((s) => s.data)).toEqual([
      [33.24, -0.01],
      [null, null],
    ]);
    expect(avg.rows[0]?.value).toBe(33.243902439024396);
    const counts = buildExploreOption(data, ['year'], 'bar');
    expect((counts.series as BarSeriesOption[])[0]?.data).toEqual([1200, 67, 950]);
  });

  it('shows a single "All" bar without dims', () => {
    const total: TabularData = {
      columns: [{ key: 'value', label: 'Rounds', type: 'int' }],
      rows: [{ value: 7480 }],
    };
    const o = buildExploreOption(total, [], 'line');
    expect(o.xAxis).toMatchObject({ data: ['All'] });
    expect((o.series as BarSeriesOption[])[0]?.data).toEqual([7480]);
  });
});

describe('shooters who share a display name', () => {
  const twoJims: TabularData = {
    columns: [
      { key: 'shooter_id', label: 'Shooter ID', type: 'int' },
      { key: 'shooter', label: 'Shooter', type: 'string' },
      { key: 'value', label: 'Avg score', type: 'number' },
    ],
    rows: [
      { shooter_id: 7, shooter: 'Desmond', value: 30 },
      { shooter_id: 9, shooter: 'Desmond', value: 40 },
    ],
  };

  it('get their id appended so each keeps its own bar', () => {
    const o = buildExploreOption(twoJims, ['shooter'], 'bar');
    expect(o.yAxis).toMatchObject({ data: ['Desmond #7', 'Desmond #9'] });
    expect((o.series as BarSeriesOption[])[0]?.data).toEqual([30, 40]);
    expect(twoJims.rows[1]?.shooter).toBe('Desmond');
  });

  it('drill to the raw row of the shooter that was clicked', () => {
    expect(rowForClick(twoJims, ['shooter'], { name: 'Desmond #9' })).toBe(twoJims.rows[1]);
  });

  it('leave one shooter spread over several rows unchanged', () => {
    const byYear: TabularData = {
      columns: [...twoJims.columns, { key: 'year', label: 'Year', type: 'int' }],
      rows: [
        { shooter_id: 3, shooter: 'Slocum, Cy', year: 2025, value: 40 },
        { shooter_id: 3, shooter: 'Slocum, Cy', year: 2026, value: 41 },
      ],
    };
    expect(buildExploreOption(byYear, ['shooter', 'year'], 'bar').yAxis).toMatchObject({
      data: ['Slocum, Cy'],
    });
  });
});

describe('rowForClick', () => {
  const data = toTabular(BY_YEAR_STATUS);
  it('finds the row behind a bar by category and series', () => {
    expect(rowForClick(data, ['year', 'status'], { name: '2025', seriesName: '—' })).toBe(
      data.rows[1],
    );
    expect(rowForClick(data, ['year'], { name: '', value: ['2026', 950] })).toBe(data.rows[2]);
    expect(rowForClick(data, [], {})).toBe(data.rows[0]);
    expect(rowForClick(data, ['year'], { name: '1999' })).toBeUndefined();
    expect(rowForClick(data, ['year'], {})).toBeUndefined();
  });

  it('matches no row when a two-dim click carries no series name', () => {
    expect(rowForClick(data, ['year', 'status'], { name: '2025' })).toBeUndefined();
  });

  it('finds the row behind a heatmap cell from its x (second dim) and y (first dim) indices', () => {
    const heat = buildExploreOption(data, ['year', 'status'], 'heatmap');
    const cells = (heat.series as HeatmapSeriesOption[])[0]?.data as [number, number, number][];
    expect(cells).toHaveLength(3);
    for (const [xi, yi, v] of cells) {
      const row = rowForClick(data, ['year', 'status'], {
        seriesType: 'heatmap',
        seriesName: 'Rounds',
        value: [xi, yi, v],
      });
      expect(row?.value).toBe(v);
    }
    expect(
      rowForClick(data, ['year', 'status'], { seriesType: 'heatmap', value: [1, 0, 67] }),
    ).toBe(data.rows[1]);
    expect(
      rowForClick(data, ['year', 'status'], { seriesType: 'heatmap', value: [5, 5, 0] }),
    ).toBeUndefined();
    expect(rowForClick(data, ['year', 'status'], { seriesType: 'heatmap' })).toBeUndefined();
  });
});

describe('allRowsSpec / allHistorySpec', () => {
  const spec = querySpec({
    metric: 'score',
    group_by: ['year'],
    filters: { date_from: '2026-06-28', date_to: '2026-09-27', round_types: ['sporting'] },
  });

  it('allRowsSpec asks for the most rows and keeps filters and dates', () => {
    const all = allRowsSpec(spec);
    expect(EXPLORE_MAX_LIMIT).toBe(5000);
    expect(all.limit).toBe(5000);
    expect(all.filters).toEqual(spec.filters);
    expect(all.metric).toBe('score');
  });

  it('allHistorySpec also clears both dates and leaves its input alone', () => {
    const before = structuredClone(spec);
    const all = allHistorySpec(spec);
    expect(all.limit).toBe(5000);
    expect(all.filters.date_from).toBeNull();
    expect(all.filters.date_to).toBeNull();
    expect(all.filters.round_types).toEqual(['sporting']);
    expect(spec).toEqual(before);
  });
});
