import type { EChartsOption } from 'echarts';
import { renderHook } from '@testing-library/react';
import { createElement, type ReactNode } from 'react';
import { MemoryRouter } from 'react-router';
import { describe, expect, it } from 'vitest';
import { ratingModel } from '../../features/shooters/charts';
import { colors } from '../../theme/tokens';
import {
  applyTarget,
  useTargetWindow,
  markedCount,
  matches,
  readTarget,
  rowTargeted,
  shooterLabels,
} from './chartTarget';

describe('readTarget', () => {
  it('reads highlight, dates, reference and page options for one chart only', () => {
    const search = new URLSearchParams(
      'trend.hl=2026-09-27,2026-09-13&trend.from=2026-06-27&trend.to=2026-09-27&trend.ref=35' +
        '&trend.line=roll10&trend.v=table&rating.hl=2026-01-04',
    );
    expect(readTarget(search, 'trend')).toEqual({
      hl: ['2026-09-27', '2026-09-13'],
      window: { from: '2026-06-27', to: '2026-09-27' },
      ref: 35,
      params: { line: 'roll10' },
      active: true,
    });
  });

  it('ignores a malformed window or reference and is inactive without params', () => {
    const bad = readTarget(new URLSearchParams('x.from=2026-09-27&x.to=2026-01-01&x.ref=abc'), 'x');
    expect(bad.window).toBeNull();
    expect(bad.ref).toBeNull();
    expect(readTarget(new URLSearchParams('x.v=table&x.line=roll10'), 'x').active).toBe(false);
  });
});

describe('matches', () => {
  it('matches labels, the date part of a timestamp and a date span', () => {
    expect(matches(['2026-09-27'], '2026-09-27T00:00:00')).toBe(true);
    expect(matches(['2026-09-01..2026-09-30'], '2026-09-13')).toBe(true);
    expect(matches(['2026-09-01..2026-09-30'], '2026-10-04')).toBe(false);
    expect(matches(['wet'], 'wet')).toBe(true);
  });
});

describe('shooterLabels', () => {
  it('turns s:{id} keys into that shooter row labels', () => {
    const rows = [
      { shooter_id: 7, display_name: 'Ace, Amy' },
      { shooter_id: 3, display_name: 'Bee, Bob' },
    ];
    expect(shooterLabels('display_name')(['s:3', '2026-09-27'], rows)).toEqual([
      'Bee, Bob',
      '2026-09-27',
    ]);
  });
});

const HIGHLIGHT = { color: colors.text, borderColor: colors.accent, borderWidth: 3 };

describe('applyTarget', () => {
  const bars: EChartsOption = {
    xAxis: { type: 'category', data: ['2025', '2026'] },
    yAxis: { type: 'value' },
    series: [{ type: 'bar', data: [30, 35] }],
  };

  it('rings the highlighted bar and leaves the rest', () => {
    const out = applyTarget(bars, ['2026'], null);
    const data = (out.series as { data: unknown[] }[])[0]?.data;
    expect(data?.[0]).toBe(30);
    expect(data?.[1]).toEqual({
      value: 35,
      itemStyle: { color: colors.text, borderColor: colors.accent, borderWidth: 3 },
    });
    expect((bars.series as { data: unknown[] }[])[0]?.data[1]).toBe(35);
    expect(markedCount(out)).toBe(1);
    expect(markedCount(bars)).toBe(0);
  });

  it('keeps the fields of a bar item that is already an object', () => {
    const objects: EChartsOption = {
      xAxis: { type: 'category', data: ['2025', '2026'] },
      yAxis: { type: 'value' },
      series: [{ type: 'bar', data: [30, { value: 35, itemStyle: {} }] }],
    };
    const data = (applyTarget(objects, ['2026'], null).series as { data: unknown[] }[])[0]?.data;
    expect(data?.[1]).toEqual({ value: 35, itemStyle: HIGHLIGHT });
  });

  it('marks line points by their x value and draws the reference line', () => {
    const line: EChartsOption = {
      xAxis: { type: 'time' },
      yAxis: { type: 'value' },
      series: [
        {
          type: 'line',
          data: [
            ['2026-09-13', 30],
            ['2026-09-27', 44],
          ],
        },
      ],
    };
    const out = applyTarget(line, ['2026-09-27'], 40);
    const series = (out.series as { data: unknown[]; markLine: { data: unknown[] } }[])[0];
    const point = (out.series as { markPoint: { data: unknown[] } }[])[0]?.markPoint.data;
    expect(series?.data).toEqual(line.series && (line.series as { data: unknown[] }[])[0]?.data);
    expect(point).toEqual([
      { coord: ['2026-09-27', 44], symbol: 'circle', symbolSize: 12, itemStyle: HIGHLIGHT },
    ]);
    expect(markedCount(out)).toBe(1);
    expect(series?.markLine.data).toEqual([{ yAxis: 40 }]);
  });

  it('puts the reference on x for horizontal bars and is a no-op with no target', () => {
    const horizontal: EChartsOption = {
      xAxis: { type: 'value' },
      yAxis: { type: 'category', data: ['Amy'] },
      series: [{ type: 'bar', data: [3] }],
    };
    const out = applyTarget(horizontal, [], 0);
    expect((out.series as { markLine: { data: unknown[] } }[])[0]?.markLine.data).toEqual([
      { xAxis: 0 },
    ]);
    expect(applyTarget(bars, [], null)).toBe(bars);
  });

  it('matches scatter points by their name (the date they carry)', () => {
    const scatter: EChartsOption = {
      xAxis: { type: 'value' },
      yAxis: { type: 'value' },
      series: [
        {
          type: 'scatter',
          data: [
            { name: '2026-09-13', value: [1.2, 3] },
            { name: '2026-09-27', value: [2.5, 4] },
          ],
        },
      ],
    };
    const out = applyTarget(scatter, ['2026-09-27'], null);
    const one = (out.series as { markPoint: { data: unknown[] } }[])[0];
    expect(one?.markPoint.data).toEqual([
      { coord: [2.5, 4], symbol: 'circle', symbolSize: 12, itemStyle: HIGHLIGHT },
    ]);
  });

  it('still rings a point on a long line chart that draws no symbols (showSymbol off)', () => {
    const days = Array.from({ length: 61 }, (_, i) => `2026-01-${String(i + 1).padStart(2, '0')}`);
    const long: EChartsOption = {
      xAxis: { type: 'category', data: days },
      yAxis: { type: 'value' },
      series: [{ type: 'line', showSymbol: false, data: days.map((_, i) => i) }],
    };
    const out = applyTarget(long, ['2026-01-05'], null);
    const one = (
      out.series as { showSymbol: boolean; markPoint: { data: { coord: unknown[] }[] } }[]
    )[0];
    expect(one?.showSymbol).toBe(false);
    expect(one?.markPoint.data.map((d) => d.coord)).toEqual([['2026-01-05', 4]]);
    expect(markedCount(out)).toBe(1);
  });

  it('marks one ring per date on the rating chart, not on its hidden range series', () => {
    const { option } = ratingModel([
      { event_date: '2026-01-04', mu: 30, lo: 25, hi: 35 },
      { event_date: '2026-01-11', mu: 32, lo: 27, hi: 37 },
    ] as Parameters<typeof ratingModel>[0]);
    const out = applyTarget(option, ['2026-01-04'], 31);
    const series = out.series as {
      name: string;
      markPoint?: { data: { name?: string; coord: unknown[] }[] };
      markLine?: unknown;
    }[];
    expect(markedCount(out)).toBe(1);
    expect(series[0]?.markPoint).toBeUndefined();
    expect(series[1]?.markPoint).toBeUndefined();
    expect(series[0]?.markLine).toBeUndefined();
    expect(series[2]?.markLine).toBeDefined();
    const names = series[2]?.markPoint?.data.map((d) => d.name ?? d.coord[0]);
    expect(names).toEqual(['Peak', '2026-01-04']);
  });

  it('rings only the first visible line of several, and skips missing values', () => {
    const two: EChartsOption = {
      xAxis: { type: 'category', data: ['a', 'b'] },
      yAxis: [{ type: 'value' }, { type: 'value' }],
      series: [
        { type: 'line', data: [1, null] },
        { type: 'line', yAxisIndex: 1, data: [5, 6] },
      ],
    };
    expect(markedCount(applyTarget(two, ['b'], null))).toBe(0);
    expect(markedCount(applyTarget(two, ['a'], null))).toBe(1);
    const only = (applyTarget(two, ['a'], null).series as { markPoint?: unknown }[])[1];
    expect(only?.markPoint).toBeUndefined();
  });
});

describe('useTargetWindow', () => {
  const wrap = (search: string) =>
    function Wrapper({ children }: { children: ReactNode }) {
      return createElement(MemoryRouter, { initialEntries: [`/?${search}`] }, children);
    };
  const page = { from: '2025-01-01', to: '2025-12-31' };

  it("prefers the link's dates over the page's window", () => {
    const { result } = renderHook(() => useTargetWindow('x', page), {
      wrapper: wrap('x.from=2026-01-01&x.to=2026-02-01'),
    });
    expect(result.current).toEqual({ from: '2026-01-01', to: '2026-02-01' });
  });

  it("falls back to the page's window", () => {
    const { result } = renderHook(() => useTargetWindow('x', page), { wrapper: wrap('') });
    expect(result.current).toBe(page);
  });
});

describe('rowTargeted', () => {
  it('needs every kind of key the link carries to match', () => {
    expect(rowTargeted(['s:7'], 7, '2021-01-17')).toBe(true);
    expect(rowTargeted(['s:7'], 3, '2021-01-17')).toBe(false);
    expect(rowTargeted(['2021-01-17'], 3, '2021-01-17')).toBe(true);
    expect(rowTargeted(['2021-01-17', 's:7'], 7, '2021-01-17')).toBe(true);
    expect(rowTargeted(['2021-01-17', 's:7'], 7, '2022-12-04')).toBe(false);
    expect(rowTargeted(['2021-01-01..2021-12-31'], 9, '2021-03-28')).toBe(true);
    expect(rowTargeted(['2021-01-17'], 7, null)).toBe(false);
    expect(rowTargeted([], 7, '2021-01-17')).toBe(false);
  });
});
