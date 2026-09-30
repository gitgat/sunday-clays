import type { Explainer } from '../../components/charts/types';

/** Plain-language copy for every chart and non-obvious stat in this feature (explainers/STYLE.md).
 * Keys are ChartFrame `urlKey`s or stat ids. */
export const explainers: Record<string, Explainer> = {
  // Trophy Room chart (urlKey "rarity").
  rarity: {
    what: 'How many shooters have earned each trophy, as a share of everyone who has shot at least one round.',
    read: [
      'A short bar means the trophy is rare; a long bar means most shooters have it.',
      'Bar colour is the trophy’s metal: bronze, silver, gold, platinum or diamond. One-off trophies have no metal.',
    ],
    computed: [
      'Rarity = shooters who hold the trophy ÷ shooters with at least one round, times 100, rounded to one decimal.',
      'A shooter counts once, even if they earned a repeatable trophy on several Sundays.',
      'Every round counts; the round-type filter does not change it.',
    ],
    scope: 'all-time',
  },
  // Trophy page chart (urlKey "holders").
  holders: {
    what: 'How the number of shooters holding this trophy has grown over the years.',
    read: [
      'Each step up is a shooter earning it for the first time.',
      'A long flat stretch means nobody new earned it for a while.',
    ],
    computed: [
      'Each holder is placed on the first Sunday they earned the trophy.',
      'The line adds them up in date order, so it never goes down.',
    ],
    scope: 'all-time',
  },
  // Trophy Case chart (urlKey "trophytl").
  trophytl: {
    what: 'Your trophies as they arrived, Sunday by Sunday.',
    read: [
      'Steady climbing means you keep earning something new.',
      'A jump on one date means several trophies landed on the same Sunday.',
    ],
    computed: [
      'Every time you earned a trophy adds one, on the Sunday you earned it.',
      'Repeatable trophies (like Welcome Back) add one each time; other trophies add one, once.',
    ],
    scope: 'all-time',
  },
  // Stats without a chart.
  'trophy-progress': {
    what: 'How close you are to the next tier of each trophy that has tiers, such as 2,500 clays broken.',
    read: [
      'A bar close to full means the next tier is near; the count shows your total against the goal.',
    ],
    computed: [
      'Bar = your total so far ÷ the next tier’s target.',
      'Each family counts its own thing (clays broken, Sundays attended, straight Sundays, best round), over all years.',
    ],
    scope: 'all-time',
  },
  'next-trophy': {
    what: 'The three tiers you are closest to earning.',
    computed: [
      'Every tiered trophy you have not finished is scored as your total ÷ the next target.',
      'The three highest scores are shown, so the closest goal comes first.',
    ],
    scope: 'all-time',
  },
};
