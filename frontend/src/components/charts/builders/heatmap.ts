import type { EChartsOption } from 'echarts';
import { colors } from '../../../theme/tokens';
import type { TabularData } from '../types';
import {
  GRID,
  NAME_BELOW,
  cellLabel,
  distinct,
  escapeHtml,
  numeric,
  requireColumn,
} from './common';

export interface HeatmapOpts {
  /** Column categories (e.g. station). */
  x: string;
  /** Row categories (e.g. shooter). */
  y: string;
  value: string;
  min?: number;
  max?: number;
  /** Print values in the cells. */
  labels?: boolean;
}

export function heatmapOption(data: TabularData, opts: HeatmapOpts): EChartsOption {
  const xCol = requireColumn(data, opts.x);
  const yCol = requireColumn(data, opts.y);
  const valueCol = requireColumn(data, opts.value);
  const xs = distinct(data.rows.map((r) => cellLabel(r[xCol.key])));
  const ys = distinct(data.rows.map((r) => cellLabel(r[yCol.key])));
  const cells = data.rows.flatMap((r): [number, number, number][] => {
    const v = numeric(r[valueCol.key]);
    return v === null
      ? []
      : [[xs.indexOf(cellLabel(r[xCol.key])), ys.indexOf(cellLabel(r[yCol.key])), v]];
  });
  const values = cells.map(([, , v]) => v);
  return {
    grid: { ...GRID, bottom: 48 },
    tooltip: {
      trigger: 'item',
      formatter: (params: unknown) => {
        const [xi, yi, v] = (params as { value: [number, number, number] }).value;
        return `${escapeHtml(ys[yi] ?? '')} · ${escapeHtml(xCol.label)} ${escapeHtml(xs[xi] ?? '')}<br/>${escapeHtml(valueCol.label)}: ${escapeHtml(v)}`;
      },
    },
    xAxis: {
      type: 'category',
      data: xs,
      name: xCol.label,
      ...NAME_BELOW,
      splitArea: { show: true },
    },
    yAxis: {
      type: 'category',
      data: ys,
      name: yCol.label,
      // The axis runs top down, so its 'start' is the top, where other charts name the y axis.
      nameLocation: 'start',
      inverse: true,
      splitArea: { show: true },
    },
    visualMap: {
      type: 'continuous',
      min: opts.min ?? (values.length ? Math.min(...values) : 0),
      max: opts.max ?? (values.length ? Math.max(...values) : 1),
      orient: 'horizontal',
      left: 'center',
      bottom: 0,
      calculable: false,
    },
    series: [
      {
        type: 'heatmap',
        name: valueCol.label,
        data: cells,
        label: { show: opts.labels ?? false },
        emphasis: { itemStyle: { borderColor: colors.text, borderWidth: 1 } },
      },
    ],
  };
}
