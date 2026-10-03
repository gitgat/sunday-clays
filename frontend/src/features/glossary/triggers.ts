import type { Explainer } from '../../components/charts/types';
import { GLOSSARY_TERMS, type GlossaryTermId } from './terms';

/**
 * Words that mean an explainer uses a glossary term (Plan 19 §3.2.2). The lint requires the term id
 * in `terms` whenever the explainer's text matches.
 */
export const GLOSSARY_TRIGGERS: Record<GlossaryTermId, RegExp> = {
  'clays-thrown': /\bclays thrown\b/i,
  difficulty: /\bdifficult/i,
  'field-adjusted': /\b(field-)?adjusted\b/i,
  'field-median': /\bfield median\b/i,
  'first-timer': /\bfirst[- ]timers?\b/i,
  'fist-bump': /\bfist bumps?\b/i,
  'held-sunday': /full results/i,
  percentile: /\bpercentiles?\b/i,
  'personal-best': /\bpersonal best|\bPB\b/,
  rarity: /\brarity\b|\brare\b/i,
  'round-types': /\bsuper sporting\b|\bround type/i,
  'special-shoot': /\bspecial shoot/i,
  streak: /\bstreak/i,
  'time-window': /\btime window\b/i,
  'trophy-tiers': /\b(bronze|silver|platinum|diamond)\b/i,
};

/** Term ids whose trigger matches the explainer's text but which its `terms` does not list. */
export function missingTerms(explainer: Explainer): GlossaryTermId[] {
  const text = [explainer.what, ...(explainer.read ?? []), ...explainer.computed].join(' ');
  const listed = new Set(explainer.terms ?? []);
  return (Object.entries(GLOSSARY_TRIGGERS) as [GlossaryTermId, RegExp][])
    .filter(([id, trigger]) => trigger.test(text) && !listed.has(id))
    .map(([id]) => id);
}

/** A builder's own terms joined to its base explainer's, in glossary order and without repeats. */
export function mergeTerms(
  base: readonly GlossaryTermId[] | undefined,
  ...extra: GlossaryTermId[]
): GlossaryTermId[] {
  const wanted = new Set([...(base ?? []), ...extra]);
  return GLOSSARY_TERMS.map((term) => term.id).filter((id) => wanted.has(id));
}
