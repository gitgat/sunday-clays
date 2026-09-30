import type { Metric } from '../../components/charts/explore';
import type { Explainer } from '../../components/charts/types';

type MetricCopy = Pick<Explainer, 'what' | 'computed'> & { read: readonly string[] };

/**
 * What each Explorer metric measures (.superpowers/sdd/explainers/club-explorer.md, checked
 * against explorer/engine.py and analytics/metrics.py, skill.py). Written for a shooter: a
 * "Sunday with full results" has scores and either no head count or scores for at least half of it.
 */
export const METRIC_COPY: Record<Metric, MetricCopy> = {
  score: {
    what: 'Round scores out of 50.',
    read: [
      'Higher is better. Aggregate picks how each bar boils its rounds down: average, best, and so on.',
    ],
    computed: [
      'Each round’s score is one value: every round, second rounds on doubleheader Sundays too.',
      'Sporting and super sporting mix unless the round-type filter is set.',
    ],
  },
  adjusted: {
    what: 'A score compared with how the whole field shot that Sunday, in targets.',
    read: [
      '+4 means 4 above that Sunday’s middle score; −3 means 3 below it.',
      'It makes easy and hard Sundays comparable.',
    ],
    computed: [
      'Score minus the middle score (median) of every round shot that Sunday, all shooters.',
      'Only Sundays with full results have a middle score; other rounds are left out.',
    ],
  },
  residual: {
    what: 'How many targets better or worse a round was than we expected from that shooter that Sunday.',
    read: [
      '+3 means 3 more than expected; −3 means 3 fewer.',
      'A group averaging near zero shoots as predicted.',
    ],
    computed: [
      'Expected score = the shooter’s rating going in, lowered on a hard Sunday and raised on an easy one (judged from everyone else’s scores).',
      'Vs expected = actual score minus expected score. Sundays with full results only.',
    ],
  },
  rating: {
    what: 'Our estimate of skill: roughly what a shooter would break out of 50 on a typical recent Sunday.',
    read: [
      'Higher is better: a 38 means we would expect about 38 on an ordinary Sunday.',
      'Group by Year or Month to watch improvement.',
    ],
    computed: [
      'One value per shooter per Sunday shot: their rating just after it (best round only).',
      'Beat what we expected and it rises; fall short and it drops. Newcomers start near 30.',
    ],
  },
  rounds: {
    what: 'How many rounds were shot.',
    read: ['A bigger bar means more shooting. There is no Aggregate choice for this metric.'],
    computed: [
      'The rounds in each group after the filters; both rounds on a doubleheader count.',
      'With Best round only, one per shooter per Sunday.',
    ],
  },
  shooters: {
    what: 'How many different people shot.',
    read: ['A person counts once per bar, so bars can add up to more than the year’s total.'],
    computed: ['Different shooters with at least one round in the group, after the filters.'],
  },
  attendance: {
    what: 'Head counts from the attendance sheet.',
    read: [
      'Average is the typical turnout per Sunday; Total adds up people-visits (someone who came 20 times counts 20).',
    ],
    computed: [
      'One value per Sunday: its head count. Sundays without one are skipped; Sundays with no scores count.',
      'Only date, weather and round-type filters apply, and it splits only by date, round type or weather.',
    ],
  },
  wins: {
    what: 'How many Sundays a shooter (or group) won.',
    read: ['Group by Shooter for a win leaderboard.'],
    computed: [
      'A win is the top score that Sunday, using each shooter’s best round. Ties: every tied shooter wins.',
      'Every scored Sunday counts. Filters only choose whose wins are counted; a win is always against the whole field.',
    ],
  },
  hit_pct: {
    what: 'The share of targets broken, from the station sheets.',
    read: [
      '70% means 70 of every 100 targets thrown were broken. Higher means an easier station or better shooting.',
    ],
    computed: [
      'Targets broken ÷ targets thrown × 100, so a 7-target station counts for more than a 5-target one.',
      'Only Sundays with a station sheet, and only rows we could match to a scored round.',
    ],
  },
  difficulty: {
    what: 'How much harder or easier each Sunday played than a normal Sunday, in targets.',
    read: [
      '+2 means shooters broke about 2 fewer targets than usual for them; negative is easier.',
      'Average over a month or a weather band to see which conditions play hard.',
    ],
    computed: [
      'One value per Sunday with full results: the Sunday page’s difficulty.',
      'Only date, weather and round-type filters apply, and it splits only by date, round type or weather.',
    ],
  },
};

/** The Explorer result's explainer for one metric; `scope` says which dates it covers. */
export function explorerExplainer(metric: Metric, scope: Explainer['scope']): Explainer {
  const copy = METRIC_COPY[metric];
  return {
    what: copy.what,
    read: [
      ...copy.read,
      'Group by and Then by choose the split. The table has the exact numbers, and n is how many values are behind each bar.',
    ],
    computed: [
      ...copy.computed,
      scope === 'windowed'
        ? 'On the page: only Sundays inside the time window at the top of the page (change it there). Fullscreen and the CSV download cover every Sunday.'
        : 'Every Sunday on record. Fullscreen and the CSV download can hold up to 5,000 rows.',
      'Filters and the round-type filter apply. At most 500 groups are shown on the page, and up to 5,000 in fullscreen and the CSV download.',
    ],
    ...(scope === undefined ? {} : { scope }),
  };
}

/** Keyed by ChartFrame urlKey: `v` is the Explorer result (the general copy, for the default metric). */
export const explainers: Record<string, Explainer> = {
  v: explorerExplainer('score', 'windowed'),
};

/** Notes on the Query card's choices, for the "About these choices" panel. */
export const CHOICES_EXPLAINER: Explainer = {
  what: 'Pick what to measure, how to combine the values, and how to split them into bars.',
  read: [
    'Aggregate: Average adds up and divides; Median is the middle value; Max and Min are highest and lowest; Total is the sum; Count is how many values; 90th percentile means 9 in 10 values are at or below it; 25th percentile means 1 in 4 are at or below it; Std dev is how spread out they are.',
    'Group by: Sunday, Month such as 2026-03, Year, Time of year (winter, spring, summer or fall), or Month of year (1 is January, all years together).',
    'Sort “Group” orders by year, date or name; “Value” makes a leaderboard. Bar suits comparing groups, Line suits time, Heatmap needs two splits.',
  ],
  computed: [
    'Time of year: winter Dec to Feb, spring Mar to May, summer Jun to Aug, fall Sep to Nov.',
    'Year to date (set by an insight link, cleared with its chip) cuts every year at the same day, so a year still running compares fairly with earlier ones.',
    'Round type: any station with an odd number of targets (5, 7…) makes a Sunday super sporting; every other Sunday, including one with no station sheet on record, counts as sporting.',
    'Status uses each shooter’s status today, not on the day. Weather is 10 a.m. to noon: temperature bands under 40, 40–55, 55–70, 70–85, 85+ °F; wind by gust under 10, 10–20, 20+ mph; rain dry under 0.02 in.',
    'Minimum score (set by an insight link, cleared with its chip) keeps only rounds at or above it.',
  ],
};
