import type { HeatmapSeriesOption, TooltipComponentOption } from 'echarts';
import { describe, expect, it } from 'vitest';
import type { TabularData } from '../types';
import { heatmapOption } from './heatmap';

const HITS: TabularData = {
  columns: [
    { key: 'station', label: 'Station', type: 'int' },
    { key: 'shooter', label: 'Shooter', type: 'string' },
    { key: 'hits', label: 'Hits', type: 'int' },
  ],
  rows: [
    { station: 4, shooter: 'Hadley, Ike', hits: 6 },
    { station: 5, shooter: 'Hadley, Ike', hits: 7 },
    { station: 4, shooter: '<img src=x onerror=alert(1)>', hits: 3 },
    { station: 5, shooter: '<img src=x onerror=alert(1)>', hits: null },
  ],
};

describe('heatmapOption', () => {
  it('indexes cells by category and skips empty cells', () => {
    const o = heatmapOption(HITS, { x: 'station', y: 'shooter', value: 'hits', labels: true });
    expect(o.xAxis).toMatchObject({ data: ['4', '5'] });
    expect(o.yAxis).toMatchObject({
      data: ['Hadley, Ike', '<img src=x onerror=alert(1)>'],
      inverse: true,
    });
    const [series] = o.series as [HeatmapSeriesOption];
    expect(series.data).toEqual([
      [0, 0, 6],
      [1, 0, 7],
      [0, 1, 3],
    ]);
    expect(series.label).toEqual({ show: true });
    expect(o.visualMap).toMatchObject({ min: 3, max: 7 });
  });

  it('names the columns below the axis and the rows above it (the y axis runs top down)', () => {
    const o = heatmapOption(HITS, { x: 'station', y: 'shooter', value: 'hits' });
    expect(o.xAxis).toMatchObject({ name: 'Station', nameLocation: 'middle', nameGap: 28 });
    // 'start' of an inverted axis is its top, where every other chart names its y axis.
    expect(o.yAxis).toMatchObject({ name: 'Shooter', inverse: true, nameLocation: 'start' });
  });

  it('honours explicit bounds and handles no data', () => {
    const o = heatmapOption(
      { columns: HITS.columns, rows: [] },
      { x: 'station', y: 'shooter', value: 'hits' },
    );
    expect(o.visualMap).toMatchObject({ min: 0, max: 1 });
    const bounded = heatmapOption(HITS, {
      x: 'station',
      y: 'shooter',
      value: 'hits',
      min: 0,
      max: 8,
    });
    expect(bounded.visualMap).toMatchObject({ min: 0, max: 8 });
  });

  it('escapes shooter names in the tooltip', () => {
    const o = heatmapOption(HITS, { x: 'station', y: 'shooter', value: 'hits' });
    const formatter = (o.tooltip as TooltipComponentOption).formatter as (p: unknown) => string;
    const html = formatter({ value: [0, 1, 3] });
    expect(html).toContain('&lt;img');
    expect(html).not.toContain('<img');
    expect(html).toBe('&lt;img src=x onerror=alert(1)&gt; · Station 4<br/>Hits: 3');
    expect(formatter({ value: [9, 9, 1] })).toBe(' · Station <br/>Hits: 1');
  });
});
