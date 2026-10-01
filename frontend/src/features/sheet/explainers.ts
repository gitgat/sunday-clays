import type { Explainer } from '../../components/charts/types';

/**
 * Plain-language copy for the Sheet's numbers and "On this day" posts, written against
 * api/routes/sheet.py and analytics/sheet.py (STYLE.md: no jargon, neutral pronouns, "Sunday" not
 * "event").
 */
const explainers = {
  shooters: {
    what: 'How many people have at least one recorded score this Sunday.',
    computed: [
      'Counts shooters with a recorded round, not everyone who came, so it can be lower than the head count.',
      'All round types count; the round-type and time filters do not apply.',
    ],
  },
  median: {
    what: 'The middle score this Sunday: half the rounds were this or better, half this or worse.',
    computed: [
      'Every round that day counts, second rounds included. Sorted by score, the middle one is taken.',
      'The round-type and time filters do not apply.',
    ],
  },
  top: {
    what: 'The best single round this Sunday, out of 50.',
    computed: [
      'The highest score among all rounds that day, second rounds included.',
      'The round-type and time filters do not apply.',
    ],
  },
  trophies: {
    what: 'How many trophies people earned this Sunday.',
    read: ['Each trophy has its own post below, naming everyone who earned it.'],
    computed: [
      'Counts every trophy earned that day: two people earning the same trophy count as two.',
      'The round-type and time filters do not apply.',
    ],
  },
  onThisDay: {
    what: 'The Sundays closest to this Sunday’s date one, two and three years ago, and who won them.',
    computed: [
      'For each of the last three years we take this Sunday’s date that many years back (29 February becomes 28 February) and pick the Sunday within three days of it, the earlier one if two are equally close.',
      'Winners: everyone whose best round of that Sunday was first, so a tie lists every winner. A Sunday with no scores shows only its head count.',
      'The round-type and time filters do not apply.',
    ],
  },
} satisfies Record<string, Explainer>;

/** Typed by key, so a wired-in lookup is never undefined. */
export const sheetExplainers: Record<keyof typeof explainers, Explainer> = explainers;
