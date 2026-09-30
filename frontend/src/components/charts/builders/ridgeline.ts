import type { EChartsOption, LineSeriesOption } from 'echarts';
import type { TabularData } from '../types';
import {
  GRID,
  NAME_BELOW,
  cellLabel,
  distinct,
  escapeHtml,
  numeric,
  paletteColor,
  requireColumn,
} from './common';

export interface RidgelineOpts {
  /** One ridge per distinct value, first value at the top (e.g. year). */
  group: string;
  value: string;
  /** Density grid; default 0..50 step 1 (round scores). */
  min?: number;
  max?: number;
  step?: number;
  /** Gaussian kernel bandwidth; default Silverman's rule per group. */
  bandwidth?: number;
  /** Ridge height in rows; >1 lets ridges overlap. */
  overlap?: number;
}

/** Silverman's rule of thumb (1.06·σ·n^-1/5), at least 0.5. */
export function silverman(values: readonly number[]): number {
  const n = values.length;
  if (n < 2) return 1;
  const mean = values.reduce((s, v) => s + v, 0) / n;
  const sd = Math.sqrt(values.reduce((s, v) => s + (v - mean) ** 2, 0) / (n - 1));
  return Math.max(0.5, 1.06 * sd * n ** -0.2);
}

/** Gaussian kernel density of `values` evaluated at each grid point. */
export function kde(
  values: readonly number[],
  grid: readonly number[],
  bandwidth: number,
): number[] {
  const n = values.length;
  if (n === 0) return grid.map(() => 0);
  const norm = 1 / (n * bandwidth * Math.sqrt(2 * Math.PI));
  return grid.map(
    (x) => norm * values.reduce((s, v) => s + Math.exp(-0.5 * ((x - v) / bandwidth) ** 2), 0),
  );
}

export function ridgelineOption(data: TabularData, opts: RidgelineOpts): EChartsOption {
  const groupKey = requireColumn(data, opts.group).key;
  const valueCol = requireColumn(data, opts.value);
  const min = opts.min ?? 0;
  const max = opts.max ?? 50;
  const step = opts.step ?? 1;
  if (!(step > 0)) throw new Error('step must be positive');
  const overlap = opts.overlap ?? 1.8;
  const grid: number[] = [];
  for (let x = min; x <= max; x += step) grid.push(x);
  const groups = distinct(data.rows.map((r) => cellLabel(r[groupKey])));
  const ridges = groups.map((name) => {
    const values = data.rows
      .filter((r) => cellLabel(r[groupKey]) === name)
      .flatMap((r) => {
        const v = numeric(r[valueCol.key]);
        return v === null ? [] : [v];
      });
    return { name, density: kde(values, grid, opts.bandwidth ?? silverman(values)) };
  });
  const peak = Math.max(0, ...ridges.flatMap((r) => r.density));
  const scale = peak > 0 ? overlap / peak : 0;
  const n = groups.length;
  const series: LineSeriesOption[] = ridges.map(({ name, density }, i) => {
    const baseline = n - 1 - i;
    const color = paletteColor(i);
    return {
      type: 'line',
      name,
      smooth: true,
      symbol: 'none',
      z: i + 2,
      lineStyle: { width: 1.5, color },
      areaStyle: { origin: baseline, opacity: 0.35, color },
      // kde() returns one density per grid point, so grid[j] is always defined.
      data: density.map((d, j) => [grid[j], baseline + d * scale]),
    };
  });
  return {
    grid: { ...GRID, left: 16 },
    tooltip: {
      trigger: 'axis',
      formatter: (params: unknown) => {
        const list = params as { seriesName?: string; dataIndex?: number; seriesIndex?: number }[];
        const x = grid[list[0]?.dataIndex ?? 0];
        const lines = list.map((p) => {
          const d = ridges[p.seriesIndex ?? 0]?.density[p.dataIndex ?? 0] ?? 0;
          return `${escapeHtml(p.seriesName ?? '')}: ${(100 * d * step).toFixed(1)}%`;
        });
        return [`${escapeHtml(valueCol.label)} ${escapeHtml(x)}`, ...lines].join('<br/>');
      },
    },
    xAxis: { type: 'value', min, max, name: valueCol.label, ...NAME_BELOW },
    yAxis: {
      type: 'value',
      min: 0,
      max: Math.max(1, n - 1 + overlap),
      interval: 1,
      axisLabel: { formatter: (v: number) => groups[n - 1 - v] ?? '' },
      splitLine: { show: false },
    },
    series,
  };
}
