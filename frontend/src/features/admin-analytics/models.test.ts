import { describe, expect, it } from 'vitest';
import { bumps, pageKinds, uptake, visitors } from './mocks';
import { bumpsModel, pageKindLabel, pageKindsModel, uptakeModel, visitorsModel } from './models';

type Series = { name: string; stack?: string; data: (number | null)[] };

describe('analytics chart models', () => {
  it('charts visitors per day or per week', () => {
    const day = visitorsModel(visitors, 'day');
    expect(day.columns.map((c) => c.label)).toEqual(['Day', 'Devices']);
    expect(day.rows[0]).toEqual({ day: '2026-09-27', devices: 14 });
    const week = visitorsModel(visitors, 'week');
    expect(week.columns.map((c) => c.label)).toEqual(['Week of', 'Devices']);
    expect(week.rows).toEqual([
      { week: '2026-09-21', devices: 18 },
      { week: '2026-09-28', devices: 7 },
    ]);
  });

  it('names page kinds in plain words and never says "event"', () => {
    expect(pageKindLabel('event')).toBe('One Sunday');
    expect(pageKindLabel('events-list')).toBe('Sundays list');
    expect(pageKindLabel('profile')).toBe('Shooter profiles');
    expect(pageKindLabel('brand-new-kind')).toBe('brand-new-kind');
    const model = pageKindsModel(pageKinds);
    expect(model.rows.map((r) => r.page)).toEqual([
      'Home',
      'Shooter profiles',
      'One Sunday',
      'Leaderboards',
    ]);
    expect(JSON.stringify(model.rows)).not.toMatch(/\bevents?\b/i);
  });

  it('charts bumps per day', () => {
    expect(bumpsModel(bumps).rows).toEqual(bumps.days.map((d) => ({ day: d.day, bumps: d.bumps })));
  });

  it('stacks the three answers per week', () => {
    const model = uptakeModel(uptake);
    const series = model.option.series as Series[];
    expect(series.map((s) => s.name)).toEqual(['Picked a name', 'Skipped', 'Not answered']);
    expect(series.every((s) => s.stack === 'total')).toBe(true);
    expect(series[0]?.data).toEqual([9, 4]);
  });
});
