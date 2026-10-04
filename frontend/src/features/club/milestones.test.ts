import { describe, expect, it } from 'vitest';
import { clubMilestones } from './mocks';
import type { Milestone } from './api';
import { metricOf, nextUp, totalsModel } from './milestones';

describe('club milestone models', () => {
  it('picks the next milestone with the smallest share still to go', () => {
    expect(nextUp(clubMilestones.next)?.label).toBe('400,000 clays thrown');
    expect(nextUp([])).toBeNull();
  });

  it('builds a table of every metric and a line of the chosen one with marked crossings', () => {
    const model = totalsModel(clubMilestones.series, clubMilestones.milestones, 'clays_thrown');
    expect(model.columns.map((c) => c.label)).toEqual([
      'Sunday',
      'Clays thrown',
      'Sundays held',
      'Shooters',
      'Rounds',
    ]);
    expect(model.rows).toHaveLength(clubMilestones.series.length);
    const series = (model.option.series as { markPoint?: { data: unknown[] } }[])[0];
    const clayCrossings = clubMilestones.milestones.filter((m) => m.metric === 'clays_thrown');
    expect(series?.markPoint?.data).toHaveLength(clayCrossings.length);
  });

  it('puts a crossing whose Sunday is not in the series at its round number', () => {
    const lone = { ...clubMilestones.latest, event_date: '2030-01-06' } as Milestone;
    const model = totalsModel(clubMilestones.series, [lone], 'clays_thrown');
    const series = (model.option.series as { markPoint?: { data: { coord: unknown[] }[] } }[])[0];
    expect(series?.markPoint?.data[0]?.coord).toEqual(['2030-01-06', 350000]);
  });

  it('reads the chip value from the URL key, defaulting to clays thrown', () => {
    expect(metricOf('rounds')).toBe('rounds');
    expect(metricOf('nonsense')).toBe('clays_thrown');
  });
});
