import type { EChartsOption, LineSeriesOption, ScatterSeriesOption } from 'echarts';
import { chartPalette } from '../../../theme/tokens';
import type { TabularData } from '../types';
import {
  GRID,
  NAME_BELOW,
  cellLabel,
  distinct,
  escapeHtml,
  legendFor,
  numeric,
  requireColumn,
} from './common';

export interface ScatterOpts {
  x: string;
  y: string;
  /** Column naming each point in the tooltip (e.g. shooter or event). */
  label?: string;
  seriesBy?: string;
  /** Adds a least-squares line through all points. */
  fit?: boolean;
  xName?: string;
  yName?: string;
}

export interface LinearFit {
  slope: number;
  intercept: number;
}

/** Ordinary least squares y = intercept + slope·x; null with <2 points or no spread in x. */
export function linearFit(points: readonly (readonly [number, number])[]): LinearFit | null {
  const n = points.length;
  if (n < 2) return null;
  const mx = points.reduce((s, [x]) => s + x, 0) / n;
  const my = points.reduce((s, [, y]) => s + y, 0) / n;
  const sxx = points.reduce((s, [x]) => s + (x - mx) ** 2, 0);
  if (sxx === 0) return null;
  const sxy = points.reduce((s, [x, y]) => s + (x - mx) * (y - my), 0);
  const slope = sxy / sxx;
  return { slope, intercept: my - slope * mx };
}

interface PointDatum {
  value: [number, number];
  name: string;
}

export function scatterOption(data: TabularData, opts: ScatterOpts): EChartsOption {
  const xCol = requireColumn(data, opts.x);
  const yCol = requireColumn(data, opts.y);
  const labelKey = opts.label === undefined ? null : requireColumn(data, opts.label).key;
  const byKey = opts.seriesBy === undefined ? null : requireColumn(data, opts.seriesBy).key;

  const points = data.rows.flatMap((row) => {
    const x = numeric(row[xCol.key]);
    const y = numeric(row[yCol.key]);
    if (x === null || y === null) return [];
    const datum: PointDatum = {
      value: [x, y],
      name: labelKey === null ? '' : cellLabel(row[labelKey]),
    };
    return [{ datum, group: byKey === null ? yCol.label : cellLabel(row[byKey]) }];
  });
  const groups = distinct(points.map((p) => p.group));
  const series: (ScatterSeriesOption | LineSeriesOption)[] = groups.map((group) => ({
    type: 'scatter',
    name: group,
    symbolSize: 8,
    data: points.filter((p) => p.group === group).map((p) => p.datum),
  }));

  const fit = opts.fit ? linearFit(points.map((p) => p.datum.value)) : null;
  if (fit) {
    const xs = points.map((p) => p.datum.value[0]);
    const lo = Math.min(...xs);
    const hi = Math.max(...xs);
    series.push({
      type: 'line',
      name: 'Fit',
      symbol: 'none',
      lineStyle: { color: chartPalette[2], type: 'dashed' },
      tooltip: { show: false },
      data: [
        [lo, fit.intercept + fit.slope * lo],
        [hi, fit.intercept + fit.slope * hi],
      ],
    });
  }

  const xName = opts.xName ?? xCol.label;
  const yName = opts.yName ?? yCol.label;
  return {
    grid: { ...GRID },
    legend: legendFor(series.length),
    tooltip: {
      trigger: 'item',
      formatter: (params: unknown) => {
        const p = params as { name?: string; value?: [number, number]; seriesName?: string };
        const [x, y] = p.value ?? [NaN, NaN];
        const title = p.name ? `<strong>${escapeHtml(p.name)}</strong><br/>` : '';
        return `${title}${escapeHtml(xName)}: ${escapeHtml(x)}<br/>${escapeHtml(yName)}: ${escapeHtml(y)}`;
      },
    },
    xAxis: { type: 'value', name: xName, ...NAME_BELOW, scale: true },
    yAxis: { type: 'value', name: yName, scale: true },
    series,
  };
}
