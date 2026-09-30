import type { EChartsOption } from 'echarts';
import { BarChart, LineChart, ScatterChart } from 'echarts/charts';
import {
  GridComponent,
  LegendComponent,
  PolarComponent,
  TooltipComponent,
} from 'echarts/components';
import { use as registerECharts } from 'echarts/core';
import { CONTAIN_AXES, CONTAIN_LABELS, NAME_BELOW } from '../../components/charts/builders/common';
import type { TabularData } from '../../components/charts/types';
import type {
  WeatherBand,
  WeatherEvent,
  WeatherModel,
  WeatherSensitivity,
  WeatherShooter,
  WeatherTurnout,
} from './api';
import { COMPASS, compassSector } from './conditions';
import {
  COVARIATE_LABELS,
  bandLabel,
  type Dimension,
  type ModelCovariate,
  type SensitivityCovariate,
} from './format';

registerECharts([
  BarChart,
  LineChart,
  ScatterChart,
  GridComponent,
  LegendComponent,
  PolarComponent,
  TooltipComponent,
]);

export interface ChartModel {
  data: TabularData;
  option: EChartsOption;
}

const round2 = (value: number): number => Math.round(value * 100) / 100;

/**
 * Event difficulty (published scale, positive = harder) against one weather covariate, with the
 * club model's partial-effect line: the other covariates held at their means.
 */
export function difficultyFitChart(
  events: WeatherEvent[],
  model: WeatherModel | null,
  covariate: ModelCovariate,
): ChartModel {
  const points = events.flatMap((e) =>
    e.difficulty === null ? [] : [{ date: e.event_date, x: e[covariate], y: e.difficulty }],
  );
  const data: TabularData = {
    columns: [
      { key: 'event_date', label: 'Event', type: 'date' },
      { key: 'x', label: COVARIATE_LABELS[covariate], type: 'number' },
      { key: 'difficulty', label: 'Difficulty', type: 'number' },
    ],
    rows: points.map((p) => ({ event_date: p.date, x: p.x, difficulty: round2(p.y) })),
  };
  const series: EChartsOption['series'] = [
    { type: 'scatter', name: 'Events', data: points.map((p) => [p.x, round2(p.y)]) },
  ];
  const term = model?.terms.find((t) => t.name === covariate);
  if (model && term && points.length > 0) {
    // Hold every other covariate at its mean; the intercept has no mean (a constant 1).
    const others = model.terms.reduce(
      (sum, t) => (t.name === covariate ? sum : sum + t.coef * (t.mean === null ? 1 : t.mean)),
      0,
    );
    const xs = points.map((p) => p.x);
    const ends = [Math.min(...xs), Math.max(...xs)];
    series.push({
      type: 'line',
      name: 'Club model',
      showSymbol: false,
      data: ends.map((x) => [x, round2(others + term.coef * x)]),
    });
  }
  return {
    data,
    option: {
      grid: { left: 8, right: 16, top: 32, bottom: 8, ...CONTAIN_LABELS },
      legend: {},
      tooltip: { trigger: 'item' },
      xAxis: { type: 'value', name: COVARIATE_LABELS[covariate], scale: true },
      yAxis: { type: 'value', name: 'Difficulty' },
      series,
    },
  };
}

/** Mean field median per wind direction (8 sectors); sectors without events stay empty. */
export function windRoseChart(events: WeatherEvent[]): ChartModel {
  const sums = new Map<string, { total: number; n: number }>();
  for (const e of events) {
    if (e.wind_dir_deg === null || e.median === null) continue;
    const sector = compassSector(e.wind_dir_deg);
    const acc = sums.get(sector) ?? { total: 0, n: 0 };
    sums.set(sector, { total: acc.total + e.median, n: acc.n + 1 });
  }
  const rows = COMPASS.map((sector) => {
    const acc = sums.get(sector);
    return {
      sector,
      events: acc?.n ?? 0,
      median: acc ? round2(acc.total / acc.n) : null,
    };
  });
  return {
    data: {
      columns: [
        { key: 'sector', label: 'Wind from', type: 'string' },
        { key: 'events', label: 'Events', type: 'int' },
        { key: 'median', label: 'Mean field median', type: 'number' },
      ],
      rows,
    },
    option: {
      tooltip: { trigger: 'item' },
      polar: {},
      angleAxis: { type: 'category', data: [...COMPASS], startAngle: 90 },
      radiusAxis: { type: 'value', min: 0, max: 50 },
      series: [
        {
          type: 'bar',
          name: 'Mean field median',
          coordinateSystem: 'polar',
          data: rows.map((r) => r.median),
        },
      ],
    },
  };
}

/** Mean score per weather band for one dimension (server order). */
export function bandScoreChart(bands: WeatherBand[], dimension: Dimension): ChartModel {
  const chosen = bands.filter((b) => b.dimension === dimension);
  return {
    data: {
      columns: [
        { key: 'band', label: 'Band', type: 'string' },
        { key: 'events', label: 'Events', type: 'int' },
        { key: 'rounds', label: 'Rounds', type: 'int' },
        { key: 'mean_score', label: 'Mean score', type: 'number' },
        { key: 'mean_difficulty', label: 'Mean difficulty', type: 'number' },
      ],
      rows: chosen.map((b) => ({
        band: bandLabel(dimension, b.band),
        events: b.n_events,
        rounds: b.n_rounds,
        mean_score: b.mean_score === null ? null : round2(b.mean_score),
        mean_difficulty: b.mean_difficulty === null ? null : round2(b.mean_difficulty),
      })),
    },
    option: {
      grid: { left: 8, right: 16, top: 16, bottom: 8, ...CONTAIN_LABELS },
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'category', data: chosen.map((b) => bandLabel(dimension, b.band)) },
      yAxis: { type: 'value', name: 'Mean score' },
      series: [
        {
          type: 'bar',
          name: 'Mean score',
          data: chosen.map((b) => (b.mean_score === null ? null : round2(b.mean_score))),
        },
      ],
    },
  };
}

/** Mean head count per weather band for one dimension. */
export function turnoutChart(turnout: WeatherTurnout[], dimension: Dimension): ChartModel {
  const chosen = turnout.filter((t) => t.dimension === dimension);
  return {
    data: {
      columns: [
        { key: 'band', label: 'Band', type: 'string' },
        { key: 'events', label: 'Events', type: 'int' },
        { key: 'mean', label: 'Mean head count', type: 'number' },
        { key: 'median', label: 'Median head count', type: 'number' },
      ],
      rows: chosen.map((t) => ({
        band: bandLabel(dimension, t.band),
        events: t.n_events,
        mean: round2(t.mean_head_count),
        median: t.median_head_count,
      })),
    },
    option: {
      grid: { left: 8, right: 16, top: 16, bottom: 8, ...CONTAIN_LABELS },
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'category', data: chosen.map((t) => bandLabel(dimension, t.band)) },
      yAxis: { type: 'value', name: 'Shooters' },
      series: [
        {
          type: 'bar',
          name: 'Mean head count',
          data: chosen.map((t) => round2(t.mean_head_count)),
        },
      ],
    },
  };
}

export const SENSITIVITY_CHART_ROWS = 12;

export interface SensitivityModel extends ChartModel {
  /**
   * True when there is nothing to draw: the club-wide spread (tau2) for this measure is zero, or
   * every shooter's estimate is zero. The page shows a note instead of bars.
   */
  flat: boolean;
}

/** The smallest tenth at or above `value`, at least 0.1: a tidy half-width for the x axis. */
const niceBound = (value: number): number => Math.max(0.1, Math.ceil(value * 10 - 1e-9) / 10);

/**
 * Shrunk per-unit effects for one covariate. The table lists every shooter with an estimate;
 * the bars show the `limit` (default 12) largest effects by size, most negative first, on an
 * axis symmetric about 0.
 */
export function sensitivityChart(
  shooters: WeatherShooter[],
  covariate: SensitivityCovariate,
  tau2: WeatherSensitivity['tau2'] = [],
  limit: number = SENSITIVITY_CHART_ROWS,
): SensitivityModel {
  const withEffect = shooters.flatMap((s) => {
    const term = s.terms.find((t) => t.covariate === covariate);
    return term && term.beta !== null
      ? [{ name: s.display_name, n: s.n_rounds, value: term.per_unit }]
      : [];
  });
  const sorted = [...withEffect].sort((a, b) => a.value - b.value || a.name.localeCompare(b.name));
  const biggest = [...withEffect]
    .sort((a, b) => Math.abs(b.value) - Math.abs(a.value) || a.name.localeCompare(b.name))
    .slice(0, limit)
    .sort((a, b) => a.value - b.value || a.name.localeCompare(b.name));
  const spread = tau2.find((t) => t.covariate === covariate)?.tau2;
  const flat =
    spread === 0 || (withEffect.length > 0 && withEffect.every((r) => round2(r.value) === 0));
  const bound = niceBound(Math.max(0, ...biggest.map((r) => Math.abs(r.value))));
  return {
    flat,
    data: {
      columns: [
        { key: 'shooter', label: 'Shooter', type: 'string' },
        { key: 'rounds', label: 'Rounds with weather', type: 'int' },
        { key: 'effect', label: 'Effect (targets)', type: 'number' },
      ],
      rows: sorted.map((r) => ({ shooter: r.name, rounds: r.n, effect: round2(r.value) })),
    },
    option: {
      grid: { left: 8, right: 16, top: 8, bottom: 8, ...CONTAIN_AXES },
      tooltip: { trigger: 'axis' },
      xAxis: {
        type: 'value',
        name: 'Targets gained or lost',
        ...NAME_BELOW,
        min: -bound,
        max: bound,
      },
      yAxis: {
        type: 'category',
        data: biggest.map((r) => r.name),
        axisLabel: { width: 96, overflow: 'truncate' },
      },
      series: [{ type: 'bar', name: 'Effect', data: biggest.map((r) => round2(r.value)) }],
    },
  };
}
