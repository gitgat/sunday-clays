import type { EChartsOption } from 'echarts';
import { BarChart, HeatmapChart, LineChart } from 'echarts/charts';
import {
  GridComponent,
  LegendComponent,
  TooltipComponent,
  VisualMapComponent,
} from 'echarts/components';
import { use as registerECharts } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import { compareStations } from '../../lib/stationLabel';

// Registration is idempotent; it guarantees these series types whatever EChart.tsx imports.
registerECharts([
  BarChart,
  LineChart,
  HeatmapChart,
  GridComponent,
  LegendComponent,
  TooltipComponent,
  VisualMapComponent,
  CanvasRenderer,
]);

export const ACCENT = '#E8A77A';
export const INSUFFICIENT_COLOR = '#8A9A90';
export const LOSS_COLOR = '#DC2626';
const TEXT = '#FEFBF6';
const GRID = { left: 8, right: 16, top: 24, bottom: 8, containLabel: true };
const PERCENT_AXIS = {
  type: 'value' as const,
  min: 0,
  max: 100,
  axisLabel: { formatter: '{value}%' },
};

export function toPct(value: number | null): number | null {
  return value === null ? null : Math.round(value * 10_000) / 100;
}

/** Tooltip value formatters; they never build HTML from data strings (C10). */
export function percentFormatter(value: unknown): string {
  return typeof value === 'number' ? `${value.toFixed(2)}%` : '—';
}

export function pointsFormatter(value: unknown): string {
  return typeof value === 'number' ? `${value > 0 ? '+' : ''}${value.toFixed(2)} pts` : '—';
}

export interface StationBar {
  /** The station's label: "7", "7A". */
  station: string;
  hitPct: number | null;
  ciLow: number | null;
  ciHigh: number | null;
}

export function hitPctBarOption(bars: StationBar[]): EChartsOption {
  const ciMarker = {
    symbol: 'rect',
    symbolSize: [14, 2],
    lineStyle: { width: 0 },
    itemStyle: { color: TEXT },
  };
  return {
    grid: GRID,
    tooltip: { trigger: 'axis', valueFormatter: percentFormatter },
    xAxis: { type: 'category', data: bars.map((bar) => `St ${bar.station}`) },
    yAxis: PERCENT_AXIS,
    series: [
      {
        type: 'bar',
        name: 'Hit %',
        data: bars.map((bar) => toPct(bar.hitPct)),
        itemStyle: { color: ACCENT },
      },
      {
        type: 'line',
        name: 'Likely range low',
        data: bars.map((bar) => toPct(bar.ciLow)),
        ...ciMarker,
      },
      {
        type: 'line',
        name: 'Likely range high',
        data: bars.map((bar) => toPct(bar.ciHigh)),
        ...ciMarker,
      },
    ],
  };
}

export interface EventPoint {
  date: string;
  station: string;
  hitPct: number;
}

export function difficultyLineOption(points: EventPoint[]): EChartsOption {
  const stations = [...new Set(points.map((p) => p.station))].sort(compareStations);
  return {
    grid: { ...GRID, bottom: 40 },
    legend: { type: 'scroll', bottom: 0 },
    tooltip: { trigger: 'axis', valueFormatter: percentFormatter },
    xAxis: { type: 'time' },
    yAxis: PERCENT_AXIS,
    series: stations.map((station) => ({
      type: 'line' as const,
      name: `St ${station}`,
      showSymbol: true,
      data: points.filter((p) => p.station === station).map((p) => [p.date, toPct(p.hitPct)]),
    })),
  };
}

export interface MatrixCell {
  shooter: string;
  station: string;
  hitPct: number;
  nRounds: number;
}

/** A shooter needs this many rounds at a station to get a square (Leaders use the same 3). */
export const HEATMAP_MIN_ROUNDS = 3;
/** Fixed colour scale for every heatmap: red at or below this hit %, peach at 100%. */
export const HEATMAP_FLOOR = 50;

function escapeHtml(text: string): string {
  return text
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

export function heatmapOption(allCells: MatrixCell[]): EChartsOption {
  const cells = allCells.filter((c) => c.nRounds >= HEATMAP_MIN_ROUNDS);
  const shooters = [...new Set(cells.map((c) => c.shooter))].sort((a, b) => a.localeCompare(b));
  const stations = [...new Set(cells.map((c) => c.station))].sort(compareStations);
  return {
    grid: { ...GRID, bottom: 56 },
    tooltip: {
      position: 'top',
      // Data strings are escaped: the tooltip renders HTML (C10).
      formatter: (params) => {
        const [x, y, hit, rounds] = (
          params as unknown as { value: [number, number, number, number] }
        ).value;
        return `${escapeHtml(shooters[y] ?? '')} · St ${stations[x] ?? ''}<br/>${percentFormatter(hit)} over ${rounds} rounds`;
      },
    },
    xAxis: { type: 'category', data: stations.map((s) => `St ${s}`), splitArea: { show: true } },
    yAxis: { type: 'category', data: shooters, splitArea: { show: true } },
    visualMap: {
      min: HEATMAP_FLOOR,
      max: 100,
      dimension: 2,
      orient: 'horizontal',
      left: 'center',
      bottom: 0,
      text: ['100%', `${HEATMAP_FLOOR}% or less`],
      inRange: { color: [LOSS_COLOR, ACCENT] },
      outOfRange: { color: [LOSS_COLOR] },
    },
    series: [
      {
        type: 'heatmap',
        name: 'Hit %',
        data: cells.map((c) => [
          stations.indexOf(c.station),
          shooters.indexOf(c.shooter),
          toPct(c.hitPct),
          c.nRounds,
        ]),
      },
    ],
  };
}

export interface EraBar {
  label: string;
  hitPct: number | null;
}

export function eraBarOption(bars: EraBar[]): EChartsOption {
  return {
    grid: GRID,
    tooltip: { trigger: 'axis', valueFormatter: percentFormatter },
    xAxis: { type: 'category', data: bars.map((bar) => bar.label) },
    yAxis: PERCENT_AXIS,
    series: [
      {
        type: 'bar',
        name: 'Hit %',
        data: bars.map((bar) => toPct(bar.hitPct)),
        itemStyle: { color: ACCENT },
      },
    ],
  };
}

export interface WindCell {
  band: string;
  hitPct: number;
  nEvents: number;
  sufficient: boolean;
}

function sundaysLabel(n: number): string {
  return `${n} ${n === 1 ? 'Sunday' : 'Sundays'}`;
}

/** The API's gust band ("<10", "10-20", "20+") with its unit. */
export function gustLabel(band: string): string {
  return `${band} mph gusts`;
}

export function windBarOption(cells: WindCell[]): EChartsOption {
  return {
    grid: GRID,
    tooltip: { trigger: 'axis', valueFormatter: percentFormatter },
    xAxis: { type: 'category', data: cells.map((cell) => gustLabel(cell.band)) },
    yAxis: PERCENT_AXIS,
    series: [
      {
        type: 'bar',
        name: 'Hit %',
        data: cells.map((cell) => ({
          value: toPct(cell.hitPct),
          itemStyle: {
            color: cell.sufficient ? ACCENT : INSUFFICIENT_COLOR,
            opacity: cell.sufficient ? 1 : 0.6,
          },
          label: {
            show: true,
            position: 'top' as const,
            formatter: cell.sufficient
              ? sundaysLabel(cell.nEvents)
              : `${sundaysLabel(cell.nEvents)} (too few)`,
          },
        })),
      },
    ],
  };
}

export interface DeltaBar {
  station: string;
  delta: number;
}

export function deltaBarOption(bars: DeltaBar[]): EChartsOption {
  return {
    grid: GRID,
    tooltip: { trigger: 'axis', valueFormatter: pointsFormatter },
    xAxis: { type: 'category', data: bars.map((bar) => `St ${bar.station}`) },
    yAxis: { type: 'value', axisLabel: { formatter: '{value} pts' } },
    series: [
      {
        type: 'bar',
        name: 'Versus the field',
        data: bars.map((bar) => ({
          value: Math.round(bar.delta * 10_000) / 100,
          itemStyle: { color: bar.delta < 0 ? LOSS_COLOR : ACCENT },
        })),
      },
    ],
  };
}
