import type { EChartsOption, LineSeriesOption } from 'echarts';
import { lineOption } from '../../components/charts/builders/line';
import type { TabularColumn, TabularData } from '../../components/charts/types';
import type { ClubTotals, Milestone, MilestoneMetric, NextMilestone } from './api';

export const METRIC_CHIPS: readonly { value: MilestoneMetric; label: string }[] = [
  { value: 'clays_thrown', label: 'Clays thrown' },
  { value: 'sundays_held', label: 'Sundays held' },
  { value: 'shooters', label: 'Shooters' },
  { value: 'rounds', label: 'Rounds' },
];

export const TOTALS_COLUMNS: TabularColumn[] = [
  { key: 'event_date', label: 'Sunday', type: 'date' },
  { key: 'clays_thrown', label: 'Clays thrown', type: 'int' },
  { key: 'sundays_held', label: 'Sundays held', type: 'int' },
  { key: 'shooters', label: 'Shooters', type: 'int' },
  { key: 'rounds', label: 'Rounds', type: 'int' },
];

/** The `mm` URL value as a metric; anything unknown is clays thrown. */
export function metricOf(raw: string | null): MilestoneMetric {
  return METRIC_CHIPS.find((c) => c.value === raw)?.value ?? 'clays_thrown';
}

/** The next milestone with the smallest share of its round number still to go (§3.5.3). */
export function nextUp(next: readonly NextMilestone[]): NextMilestone | null {
  return [...next].sort((a, b) => a.remaining / a.threshold - b.remaining / b.threshold)[0] ?? null;
}

/** Table rows of every metric, and a line of `metric` with a dot at each of its crossings. */
export function totalsModel(
  series: readonly ClubTotals[],
  crossings: readonly Milestone[],
  metric: MilestoneMetric,
): TabularData & { option: EChartsOption } {
  const rows = series.map((r) => ({ ...r }));
  const data: TabularData = { columns: TOTALS_COLUMNS, rows };
  const base = lineOption(data, { x: 'event_date', y: [metric] });
  const valueOn = new Map(series.map((r) => [r.event_date, r[metric]]));
  const [first, ...rest] = base.series as LineSeriesOption[];
  const marked: LineSeriesOption = {
    ...first,
    markPoint: {
      symbol: 'circle',
      symbolSize: 10,
      label: { show: true, position: 'top', formatter: '{b}' },
      data: crossings
        .filter((c) => c.metric === metric)
        .map((c) => ({
          name: c.threshold.toLocaleString('en-US'),
          coord: [c.event_date, valueOn.get(c.event_date) ?? c.threshold],
        })),
    },
  };
  return { ...data, option: { ...base, series: [marked, ...rest] } };
}
