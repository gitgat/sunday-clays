import type { Explainer } from '../../components/charts/types';
import { mergeTerms } from '../glossary/terms';
import { formatEventDate } from './format';

/** The dates a records view covers; a missing start is the first Sunday. */
export interface RecordsRange {
  since?: string;
  asOf: string;
}

/**
 * Plain-language copy per ChartFrame `urlKey` (.superpowers/sdd/explainers/STYLE.md; checked against
 * analytics/records.py and analytics/streaks.py). The header time window picks the Sundays that count
 * (`scope: 'windowed'`); `recordsExplainer` adds a line naming the dates.
 */
export const explainers: Record<string, Explainer> = {
  'rec-events': {
    what: 'Who has come to the most Sundays: the top ten here, everyone in fullscreen and the CSV download.',
    read: [
      'The longest bar is the most Sundays shot. Hover a bar, or open Table, to see the number.',
      'Two rounds on one Sunday still count once.',
    ],
    computed: [
      'For each shooter, the number of different Sundays with at least one round of theirs.',
      'Every Sunday with scores counts, whether or not its results are complete.',
      'The round-type filter applies: Super Sporting counts only Super Sporting Sundays.',
    ],
    scope: 'windowed',
    terms: ['round-types'],
  },
  'rec-streaks': {
    what: 'The most Sundays in a row that someone has shot without missing one.',
    read: [
      '56 means 56 Sundays in a row.',
      'It is their best run ever, which may or may not still be going.',
      'Fullscreen and the CSV download list everyone with a streak.',
    ],
    computed: [
      'Only Sundays with complete results count, in date order. Each one you shot adds 1; missing one starts the count again.',
      'Sundays without complete results are skipped: they neither add to a run nor break it.',
      'The round-type filter applies, so a Super Sporting streak only looks at Super Sporting Sundays.',
    ],
    scope: 'windowed',
    terms: ['round-types', 'streak'],
  },
  'rec-highest': {
    what: 'The highest single rounds shot in the time window.',
    read: ['50 is a perfect round. Ties share a place.'],
    computed: [
      'Every round counts, second rounds on doubleheader Sundays too.',
      'The round-type filter applies.',
    ],
    scope: 'windowed',
    terms: ['round-types', 'time-window'],
  },
};

/** "Jan 7, 2024 to Dec 29, 2024": the dates a range covers, in words. */
export function rangeWords({ since, asOf }: RecordsRange): string {
  return `${since === undefined ? 'the first Sunday' : formatEventDate(since)} to ${formatEventDate(asOf)}`;
}

/**
 * The explainer for one record chart: the header time window picks the Sundays that count
 * (analytics/records.py), and a line names its dates.
 */
export function recordsExplainer(key: string, range: RecordsRange): Explainer {
  const base = explainers[key] as Explainer;
  const streaks = key === 'rec-streaks';
  return {
    ...base,
    read: streaks
      ? base.read?.map((line) =>
          line.startsWith('It is their best run ever')
            ? 'It is their best run inside the time window, which may or may not still be going.'
            : line,
        )
      : base.read,
    computed: [
      ...base.computed,
      `Only Sundays from ${rangeWords(range)} count. The time window at the top picks them.`,
      ...(streaks ? ['A run that began before the start date counts from the start date.'] : []),
    ],
    terms: mergeTerms(base.terms, 'time-window'),
  };
}
