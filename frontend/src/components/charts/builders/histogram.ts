import type { BarSeriesOption, EChartsOption } from 'echarts';
import type { TabularData } from '../types';
import { GRID, NAME_BELOW, cellLabel, distinct, legendFor, numeric, requireColumn } from './common';

export interface HistogramOpts {
  value: string;
  /** Bins are half-open [lo, lo + binWidth). */
  binWidth: number;
  /** First bin start; default = data min rounded down to a multiple of binWidth. */
  min?: number;
  /** Last value that must fall in a bin; default = data max. */
  max?: number;
  /** One histogram per distinct value (e.g. "You" vs "Club"). */
  seriesBy?: string;
  /** Show each series as % of its own total so different-sized groups compare. */
  normalize?: boolean;
  xName?: string;
}

/** Counts per bin [min + i·w, min + (i+1)·w) for i = 0..floor((max-min)/w); outside values are dropped. */
export function binValues(
  values: readonly number[],
  binWidth: number,
  min: number,
  max: number,
): number[] {
  const n = Math.max(0, Math.floor((max - min) / binWidth) + 1);
  const counts = new Array<number>(n).fill(0);
  for (const v of values) {
    const i = Math.floor((v - min) / binWidth);
    const count = counts[i]; // undefined outside the bins
    if (count !== undefined) counts[i] = count + 1;
  }
  return counts;
}

export function histogramOption(data: TabularData, opts: HistogramOpts): EChartsOption {
  if (!(opts.binWidth > 0)) throw new Error('binWidth must be positive');
  const valueCol = requireColumn(data, opts.value);
  const byKey = opts.seriesBy === undefined ? null : requireColumn(data, opts.seriesBy).key;
  const all = data.rows.flatMap((r) => {
    const v = numeric(r[valueCol.key]);
    return v === null ? [] : [{ v, group: byKey === null ? valueCol.label : cellLabel(r[byKey]) }];
  });
  const values = all.map((a) => a.v);
  const min =
    opts.min ??
    (values.length ? Math.floor(Math.min(...values) / opts.binWidth) * opts.binWidth : 0);
  // At least min, so a min above the data (or max below min) still gives one bin, not a RangeError.
  const max = Math.max(opts.max ?? (values.length ? Math.max(...values) : min), min);
  const labels = binValues([], opts.binWidth, min, max).map((_, i) => {
    const lo = min + i * opts.binWidth;
    return opts.binWidth === 1 ? String(lo) : `${lo}–${lo + opts.binWidth}`;
  });
  const series: BarSeriesOption[] = distinct(all.map((a) => a.group)).map((group) => {
    const counts = binValues(
      all.filter((a) => a.group === group).map((a) => a.v),
      opts.binWidth,
      min,
      max,
    );
    const total = counts.reduce((s, c) => s + c, 0);
    return {
      type: 'bar',
      name: group,
      barGap: '0%',
      data: opts.normalize ? counts.map((c) => (total ? (100 * c) / total : 0)) : counts,
    };
  });
  return {
    grid: { ...GRID },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: legendFor(series.length),
    xAxis: {
      type: 'category',
      data: labels,
      name: opts.xName ?? valueCol.label,
      ...NAME_BELOW,
    },
    yAxis: { type: 'value', name: opts.normalize ? '% of rounds' : 'Count' },
    series,
  };
}
