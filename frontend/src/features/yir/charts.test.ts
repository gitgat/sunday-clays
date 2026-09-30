import { describe, expect, it } from 'vitest';
import { clubMonthChart, shooterMonthChart } from './charts';
import { YIR_2025, YIR_GRIMSBY_2025 } from './mocks';

describe('year in review charts', () => {
  it('shows club rounds as bars and the average as a line on its own axis', () => {
    const { data, option } = clubMonthChart(YIR_2025.months);
    expect(data.rows.slice(0, 3)).toEqual([
      { month: 'Jan', events: 4, rounds: 119, avg: 35.09 },
      { month: 'Feb', events: 4, rounds: 117, avg: 37.89 },
      { month: 'Mar', events: 0, rounds: 0, avg: null },
    ]);
    expect(option.series).toEqual([
      expect.objectContaining({ type: 'bar', data: [119, 117, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0] }),
      expect.objectContaining({ type: 'line', yAxisIndex: 1 }),
    ]);
  });

  it("puts the shooter's monthly average next to the club's", () => {
    const { data, option } = shooterMonthChart(YIR_GRIMSBY_2025.months, 'Grimsby, Gregor');
    expect(data.columns.map((c) => c.label)).toEqual([
      'Month',
      'Rounds',
      'Grimsby, Gregor average',
      'Club average',
    ]);
    expect(data.rows[0]).toEqual({ month: 'Jan', rounds: 2, avg: 44.5, club: 35.09 });
    expect(option.series).toEqual([
      expect.objectContaining({ name: 'Grimsby, Gregor' }),
      expect.objectContaining({ name: 'Club' }),
    ]);
  });
});
