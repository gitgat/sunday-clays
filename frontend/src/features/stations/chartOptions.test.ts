import { describe, expect, it } from 'vitest';
import {
  ACCENT,
  deltaBarOption,
  difficultyLineOption,
  eraBarOption,
  gustLabel,
  heatmapOption,
  HEATMAP_FLOOR,
  HEATMAP_MIN_ROUNDS,
  hitPctBarOption,
  INSUFFICIENT_COLOR,
  LOSS_COLOR,
  percentFormatter,
  pointsFormatter,
  toPct,
  windBarOption,
} from './chartOptions';

describe('station chart options', () => {
  it('converts fractions to one-decimal percentages', () => {
    expect(toPct(0.501931)).toBe(50.19);
    expect(toPct(null)).toBeNull();
    expect(percentFormatter(50.19)).toBe('50.19%');
    expect(percentFormatter([1, 2])).toBe('—');
    expect(pointsFormatter(4.8)).toBe('+4.80 pts');
    expect(pointsFormatter(-2.5)).toBe('-2.50 pts');
    expect(pointsFormatter(null)).toBe('—');
  });

  it('plots hit % per station with likely-range markers', () => {
    const option = hitPctBarOption([
      { station: '9', hitPct: 0.501931, ciLow: 0.432572, ciHigh: 0.571215 },
    ]);
    expect(option.xAxis).toMatchObject({ type: 'category', data: ['St 9'] });
    expect(option.series).toEqual([
      expect.objectContaining({ type: 'bar', data: [50.19] }),
      expect.objectContaining({ type: 'line', name: 'Likely range low', data: [43.26] }),
      expect.objectContaining({ type: 'line', name: 'Likely range high', data: [57.12] }),
    ]);
  });

  it('draws one difficulty line per station', () => {
    const option = difficultyLineOption([
      { date: '2026-09-06', station: '9', hitPct: 0.5119 },
      { date: '2026-09-13', station: '9', hitPct: 0.4835 },
      { date: '2026-09-06', station: '4', hitPct: 0.7143 },
    ]);
    expect(option.series).toEqual([
      expect.objectContaining({ type: 'line', name: 'St 4', data: [['2026-09-06', 71.43]] }),
      expect.objectContaining({
        type: 'line',
        name: 'St 9',
        data: [
          ['2026-09-06', 51.19],
          ['2026-09-13', 48.35],
        ],
      }),
    ]);
  });

  it('maps shooter × station cells onto a heatmap grid with a fixed colour scale', () => {
    const option = heatmapOption([
      { shooter: 'Yoder, Gavin', station: '4', hitPct: 0.5, nRounds: 3 },
      { shooter: 'Hadley, Ike', station: '9', hitPct: 0.857143, nRounds: 12 },
    ]);
    expect(option.yAxis).toMatchObject({ data: ['Hadley, Ike', 'Yoder, Gavin'] });
    expect(option.xAxis).toMatchObject({ data: ['St 4', 'St 9'] });
    expect(option.visualMap).toMatchObject({
      min: HEATMAP_FLOOR,
      max: 100,
      dimension: 2,
      inRange: { color: [LOSS_COLOR, ACCENT] },
      outOfRange: { color: [LOSS_COLOR] },
    });
    expect(option.series).toEqual([
      expect.objectContaining({
        type: 'heatmap',
        data: [
          [0, 1, 50, 3],
          [1, 0, 85.71, 12],
        ],
      }),
    ]);
  });

  it('leaves out squares with fewer than 3 rounds', () => {
    const option = heatmapOption([
      { shooter: 'Yoder, Gavin', station: '4', hitPct: 0.5, nRounds: 2 },
      { shooter: 'Hadley, Ike', station: '4', hitPct: 0.9, nRounds: 3 },
    ]);
    expect(HEATMAP_MIN_ROUNDS).toBe(3);
    expect(option.yAxis).toMatchObject({ data: ['Hadley, Ike'] });
    expect(option.series).toEqual([expect.objectContaining({ data: [[0, 0, 90, 3]] })]);
  });

  it('tooltips name the shooter and the rounds, escaping the name', () => {
    const option = heatmapOption([
      { shooter: '<b>"O\'Neil" & Co</b>', station: '4', hitPct: 0.5, nRounds: 5 },
    ]);
    const { formatter } = option.tooltip as { formatter: (p: unknown) => string };
    expect(formatter({ value: [0, 0, 50, 5] })).toBe(
      '&lt;b&gt;&quot;O&#39;Neil&quot; &amp; Co&lt;/b&gt; · St 4<br/>50.00% over 5 rounds',
    );
    expect(formatter({ value: [9, 9, 50, 5] })).toBe(' · St <br/>50.00% over 5 rounds');
  });

  it('plots one bar per era', () => {
    const option = eraBarOption([
      { label: 'Original setup', hitPct: 0.5119 },
      { label: 'Since 2026-09-10', hitPct: null },
    ]);
    expect(option.series).toEqual([expect.objectContaining({ type: 'bar', data: [51.19, null] })]);
  });

  it('greys out insufficient wind cells and labels every cell with its Sundays', () => {
    const option = windBarOption([
      { band: '<10', hitPct: 0.72, nEvents: 6, sufficient: true },
      { band: '20+', hitPct: 0.61, nEvents: 2, sufficient: false },
    ]);
    expect(option.xAxis).toMatchObject({ data: ['<10 mph gusts', '20+ mph gusts'] });
    expect(option.series).toEqual([
      expect.objectContaining({
        data: [
          expect.objectContaining({
            value: 72,
            itemStyle: { color: ACCENT, opacity: 1 },
            label: expect.objectContaining({ formatter: '6 Sundays' }),
          }),
          expect.objectContaining({
            value: 61,
            itemStyle: { color: INSUFFICIENT_COLOR, opacity: 0.6 },
            label: expect.objectContaining({ formatter: '2 Sundays (too few)' }),
          }),
        ],
      }),
    ]);
  });

  it('colours losses and gains differently', () => {
    const option = deltaBarOption([
      { station: '4', delta: 0.048 },
      { station: '9', delta: -0.025 },
    ]);
    expect(option.series).toEqual([
      expect.objectContaining({
        data: [
          { value: 4.8, itemStyle: { color: ACCENT } },
          { value: -2.5, itemStyle: { color: LOSS_COLOR } },
        ],
      }),
    ]);
  });

  it('labels one Sunday in the singular and adds the unit to a gust band', () => {
    const option = windBarOption([{ band: '10-20', hitPct: 0.5, nEvents: 1, sufficient: false }]);
    expect(option.series).toEqual([
      expect.objectContaining({
        data: [
          expect.objectContaining({
            label: expect.objectContaining({ formatter: '1 Sunday (too few)' }),
          }),
        ],
      }),
    ]);
    expect(gustLabel('10-20')).toBe('10-20 mph gusts');
  });

  it('sorts a lettered station after its number in every chart', () => {
    const line = difficultyLineOption([
      { date: '2026-09-06', station: '8', hitPct: 0.5 },
      { date: '2026-09-06', station: '7A', hitPct: 0.5 },
      { date: '2026-09-06', station: '10', hitPct: 0.5 },
      { date: '2026-09-13', station: '7', hitPct: 0.5 },
    ]);
    expect((line.series as { name: string }[]).map((x) => x.name)).toEqual([
      'St 7',
      'St 7A',
      'St 8',
      'St 10',
    ]);
    const grid = heatmapOption([
      { shooter: 'Hadley, Ike', station: '8', hitPct: 0.9, nRounds: 3 },
      { shooter: 'Hadley, Ike', station: '7A', hitPct: 0.8, nRounds: 3 },
      { shooter: 'Hadley, Ike', station: '7', hitPct: 0.7, nRounds: 3 },
    ]);
    expect(grid.xAxis).toMatchObject({ data: ['St 7', 'St 7A', 'St 8'] });
    const bars = hitPctBarOption([
      { station: '7', hitPct: 0.5, ciLow: 0.4, ciHigh: 0.6 },
      { station: '7A', hitPct: 0.5, ciLow: 0.4, ciHigh: 0.6 },
    ]);
    expect(bars.xAxis).toMatchObject({ data: ['St 7', 'St 7A'] });
    const deltas = deltaBarOption([{ station: '7A', delta: 0.05 }]);
    expect(deltas.xAxis).toMatchObject({ data: ['St 7A'] });
  });
});
