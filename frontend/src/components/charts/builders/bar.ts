import type { BarSeriesOption, EChartsOption } from 'echarts';
import type { TabularData } from '../types';
import { GRID, NAME_BELOW, cellLabel, distinct, legendFor, numeric, requireColumn } from './common';

export interface BarOpts {
  /** Category column. */
  x: string;
  /** One series per y column. */
  y: string[];
  /** Long format: one series per distinct value of this column (uses y[0]). */
  seriesBy?: string;
  /** Categories on the y axis, first row at the top (long names, e.g. shooters). */
  horizontal?: boolean;
  stack?: boolean;
  yName?: string;
  /** Print values on the bars. */
  labels?: boolean;
}

export function barOption(data: TabularData, opts: BarOpts): EChartsOption {
  const xKey = requireColumn(data, opts.x).key;
  const yCols = opts.y.map((key) => requireColumn(data, key));
  const firstY = yCols[0];
  if (!firstY) throw new Error('barOption needs at least one y column');
  const rowLabels = data.rows.map((r) => cellLabel(r[xKey]));
  const common = {
    type: 'bar' as const,
    ...(opts.stack ? { stack: 'total' } : {}),
    label: {
      show: opts.labels ?? false,
      position: opts.horizontal ? ('right' as const) : ('top' as const),
    },
  };

  let categories: string[];
  let series: BarSeriesOption[];
  if (opts.seriesBy !== undefined) {
    // Long format: one category per distinct x, each series aligned to them.
    categories = distinct(rowLabels);
    const by = requireColumn(data, opts.seriesBy).key;
    series = distinct(data.rows.map((r) => cellLabel(r[by]))).map((group) => {
      const byCategory = new Map(
        data.rows
          .filter((r) => cellLabel(r[by]) === group)
          .map((r) => [cellLabel(r[xKey]), numeric(r[firstY.key])]),
      );
      return { ...common, name: group, data: categories.map((c) => byCategory.get(c) ?? null) };
    });
  } else {
    // Wide format: one category per row, so a repeated x (namesakes) keeps its own value.
    categories = rowLabels;
    series = yCols.map((col) => ({
      ...common,
      name: col.label,
      data: data.rows.map((r) => numeric(r[col.key])),
    }));
  }

  const categoryAxis = {
    type: 'category' as const,
    data: categories,
    inverse: opts.horizontal ?? false,
  };
  const valueAxis = {
    type: 'value' as const,
    name: opts.yName ?? firstY.label,
    // Along x (horizontal bars) the name goes under the axis, as on every x axis: at the axis
    // end it would take width from the bars on a phone.
    ...(opts.horizontal ? NAME_BELOW : {}),
  };
  return {
    grid: { ...GRID },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: legendFor(series.length),
    xAxis: opts.horizontal ? valueAxis : categoryAxis,
    yAxis: opts.horizontal ? categoryAxis : valueAxis,
    series,
  };
}
