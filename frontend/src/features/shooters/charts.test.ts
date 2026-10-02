import { describe, expect, it } from 'vitest';
import type { ClubDistributionGroup, RatingPoint, ShooterRound, SplitRow } from './api';
import {
  activeYears,
  attendanceModel,
  distributionModel,
  learningCurveModel,
  monthsBetween,
  monthsModel,
  pbRoundIds,
  ratingModel,
  finishesModel,
  splitsModel,
  toughDaysModel,
  trendLineByDate,
  trendModel,
} from './charts';
import { hadleyRounds } from './mocks';

type LineSeries = { name: string; data: unknown[]; markPoint?: { data: { coord: unknown[] }[] } };

// Every Plan 06 ShooterRoundOut field; only event_date, ordinal, score, adjusted and round_id matter here.
function round(over: Partial<ShooterRound>): ShooterRound {
  return {
    round_id: 1,
    event_date: '2026-01-04',
    ordinal: 1,
    score: 30,
    gauge_class: null,
    status: 'member',
    round_type: 'sporting',
    is_best_round: true,
    event_rank: 1,
    percentile: 0.5,
    field_median: null,
    adjusted: 0,
    expected: null,
    residual: null,
    mu_before: null,
    mu_after: null,
    condition: null,
    ...over,
  };
}

// Seven dates; 2026-02-08 has two equal rounds listed ordinal 2 first.
const history: ShooterRound[] = [
  round({ round_id: 1, event_date: '2026-01-04', score: 30, adjusted: -5 }),
  round({ round_id: 2, event_date: '2026-01-11', score: 32, adjusted: -3 }),
  round({ round_id: 3, event_date: '2026-01-18', score: 31, adjusted: -4 }),
  round({ round_id: 4, event_date: '2026-01-25', score: 33, adjusted: -2 }),
  round({ round_id: 5, event_date: '2026-02-01', score: 35, adjusted: 0 }),
  round({
    round_id: 6,
    event_date: '2026-02-08',
    ordinal: 2,
    score: 37,
    adjusted: 2,
    is_best_round: false,
  }),
  round({ round_id: 7, event_date: '2026-02-08', ordinal: 1, score: 37, adjusted: 2 }),
  round({ round_id: 8, event_date: '2026-02-15', score: 38, adjusted: null }),
];

describe('pbRoundIds', () => {
  it('marks a day-best above every earlier-dated round once 5 earlier rounds exist, one per day, lowest ordinal', () => {
    expect([...pbRoundIds(history)].sort()).toEqual([7, 8]);
  });
});

describe('trendModel', () => {
  it('orders rounds by date then ordinal, flags PBs and pins them on the score series', () => {
    const model = trendModel([...history].reverse());
    expect(model.rows.map((r) => [r.event_date, r.score, r.pb])).toEqual([
      ['2026-01-04', 30, ''],
      ['2026-01-11', 32, ''],
      ['2026-01-18', 31, ''],
      ['2026-01-25', 33, ''],
      ['2026-02-01', 35, ''],
      ['2026-02-08', 37, 'PB'],
      ['2026-02-08', 37, ''],
      ['2026-02-15', 38, 'PB'],
    ]);
    expect(model.rows[7]?.adjusted).toBeNull();
    const [score, adjusted] = model.option.series as LineSeries[];
    expect(score?.markPoint?.data.map((d) => d.coord)).toEqual([
      [5, 37],
      [7, 38],
    ]);
    expect(adjusted?.data).toEqual([-5, -3, -4, -2, 0, 2, 2, null]);
  });
});

describe('ratingModel', () => {
  // lo/hi are the server's mu ∓ 1.96·√var, hand-computed: ±3.92 for var 4, ±3.528 for var 3.24.
  const points: RatingPoint[] = [
    { event_date: '2026-09-06', mu: 35.3, var: 4, lo: 31.38, hi: 39.22 },
    { event_date: '2026-09-13', mu: 35.0, var: 4, lo: 31.08, hi: 38.92 },
    { event_date: '2026-09-27', mu: 35.4, var: 3.24, lo: 31.872, hi: 38.928 },
  ];

  it('draws the server band (lo..hi) rounded to one decimal and pins the peak rating', () => {
    const model = ratingModel(points);
    expect(model.rows).toEqual([
      { event_date: '2026-09-06', rating: 35.3, low: 31.4, high: 39.2 },
      { event_date: '2026-09-13', rating: 35, low: 31.1, high: 38.9 },
      { event_date: '2026-09-27', rating: 35.4, low: 31.9, high: 38.9 },
    ]);
    const [low, width, rating] = model.option.series as LineSeries[];
    expect(low?.data).toEqual([31.4, 31.1, 31.9]);
    expect(width?.data).toEqual([7.8, 7.8, 7]);
    expect(rating?.markPoint?.data[0]?.coord).toEqual(['2026-09-27', 35.4]);
  });

  it('has no peak pin without points', () => {
    const [, , rating] = ratingModel([]).option.series as LineSeries[];
    expect(rating?.markPoint).toBeUndefined();
  });
});

describe('distributionModel', () => {
  const counts = (entries: Record<number, number>) =>
    Array.from({ length: 51 }, (_, s) => entries[s] ?? 0);
  // Only `counts` feed the model; the other DistributionOut fields are set because they are required.
  const groups: ClubDistributionGroup[] = [
    {
      key: '2025',
      n: 4,
      mean: 40.75,
      median: 40.5,
      p10: 40,
      p25: 40,
      p75: 41.25,
      p90: 41.7,
      counts: counts({ 40: 2, 41: 1, 42: 1 }),
    },
    {
      key: '2026',
      n: 2,
      mean: 45.5,
      median: 45.5,
      p10: 41.9,
      p25: 43.25,
      p75: 47.75,
      p90: 49.1,
      counts: counts({ 41: 1, 50: 1 }),
    },
  ];

  it('compares the shooter score shares with the club shares from the lowest score seen up to 50', () => {
    const model = distributionModel(
      [round({ score: 40 }), round({ round_id: 2, score: 40 }), round({ round_id: 3, score: 42 })],
      groups,
    );
    expect(model.rows[0]).toEqual({ score: 40, you_pct: 66.7, club_pct: 33.3 });
    expect(model.rows[1]).toEqual({ score: 41, you_pct: 0, club_pct: 33.3 });
    expect(model.rows[2]).toEqual({ score: 42, you_pct: 33.3, club_pct: 16.7 });
    expect(model.rows.at(-1)).toEqual({ score: 50, you_pct: 0, club_pct: 16.7 });
    expect(model.rows).toHaveLength(11);
  });

  it('shows zero shares for a shooter with no rounds in the current filter', () => {
    expect(distributionModel([], groups).rows[0]).toEqual({
      score: 40,
      you_pct: 0,
      club_pct: 33.3,
    });
  });

  it('shows zero club shares when the club distribution is empty', () => {
    expect(distributionModel([round({ score: 45 })], []).rows).toEqual([
      { score: 45, you_pct: 100, club_pct: 0 },
      { score: 46, you_pct: 0, club_pct: 0 },
      { score: 47, you_pct: 0, club_pct: 0 },
      { score: 48, you_pct: 0, club_pct: 0 },
      { score: 49, you_pct: 0, club_pct: 0 },
      { score: 50, you_pct: 0, club_pct: 0 },
    ]);
  });

  it('is empty when nobody has a round', () => {
    expect(distributionModel([], []).rows).toEqual([]);
  });

  it('names the shared y axis for both series and keeps the legend clear of the toolbox', () => {
    const option = distributionModel([round({ score: 40 })], groups).option;
    expect((option.yAxis as { name: string }).name).toBe('Share of rounds (%)');
    expect(option.legend).toMatchObject({ left: 0, right: 110 });
  });
});

describe('learningCurveModel', () => {
  it('lists the shooter value and the club median per career event, keeping a missing club median', () => {
    const curve = [
      { k: 1, value: -4, club_median: -3, n_club: 180 },
      { k: 2, value: -2.5, club_median: null, n_club: 0 },
    ];
    expect(learningCurveModel(curve).rows).toEqual([
      { k: 1, you: -4, club: -3, club_n: 180 },
      { k: 2, you: -2.5, club: null, club_n: 0 },
    ]);
  });

  it('hides a club point backed by fewer than 3 shooters', () => {
    const curve = [
      { k: 30, value: 1, club_median: 4, n_club: 2 },
      { k: 29, value: 1, club_median: 4, n_club: 3 },
    ];
    expect(learningCurveModel(curve).rows.map((r) => r.club)).toEqual([null, 4]);
  });

  it('reports whether any club point was hidden for having too few shooters', () => {
    const hidden = [{ k: 30, value: 1, club_median: 4, n_club: 2 }];
    const shown = [{ k: 29, value: 1, club_median: 4, n_club: 3 }];
    const absent = [{ k: 28, value: 1, club_median: null, n_club: 0 }];
    expect(learningCurveModel(hidden).clubHidden).toBe(true);
    expect(learningCurveModel(shown).clubHidden).toBe(false);
    expect(learningCurveModel(absent).clubHidden).toBe(false);
  });
});

describe('learningCurveModel axis and legend', () => {
  it('names the shared y axis for both series and keeps the legend clear of the toolbox', () => {
    const option = learningCurveModel([{ k: 1, value: -4, club_median: -3, n_club: 180 }]).option;
    expect((option.yAxis as { name: string }).name).toBe('Vs middle score');
    expect(option.legend).toMatchObject({ left: 0, right: 110 });
  });
});

describe('splitsModel', () => {
  it('rounds averages to one decimal and keeps best and round counts for the table', () => {
    const splits: SplitRow[] = [
      {
        key: '2026',
        n_rounds: 33,
        n_events: 33,
        avg: 35.14,
        median: 35.5,
        best: 44,
        avg_adjusted: -1.1,
      },
      {
        key: 'unspecified',
        n_rounds: 267,
        n_events: 267,
        avg: 35.31,
        median: 36,
        best: 45,
        avg_adjusted: null,
      },
    ];
    expect(splitsModel(splits).rows).toEqual([
      { key: '2026', n_rounds: 33, avg: 35.1, median: 35.5, best: 44 },
      { key: 'unspecified', n_rounds: 267, avg: 35.3, median: 36, best: 45 },
    ]);
  });
});

describe('activeYears and attendanceModel', () => {
  const rounds = [
    round({ event_date: '2025-11-09', score: 40 }),
    round({ round_id: 2, event_date: '2025-11-09', ordinal: 2, score: 42 }),
    round({ round_id: 3, event_date: '2026-09-13', score: 34 }),
  ];

  it('lists the years with rounds, newest first', () => {
    expect(activeYears(rounds)).toEqual([2026, 2025]);
  });

  it('puts the best score of each attended Sunday of the chosen year on the calendar', () => {
    expect(attendanceModel(rounds, [], 2025).rows).toEqual([
      { date: '2025-11-09', state: 'shot', score: 42 },
    ]);
  });

  it('adds every held Sunday of the year the shooter did not shoot as missed, in date order', () => {
    const held = ['2025-01-05', '2025-11-02', '2025-11-09', '2025-11-16', '2026-09-06'];
    expect(attendanceModel(rounds, held, 2025).rows).toEqual([
      { date: '2025-01-05', state: 'missed', score: null },
      { date: '2025-11-02', state: 'missed', score: null },
      { date: '2025-11-09', state: 'shot', score: 42 },
      { date: '2025-11-16', state: 'missed', score: null },
    ]);
  });

  it('never calls a Sunday in another year missed', () => {
    const rows = attendanceModel(rounds, ['2024-12-29', '2026-09-06'], 2025).rows;
    expect(rows.map((r) => r.date)).toEqual(['2025-11-09']);
  });

  it('lists Sunday, state and best score, and draws a Sunday grid', () => {
    const m = attendanceModel(rounds, [], 2025);
    expect(m.columns.map((c) => c.label)).toEqual(['Sunday', 'State', 'Best score']);
    expect((m.option.xAxis as { data: string[] }).data).toEqual([
      '1st',
      '2nd',
      '3rd',
      '4th',
      '5th',
    ]);
    expect(m.option.calendar).toBeUndefined();
  });

  it('is empty for a year with no rounds and no held Sundays', () => {
    expect(attendanceModel([], [], 2025).rows).toEqual([]);
  });
});

describe('trend lines (Plan 12)', () => {
  const round = (event_date: string, score: number, ordinal = 1) =>
    ({
      ...history[0],
      round_id: Number(event_date.replaceAll('-', '')) + ordinal,
      event_date,
      score,
      ordinal,
    }) as (typeof history)[number];
  const rounds = [
    round('2026-01-04', 30),
    round('2026-01-11', 40),
    round('2026-01-11', 20, 2),
    round('2026-01-18', 35),
  ];

  it('works out the average so far over earlier rounds and the running personal best', () => {
    expect([...trendLineByDate(rounds, 'so_far')]).toEqual([
      ['2026-01-04', null],
      ['2026-01-11', 30],
      ['2026-01-18', 30],
    ]);
    expect([...trendLineByDate(rounds, 'pb').values()]).toEqual([30, 40, 40]);
  });

  it('needs 10 Sundays before the 10-Sunday average, taking each Sunday best round', () => {
    const many = Array.from({ length: 11 }, (_, i) =>
      round(`2026-02-${String(i + 1).padStart(2, '0')}`, 30 + i),
    );
    const values = [...trendLineByDate(many, 'roll10').values()];
    expect(values.slice(0, 9)).toEqual(Array(9).fill(null));
    expect(values[9]).toBe(34.5);
    expect(values[10]).toBe(35.5);
  });

  it('adds the chosen line as a series and a table column', () => {
    const model = trendModel(rounds, 'pb');
    expect(model.columns.map((c) => c.label)).toContain('Personal best');
    expect((model.option.series as { name: string }[]).map((s) => s.name)).toEqual([
      'Score',
      'Vs middle score',
      'Personal best',
    ]);
    expect(trendModel(rounds).columns.map((c) => c.key)).not.toContain('line');
  });
});

describe('finishesModel', () => {
  it('keeps each Sunday best-round place, oldest first', () => {
    const model = finishesModel([
      {
        ...history[0],
        event_date: '2026-02-01',
        is_best_round: true,
        event_rank: 2,
        percentile: 0.5,
      },
      {
        ...history[0],
        event_date: '2026-01-04',
        is_best_round: true,
        event_rank: 5,
        percentile: 0.2,
      },
      { ...history[0], event_date: '2026-01-04', is_best_round: false, event_rank: null },
      // A Sunday without full results still has a place, but no percentile: it is left out.
      {
        ...history[0],
        event_date: '2026-01-18',
        is_best_round: true,
        event_rank: 1,
        percentile: null,
      },
    ] as typeof history);
    expect(model.rows).toEqual([
      { event_date: '2026-01-04', place: 5 },
      { event_date: '2026-02-01', place: 2 },
    ]);
  });
});

describe('monthsBetween', () => {
  it('lists every month across a year end, both ends included', () => {
    expect(monthsBetween('2025-11', '2026-02')).toEqual([
      '2025-11',
      '2025-12',
      '2026-01',
      '2026-02',
    ]);
    expect(monthsBetween('2026-03', '2026-03')).toEqual(['2026-03']);
  });
});

describe('monthsModel', () => {
  const at = (event_date: string, round_id: number) => round({ event_date, round_id });

  it('counts Sundays (not rounds) per month, empty months included', () => {
    const rounds = [
      at('2025-11-02', 1),
      at('2025-11-02', 2), // a second round the same Sunday
      at('2025-11-16', 3),
      at('2026-01-04', 4),
    ];
    expect(monthsModel(rounds).rows).toEqual([
      { month: '2025-11', sundays: 2 },
      { month: '2025-12', sundays: 0 },
      { month: '2026-01', sundays: 1 },
    ]);
  });

  it('no rounds: no bars', () => {
    expect(monthsModel([]).rows).toEqual([]);
  });
});

describe('toughDaysModel', () => {
  it('joins best rounds to how each day played, by date', () => {
    const rounds = [
      round({ round_id: 1, event_date: '2026-08-16', adjusted: 2.04, is_best_round: true }),
      round({ round_id: 2, event_date: '2026-08-16', adjusted: -4, is_best_round: false }),
      round({ round_id: 3, event_date: '2026-08-23', adjusted: null, is_best_round: true }),
      round({ round_id: 4, event_date: '2026-08-30', adjusted: 1, is_best_round: true }),
    ];
    const difficulty = [
      { event: '2026-08-16', value: 1.26 },
      { event: '2026-08-23', value: 0.3 },
      { event: 'not a date row', value: null },
    ];
    const model = toughDaysModel(rounds, difficulty);
    expect(model.rows).toEqual([{ event_date: '2026-08-16', difficulty: 1.3, adjusted: 2 }]);
    expect(model.option.series).toBeDefined();
  });

  it('lists the Sundays oldest first', () => {
    const rounds = [
      round({ round_id: 1, event_date: '2026-08-23', adjusted: 1 }),
      round({ round_id: 2, event_date: '2026-08-16', adjusted: 2 }),
    ];
    const difficulty = [
      { event: '2026-08-23', value: 0 },
      { event: '2026-08-16', value: 1 },
    ];
    expect(toughDaysModel(rounds, difficulty).rows.map((r) => r.event_date)).toEqual([
      '2026-08-16',
      '2026-08-23',
    ]);
  });
});

describe('special shoots in the attendance views (Plan 17)', () => {
  const held = ['2026-09-06', '2026-09-13', '2026-09-27'];

  it('marks a special shoot as special, never missed, once however many rounds', () => {
    const m = attendanceModel(hadleyRounds, held, 2026, ['2026-09-20', '2026-09-20']);
    expect(m.rows.filter((r) => r.date === '2026-09-20')).toEqual([
      { date: '2026-09-20', state: 'special', score: null },
    ]);
    expect(m.rows.map((r) => r.date)).toEqual([...m.rows.map((r) => r.date)].sort());
  });

  it('never calls a held date missed when the shooter came to a special shoot on it', () => {
    const m = attendanceModel([], ['2026-09-20'], 2026, ['2026-09-20']);
    expect(m.rows).toEqual([{ date: '2026-09-20', state: 'special', score: null }]);
  });

  it('leaves out a special shoot of another year', () => {
    expect(attendanceModel([], [], 2025, ['2026-09-20']).rows).toEqual([]);
  });

  it('counts a special shoot as a year shot and a Sunday shot that month', () => {
    expect(activeYears([], ['2024-06-16'])).toEqual([2024]);
    expect(activeYears(hadleyRounds, ['2024-06-16'])).toEqual([2026, 2024]);
    const months = monthsModel(hadleyRounds, ['2026-09-20']);
    expect(months.rows.find((r) => r.month === '2026-09')).toEqual({
      month: '2026-09',
      sundays: 4,
    });
    expect(monthsModel([], ['2026-09-20']).rows).toEqual([{ month: '2026-09', sundays: 1 }]);
  });
});
