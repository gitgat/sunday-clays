import type { EChartsOption } from 'echarts';
import { describe, expect, it } from 'vitest';
import { withCompare } from './explore';
import type { TabularData } from './types';

const compare: TabularData = {
  columns: [
    { key: 'year', label: 'Year', type: 'string' },
    { key: 'value', label: 'Avg', type: 'number' },
  ],
  rows: [
    { year: '2026', value: 1.5 },
    { year: '2025', value: -0.5 },
  ],
};

describe('withCompare', () => {
  it('aligns the compare values to the main categories as a dashed line', () => {
    const main: EChartsOption = {
      xAxis: { type: 'category', data: ['2024', '2025', '2026'] },
      series: [{ type: 'bar', data: [30, 31, 32] }],
    };
    const out = withCompare(main, compare, ['year'], 'Everyone');
    const series = out.series as { type: string; name?: string; data: unknown[] }[];
    expect(series).toHaveLength(2);
    expect(series[1]).toMatchObject({ type: 'line', name: 'Everyone', data: [null, -0.5, 1.5] });
  });

  it('keeps [x, y] points on a time axis and ignores an ungrouped result', () => {
    const main: EChartsOption = { xAxis: { type: 'time' }, series: [{ type: 'line', data: [] }] };
    const out = withCompare(main, compare, ['year'], 'Everyone');
    expect((out.series as { data: unknown[] }[])[1]?.data).toEqual([
      ['2026', 1.5],
      ['2025', -0.5],
    ]);
    expect(withCompare(main, compare, [], 'Everyone')).toBe(main);
  });

  it('rounds the compare values like the main series', () => {
    const main: EChartsOption = {
      xAxis: { type: 'category', data: ['2026'] },
      series: [{ type: 'bar', data: [30] }],
    };
    const raw: TabularData = {
      columns: compare.columns,
      rows: [{ year: '2026', value: 31.846153846 }],
    };
    const out = withCompare(main, raw, ['year'], 'Everyone');
    expect((out.series as { data: unknown[] }[])[1]?.data).toEqual([31.85]);
  });

  it('leaves horizontal (value x axis) and two-dimension charts alone', () => {
    const horizontal: EChartsOption = {
      xAxis: { type: 'value' },
      yAxis: { type: 'category', data: ['A'] },
      series: [{ type: 'bar', data: [1] }],
    };
    expect(withCompare(horizontal, compare, ['shooter'], 'Everyone')).toBe(horizontal);
    const two: EChartsOption = {
      xAxis: { type: 'category', data: ['2026'] },
      series: [{ type: 'bar', data: [1] }],
    };
    expect(withCompare(two, compare, ['year', 'round_type'], 'Everyone')).toBe(two);
  });
});
