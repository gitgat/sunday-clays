import { describe, expect, it } from 'vitest';
import type { WeatherEvent } from './api';
import { compassSector, filterEvents, summarize } from './conditions';
import { WEATHER_EVENTS } from './mocks';

const dates = (events: { event_date: string }[]) => events.map((e) => e.event_date);

describe('conditions explorer rules', () => {
  it('keeps events inside the temperature range, gust limit and rain choice', () => {
    const all = { temp: [20, 100] as [number, number], gustMax: 40, rain: 'any' as const };
    expect(dates(filterEvents(WEATHER_EVENTS, all))).toHaveLength(4);
    expect(dates(filterEvents(WEATHER_EVENTS, { ...all, temp: [58, 60] }))).toEqual([
      '2026-09-13',
      '2026-09-27',
    ]);
    expect(dates(filterEvents(WEATHER_EVENTS, { ...all, gustMax: 12 }))).toEqual([
      '2018-12-30',
      '2026-08-16',
      '2026-09-27',
    ]);
    expect(dates(filterEvents(WEATHER_EVENTS, { ...all, rain: 'wet' }))).toEqual(['2026-09-13']);
    expect(dates(filterEvents(WEATHER_EVENTS, { ...all, rain: 'dry' }))).toHaveLength(3);
  });

  it('treats the slider ends as open: outliers stay in at the default filter', () => {
    const outliers = [
      { ...(WEATHER_EVENTS[0] as WeatherEvent), temp_f: 12, gust_mph: 55 },
      { ...(WEATHER_EVENTS[1] as WeatherEvent), temp_f: 104, gust_mph: 5 },
    ];
    const all = { temp: [20, 100] as [number, number], gustMax: 40, rain: 'any' as const };
    expect(filterEvents(outliers, all)).toHaveLength(2);
    expect(filterEvents(outliers, { ...all, temp: [25, 95] })).toHaveLength(0);
    expect(filterEvents(outliers, { ...all, gustMax: 35 })).toHaveLength(1);
  });

  it('summarises scored events only', () => {
    // scored: medians 39, 34, 39; difficulties -1.5, 1.2, -0.5
    const summary = summarize(WEATHER_EVENTS);
    expect(summary.events).toBe(3);
    expect(summary.meanMedian).toBeCloseTo(37.333, 3);
    expect(summary.meanDifficulty).toBeCloseTo(-0.2667, 4);
    expect(summarize([])).toEqual({ events: 0, meanMedian: null, meanDifficulty: null });
  });

  it('maps wind directions to 8 compass sectors', () => {
    expect([0, 22, 23, 44, 180, 200, 270, 350, -90, 725].map(compassSector)).toEqual([
      'N',
      'N',
      'NE',
      'NE',
      'S',
      'S',
      'W',
      'N',
      'W',
      'N',
    ]);
  });
});
