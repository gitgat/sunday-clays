import type { Explainer } from '../../components/charts/types';

/**
 * Plain-language copy for the home page, keyed by chart urlKey or stat id. Written against
 * api/routes/events.py, analytics/metrics.py, analytics/streaks.py and the home components
 * (STYLE.md: no jargon, neutral pronouns, "Sunday" not "event"; "you" for the personal panel).
 */
const explainers = {
  pulse: {
    what: 'How many people came to each Sunday in the time window you picked at the top.',
    read: [
      'Tall bars are big turnouts; a dip is a slow Sunday (weather, holidays).',
      'Drag or pinch the chart to look at earlier Sundays from the same year. Fullscreen and the CSV download cover every Sunday on record.',
    ],
    computed: [
      'One bar per Sunday with scores.',
      'Bar height is the attendance head count, or the number of shooters with scores when there is no head count.',
      'The round-type filter applies. Sundays with attendance but no scores are left out.',
    ],
    scope: 'windowed',
  },
  pulseHeld: {
    what: 'How many Sundays in the time window have full results.',
    computed: [
      'A Sunday has full results when scores were entered and at least half of the people who came have scores.',
      'The round-type filter applies.',
    ],
    scope: 'windowed',
  },
  pulseTurnout: {
    what: 'The typical crowd: the average number of people per scored Sunday in the time window.',
    computed: [
      'Adds up the head count of each scored Sunday (or the number with scores when there is no head count) and divides by the number of Sundays, to 0.1.',
      'The round-type filter applies.',
    ],
    scope: 'windowed',
  },
  pulseHigh: {
    what: 'The best single round anyone shot in the time window, out of 50.',
    computed: [
      'The highest score of any round on a scored Sunday in the window, second rounds included.',
      'It is one round, not an average. The round-type filter applies.',
    ],
    scope: 'windowed',
  },
  pulseSheet: {
    what: 'How many people came to each Sunday in the 8 weeks up to this issue’s Sunday.',
    read: [
      'Tall bars are big turnouts; a dip is a slow Sunday (weather, holidays).',
      'Fullscreen and the CSV download cover every Sunday on record.',
    ],
    computed: [
      'One bar per Sunday with scores.',
      'Bar height is the attendance head count, or the number of shooters with scores when there is no head count.',
      'The round-type filter applies. The time filter does not: the Sheet always shows the 8 weeks up to its Sunday.',
    ],
  },
  pulseHeldSheet: {
    what: 'How many Sundays in the 8 weeks up to this issue’s Sunday have full results.',
    computed: [
      'A Sunday has full results when scores were entered and at least half of the people who came have scores.',
      'The round-type filter applies; the time filter does not.',
    ],
  },
  pulseTurnoutSheet: {
    what: 'The typical crowd: the average number of people per scored Sunday in the 8 weeks up to this issue’s Sunday.',
    computed: [
      'Adds up the head count of each scored Sunday (or the number with scores when there is no head count) and divides by the number of Sundays, to 0.1.',
      'The round-type filter applies; the time filter does not.',
    ],
  },
  pulseHighSheet: {
    what: 'The best single round anyone shot in the 8 weeks up to this issue’s Sunday, out of 50.',
    computed: [
      'The highest score of any round on a scored Sunday in those 8 weeks, second rounds included.',
      'It is one round, not an average. The round-type filter applies; the time filter does not.',
    ],
  },
  meLast: {
    what: 'Your most recent Sunday: the date, your best score, where it placed and how your rating moved.',
    read: [
      '"44 · 2nd" means your best round was a 44 and it finished second.',
      'Rating move is how much that Sunday changed your rating, our skill estimate out of 50.',
    ],
    computed: [
      'Last out is the newest Sunday you shot, within the round-type filter.',
      'Score is your best round; finish is its place among best rounds.',
      'Rating move = rating after minus rating before, to 0.1. "—" means the Sunday had partial results, so ratings did not move.',
    ],
  },
  meOdometer: {
    what: 'Your lifetime totals at Sunday Clays.',
    read: ['Current streak counts Sundays in a row that you shot.'],
    computed: [
      'Clays broken: every score you have shot, added up, second rounds included.',
      'Sundays: Sundays with at least one round from you.',
      'Current streak: Sundays in a row, counting back from the latest Sunday with full results (0 if you missed it). Partial Sundays neither add nor break it.',
      'All round types count; the round-type filter does not apply.',
    ],
    scope: 'lifetime',
  },
} satisfies Record<string, Explainer>;

/** Typed by key, so a wired-in lookup is never undefined. */
export const homeExplainers: Record<keyof typeof explainers, Explainer> = explainers;
