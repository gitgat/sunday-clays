import type { LineSeriesOption, ScatterSeriesOption, TooltipComponentOption } from 'echarts';
import { describe, expect, it } from 'vitest';
import type { TabularData } from '../types';
import { linearFit, scatterOption } from './scatter';

const DATA: TabularData = {
  columns: [
    { key: 'gust', label: 'Gust (mph)', type: 'number' },
    { key: 'difficulty', label: 'Difficulty', type: 'number' },
    { key: 'event', label: 'Event', type: 'date' },
    { key: 'kind', label: 'Kind', type: 'string' },
  ],
  rows: [
    { gust: 0, difficulty: 1, event: '2026-01-04', kind: 'a' },
    { gust: 10, difficulty: 4, event: '<img src=x onerror=alert(1)>', kind: 'b' },
    { gust: 20, difficulty: 7, event: '2026-01-18', kind: 'a' },
    { gust: null, difficulty: 9, event: '2026-01-25', kind: 'a' },
  ],
};

function tooltipText(o: ReturnType<typeof scatterOption>, params: unknown): string {
  const formatter = (o.tooltip as TooltipComponentOption).formatter as (p: unknown) => string;
  return formatter(params);
}

describe('linearFit', () => {
  it('recovers slope and intercept of exact points', () => {
    expect(
      linearFit([
        [0, 1],
        [10, 4],
        [20, 7],
      ]),
    ).toEqual({ slope: 0.3, intercept: 1 });
  });

  it('returns null with fewer than two points or no spread in x', () => {
    expect(linearFit([[1, 1]])).toBeNull();
    expect(
      linearFit([
        [2, 1],
        [2, 5],
      ]),
    ).toBeNull();
  });
});

describe('scatterOption', () => {
  it('plots finite x/y pairs named by the label column and adds a dashed fit line', () => {
    const o = scatterOption(DATA, { x: 'gust', y: 'difficulty', label: 'event', fit: true });
    const [points, fit] = o.series as [ScatterSeriesOption, LineSeriesOption];
    expect(points.data).toEqual([
      { value: [0, 1], name: '2026-01-04' },
      { value: [10, 4], name: '<img src=x onerror=alert(1)>' },
      { value: [20, 7], name: '2026-01-18' },
    ]);
    expect(fit).toMatchObject({
      name: 'Fit',
      data: [
        [0, 1],
        [20, 7],
      ],
    });
  });

  it('escapes names in the tooltip so a shooter name cannot inject HTML', () => {
    const o = scatterOption(DATA, { x: 'gust', y: 'difficulty', label: 'event' });
    const html = tooltipText(o, { name: '<img src=x onerror=alert(1)>', value: [10, 4] });
    expect(html).toContain('&lt;img');
    expect(html).not.toContain('<img');
    expect(html).toContain('Gust (mph): 10');
  });

  it('omits the title line for unnamed points and splits series by a column', () => {
    const o = scatterOption(DATA, {
      x: 'gust',
      y: 'difficulty',
      seriesBy: 'kind',
      xName: 'Gust',
      yName: 'Diff',
    });
    expect((o.series as ScatterSeriesOption[]).map((s) => s.name)).toEqual(['a', 'b']);
    expect(tooltipText(o, { name: '', value: [1, 2] })).toBe('Gust: 1<br/>Diff: 2');
    expect(tooltipText(o, {})).toBe('Gust: NaN<br/>Diff: NaN');
  });

  it('skips the fit line when no fit is possible', () => {
    const one: TabularData = {
      columns: DATA.columns,
      rows: [{ gust: 1, difficulty: 2, event: 'x', kind: 'a' }],
    };
    expect(scatterOption(one, { x: 'gust', y: 'difficulty', fit: true }).series).toHaveLength(1);
  });
});
