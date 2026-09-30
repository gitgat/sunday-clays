import type { LineSeriesOption } from 'echarts';
import { describe, expect, it } from 'vitest';
import type { LeaderboardFrame } from '../types';
import { bumpOption } from './bump';
import { colorFor } from './race';

const FRAMES: LeaderboardFrame[] = [
  {
    date: '2026-09-06',
    rows: [
      { id: 1, name: 'Able', value: 10, rank: 1 },
      { id: 2, name: 'Baker', value: 8, rank: 2 },
      { id: 3, name: 'Slocum', value: 6, rank: 3 },
    ],
  },
  {
    date: '2026-09-13',
    rows: [
      { id: 2, name: 'Baker', value: 18, rank: 1 },
      { id: 1, name: 'Able', value: 16, rank: 2 },
    ],
  },
];

describe('bumpOption', () => {
  it('draws one rank line per shooter in the top N, with gaps when out of it', () => {
    const o = bumpOption(FRAMES, { top: 2 });
    const series = o.series as LineSeriesOption[];
    expect(series.map((s) => [s.name, s.data])).toEqual([
      ['Able', [1, 2]],
      ['Baker', [2, 1]],
    ]);
    expect(series[0]).toMatchObject({
      itemStyle: { color: colorFor('1') },
      endLabel: { show: true },
    });
    expect(o.xAxis).toMatchObject({ data: ['2026-09-06', '2026-09-13'] });
    expect(o.yAxis).toMatchObject({ inverse: true, min: 1, max: 2 });
    // 'start' of the inverted rank axis is its top (rank 1), clear of the date labels.
    expect(o.yAxis).toMatchObject({ name: 'Rank', nameLocation: 'start' });
  });

  it('prints end labels as plain text, so template tokens in a name are not substituted', () => {
    const o = bumpOption([
      { date: '2026-09-06', rows: [{ id: 5, name: 'Tom {a} {@x}', value: 9, rank: 1 }] },
    ]);
    const [line] = o.series as [LineSeriesOption];
    expect(line.name).toBe('Tom {a} {@x}');
    const { formatter } = line.endLabel as { formatter: (p: { seriesName?: string }) => string };
    expect(typeof formatter).toBe('function');
    expect(formatter({ seriesName: 'Tom {a} {@x}' })).toBe('Tom {a} {@x}');
    expect(formatter({})).toBe('');
  });

  it('defaults to the top 10', () => {
    const o = bumpOption(FRAMES);
    expect((o.series as LineSeriesOption[]).map((s) => [s.name, s.data])).toEqual([
      ['Able', [1, 2]],
      ['Baker', [2, 1]],
      ['Slocum', [3, null]],
    ]);
    expect(o.yAxis).toMatchObject({ max: 10 });
  });
});
