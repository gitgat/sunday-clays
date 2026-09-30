import type { EChartsOption } from 'echarts';
import { colors } from '../../../theme/tokens';
import type { TabularData } from '../types';
import { numeric, requireColumn } from './common';

export interface CalendarOpts {
  /** ISO date column. */
  date: string;
  value: string;
  year: number;
  min?: number;
  max?: number;
  /** 'vertical' fits phones (weeks run down the screen). */
  orient?: 'horizontal' | 'vertical';
}

export function calendarOption(data: TabularData, opts: CalendarOpts): EChartsOption {
  const dateKey = requireColumn(data, opts.date).key;
  const valueCol = requireColumn(data, opts.value);
  const prefix = `${opts.year}-`;
  const cells = data.rows.flatMap((r) => {
    const d = r[dateKey];
    const v = numeric(r[valueCol.key]);
    return typeof d === 'string' && d.startsWith(prefix) && v !== null
      ? [[d, v] as [string, number]]
      : [];
  });
  const values = cells.map(([, v]) => v);
  const vertical = opts.orient === 'vertical';
  return {
    tooltip: { trigger: 'item' },
    visualMap: {
      type: 'continuous',
      min: opts.min ?? (values.length ? Math.min(...values) : 0),
      max: opts.max ?? (values.length ? Math.max(...values) : 1),
      orient: 'horizontal',
      left: 'center',
      bottom: 0,
      calculable: false,
    },
    calendar: {
      range: String(opts.year),
      orient: opts.orient ?? 'horizontal',
      top: vertical ? 32 : 24,
      left: vertical ? 40 : 32,
      right: 16,
      bottom: 48,
      cellSize: vertical ? [16, 'auto'] : ['auto', 16],
      yearLabel: { show: false },
      dayLabel: { firstDay: 0, color: colors.textMuted },
      monthLabel: { color: colors.textMuted },
      itemStyle: { color: colors.surface, borderColor: colors.elevated, borderWidth: 2 },
      splitLine: { show: false },
    },
    series: [{ type: 'heatmap', coordinateSystem: 'calendar', name: valueCol.label, data: cells }],
  };
}
