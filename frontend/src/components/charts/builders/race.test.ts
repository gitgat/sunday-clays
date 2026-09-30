import type { BarSeriesOption, GraphicComponentOption, YAXisComponentOption } from 'echarts';
import { describe, expect, it } from 'vitest';
import { chartPalette } from '../../../theme/tokens';
import type { LeaderboardFrame } from '../types';
import { colorFor, raceOption } from './race';

const FRAME: LeaderboardFrame = {
  date: '2026-09-13',
  rows: [
    { id: 7, name: 'Able, Ann', value: 58, rank: 1 },
    { id: 9, name: 'Tarleton, Jo', value: 51, rank: 2 },
    { id: 12, name: 'Tarleton, Jo', value: 40, rank: 3 },
  ],
};

describe('colorFor', () => {
  it('gives the same id the same palette color every time', () => {
    expect(colorFor(7)).toBe(colorFor('7'));
    expect(chartPalette).toContain(colorFor(12345));
  });
});

describe('raceOption', () => {
  it('builds a realtime-sorted bar frame with stable colors and the frame date', () => {
    const o = raceOption(FRAME, { top: 2, valueName: 'Points', durationMs: 500 });
    const yAxis = o.yAxis as YAXisComponentOption & { data: string[]; max: number };
    expect(yAxis).toMatchObject({ inverse: true, max: 1 });
    expect(yAxis.data).toEqual(['Able, Ann', 'Tarleton, Jo #9', 'Tarleton, Jo #12']);
    const [bars] = o.series as [BarSeriesOption];
    expect(bars).toMatchObject({ realtimeSort: true, name: 'Points' });
    expect(bars.data).toEqual([
      { value: 58, itemStyle: { color: colorFor(7) } },
      { value: 51, itemStyle: { color: colorFor(9) } },
      { value: 40, itemStyle: { color: colorFor(12) } },
    ]);
    expect(o.animationDurationUpdate).toBe(500);
    const graphic = o.graphic as { elements: GraphicComponentOption[] };
    expect(graphic.elements[0]).toMatchObject({ style: { text: '2026-09-13' } });
  });

  it('defaults to a top 10 and copes with an empty frame', () => {
    const o = raceOption({ date: '2026-01-04', rows: [] });
    expect(o.yAxis).toMatchObject({ max: 0, data: [] });
    expect(o.animationDurationUpdate).toBe(800);
  });
});
