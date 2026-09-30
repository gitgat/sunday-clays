import type { Explainer } from '../../components/charts/types';
import type { LeaderboardMetric, LeaderboardPeriod } from './api';

const FILTERS_APPLY = 'The round-type and gauge filters apply.';

/** "How it's worked out" for each measure (checked against analytics/leaderboards.py and points.py). */
const METRIC_COMPUTED: Record<LeaderboardMetric, readonly string[]> = {
  avg_score: [
    'Add up every round’s score in the period and divide by the number of rounds. Second rounds count.',
    FILTERS_APPLY,
  ],
  avg_adjusted: [
    'For each round: score minus that Sunday’s middle score (every round shot that day, second rounds included, lined up low to high). Then average those differences.',
    `Only Sundays with complete results count. ${FILTERS_APPLY}`,
  ],
  best_score: [
    'The highest score among a shooter’s rounds in the period, second rounds included.',
    FILTERS_APPLY,
  ],
  wins: [
    'Each Sunday, everyone is ranked by their best round of the day. First place is a win, and a tie for first gives each shooter a win.',
    'Every Sunday with scores counts. The gauge filter keeps a win only if the winning round used that gauge.',
  ],
  podiums: [
    'Each Sunday, everyone is ranked by their best round of the day. Finishing 1st, 2nd or 3rd is a podium, so a win is also a podium. Tied shooters share a place.',
    'Every Sunday with scores counts. The gauge filter keeps a podium only if that round used the gauge.',
  ],
  events: [
    'The number of different Sundays with at least one round of theirs in the period. Two rounds on one Sunday count once.',
    FILTERS_APPLY,
  ],
  rounds: [
    'A count of the 50-target rounds shot in the period. Second rounds on the same Sunday count separately.',
    FILTERS_APPLY,
  ],
  rating_gain: [
    'Rating is our estimate of the score someone would post on a normal Sunday now, out of 50. Rating gain is how far it has climbed: their rating now minus their last rating before the period began. For All time: rating now minus their rating after their 10th round.',
    'Only shooters whose rating went up are listed. Needs 10 or more rounds before the period and 5 or more inside it (last 8 weeks: 3 or more inside; All time: 15 or more rounds in total). It ignores the round-type and gauge filters. The Members/Guests filter still applies.',
  ],
  season_points: [
    'Each Sunday, everyone is placed by their best round (ties share a place). 1st to 8th earn 10, 8, 6, 5, 4, 3, 2 and 1 points, and everyone who shot earns 1 more for turning up, so a win is worth 11.',
    'Points are added up over the period, and places are always against the whole field. All time gives career points.',
  ],
};

/** How the board's dates and thresholds are picked: the four API periods, or a start date (3M, 6M, Custom). */
export type BoardKind = LeaderboardPeriod | 'custom';

const PERIOD_COMPUTED: Record<BoardKind, string> = {
  season:
    'Period: the last 8 Sundays, which is the 56 days ending on the board’s date. It rolls forward and never restarts in January.',
  ytd: 'Period: January 1 of that year up to the board’s date. It starts again each January.',
  rolling_12: 'Period: the 364 days ending on the board’s date.',
  all_time: 'Period: every round up to the board’s date.',
  custom:
    'Period: from the start of your time window (3 months, 6 months or your own dates) up to the board’s date.',
};

/** Who qualifies for an average, by period (analytics/leaderboards.py: scaled_min_rounds, _AVERAGE_MIN_ROUNDS). */
const AVERAGE_QUALIFY: Partial<Record<BoardKind, string>> = {
  season:
    'To be listed you need as many rounds as 40% of the Sundays with scores in the period, rounded up and never more than 5.',
  ytd: 'To be listed you need as many rounds as 40% of the Sundays with scores in the period, rounded up and never more than 5.',
  rolling_12: 'To be listed you need 8 or more rounds in the period.',
  all_time: 'To be listed you need 15 or more rounds.',
};

const WINDOW_LINE =
  'The time window at the top picks the dates. Move “Board as of” to see the board on an earlier Sunday.';

/**
 * Lines that replace or add to a measure's copy when the board runs from a start date (checked against
 * analytics/leaderboards.py: custom_min_rounds, IMPROVED_MIN_BEFORE / IMPROVED_MIN_INSIDE, the
 * per-Sunday points in points.py).
 */
const CUSTOM_EXTRA: Partial<Record<LeaderboardMetric, readonly string[]>> = {
  avg_score: [
    'With your own start date you need at least as many rounds as 40% of the Sundays with scores in your dates (at most 5); on longer ranges that rises to 15% of them, never more than 15.',
  ],
  avg_adjusted: [
    'With your own start date you need at least as many rounds as 40% of the Sundays with scores in your dates (at most 5); on longer ranges that rises to 15% of them, never more than 15.',
  ],
};

const CUSTOM_REPLACE: Partial<Record<LeaderboardMetric, readonly string[]>> = {
  wins: [
    METRIC_COMPUTED.wins[0] as string,
    'Every Sunday with scores in your dates counts. The gauge filter keeps a win only if the winning round used that gauge.',
  ],
  podiums: [
    METRIC_COMPUTED.podiums[0] as string,
    'Every Sunday with scores in your dates counts. The gauge filter keeps a podium only if that round used the gauge.',
  ],
  rating_gain: [
    'Rating is our estimate of the score someone would post on a normal Sunday now, out of 50. Rating gain is their rating now minus their last rating before the start date.',
    'Only shooters whose rating went up are listed. Needs 10 or more rounds before the start date and 5 or more inside your dates. It ignores the round-type and gauge filters. The Members/Guests filter still applies.',
  ],
  season_points: [
    METRIC_COMPUTED.season_points[0] as string,
    'Points are added up over the Sundays in your dates; places are always against the whole field that day.',
  ],
};

/** Base copy, keyed by `urlKey` like every other feature's explainers. */
export const explainers: Record<string, Explainer> = {
  'lb-chart': {
    what: 'The top ten shooters in the standings table below, as bars, for the measure, period and filters you picked.',
    read: [
      'The longest bar is first place. Hover a bar, or open Table, to see the number.',
      'Bars start at zero, so close values (averages of 38 to 41, say) look nearly the same length. Read the numbers.',
      'Ties share a place, and a tie for tenth can be cut from the chart. Fullscreen, the table below and the CSV download list everyone.',
    ],
    computed: [
      'The first ten rows of the standings (every row in fullscreen and the CSV); bar length is that measure’s value for each shooter.',
    ],
    scope: 'windowed',
  },
  'lb-movers': {
    what: 'The shooters whose skill rating climbed the most over the time window, and by how many points.',
    read: [
      'Longer bars gained more rating points. Only climbers are shown, and this is a celebration of improvement, not a ranking of skill.',
      'A ringed bar is the shooter an insight points to. Fullscreen and the CSV download list everyone who gained.',
    ],
    computed: [
      'Rating is our estimate of the score someone would post on a normal Sunday now, out of 50. Rating points gained = their rating now minus their last rating before the window began (for All time: their rating after their 10th round).',
      'To be listed you need 10 or more rounds before the window and 5 or more inside it (last 8 weeks: 3 or more inside; All time: 15 or more rounds in total), and your rating must have gone up.',
      'It ignores the round-type and gauge filters; the Members/Guests filter applies. The time window at the top picks the dates.',
    ],
    scope: 'windowed',
  },
};

/**
 * The leaderboard chart's explainer for one measure and board kind. The header time window picks the dates,
 * so the chart is tagged with it (`scope: 'windowed'`).
 */
export function boardExplainer(metric: LeaderboardMetric, kind: BoardKind): Explainer {
  const base = explainers['lb-chart'] as Explainer;
  const custom = kind === 'custom';
  const measure = custom
    ? [...(CUSTOM_REPLACE[metric] ?? METRIC_COMPUTED[metric]), ...(CUSTOM_EXTRA[metric] ?? [])]
    : [
        ...METRIC_COMPUTED[metric],
        ...(metric === 'avg_score' || metric === 'avg_adjusted'
          ? [AVERAGE_QUALIFY[kind] as string]
          : []),
      ];
  return {
    ...base,
    computed: [...base.computed, ...measure, PERIOD_COMPUTED[kind], WINDOW_LINE],
  };
}
