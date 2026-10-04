/** The words Sunday Clays uses, in plain English (Plan 19 §3.2.2). The id is the page anchor. */
export type GlossaryTermId =
  | 'clays-thrown'
  | 'difficulty'
  | 'field-adjusted'
  | 'field-median'
  | 'first-timer'
  | 'fist-bump'
  | 'held-sunday'
  | 'percentile'
  | 'personal-best'
  | 'rarity'
  | 'round-types'
  | 'special-shoot'
  | 'streak'
  | 'time-window'
  | 'trophy-tiers';

export interface GlossaryTerm {
  id: GlossaryTermId;
  term: string;
  definition: string;
}

/** Sorted by id, the order the Glossary page lists them in. */
export const GLOSSARY_TERMS: readonly GlossaryTerm[] = [
  {
    id: 'clays-thrown',
    term: 'Clays thrown and broken',
    definition:
      'Thrown is 50 for every regular round. Broken is the score. Special shoots are left out of both.',
  },
  {
    id: 'difficulty',
    term: 'Difficulty',
    definition:
      'How much harder or easier a Sunday was than usual, in targets. It is worked out from how everyone scored compared with their own normal.',
  },
  {
    id: 'field-adjusted',
    term: 'Field-adjusted score',
    definition:
      "Your score minus that Sunday's field median. +4 means 4 targets better than the middle of the field, so easy and hard days compare fairly.",
  },
  {
    id: 'field-median',
    term: 'Field median',
    definition: 'The middle score of all rounds that Sunday: half scored more, half scored less.',
  },
  {
    id: 'first-timer',
    term: 'First-timer',
    definition: 'Someone whose first Sunday on record is that day. Special shoots count.',
  },
  {
    id: 'fist-bump',
    term: 'Fist bump',
    definition:
      'A thumbs-up on an insight. It is anonymous: it uses a random ID made by your browser, never your name.',
  },
  {
    id: 'held-sunday',
    term: 'Sunday with full results',
    definition:
      'A Sunday that has scores, where either no head count was written down or at least half the people counted have a score. Streaks, Sundays held and milestones count these.',
  },
  {
    id: 'percentile',
    term: 'Percentile',
    definition:
      'Where your best round of the day landed in the field, from 0% (lowest) to 100% (highest). Ties share a spot. It is (shooters − your average place) ÷ (shooters − 1).',
  },
  {
    id: 'personal-best',
    term: 'Personal best (PB)',
    definition:
      "Your best single round so far. On a Sunday's page, in the recap and on the summary card, a new PB counts once you have at least 5 earlier rounds.",
  },
  {
    id: 'rarity',
    term: 'Rarity',
    definition:
      'The share of everyone who has shot a round who holds that trophy. 5% means about 1 in 20 shooters.',
  },
  {
    id: 'round-types',
    term: 'Sporting and Super Sporting',
    definition:
      "Every regular round is 50 targets. If any station that day threw an odd number of targets, the round is Super Sporting (some single targets mixed with pairs). Otherwise it is Sporting (all pairs). An admin can correct a Sunday's type.",
  },
  {
    id: 'special-shoot',
    term: 'Special shoot',
    definition:
      'A Sunday with its own format, such as the 3-Bird Shoot (60 targets). It counts as a Sunday you came to, for streaks, Sundays shot and attendance trophies, but its scores stay out of averages, personal bests, records and leaderboards.',
  },
  {
    id: 'streak',
    term: 'Streak',
    definition:
      'Sundays in a row you came to, counting Sundays with full results. A special shoot adds one if you came, and never breaks a run if you did not.',
  },
  {
    id: 'time-window',
    term: 'Time window',
    definition:
      'The 8W / 3M / 6M / 12M / YTD / All / Custom control at the top. Charts and stats on the page follow it. Fullscreen and CSV downloads show everything.',
  },
  {
    id: 'trophy-tiers',
    term: 'Trophy tiers',
    definition:
      'Tiered trophies go Bronze, Silver, Gold, Platinum, then Diamond as the number grows.',
  },
];

export function termById(id: GlossaryTermId): GlossaryTerm {
  const found = GLOSSARY_TERMS.find((t) => t.id === id);
  if (found === undefined) throw new Error(`no glossary term ${id}`);
  return found;
}

/** A builder's own terms joined to its base explainer's, in glossary order and without repeats. */
export function mergeTerms(
  base: readonly GlossaryTermId[] | undefined,
  ...extra: GlossaryTermId[]
): GlossaryTermId[] {
  const wanted = new Set([...(base ?? []), ...extra]);
  return GLOSSARY_TERMS.map((term) => term.id).filter((id) => wanted.has(id));
}
