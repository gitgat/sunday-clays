import type { Explainer } from '../../components/charts/types';
import { mergeTerms } from '../glossary/terms';
import type { RaceMode } from './labels';

/**
 * Plain-language copy per ChartFrame `urlKey` (.superpowers/sdd/explainers/STYLE.md; checked against
 * analytics/leaderboard_history.py, analytics/leaderboards.py, analytics/points.py and race/usePlayer.ts).
 * The header time window picks the Sundays that are replayed; the race buttons (last 12 months, last
 * 8 Sundays, since 1 January) pick how each step is counted. `raceExplainer` writes that line for the
 * chosen points rule.
 */
export const explainers: Record<string, Explainer> = {
  'race-bars': {
    what: 'The top ten changing Sunday by Sunday, like a scoreboard replay.',
    read: [
      'Each bar is a shooter, longest on top. Bars slide past each other as places change.',
      'It opens on the latest Sunday. Press Play to replay from the first Sunday of the time window, or drag the slider.',
      'Fullscreen draws the top 50; its table and the CSV download list the same top 50 ranked that Sunday.',
    ],
    computed: [
      'One step per Sunday with scores inside the time window: that Sunday’s top ten for the chosen measure, worked out the same way as on Leaderboards.',
      'A new Sunday every 1.2 seconds. Bars start at zero, so close values look alike; the number at the end of each bar tells them apart.',
    ],
    terms: ['time-window'],
  },
  'race-bump': {
    what: 'Each shooter’s place after every Sunday of the race, so you can see who climbed and who slid.',
    read: [
      'First place is at the top. A line rising means moving up the standings.',
      'A gap means that shooter was outside the top ten (top 50 in fullscreen) that Sunday. Two dots on the same place mean a tie.',
      'Fullscreen follows the top 50; its table and the CSV download have the top 50 on every Sunday.',
    ],
    computed: [
      'One line for everyone who made the top ten on at least one Sunday of the race.',
      'Each dot is their place on that Sunday’s board for the chosen measure.',
    ],
  },
};

/** How each points rule counts each step, in one sentence (the header time window picks the Sundays). */
const MODE_COMPUTED: Record<RaceMode, string> = {
  rolling_12:
    'The time window at the top picks the Sundays that are replayed. Each step counts the 364 days ending on that Sunday (the last 52 Sundays), so a Sunday’s points drop off a year later.',
  season:
    'The time window at the top picks the Sundays that are replayed. Each step counts the last 8 Sundays (56 days) up to that Sunday, so it rolls forward and never restarts.',
  ytd: 'The time window at the top picks the Sundays that are replayed. Each step counts from 1 January up to that Sunday, so everyone starts again at zero each January.',
};

/** A race chart's explainer for the chosen points rule; both charts follow the time window. */
export function raceExplainer(key: 'race-bars' | 'race-bump', mode: RaceMode): Explainer {
  const base = explainers[key] as Explainer;
  return {
    ...base,
    computed: [...base.computed, MODE_COMPUTED[mode]],
    terms: mergeTerms(base.terms, 'time-window'),
    scope: 'windowed',
  };
}

const POINTS =
  'Points: 1st place earns 10, 2nd 8, 3rd 6, 4th 5, 5th 4, 6th 3, 7th 2 and 8th 1, plus 1 for turning up. Ties share a place.';

/** What the chosen points rule means for the points, in plain words. */
const MODE_INTRO: Record<RaceMode, string> = {
  rolling_12:
    'Last 12 months counts points from the last 52 Sundays. Each Sunday’s points drop off a year later, so there is no reset.',
  season:
    'Last 8 Sundays counts points from the last 8 Sundays. It rolls forward every Sunday, so there is no reset.',
  ytd: 'Since Jan 1 counts points since 1 January. It resets every 1 January.',
};

/** The paragraph at the top of the page: what the race is, how points work, and what the chosen rule resets. */
export function raceIntro(mode: RaceMode): { what: string; points: string; mode: string } {
  return {
    what: 'The race replays each Sunday’s standings as bars, so you can watch the leaders change. The time window at the top picks the Sundays. Rank over time shows the same places as lines.',
    points: POINTS,
    mode: MODE_INTRO[mode],
  };
}
