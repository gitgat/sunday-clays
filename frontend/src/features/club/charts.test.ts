import { describe, expect, it } from 'vitest';
import type { ConversionYear, EventTrend, ParityYear, YearTrend } from './api';
import {
  attendanceModel,
  conversionModel,
  difficultyModel,
  distributionModel,
  distributionObservations,
  memberGuestModel,
  firstRoundsModel,
  newcomersModel,
  parityModel,
  retentionModel,
  scoreTrendModel,
  seasonalityModel,
  yearTrendsModel,
} from './charts';
import {
  clubAttendance,
  clubCohorts,
  clubFirstRounds,
  clubConversion,
  clubDistribution,
  clubParity,
  clubSummary,
  clubTrends,
} from './mocks';

describe('attendanceModel', () => {
  it('lists head count, score rows and shooters per event in date order', () => {
    const model = attendanceModel([...clubAttendance].reverse());
    expect(model.rows).toEqual([
      { event_date: '2018-12-30', head_count: 7, rounds: 0, shooters: 0 },
      { event_date: '2019-01-14', head_count: 9, rounds: 0, shooters: 0 },
      { event_date: '2026-08-30', head_count: 36, rounds: 36, shooters: 35 },
      { event_date: '2026-09-13', head_count: 13, rounds: 13, shooters: 13 },
      { event_date: '2026-09-27', head_count: 23, rounds: 23, shooters: 23 },
    ]);
    expect(model.columns.map((c) => c.label)).toEqual([
      'Date',
      'Head count',
      'Rounds scored',
      'Shooters with scores',
    ]);
  });
});

describe('yearTrendsModel', () => {
  it('rounds the mean head count and shows the year-to-date change as a percentage', () => {
    expect(yearTrendsModel(clubTrends.years).rows).toEqual([
      {
        year: '2020',
        events_held: 39,
        mean_head_count: 20.7,
        unique_shooters: 92,
        ytd_events: 26,
        ytd_events_yoy_pct: null,
      },
      {
        year: '2025',
        events_held: 48,
        mean_head_count: 25.9,
        unique_shooters: 139,
        ytd_events: 35,
        ytd_events_yoy_pct: 2.9,
      },
      {
        year: '2026',
        events_held: 36,
        mean_head_count: 26.9,
        unique_shooters: 129,
        ytd_events: 36,
        ytd_events_yoy_pct: 2.9,
      },
    ]);
  });

  it('keeps a year without head counts empty', () => {
    const year: YearTrend = {
      year: 2019,
      events_held: 0,
      mean_head_count: null,
      unique_shooters: 0,
      ytd_events: 0,
      ytd_rounds: 0,
      ytd_unique_shooters: 0,
      ytd_events_yoy: null,
    };
    expect(yearTrendsModel([year]).rows[0]?.mean_head_count).toBeNull();
  });
});

describe('seasonalityModel', () => {
  it('orders months January to December and rounds the means', () => {
    expect(seasonalityModel([...clubTrends.months].reverse()).rows).toEqual([
      { month: 'Jan', n_events: 28, mean_head_count: 23.5, mean_median: 36.3 },
      { month: 'Sep', n_events: 27, mean_head_count: 22, mean_median: 35.9 },
      { month: 'Dec', n_events: 24, mean_head_count: 21.4, mean_median: 35.5 },
    ]);
  });

  it('keeps a month without held events empty', () => {
    expect(
      seasonalityModel([{ month: 2, n_events: 0, mean_head_count: null, mean_median: null }]).rows,
    ).toEqual([{ month: 'Feb', n_events: 0, mean_head_count: null, mean_median: null }]);
  });
});

describe('score trend and difficulty', () => {
  it("uses the server's 8-event rolling means, rounded to one decimal, in date order", () => {
    expect(scoreTrendModel([...clubTrends.events].reverse()).rows).toEqual([
      {
        event_date: '2026-09-06',
        median: 36,
        median_rolling8: 38.1,
        top_score: 48,
        top_score_rolling8: 46.9,
      },
      {
        event_date: '2026-09-13',
        median: 34,
        median_rolling8: 37.4,
        top_score: 42,
        top_score_rolling8: 46.5,
      },
      {
        event_date: '2026-09-27',
        median: 39,
        median_rolling8: 37.3,
        top_score: 49,
        top_score_rolling8: 46.6,
      },
    ]);
  });

  it('shows difficulty and its rolling mean, keeping events without a difficulty empty', () => {
    const unrated: EventTrend = {
      event_date: '2020-01-05',
      top_score: 45,
      median: 34,
      difficulty: null,
      top_score_rolling8: 45,
      median_rolling8: 34,
      difficulty_rolling8: null,
    };
    expect(difficultyModel([...clubTrends.events, unrated]).rows).toEqual([
      { event_date: '2020-01-05', difficulty: null, difficulty_rolling8: null },
      { event_date: '2026-09-06', difficulty: 0.3, difficulty_rolling8: 0.4 },
      { event_date: '2026-09-13', difficulty: 2.1, difficulty_rolling8: 0.6 },
      { event_date: '2026-09-27', difficulty: -1.4, difficulty_rolling8: 0.3 },
    ]);
  });
});

describe('distribution', () => {
  it('expands the counts into one row per round, newest year first, for the ridgeline', () => {
    expect(distributionObservations(clubDistribution).rows).toEqual([
      { year: '2026', score: 41 },
      { year: '2026', score: 50 },
      { year: '2025', score: 40 },
      { year: '2025', score: 40 },
      { year: '2025', score: 41 },
      { year: '2025', score: 42 },
    ]);
  });

  it('names the spread columns Low end and High end, as the shooter pages do', () => {
    expect(distributionModel(clubDistribution).columns.map((c) => c.label)).toEqual([
      'Year',
      'Rounds',
      'Average',
      'Low end',
      'Lower middle',
      'Middle score',
      'Upper middle',
      'High end',
    ]);
  });

  it('tables the rounds, mean and quantiles per year', () => {
    expect(distributionModel(clubDistribution).rows).toEqual([
      { year: '2025', n: 4, mean: 40.8, p10: 40, p25: 40, median: 40.5, p75: 41.25, p90: 41.7 },
      {
        year: '2026',
        n: 2,
        mean: 45.5,
        p10: 41.9,
        p25: 43.25,
        median: 45.5,
        p75: 47.75,
        p90: 49.1,
      },
    ]);
  });
});

describe('cohort models', () => {
  const rows = [
    { year: '2024', n_new: 35, n_returned: 18, retained_1y_pct: 40, retained_2y_pct: 25.7 },
    { year: '2025', n_new: 57, n_returned: 24, retained_1y_pct: 35.1, retained_2y_pct: null },
    { year: '2026', n_new: 41, n_returned: 15, retained_1y_pct: null, retained_2y_pct: null },
  ];

  it('newcomers per year with 1- and 2-year retention read from the retention offsets', () => {
    expect(newcomersModel([...clubCohorts].reverse()).rows).toEqual(rows);
  });

  it('retention charts the same per-year rows', () => {
    expect(retentionModel(clubCohorts).rows).toEqual(rows);
  });
});

describe('membership, conversion and parity', () => {
  it('splits rounds by the status recorded on each round', () => {
    expect(memberGuestModel(clubSummary.status_by_year).rows).toEqual([
      {
        year: '2025',
        member_rounds: 1210,
        guest_rounds: 45,
        deceased_rounds: 12,
        unrecorded_rounds: 0,
      },
      {
        year: '2026',
        member_rounds: 915,
        guest_rounds: 54,
        deceased_rounds: 0,
        unrecorded_rounds: 0,
      },
    ]);
  });

  it('computes the conversion rate from new guests and conversions', () => {
    expect(conversionModel(clubConversion).rows).toEqual([
      { year: '2024', new_guests: 11, converted: 1, rate_pct: 9.1, median_days: 112 },
      { year: '2025', new_guests: 31, converted: 2, rate_pct: 6.5, median_days: 224 },
      { year: '2026', new_guests: 29, converted: 1, rate_pct: 3.4, median_days: 217 },
    ]);
  });

  it('has no conversion rate for a year without new guests', () => {
    const year: ConversionYear = {
      year: 2027,
      new_guests: 0,
      converted: 1,
      median_days_to_convert: 30,
    };
    expect(conversionModel([year]).rows[0]?.rate_pct).toBeNull();
  });

  it('shows parity shares as percentages and keeps missing shares empty', () => {
    const unrated: ParityYear = {
      year: 2020,
      n_events: 39,
      distinct_winners: 14,
      top3_share: null,
      favorite_win_rate: null,
    };
    expect(parityModel([unrated, ...clubParity]).rows).toEqual([
      {
        year: '2020',
        n_events: 39,
        distinct_winners: 14,
        top3_share_pct: null,
        favorite_win_pct: null,
      },
      {
        year: '2025',
        n_events: 48,
        distinct_winners: 23,
        top3_share_pct: 39,
        favorite_win_pct: 14.6,
      },
      {
        year: '2026',
        n_events: 36,
        distinct_winners: 18,
        top3_share_pct: 38.6,
        favorite_win_pct: 11.1,
      },
    ]);
  });
});

describe('firstRoundsModel', () => {
  it('bars from the lowest to the highest first-round score, shares of all first rounds', () => {
    const model = firstRoundsModel(clubFirstRounds);
    expect(model.rows[0]).toEqual({ score: '22', n: 2, share_pct: 10 });
    expect(model.rows.at(-1)).toEqual({ score: '45', n: 1, share_pct: 5 });
    expect(model.rows).toHaveLength(45 - 22 + 1);
    expect(model.rows.reduce((sum, r) => sum + Number(r.n), 0)).toBe(clubFirstRounds.n);
    expect(model.rows.find((r) => r.score === '34')).toEqual({ score: '34', n: 8, share_pct: 40 });
  });

  it('no first rounds: no bars', () => {
    expect(
      firstRoundsModel({ n: 0, median: null, counts: Array<number>(51).fill(0) }).rows,
    ).toEqual([]);
  });
});
