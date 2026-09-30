import type { LineSeriesOption, TooltipComponentOption, YAXisComponentOption } from 'echarts';
import { describe, expect, it } from 'vitest';
import type { TabularData } from '../types';
import { kde, ridgelineOption, silverman } from './ridgeline';

describe('kde', () => {
  it('is a normal density centred on a single value', () => {
    const [atMean, oneSdAway] = kde([30], [30, 32], 2);
    expect(atMean).toBeCloseTo(1 / (2 * Math.sqrt(2 * Math.PI)), 10);
    expect(oneSdAway).toBeCloseTo(Math.exp(-0.5) / (2 * Math.sqrt(2 * Math.PI)), 10);
  });

  it('is zero everywhere without values', () => {
    expect(kde([], [0, 1], 1)).toEqual([0, 0]);
  });
});

describe('silverman', () => {
  it('follows 1.06·sd·n^(-1/5) with a floor of 0.5 and 1 for tiny samples', () => {
    expect(silverman([30, 34, 38, 42])).toBeCloseTo(1.06 * Math.sqrt(80 / 3) * 4 ** -0.2, 10);
    expect(silverman([35, 35, 35])).toBe(0.5);
    expect(silverman([35])).toBe(1);
  });
});

const BY_YEAR: TabularData = {
  columns: [
    { key: 'year', label: 'Year', type: 'int' },
    { key: 'score', label: 'Score', type: 'int' },
  ],
  rows: [
    { year: 2025, score: 34 },
    { year: 2025, score: 36 },
    { year: 2026, score: 40 },
    { year: '<img src=x onerror=alert(1)>', score: null },
  ],
};

describe('ridgelineOption', () => {
  it('stacks one ridge per group, first group on top, filled from its own baseline', () => {
    const o = ridgelineOption(BY_YEAR, {
      group: 'year',
      value: 'score',
      min: 30,
      max: 44,
      step: 2,
      bandwidth: 2,
      overlap: 1,
    });
    const series = o.series as LineSeriesOption[];
    expect(series.map((s) => s.name)).toEqual(['2025', '2026', '<img src=x onerror=alert(1)>']);
    expect(series.map((s) => (s.areaStyle as { origin: number }).origin)).toEqual([2, 1, 0]);
    const tallest = Math.max(
      ...series.flatMap((s) =>
        (s.data as [number, number][]).map(
          ([, y]) => y - (s.areaStyle as { origin: number }).origin,
        ),
      ),
    );
    expect(tallest).toBeCloseTo(1, 10);
    expect((series[2]?.data as [number, number][]).every(([, y]) => y === 0)).toBe(true);
    const yAxis = o.yAxis as YAXisComponentOption & {
      axisLabel: { formatter: (v: number) => string };
    };
    expect([0, 1, 2, 3].map((v) => yAxis.axisLabel.formatter(v))).toEqual([
      '<img src=x onerror=alert(1)>',
      '2026',
      '2025',
      '',
    ]);
  });

  it('escapes group names in the tooltip', () => {
    const o = ridgelineOption(BY_YEAR, { group: 'year', value: 'score', bandwidth: 2 });
    const formatter = (o.tooltip as TooltipComponentOption).formatter as (p: unknown) => string;
    const html = formatter([
      { seriesName: '2025', seriesIndex: 0, dataIndex: 35 },
      { seriesName: '<img src=x onerror=alert(1)>', seriesIndex: 2, dataIndex: 35 },
    ]);
    expect(html).toContain('&lt;img');
    expect(html).not.toContain('<img');
    expect(html.startsWith('Score 35<br/>2025: ')).toBe(true);
    expect(formatter([])).toBe('Score 0');
    expect(formatter([{ seriesIndex: 9 }, {}])).toBe('Score 0<br/>: 0.0%<br/>: 0.0%');
  });

  it('defaults to a 0–50 grid, a 1.8-row ridge height and a Silverman bandwidth per group', () => {
    const o = ridgelineOption(BY_YEAR, { group: 'year', value: 'score' });
    expect(o.xAxis).toMatchObject({ min: 0, max: 50 });
    expect((o.yAxis as { max: number }).max).toBeCloseTo(3.8, 10);
    const series = o.series as LineSeriesOption[];
    // 2026 holds one score (40), so Silverman gives bandwidth 1: a unit normal around 40.
    const ridge = (series[1]?.data ?? []) as [number, number][];
    expect(ridge).toHaveLength(51);
    const height = (x: number) => (ridge[x]?.[1] ?? NaN) - 1;
    expect(height(40) / height(41)).toBeCloseTo(Math.exp(0.5), 10);
    const tallest = Math.max(
      ...series.flatMap((s, i) => (s.data as [number, number][]).map(([, y]) => y - (2 - i))),
    );
    expect(tallest).toBeCloseTo(1.8, 10);
  });

  it('rejects a missing or non-positive step instead of looping forever', () => {
    // NaN first: before the guard it returns (one grid point) where 0 and -1 would never return.
    for (const step of [Number.NaN, 0, -1]) {
      expect(() => ridgelineOption(BY_YEAR, { group: 'year', value: 'score', step })).toThrow(
        'step must be positive',
      );
    }
  });

  it('handles no data at all', () => {
    const o = ridgelineOption(
      { columns: BY_YEAR.columns, rows: [] },
      { group: 'year', value: 'score' },
    );
    expect(o.series).toEqual([]);
    expect(o.yAxis).toMatchObject({ max: 1 });
  });
});
