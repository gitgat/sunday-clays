import type { LineSeriesOption } from 'echarts';
import { describe, expect, it } from 'vitest';
import type { TabularData } from '../types';
import { lineOption } from './line';

const RATING: TabularData = {
  columns: [
    { key: 'event_date', label: 'Event', type: 'date' },
    { key: 'mu', label: 'Rating', type: 'number' },
    { key: 'lo', label: 'Low', type: 'number' },
    { key: 'hi', label: 'High', type: 'number' },
    { key: 'pb', label: 'PB', type: 'int' },
  ],
  rows: [
    { event_date: '2026-09-06', mu: 35, lo: 31, hi: 39, pb: 0 },
    { event_date: '2026-09-13', mu: 36.5, lo: 33, hi: 40, pb: 1 },
    { event_date: '2026-09-20', mu: null, lo: null, hi: 41, pb: 0 },
  ],
};

const series = (o: ReturnType<typeof lineOption>) => o.series as LineSeriesOption[];

describe('lineOption', () => {
  it('draws one series per y column on a time axis for dates, with gaps for nulls', () => {
    const o = lineOption(RATING, { x: 'event_date', y: ['mu'] });
    expect(o.xAxis).toMatchObject({ type: 'time', name: 'Event' });
    expect(o.yAxis).toMatchObject({ name: 'Rating', scale: false });
    expect(series(o)).toHaveLength(1);
    expect(series(o)[0]).toMatchObject({
      type: 'line',
      name: 'Rating',
      data: [
        ['2026-09-06', 35],
        ['2026-09-13', 36.5],
        ['2026-09-20', null],
      ],
    });
    expect(o.legend).toMatchObject({ show: false });
  });

  it('adds a stacked band (lower + width) hidden from the tooltip, and PB markers', () => {
    const o = lineOption(RATING, {
      x: 'event_date',
      y: ['mu'],
      band: { lower: 'lo', upper: 'hi', name: '95% band' },
      markers: { flag: 'pb', name: 'Personal best' },
      scaleY: true,
      yName: 'Rating (μ)',
    });
    const [low, width, line, markers] = series(o) as [
      LineSeriesOption,
      LineSeriesOption,
      LineSeriesOption,
      LineSeriesOption,
    ];
    expect(low).toMatchObject({
      stack: 'band',
      tooltip: { show: false },
      data: [
        ['2026-09-06', 31],
        ['2026-09-13', 33],
        ['2026-09-20', null],
      ],
    });
    expect(width).toMatchObject({
      name: '95% band',
      stack: 'band',
      data: [
        ['2026-09-06', 8],
        ['2026-09-13', 7],
        ['2026-09-20', null],
      ],
    });
    expect(line.name).toBe('Rating');
    expect(markers).toMatchObject({
      type: 'scatter',
      name: 'Personal best',
      data: [['2026-09-13', 36.5]],
    });
    expect(o.legend).toMatchObject({ data: ['95% band', 'Rating', 'Personal best'] });
    expect(o.yAxis).toMatchObject({ name: 'Rating (μ)', scale: true });
  });

  it('splits long-format rows into one series per group, with optional area and smoothing', () => {
    const data: TabularData = {
      columns: [
        { key: 'month', label: 'Month', type: 'string' },
        { key: 'who', label: 'Who', type: 'string' },
        { key: 'value', label: 'Avg score', type: 'number' },
      ],
      rows: [
        { month: '2026-08', who: 'You', value: 38 },
        { month: '2026-08', who: 'Club', value: 35 },
        { month: '2026-09', who: 'You', value: 40 },
      ],
    };
    const o = lineOption(data, {
      x: 'month',
      y: ['value'],
      seriesBy: 'who',
      area: true,
      smooth: true,
    });
    expect(o.xAxis).toMatchObject({ type: 'category' });
    expect(series(o).map((s) => [s.name, s.data])).toEqual([
      [
        'You',
        [
          ['2026-08', 38],
          ['2026-09', 40],
        ],
      ],
      ['Club', [['2026-08', 35]]],
    ]);
    expect(series(o)[0]).toMatchObject({ smooth: true, areaStyle: { opacity: 0.2 } });
  });

  it('shades wide series when asked and names an unnamed band "Range"', () => {
    const o = lineOption(RATING, {
      x: 'event_date',
      y: ['mu'],
      band: { lower: 'lo', upper: 'hi' },
      area: true,
    });
    const [, width, line] = series(o) as [LineSeriesOption, LineSeriesOption, LineSeriesOption];
    expect(width.name).toBe('Range');
    expect(line).toMatchObject({ name: 'Rating', areaStyle: { opacity: 0.2 } });
    expect(o.legend).toMatchObject({ data: ['Range', 'Rating'] });
  });

  it('keeps rows with a missing x or group cell, at x "" in a group named "—"', () => {
    const data: TabularData = {
      columns: [...RATING.columns, { key: 'who', label: 'Who', type: 'string' }],
      rows: [
        { event_date: '2026-09-06', mu: 35, lo: 31, hi: 39, pb: 0, who: 'You' },
        { mu: 37, lo: 34, hi: 40, pb: 0 },
      ],
    };
    const long = lineOption(data, { x: 'event_date', y: ['mu'], seriesBy: 'who' });
    expect(series(long).map((s) => [s.name, s.data])).toEqual([
      ['You', [['2026-09-06', 35]]],
      ['—', [['', 37]]],
    ]);
    expect(series(long)[0]).not.toHaveProperty('areaStyle');
    const banded = lineOption(data, {
      x: 'event_date',
      y: ['mu'],
      band: { lower: 'lo', upper: 'hi' },
    });
    expect(series(banded)[1]?.data).toEqual([
      ['2026-09-06', 8],
      ['', 6],
    ]);
  });

  it('orders a category x axis by row order even when the first series has a gap', () => {
    const data: TabularData = {
      columns: [
        { key: 'month', label: 'Month', type: 'string' },
        { key: 'who', label: 'Who', type: 'string' },
        { key: 'value', label: 'Avg score', type: 'number' },
      ],
      rows: [
        { month: '2026-08', who: 'You', value: 38 },
        { month: '2026-08', who: 'Club', value: 35 },
        { month: '2026-09', who: 'Club', value: 36 },
        { month: '2026-10', who: 'You', value: 40 },
        { month: '2026-10', who: 'Club', value: 37 },
      ],
    };
    const o = lineOption(data, { x: 'month', y: ['value'], seriesBy: 'who' });
    expect(o.xAxis).toMatchObject({ type: 'category', data: ['2026-08', '2026-09', '2026-10'] });
    // Time and value axes place points by their x value, so they take no category list.
    expect(lineOption(RATING, { x: 'event_date', y: ['mu'] }).xAxis).not.toHaveProperty('data');
  });

  it('charts numeric cells in a string x column as category names, not category indexes', () => {
    const data: TabularData = {
      columns: [
        { key: 'season', label: 'Season', type: 'string' },
        { key: 'value', label: 'Avg score', type: 'number' },
      ],
      rows: [
        { season: 2026, value: 1 },
        { season: 2027, value: 2 },
        { season: null, value: 3 },
      ],
    };
    const o = lineOption(data, { x: 'season', y: ['value'] });
    const categories = (o.xAxis as { data: unknown[] }).data;
    expect(categories).toEqual(['2026', '2027', '—']);
    const points = series(o)[0]?.data as [unknown, number][];
    expect(points).toEqual([
      ['2026', 1],
      ['2027', 2],
      ['—', 3],
    ]);
    for (const [x] of points) expect(categories).toContain(x);
  });

  it('keeps a real series named "… (low)" in the legend, hiding only the band\'s lower edge', () => {
    const data: TabularData = {
      columns: [...RATING.columns, { key: 'wind', label: 'Wind (low)', type: 'number' }],
      rows: RATING.rows.map((r, i) => ({ ...r, wind: 5 + i })),
    };
    const o = lineOption(data, {
      x: 'event_date',
      y: ['mu', 'wind'],
      band: { lower: 'lo', upper: 'hi' },
    });
    expect(series(o).map((s) => s.name)).toEqual(['Range (low)', 'Range', 'Rating', 'Wind (low)']);
    expect(o.legend).toMatchObject({ type: 'scroll', data: ['Range', 'Rating', 'Wind (low)'] });
  });

  it('rejects an unknown column or an empty y list', () => {
    expect(() => lineOption(RATING, { x: 'nope', y: ['mu'] })).toThrow('Unknown column "nope"');
    expect(() => lineOption(RATING, { x: 'event_date', y: [] })).toThrow('at least one y column');
  });
});
