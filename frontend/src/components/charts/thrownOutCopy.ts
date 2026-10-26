/**
 * Shared disclosure lines for a Sunday with a station thrown out. Appended to every explainer whose
 * numbers leave such a Sunday out (ROUNDS, STATION), count it (COUNTS) or draw it hollow (HOLLOW).
 */
export const THROWN_OUT_ROUNDS = 'Sundays with a station thrown out (marked *) are left out.';
export const THROWN_OUT_STATION = 'A station thrown out on the day is left out.';
export const THROWN_OUT_COUNTS = 'Sundays with a station thrown out count here, marked *.';
export const THROWN_OUT_HOLLOW = 'A hollow point is a Sunday with a station thrown out.';

const SCORE_MEASURES: ReadonlySet<string> = new Set([
  'avg_score',
  'avg_adjusted',
  'best_score',
  'rating_gain',
]);

/** The disclosure line for a leaderboard or race measure: score measures leave such Sundays out, counts keep them. */
export function thrownOutLineFor(metric: string): string {
  return SCORE_MEASURES.has(metric) ? THROWN_OUT_ROUNDS : THROWN_OUT_COUNTS;
}
