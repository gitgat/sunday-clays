import type { BoxplotSeriesOption, ScatterSeriesOption } from 'echarts';
import { describe, expect, it } from 'vitest';
import type { TabularData } from '../types';
import { boxplotOption, fiveNumber, quantile } from './boxplot';

describe('quantile / fiveNumber', () => {
  it('interpolates linearly between order statistics', () => {
    expect(quantile([1, 2, 3, 4], 0.25)).toBe(1.75);
    expect(quantile([10], 0.9)).toBe(10);
    expect(quantile([], 0.5)).toBeNaN();
  });

  it('computes Tukey whiskers and outliers', () => {
    // q1 = 30.75, q3 = 36.5, IQR 5.75 → fences 22.125 and 45.125
    expect(fiveNumber([10, 30, 31, 33, 35, 36, 38, 50])).toEqual({
      min: 30,
      q1: 30.75,
      median: 34,
      q3: 36.5,
      max: 38,
      outliers: [10, 50],
    });
    expect(fiveNumber([])).toBeNull();
  });

  it('falls back to the box edges when no value lies inside the fences (non-finite input)', () => {
    expect(fiveNumber([Number.NaN])).toEqual({
      min: NaN,
      q1: NaN,
      median: NaN,
      q3: NaN,
      max: NaN,
      outliers: [],
    });
  });
});

describe('boxplotOption', () => {
  it('draws one box per group and outliers at their group index', () => {
    const data: TabularData = {
      columns: [
        { key: 'year', label: 'Year', type: 'int' },
        { key: 'score', label: 'Score', type: 'int' },
      ],
      rows: [
        ...[10, 30, 31, 33, 35, 36, 38, 50].map((score) => ({ year: 2025, score })),
        { year: 2026, score: 40 },
        { year: 2027, score: null },
      ],
    };
    const o = boxplotOption(data, { group: 'year', value: 'score' });
    expect(o.xAxis).toMatchObject({ data: ['2025', '2026', '2027'] });
    const [boxes, outliers] = o.series as [BoxplotSeriesOption, ScatterSeriesOption];
    expect(boxes.data).toEqual([[30, 30.75, 34, 36.5, 38], [40, 40, 40, 40, 40], []]);
    expect(outliers.data).toEqual([
      [0, 10],
      [0, 50],
    ]);
  });
});
