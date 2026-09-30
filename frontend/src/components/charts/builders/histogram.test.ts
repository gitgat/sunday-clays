import type { BarSeriesOption } from 'echarts';
import { describe, expect, it } from 'vitest';
import type { TabularData } from '../types';
import { binValues, histogramOption } from './histogram';

const SCORES: TabularData = {
  columns: [
    { key: 'score', label: 'Score', type: 'int' },
    { key: 'who', label: 'Who', type: 'string' },
  ],
  rows: [
    { score: 30, who: 'You' },
    { score: 34, who: 'You' },
    { score: 35, who: 'Club' },
    { score: 36, who: 'Club' },
    { score: 50, who: 'Club' },
    { score: null, who: 'Club' },
  ],
};

describe('binValues', () => {
  it('counts half-open bins and drops values outside the range', () => {
    // bins [0,5) [5,10) [10,15); -1 and 15 fall outside
    expect(binValues([0, 4, 5, 9, 10, 14, 15, -1], 5, 0, 10)).toEqual([2, 2, 2]);
  });

  it('has no bins, rather than throwing, when max is below min', () => {
    expect(binValues([1, 2], 1, 5, 0)).toEqual([]);
  });
});

describe('histogramOption', () => {
  it('bins by width with range labels and one series per group', () => {
    const o = histogramOption(SCORES, { value: 'score', binWidth: 5, seriesBy: 'who' });
    expect(o.xAxis).toMatchObject({ data: ['30–35', '35–40', '40–45', '45–50', '50–55'] });
    expect((o.series as BarSeriesOption[]).map((s) => [s.name, s.data])).toEqual([
      ['You', [2, 0, 0, 0, 0]],
      ['Club', [0, 2, 0, 0, 1]],
    ]);
    expect(o.yAxis).toMatchObject({ name: 'Count' });
  });

  it('normalizes each series to percent of its own total', () => {
    const o = histogramOption(SCORES, {
      value: 'score',
      binWidth: 5,
      min: 30,
      max: 50,
      seriesBy: 'who',
      normalize: true,
    });
    expect((o.series as BarSeriesOption[])[1]?.data).toEqual([0, (100 * 2) / 3, 0, 0, 100 / 3]);
    expect(o.yAxis).toMatchObject({ name: '% of rounds' });
  });

  it('normalizes a group with no values in range to zeros, not NaN', () => {
    const o = histogramOption(SCORES, {
      value: 'score',
      binWidth: 5,
      min: 30,
      max: 34,
      seriesBy: 'who',
      normalize: true,
    });
    expect((o.series as BarSeriesOption[]).map((s) => [s.name, s.data])).toEqual([
      ['You', [100]],
      ['Club', [0]],
    ]);
  });

  it('labels single-width bins by value and tolerates empty data', () => {
    const o = histogramOption(SCORES, { value: 'score', binWidth: 1, min: 48, max: 50 });
    expect(o.xAxis).toMatchObject({ data: ['48', '49', '50'] });
    expect((o.series as BarSeriesOption[])[0]).toMatchObject({ name: 'Score', data: [0, 0, 1] });
    const empty = histogramOption(
      { columns: SCORES.columns, rows: [] },
      { value: 'score', binWidth: 1, normalize: true },
    );
    expect(empty.xAxis).toMatchObject({ data: ['0'] });
    expect(empty.series).toEqual([]);
  });

  it('draws one empty bin at min, never throwing, when min is above the data or max', () => {
    const above = histogramOption(SCORES, { value: 'score', binWidth: 5, min: 60 });
    expect(above.xAxis).toMatchObject({ data: ['60–65'] });
    expect((above.series as BarSeriesOption[]).map((s) => [s.name, s.data])).toEqual([
      ['Score', [0]],
    ]);
    const inverted = histogramOption(SCORES, { value: 'score', binWidth: 5, min: 40, max: 10 });
    expect(inverted.xAxis).toMatchObject({ data: ['40–45'] });
  });

  it('rejects a non-positive bin width', () => {
    expect(() => histogramOption(SCORES, { value: 'score', binWidth: 0 })).toThrow(
      'binWidth must be positive',
    );
  });
});
