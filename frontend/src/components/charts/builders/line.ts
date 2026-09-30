import type { EChartsOption, LineSeriesOption, ScatterSeriesOption } from 'echarts';
import { chartPalette } from '../../../theme/tokens';
import type { TabularData } from '../types';
import {
  GRID,
  NAME_BELOW,
  axisTypeFor,
  cellLabel,
  distinct,
  legendFor,
  numeric,
  requireColumn,
} from './common';

export interface LineOpts {
  /** x column (date → time axis, string → category, number → value). */
  x: string;
  /** One series per y column, named by the column label. */
  y: string[];
  /** Long format: one series per distinct value of this column (uses y[0]). */
  seriesBy?: string;
  /** Shaded band between two columns, e.g. a rating ±1.96σ. */
  band?: { lower: string; upper: string; name?: string };
  /** Point markers at rows where `flag` is truthy (e.g. personal bests), placed on y[0]. */
  markers?: { flag: string; name: string };
  area?: boolean;
  smooth?: boolean;
  yName?: string;
  /** Fit the y axis to the data instead of starting at 0. */
  scaleY?: boolean;
}

export function lineOption(data: TabularData, opts: LineOpts): EChartsOption {
  const xCol = requireColumn(data, opts.x);
  const yCols = opts.y.map((key) => requireColumn(data, key));
  const firstY = yCols[0];
  if (!firstY) throw new Error('lineOption needs at least one y column');
  const xType = axisTypeFor(xCol);
  // ECharts reads a number on a category axis as a category index, so category x values are
  // always labels (as in barOption); time and value axes keep the raw cell.
  const xValue = (row: TabularData['rows'][number]): string | number =>
    xType === 'category' ? cellLabel(row[opts.x]) : (row[opts.x] ?? '');
  const point = (
    row: TabularData['rows'][number],
    key: string,
  ): [string | number, number | null] => [xValue(row), numeric(row[key])];
  const base = {
    type: 'line' as const,
    smooth: opts.smooth ?? false,
    showSymbol: data.rows.length <= 60,
  };
  const areaStyle = opts.area ? { opacity: 0.2 } : undefined;

  let series: (LineSeriesOption | ScatterSeriesOption)[];
  if (opts.seriesBy !== undefined) {
    const by = requireColumn(data, opts.seriesBy).key;
    series = distinct(data.rows.map((r) => r[by] ?? null)).map((group) => ({
      ...base,
      name: cellLabel(group),
      ...(areaStyle ? { areaStyle } : {}),
      data: data.rows.filter((r) => (r[by] ?? null) === group).map((r) => point(r, firstY.key)),
    }));
  } else {
    series = yCols.map((col) => ({
      ...base,
      name: col.label,
      ...(areaStyle ? { areaStyle } : {}),
      data: data.rows.map((r) => point(r, col.key)),
    }));
  }

  // The band's invisible lower edge; kept out of the legend by identity, not by name.
  let lowSeries: LineSeriesOption | undefined;
  if (opts.band) {
    const lower = requireColumn(data, opts.band.lower).key;
    const upper = requireColumn(data, opts.band.upper).key;
    const bandName = opts.band.name ?? 'Range';
    lowSeries = {
      type: 'line',
      name: `${bandName} (low)`,
      stack: 'band',
      symbol: 'none',
      lineStyle: { opacity: 0 },
      tooltip: { show: false },
      data: data.rows.map((r) => point(r, lower)),
    };
    series.unshift(lowSeries, {
      type: 'line',
      name: bandName,
      stack: 'band',
      symbol: 'none',
      lineStyle: { opacity: 0 },
      areaStyle: { color: chartPalette[0], opacity: 0.15 },
      tooltip: { show: false },
      data: data.rows.map((r) => {
        const lo = numeric(r[lower]);
        const hi = numeric(r[upper]);
        return [xValue(r), lo === null || hi === null ? null : hi - lo];
      }),
    });
  }

  if (opts.markers) {
    const flag = requireColumn(data, opts.markers.flag).key;
    series.push({
      type: 'scatter',
      name: opts.markers.name,
      symbolSize: 10,
      itemStyle: { color: chartPalette[3] },
      data: data.rows.filter((r) => Boolean(r[flag])).map((r) => point(r, firstY.key)),
    });
  }

  const named = series.filter((s) => s !== lowSeries);
  return {
    grid: { ...GRID },
    tooltip: { trigger: 'axis' },
    legend: { ...legendFor(named.length), data: named.map((s) => String(s.name)) },
    xAxis: {
      type: xType,
      // Without this, a category axis orders by first appearance across series, so a gap in
      // the first series misorders it; list every x in row order (the values the points use).
      ...(xType === 'category' ? { data: distinct(data.rows.map(xValue)) } : {}),
      name: xCol.label,
      ...NAME_BELOW,
    },
    yAxis: { type: 'value', name: opts.yName ?? firstY.label, scale: opts.scaleY ?? false },
    series,
  };
}
