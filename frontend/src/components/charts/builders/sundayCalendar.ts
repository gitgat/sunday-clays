import type { EChartsOption } from 'echarts';
import { colors } from '../../../theme/tokens';
import type { TabularData } from '../types';
import { GRID, NAME_BELOW, escapeHtml, numeric, requireColumn } from './common';

export interface SundayCalendarOpts {
  /** ISO date column. */
  date: string;
  /** Best score that day; empty for a missed Sunday. */
  value: string;
  /** 'shot' (the shooter shot that Sunday) or 'missed' (the club held a shoot and they did not). */
  state: string;
  year: number;
  min?: number;
  max?: number;
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const NTH = ['1st', '2nd', '3rd', '4th', '5th'];

/** Which Sunday of its month a Sunday is: days 1-7 are the 1st, 8-14 the 2nd, and so on. */
export function sundayOfMonth(date: string): number {
  return Math.ceil(Number(date.slice(8, 10)) / 7);
}

/** A missed cell's value: below any score, so the colour scale leaves it uncoloured (outOfRange). */
const MISSED = -1;

/** ECharts gives a heatmap item back as `data`; the date rides on it for tooltips and clicks. */
interface CellItem {
  value: [number, number, number];
  date: string;
}

function cell(date: string, score: number): CellItem {
  return { value: [sundayOfMonth(date) - 1, Number(date.slice(5, 7)) - 1, score], date };
}

/**
 * A Sunday-only year: one row per month, one column per Sunday of the month (1st to 5th), never a
 * 7-day grid. A 'shot' cell is coloured by the best score that day; a 'missed' cell (a held Sunday
 * the shooter skipped) is an outlined empty square; a date with no held Sunday has no cell.
 */
export function sundayCalendarOption(data: TabularData, opts: SundayCalendarOpts): EChartsOption {
  const dateKey = requireColumn(data, opts.date).key;
  const valueKey = requireColumn(data, opts.value).key;
  const stateKey = requireColumn(data, opts.state).key;
  const prefix = `${opts.year}-`;
  const shot: CellItem[] = [];
  const missed: CellItem[] = [];
  for (const row of data.rows) {
    const date = row[dateKey];
    if (typeof date !== 'string' || !date.startsWith(prefix)) continue;
    const state = row[stateKey];
    const score = numeric(row[valueKey]);
    if (state === 'shot' && score !== null) shot.push(cell(date, score));
    else if (state === 'missed') missed.push(cell(date, MISSED));
  }
  const scores = shot.map((c) => c.value[2]);
  return {
    grid: { ...GRID, bottom: 56 },
    tooltip: {
      trigger: 'item',
      formatter: (params: unknown) => {
        const { seriesName, data: item } = params as { seriesName: string; data: CellItem };
        const head = `Sunday ${escapeHtml(item.date)}`;
        return seriesName === 'Shot'
          ? `${head}<br/>Best score: ${escapeHtml(item.value[2])}`
          : `${head}<br/>Held, not shot`;
      },
    },
    xAxis: {
      type: 'category',
      data: NTH,
      name: 'Sunday of the month',
      ...NAME_BELOW,
      splitArea: { show: true },
    },
    yAxis: { type: 'category', data: MONTHS, inverse: true, splitArea: { show: true } },
    visualMap: [
      {
        type: 'continuous',
        seriesIndex: 0,
        dimension: 2,
        min: opts.min ?? (scores.length ? Math.min(...scores) : 0),
        max: opts.max ?? (scores.length ? Math.max(...scores) : 1),
        orient: 'horizontal',
        left: 'center',
        bottom: 0,
        calculable: false,
      },
      // A missed cell takes no fill, only its outline (a heatmap must sit under a visualMap; only the
      // continuous one is registered).
      {
        type: 'continuous',
        seriesIndex: 1,
        dimension: 2,
        show: false,
        min: MISSED - 1,
        max: MISSED,
        inRange: { color: ['transparent', 'transparent'] },
      },
    ],
    series: [
      {
        type: 'heatmap',
        name: 'Shot',
        data: shot,
        itemStyle: { borderColor: colors.elevated, borderWidth: 2 },
        label: {
          show: true,
          formatter: (p: unknown) => String((p as { value: number[] }).value[2]),
        },
        emphasis: { itemStyle: { borderColor: colors.text, borderWidth: 1 } },
      },
      {
        type: 'heatmap',
        name: 'Missed',
        data: missed,
        itemStyle: { color: 'transparent', borderColor: colors.textMuted, borderWidth: 2 },
        emphasis: { itemStyle: { borderColor: colors.text, borderWidth: 2 } },
      },
    ],
  };
}

/** The date of a clicked shot cell, or null for a missed cell or anything else. */
export function shotDateOf(params: { seriesName?: string; data?: unknown }): string | null {
  if (params.seriesName !== 'Shot') return null;
  const date = (params.data as { date?: unknown } | undefined)?.date;
  return typeof date === 'string' ? date : null;
}
