import type { EChartsOption } from 'echarts';
import { colors } from '../../../theme/tokens';
import type { LeaderboardFrame } from '../types';
import { CONTAIN_LABELS, paletteColor } from './common';

export interface RaceOpts {
  /** Bars visible at once. */
  top?: number;
  valueName?: string;
  /** Transition time between frames, ms. */
  durationMs?: number;
}

/** A stable palette color per shooter so bars keep their color from frame to frame. */
export function colorFor(id: number | string): string {
  const text = String(id);
  let hash = 0;
  for (let i = 0; i < text.length; i += 1) hash = (hash * 31 + text.charCodeAt(i)) >>> 0;
  return paletteColor(hash);
}

/** Names repeated within one frame get their id appended so categories stay unique. */
function uniqueNames(rows: LeaderboardFrame['rows']): string[] {
  const seen = new Set<string>();
  const repeated = new Set<string>();
  for (const r of rows) (seen.has(r.name) ? repeated : seen).add(r.name);
  return rows.map((r) => (repeated.has(r.name) ? `${r.name} #${r.id}` : r.name));
}

/** One frame of a bar-chart race; feed successive frames to the same EChart to animate. */
export function raceOption(frame: LeaderboardFrame, opts: RaceOpts = {}): EChartsOption {
  const top = opts.top ?? 10;
  const duration = opts.durationMs ?? 800;
  const names = uniqueNames(frame.rows);
  return {
    grid: { left: 8, right: 56, top: 16, bottom: 32, ...CONTAIN_LABELS },
    xAxis: { type: 'value', max: 'dataMax', name: opts.valueName ?? '' },
    yAxis: {
      type: 'category',
      inverse: true,
      max: Math.max(0, Math.min(top, frame.rows.length) - 1),
      data: names,
      animationDuration: 300,
      animationDurationUpdate: 300,
    },
    series: [
      {
        type: 'bar',
        realtimeSort: true,
        name: opts.valueName ?? 'Value',
        data: frame.rows.map((r) => ({ value: r.value, itemStyle: { color: colorFor(r.id) } })),
        label: { show: true, position: 'right', valueAnimation: true },
      },
    ],
    animationDuration: 0,
    animationDurationUpdate: duration,
    animationEasing: 'linear',
    animationEasingUpdate: 'linear',
    graphic: {
      elements: [
        {
          type: 'text',
          right: 16,
          bottom: 40,
          style: { text: frame.date, font: 'bold 28px Roboto, sans-serif', fill: colors.textMuted },
        },
      ],
    },
  };
}
