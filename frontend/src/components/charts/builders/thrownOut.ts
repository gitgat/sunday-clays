import type { TabularColumn } from '../types';
import { escapeHtml } from './common';

export const THROWN_OUT_COLUMN: TabularColumn = {
  key: 'thrown_out',
  label: 'Thrown out',
  type: 'string',
};

export function thrownOutCell(excluded: boolean): 'yes' | '' {
  return excluded ? 'yes' : '';
}

export function hollowPoint<T>(
  value: T,
  excluded: boolean,
): T | { value: T; symbol: 'emptyCircle'; symbolSize: 8 } {
  return excluded ? { value, symbol: 'emptyCircle', symbolSize: 8 } : value;
}

/** Returns a copy of `option` with the named series' points hollow where `excluded[i]` is true. */
export function hollowSeries<O extends { series?: unknown }>(
  option: O,
  seriesNames: readonly string[],
  excluded: readonly boolean[],
): O {
  const series = Array.isArray(option.series) ? (option.series as Record<string, unknown>[]) : [];
  return {
    ...option,
    series: series.map((s) => {
      if (typeof s.name !== 'string' || !seriesNames.includes(s.name) || !Array.isArray(s.data))
        return s;
      return {
        ...s,
        data: s.data.map((d: unknown, i: number) => hollowPoint(d, excluded[i] === true)),
      };
    }),
  };
}

interface AxisParam {
  axisValue?: unknown;
  axisValueLabel?: unknown;
  marker?: unknown;
  seriesName?: unknown;
  value?: unknown;
}

function dateKey(v: unknown): string {
  return typeof v === 'number' ? new Date(v).toISOString().slice(0, 10) : String(v);
}

/** Axis-tooltip formatter that stars the header of a thrown-out date. */
export function thrownOutAxisTooltip(excludedDates: ReadonlySet<string>) {
  return (params: readonly AxisParam[]): string => {
    const first = params[0];
    if (!first) return '';
    const star = excludedDates.has(dateKey(first.axisValue)) ? ' *' : '';
    const lines = [`${escapeHtml(first.axisValueLabel)}${star}`];
    for (const p of params) {
      const v = Array.isArray(p.value) ? (p.value[p.value.length - 1] as unknown) : p.value;
      if (v === null || v === undefined) continue;
      lines.push(`${String(p.marker ?? '')}${escapeHtml(p.seriesName)}: ${escapeHtml(v)}`);
    }
    return lines.join('<br/>');
  };
}
