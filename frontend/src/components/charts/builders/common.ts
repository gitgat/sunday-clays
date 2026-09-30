import { format } from 'echarts/core';
import { chartPalette } from '../../../theme/tokens';
import type { Cell, TabularColumn, TabularData } from '../types';

/** Every data-derived string in a string tooltip formatter goes through this (C10). */
export function escapeHtml(value: unknown): string {
  return format.encodeHTML(String(value));
}

export function requireColumn(data: TabularData, key: string): TabularColumn {
  const column = data.columns.find((c) => c.key === key);
  if (!column) throw new Error(`Unknown column "${key}"`);
  return column;
}

export function numeric(cell: Cell | undefined): number | null {
  return typeof cell === 'number' && Number.isFinite(cell) ? cell : null;
}

export function axisTypeFor(column: TabularColumn): 'time' | 'category' | 'value' {
  if (column.type === 'date') return 'time';
  return column.type === 'string' ? 'category' : 'value';
}

/** Distinct values in first-appearance order. */
export function distinct<T>(values: readonly T[]): T[] {
  return [...new Set(values)];
}

export function cellLabel(cell: Cell | undefined): string {
  return cell === null || cell === undefined ? '—' : String(cell);
}

/** Palette color for an index, wrapping in both directions; a non-integer gets the first color. */
export function paletteColor(index: number): string {
  const n = chartPalette.length;
  return chartPalette[((index % n) + n) % n] ?? chartPalette[0];
}

/** Keeps axis labels inside the grid: ECharts 6's form of the deprecated `containLabel: true`. */
export const CONTAIN_LABELS = { outerBoundsMode: 'same', outerBoundsContain: 'axisLabel' } as const;

/**
 * Keeps axis names inside the grid as well as axis labels: the plot shrinks until both fit, so a
 * name under an x axis (NAME_BELOW), at an axis end or above a y axis is never cut off at the
 * chart edge, and withZoom's slider room moves the name clear of the slider with the labels.
 */
export const CONTAIN_AXES = { outerBoundsMode: 'same', outerBoundsContain: 'all' } as const;

/**
 * Shared grid margins; frozen, so builders spread a copy that a chart may adjust on its own.
 * `top` is the legend and zoom toolbox row; a y-axis name sits below it, inside the grid.
 */
export const GRID = Object.freeze({ left: 8, right: 24, top: 32, bottom: 8, ...CONTAIN_AXES });

/** An x-axis name centred under the tick labels (GRID keeps it inside the chart). */
export const NAME_BELOW = { nameLocation: 'middle', nameGap: 28 } as const;

export function legendFor(seriesCount: number) {
  return seriesCount > 1 ? { type: 'scroll' as const, top: 0 } : { show: false };
}
