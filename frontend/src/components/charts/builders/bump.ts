import type { EChartsOption, LineSeriesOption } from 'echarts';
import type { LeaderboardFrame } from '../types';
import { GRID } from './common';
import { colorFor } from './race';

export interface BumpOpts {
  /** Ranks shown (1..top); lower ranks leave gaps in a line. */
  top?: number;
}

/** Rank-over-time lines, one per shooter who reached the top N in any frame. */
export function bumpOption(
  frames: readonly LeaderboardFrame[],
  opts: BumpOpts = {},
): EChartsOption {
  const top = opts.top ?? 10;
  const dates = frames.map((f) => f.date);
  const names = new Map<string, string>();
  for (const f of frames)
    for (const r of f.rows) if (r.rank <= top) names.set(String(r.id), r.name);
  const series: LineSeriesOption[] = [...names].map(([id, name]) => ({
    type: 'line',
    name,
    smooth: true,
    symbolSize: 8,
    connectNulls: false,
    itemStyle: { color: colorFor(id) },
    emphasis: { focus: 'series' },
    // A function: a string formatter is a template, so a name holding {a} or {@x} would be rewritten.
    endLabel: { show: true, formatter: (p) => p.seriesName ?? '' },
    data: frames.map((f) => {
      const row = f.rows.find((r) => String(r.id) === id);
      return row && row.rank <= top ? row.rank : null;
    }),
  }));
  return {
    grid: { ...GRID, right: 120 },
    tooltip: { trigger: 'item' },
    xAxis: { type: 'category', data: dates, boundaryGap: false },
    yAxis: {
      type: 'value',
      inverse: true,
      min: 1,
      max: top,
      interval: 1,
      name: 'Rank',
      // The rank axis runs top down: its 'start' (rank 1) is the top, clear of the date labels.
      nameLocation: 'start',
    },
    series,
  };
}
