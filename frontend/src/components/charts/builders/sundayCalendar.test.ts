import type { HeatmapSeriesOption } from 'echarts';
import { describe, expect, it } from 'vitest';
import type { TabularData } from '../types';
import { shotDateOf, sundayCalendarOption, sundayOfMonth } from './sundayCalendar';

const DATA: TabularData = {
  columns: [
    { key: 'date', label: 'Sunday', type: 'date' },
    { key: 'score', label: 'Best score', type: 'int' },
    { key: 'state', label: 'State', type: 'string' },
  ],
  rows: [
    { date: '2025-12-28', score: 20, state: 'shot' },
    { date: '2026-01-04', score: 38, state: 'shot' },
    { date: '2026-01-11', score: null, state: 'missed' },
    { date: '2026-01-25', score: 44, state: 'shot' },
    { date: '2026-05-31', score: 41, state: 'shot' },
    { date: '2026-06-07', score: 30, state: 'nonsense' },
  ],
};
const OPTS = { date: 'date', value: 'score', state: 'state', year: 2026 } as const;

type Item = { value: [number, number, number]; date: string };
const series = (o: ReturnType<typeof sundayCalendarOption>) =>
  o.series as [HeatmapSeriesOption, HeatmapSeriesOption];

describe('sundayOfMonth', () => {
  it.each([
    ['2026-01-04', 1],
    ['2026-01-11', 2],
    ['2026-01-25', 4],
    ['2026-05-31', 5],
  ])('%s is Sunday number %s of its month', (date, n) => {
    expect(sundayOfMonth(date)).toBe(n);
  });
});

describe('sundayCalendarOption', () => {
  it('has months down the side and 1st to 5th Sunday across, not a 7-day grid', () => {
    const o = sundayCalendarOption(DATA, OPTS);
    const x = o.xAxis as { data: string[] };
    const y = o.yAxis as { data: string[]; inverse: boolean };
    expect(x.data).toEqual(['1st', '2nd', '3rd', '4th', '5th']);
    expect(y.data).toEqual([
      'Jan',
      'Feb',
      'Mar',
      'Apr',
      'May',
      'Jun',
      'Jul',
      'Aug',
      'Sep',
      'Oct',
      'Nov',
      'Dec',
    ]);
    expect(y.inverse).toBe(true);
    expect(o.calendar).toBeUndefined();
  });

  it('draws a shot cell per attended Sunday of the year, valued by the best score', () => {
    const [shot] = series(sundayCalendarOption(DATA, OPTS));
    expect(shot.name).toBe('Shot');
    expect(shot.data as Item[]).toEqual([
      { value: [0, 0, 38], date: '2026-01-04' },
      { value: [3, 0, 44], date: '2026-01-25' },
      { value: [4, 4, 41], date: '2026-05-31' },
    ]);
  });

  it('draws an outlined empty cell for a held Sunday the shooter missed', () => {
    const [, missed] = series(sundayCalendarOption(DATA, OPTS));
    expect(missed.name).toBe('Missed');
    expect(missed.data as Item[]).toEqual([{ value: [1, 0, -1], date: '2026-01-11' }]);
    expect(missed.itemStyle).toMatchObject({ color: 'transparent', borderWidth: 2 });
  });

  it('draws nothing for a date with no held Sunday, other years or unknown states', () => {
    const o = sundayCalendarOption(DATA, OPTS);
    const dates = series(o).flatMap((s) => (s.data as Item[]).map((d) => d.date));
    expect(dates).not.toContain('2025-12-28');
    expect(dates).not.toContain('2026-01-18');
    expect(dates).not.toContain('2026-06-07');
  });

  it('colours shot cells by score over the shot values, or fixed bounds', () => {
    const scale = (o: ReturnType<typeof sundayCalendarOption>) =>
      (o.visualMap as Record<string, unknown>[])[0];
    expect(scale(sundayCalendarOption(DATA, OPTS))).toMatchObject({
      type: 'continuous',
      min: 38,
      max: 44,
      seriesIndex: 0,
      dimension: 2,
    });
    expect(scale(sundayCalendarOption(DATA, { ...OPTS, min: 0, max: 50 }))).toMatchObject({
      min: 0,
      max: 50,
    });
    expect(scale(sundayCalendarOption(DATA, { ...OPTS, year: 2024 }))).toMatchObject({
      min: 0,
      max: 1,
    });
  });

  it('gives missed cells no fill, so only their outline shows', () => {
    const [, none] = sundayCalendarOption(DATA, OPTS).visualMap as Record<string, unknown>[];
    expect(none).toMatchObject({
      type: 'continuous',
      seriesIndex: 1,
      show: false,
      min: -2,
      max: -1,
      inRange: { color: ['transparent', 'transparent'] },
    });
  });

  it('prints the score in shot cells', () => {
    const [shot] = series(sundayCalendarOption(DATA, OPTS));
    const label = shot.label as { show: boolean; formatter: (p: { value: number[] }) => string };
    expect(label.show).toBe(true);
    expect(label.formatter({ value: [0, 0, 38] })).toBe('38');
  });

  it('escapes the date in the tooltip and says shot or missed in words', () => {
    const o = sundayCalendarOption(DATA, OPTS);
    const tip = (o.tooltip as { formatter: (p: unknown) => string }).formatter;
    expect(tip({ seriesName: 'Shot', data: { value: [0, 0, 38], date: '2026-01-04' } })).toBe(
      'Sunday 2026-01-04<br/>Best score: 38',
    );
    expect(tip({ seriesName: 'Missed', data: { value: [1, 0, -1], date: '2026-01-11' } })).toBe(
      'Sunday 2026-01-11<br/>Held, not shot',
    );
    expect(
      tip({ seriesName: 'Shot', data: { value: [0, 0, 1], date: '<img src=x onerror=alert(1)>' } }),
    ).not.toContain('<img');
  });

  it('ignores a shot row whose score is missing', () => {
    const data: TabularData = {
      ...DATA,
      rows: [{ date: '2026-02-01', score: null, state: 'shot' }],
    };
    const [shot] = series(sundayCalendarOption(data, OPTS));
    expect(shot.data).toEqual([]);
  });

  it('ignores rows without a text date', () => {
    const data: TabularData = { ...DATA, rows: [{ date: null, score: 30, state: 'shot' }] };
    expect(series(sundayCalendarOption(data, OPTS))[0].data).toEqual([]);
  });

  it('throws for a column it is not given', () => {
    expect(() => sundayCalendarOption(DATA, { ...OPTS, state: 'nope' })).toThrow('nope');
  });

  it('draws a special shoot the shooter came to as an accent-ringed cell off the score scale', () => {
    const data: TabularData = {
      ...DATA,
      rows: [...DATA.rows, { date: '2026-09-20', score: null, state: 'special' }],
    };
    const o = sundayCalendarOption(data, OPTS);
    const special = (o.series as HeatmapSeriesOption[])[2] as HeatmapSeriesOption;
    expect(special.name).toBe('Special');
    expect(special.data as Item[]).toEqual([{ value: [2, 8, -3], date: '2026-09-20' }]);
    expect(special.itemStyle).toMatchObject({ color: 'transparent', borderWidth: 3 });
    const label = special.label as { show: boolean; formatter: () => string };
    expect(label.show).toBe(true);
    expect(label.formatter()).toBe('★');
    // The score scale still spans the shot cells only.
    expect((o.visualMap as Record<string, unknown>[])[0]).toMatchObject({ min: 38, max: 44 });
    expect((o.visualMap as Record<string, unknown>[])[2]).toMatchObject({
      seriesIndex: 2,
      show: false,
      min: -4,
      max: -3,
    });
  });

  it('says special shoot in the tooltip', () => {
    const tip = (sundayCalendarOption(DATA, OPTS).tooltip as { formatter: (p: unknown) => string })
      .formatter;
    expect(tip({ seriesName: 'Special', data: { value: [2, 8, -3], date: '2026-09-20' } })).toBe(
      'Sunday 2026-09-20<br/>Special shoot, counts as a Sunday shot',
    );
  });
});

describe('shotDateOf', () => {
  it('returns the date of a clicked shot cell only', () => {
    expect(shotDateOf({ seriesName: 'Shot', data: { date: '2026-01-04' } })).toBe('2026-01-04');
    expect(shotDateOf({ seriesName: 'Missed', data: { date: '2026-01-11' } })).toBeNull();
    expect(shotDateOf({ seriesName: 'Shot', data: undefined })).toBeNull();
    expect(shotDateOf({ seriesName: 'Shot', data: { date: 5 } })).toBeNull();
  });

  it('opens a clicked special shoot too', () => {
    expect(shotDateOf({ seriesName: 'Special', data: { date: '2026-09-20' } })).toBe('2026-09-20');
  });
});
