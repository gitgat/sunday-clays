import type { EChartsOption } from 'echarts';
import { BarChart, LineChart } from 'echarts/charts';
import { GridComponent, TooltipComponent } from 'echarts/components';
import { use as registerECharts } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';

// Registration is idempotent; it guarantees these series types whatever EChart.tsx imports.
registerECharts([BarChart, LineChart, GridComponent, TooltipComponent, CanvasRenderer]);

export interface RarityBar {
  label: string;
  rarityPct: number;
  color: string;
}

export interface CumulativePoint {
  date: string;
  total: number;
}

/** Tooltip value formatter; never builds HTML from data strings (C10). */
export function percentFormatter(value: unknown): string {
  return typeof value === 'number' ? `${value.toFixed(2)}%` : '—';
}

export function rarityBarOption(bars: RarityBar[]): EChartsOption {
  return {
    grid: { left: 8, right: 24, top: 8, bottom: 8, containLabel: true },
    tooltip: { trigger: 'axis', valueFormatter: percentFormatter },
    xAxis: { type: 'value', min: 0, max: 100, axisLabel: { formatter: '{value}%' } },
    yAxis: {
      type: 'category',
      inverse: true,
      data: bars.map((bar) => bar.label),
      axisLabel: { width: 130, overflow: 'truncate' },
    },
    series: [
      {
        type: 'bar',
        name: 'Rarity',
        data: bars.map((bar) => ({ value: bar.rarityPct, itemStyle: { color: bar.color } })),
      },
    ],
  };
}

export function cumulativeByDate(dates: readonly string[]): CumulativePoint[] {
  const counts = new Map<string, number>();
  for (const date of dates) counts.set(date, (counts.get(date) ?? 0) + 1);
  let total = 0;
  return [...counts.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([date, n]) => {
      total += n;
      return { date, total };
    });
}

export function cumulativeLineOption(points: CumulativePoint[], seriesName: string): EChartsOption {
  return {
    grid: { left: 8, right: 24, top: 16, bottom: 8, containLabel: true },
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'time' },
    yAxis: { type: 'value', minInterval: 1 },
    series: [
      {
        type: 'line',
        name: seriesName,
        step: 'end',
        showSymbol: false,
        data: points.map((point) => [point.date, point.total]),
      },
    ],
  };
}
