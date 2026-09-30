import type { HeatmapSeriesOption } from 'echarts';
import { describe, expect, it } from 'vitest';
import type { TabularData } from '../types';
import { calendarOption } from './calendar';

const ATTENDED: TabularData = {
  columns: [
    { key: 'event_date', label: 'Event', type: 'date' },
    { key: 'score', label: 'Score', type: 'int' },
  ],
  rows: [
    { event_date: '2025-12-28', score: 30 },
    { event_date: '2026-09-06', score: 38 },
    { event_date: '2026-09-13', score: 41 },
    { event_date: '2026-09-20', score: null },
  ],
};

describe('calendarOption', () => {
  it('keeps only the requested year and scales colors to its values', () => {
    const o = calendarOption(ATTENDED, { date: 'event_date', value: 'score', year: 2026 });
    const [series] = o.series as [HeatmapSeriesOption];
    expect(series).toMatchObject({ coordinateSystem: 'calendar', name: 'Score' });
    expect(series.data).toEqual([
      ['2026-09-06', 38],
      ['2026-09-13', 41],
    ]);
    expect(o.calendar).toMatchObject({
      range: '2026',
      orient: 'horizontal',
      cellSize: ['auto', 16],
    });
    expect(o.visualMap).toMatchObject({ min: 38, max: 41 });
  });

  it('supports a vertical phone layout, fixed bounds and an empty year', () => {
    const o = calendarOption(ATTENDED, {
      date: 'event_date',
      value: 'score',
      year: 2024,
      orient: 'vertical',
      min: 0,
      max: 50,
    });
    expect(o.calendar).toMatchObject({ orient: 'vertical', cellSize: [16, 'auto'] });
    expect(o.visualMap).toMatchObject({ min: 0, max: 50 });
    const empty = calendarOption(ATTENDED, { date: 'event_date', value: 'score', year: 2024 });
    expect(empty.visualMap).toMatchObject({ min: 0, max: 1 });
  });
});
