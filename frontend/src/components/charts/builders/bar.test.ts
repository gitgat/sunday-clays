import type { BarSeriesOption } from 'echarts';
import { describe, expect, it } from 'vitest';
import type { TabularData } from '../types';
import { barOption } from './bar';

const BY_YEAR: TabularData = {
  columns: [
    { key: 'year', label: 'Year', type: 'int' },
    { key: 'status', label: 'Status', type: 'string' },
    { key: 'value', label: 'Rounds', type: 'int' },
  ],
  rows: [
    { year: 2025, status: 'member', value: 1200 },
    { year: 2025, status: 'guest', value: 67 },
    { year: 2026, status: 'member', value: 950 },
  ],
};

describe('barOption', () => {
  it('uses the x column as categories and one series per y column', () => {
    const o = barOption(
      {
        columns: BY_YEAR.columns,
        rows: [
          { year: 2025, value: 1267 },
          { year: 2026, value: 969 },
        ],
      },
      { x: 'year', y: ['value'], labels: true },
    );
    expect(o.xAxis).toMatchObject({ type: 'category', data: ['2025', '2026'], inverse: false });
    expect(o.yAxis).toMatchObject({ type: 'value', name: 'Rounds' });
    expect(o.series).toEqual([
      expect.objectContaining({
        type: 'bar',
        name: 'Rounds',
        data: [1267, 969],
        label: { show: true, position: 'top' },
      }),
    ]);
  });

  it('pivots long rows into aligned, stacked series with null for missing categories', () => {
    const o = barOption(BY_YEAR, { x: 'year', y: ['value'], seriesBy: 'status', stack: true });
    const series = o.series as BarSeriesOption[];
    expect(series.map((s) => [s.name, s.data, s.stack])).toEqual([
      ['member', [1200, 950], 'total'],
      ['guest', [67, null], 'total'],
    ]);
    expect(o.legend).toMatchObject({ type: 'scroll' });
  });

  it('puts categories on the y axis, first row on top, when horizontal', () => {
    const o = barOption(BY_YEAR, { x: 'status', y: ['value'], horizontal: true, yName: 'n' });
    expect(o.yAxis).toMatchObject({
      type: 'category',
      inverse: true,
      data: ['member', 'guest', 'member'],
    });
    // Named below the axis, like every x axis: at its end it would squeeze the bars on a phone.
    expect(o.xAxis).toMatchObject({
      type: 'value',
      name: 'n',
      nameLocation: 'middle',
      nameGap: 28,
    });
    expect((o.series as BarSeriesOption[])[0]?.label).toMatchObject({ position: 'right' });
    // Upright bars keep the value axis name at the top of the axis.
    expect(barOption(BY_YEAR, { x: 'status', y: ['value'] }).yAxis).not.toHaveProperty(
      'nameLocation',
    );
  });

  it('keeps one category per row in wide format, so namesakes stay aligned with their values', () => {
    const o = barOption(
      {
        columns: [
          { key: 'shooter', label: 'Shooter', type: 'string' },
          { key: 'value', label: 'Avg score', type: 'number' },
        ],
        rows: [
          { shooter: 'Tarleton, Jo', value: 41 },
          { shooter: 'Able, Ann', value: 38 },
          { shooter: 'Tarleton, Jo', value: 30 },
        ],
      },
      { x: 'shooter', y: ['value'] },
    );
    const categories = (o.xAxis as { data: string[] }).data;
    const values = (o.series as BarSeriesOption[])[0]?.data as number[];
    expect(categories).toHaveLength(values.length);
    expect(categories.map((c, i) => [c, values[i]])).toEqual([
      ['Tarleton, Jo', 41],
      ['Able, Ann', 38],
      ['Tarleton, Jo', 30],
    ]);
  });

  it('needs at least one y column', () => {
    expect(() => barOption(BY_YEAR, { x: 'year', y: [] })).toThrow('at least one y column');
  });
});
