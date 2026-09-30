import type { BoxplotSeriesOption, EChartsOption, ScatterSeriesOption } from 'echarts';
import type { TabularData } from '../types';
import { GRID, cellLabel, distinct, numeric, requireColumn } from './common';

export interface BoxplotOpts {
  group: string;
  value: string;
  yName?: string;
}

export interface FiveNumber {
  min: number;
  q1: number;
  median: number;
  q3: number;
  max: number;
  outliers: number[];
}

/** Linear-interpolated quantile (numpy/pandas default) of sorted values. */
export function quantile(sorted: readonly number[], p: number): number {
  const pos = (sorted.length - 1) * p;
  const lo = Math.floor(pos);
  const a = sorted[lo] ?? NaN;
  const b = sorted[Math.min(lo + 1, sorted.length - 1)] ?? NaN;
  return a + (b - a) * (pos - lo);
}

/** Tukey box: whiskers at the most extreme values within 1.5·IQR of the box; the rest are outliers. */
export function fiveNumber(values: readonly number[]): FiveNumber | null {
  if (values.length === 0) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const q1 = quantile(sorted, 0.25);
  const q3 = quantile(sorted, 0.75);
  const fence = 1.5 * (q3 - q1);
  const inside = sorted.filter((v) => v >= q1 - fence && v <= q3 + fence);
  return {
    min: inside[0] ?? q1,
    q1,
    median: quantile(sorted, 0.5),
    q3,
    max: inside[inside.length - 1] ?? q3,
    outliers: sorted.filter((v) => v < q1 - fence || v > q3 + fence),
  };
}

export function boxplotOption(data: TabularData, opts: BoxplotOpts): EChartsOption {
  const groupKey = requireColumn(data, opts.group).key;
  const valueCol = requireColumn(data, opts.value);
  const groups = distinct(data.rows.map((r) => cellLabel(r[groupKey])));
  const stats = groups.map((g) =>
    fiveNumber(
      data.rows
        .filter((r) => cellLabel(r[groupKey]) === g)
        .flatMap((r) => {
          const v = numeric(r[valueCol.key]);
          return v === null ? [] : [v];
        }),
    ),
  );
  const boxes: BoxplotSeriesOption = {
    type: 'boxplot',
    name: valueCol.label,
    data: stats.map((s) => (s ? [s.min, s.q1, s.median, s.q3, s.max] : [])),
  };
  const outliers: ScatterSeriesOption = {
    type: 'scatter',
    name: 'Outliers',
    symbolSize: 6,
    data: stats.flatMap((s, i) => (s ? s.outliers.map((v) => [i, v]) : [])),
  };
  return {
    grid: { ...GRID },
    tooltip: { trigger: 'item' },
    xAxis: { type: 'category', data: groups },
    yAxis: { type: 'value', name: opts.yName ?? valueCol.label, scale: true },
    series: [boxes, outliers],
  };
}
