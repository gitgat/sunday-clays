import type { EChartsOption } from 'echarts';
import { BarChart, LineChart } from 'echarts/charts';
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components';
import { use as registerECharts } from 'echarts/core';
import type { TabularData } from '../../components/charts/types';
import type { YirClub, YirShooter } from './api';
import { monthName } from './format';

registerECharts([BarChart, LineChart, GridComponent, LegendComponent, TooltipComponent]);

const round2 = (value: number | null): number | null =>
  value === null ? null : Math.round(value * 100) / 100;

/** Club months: rounds as bars (left axis) and the average score as a line (right axis). */
export function clubMonthChart(months: YirClub['months']): {
  data: TabularData;
  option: EChartsOption;
} {
  const labels = months.map((m) => monthName(m.month));
  return {
    data: {
      columns: [
        { key: 'month', label: 'Month', type: 'string' },
        { key: 'events', label: 'Sundays', type: 'int' },
        { key: 'rounds', label: 'Rounds', type: 'int' },
        { key: 'avg', label: 'Average score', type: 'number' },
      ],
      rows: months.map((m) => ({
        month: monthName(m.month),
        events: m.events,
        rounds: m.rounds,
        avg: round2(m.avg_score),
      })),
    },
    option: {
      grid: { left: 8, right: 8, top: 40, bottom: 8, containLabel: true },
      legend: {},
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'category', data: labels },
      yAxis: [
        { type: 'value', name: 'Rounds' },
        { type: 'value', name: 'Average', scale: true },
      ],
      series: [
        { type: 'bar', name: 'Rounds', data: months.map((m) => m.rounds) },
        {
          type: 'line',
          name: 'Average score',
          yAxisIndex: 1,
          connectNulls: true,
          data: months.map((m) => round2(m.avg_score)),
        },
      ],
    },
  };
}

/** The shooter's monthly average against the club's. */
export function shooterMonthChart(
  months: YirShooter['months'],
  name: string,
): { data: TabularData; option: EChartsOption } {
  return {
    data: {
      columns: [
        { key: 'month', label: 'Month', type: 'string' },
        { key: 'rounds', label: 'Rounds', type: 'int' },
        { key: 'avg', label: `${name} average`, type: 'number' },
        { key: 'club', label: 'Club average', type: 'number' },
      ],
      rows: months.map((m) => ({
        month: monthName(m.month),
        rounds: m.rounds,
        avg: round2(m.avg_score),
        club: round2(m.club_avg_score),
      })),
    },
    option: {
      grid: { left: 8, right: 8, top: 40, bottom: 8, containLabel: true },
      legend: {},
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'category', data: months.map((m) => monthName(m.month)) },
      yAxis: { type: 'value', name: 'Average', scale: true },
      series: [
        { type: 'line', name, connectNulls: false, data: months.map((m) => round2(m.avg_score)) },
        {
          type: 'line',
          name: 'Club',
          connectNulls: true,
          data: months.map((m) => round2(m.club_avg_score)),
        },
      ],
    },
  };
}
