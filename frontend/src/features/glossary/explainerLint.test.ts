import { describe, expect, it } from 'vitest';
import type { Explainer } from '../../components/charts/types';
import { METRIC_COPY, explorerExplainer } from '../explorer/explainers';
import { boardExplainer } from '../leaderboards/explainers';
import { raceExplainer } from '../race/explainers';
import { recordsExplainer } from '../records/explainers';
import { mergeTerms, missingTerms } from './triggers';
import type { Metric } from '../../components/charts/explore';
import type { LeaderboardMetric } from '../leaderboards/api';

const modules = import.meta.glob<Record<string, unknown>>('../*/explainers.ts', { eager: true });

function isExplainer(value: unknown): value is Explainer {
  return (
    typeof value === 'object' &&
    value !== null &&
    typeof (value as Explainer).what === 'string' &&
    Array.isArray((value as Explainer).computed)
  );
}

/** Every static explainer exported by a feature: an Explainer export, or a record of them. */
function allExplainers(): [string, Explainer][] {
  const found: [string, Explainer][] = [];
  for (const [file, exports] of Object.entries(modules)) {
    for (const [name, value] of Object.entries(exports)) {
      if (isExplainer(value)) found.push([`${file} ${name}`, value]);
      else if (typeof value === 'object' && value !== null) {
        for (const [key, entry] of Object.entries(value)) {
          if (isExplainer(entry)) found.push([`${file} ${name}.${key}`, entry]);
        }
      }
    }
  }
  return found;
}

describe('glossary trigger lint', () => {
  it('walks a real set of explainers', () => {
    expect(allExplainers().length).toBeGreaterThan(40);
  });

  it('flags a trigger without its term, and passes once the term is listed', () => {
    const bare: Explainer = { what: 'Your percentile on the day.', computed: ['x'] };
    expect(missingTerms(bare)).toEqual(['percentile']);
    expect(missingTerms({ ...bare, terms: ['percentile'] })).toEqual([]);
  });

  it('every explainer lists the glossary terms its text uses', () => {
    const problems = allExplainers().flatMap(([name, explainer]) =>
      missingTerms(explainer).map((id) => `${name}: add '${id}' to terms`),
    );
    expect(problems).toEqual([]);
  });

  it('merges terms in glossary order, without duplicates', () => {
    expect(mergeTerms(undefined, 'time-window')).toEqual(['time-window']);
    expect(mergeTerms(['time-window', 'percentile'], 'percentile', 'difficulty')).toEqual([
      'difficulty',
      'percentile',
      'time-window',
    ]);
  });

  it('every explainer built at run time lists the terms its text uses', () => {
    const boardMetrics: LeaderboardMetric[] = [
      'avg_score',
      'avg_adjusted',
      'best_score',
      'wins',
      'podiums',
      'events',
      'rounds',
      'rating_gain',
      'season_points',
    ];
    const built: [string, Explainer][] = [];
    for (const metric of boardMetrics) {
      for (const kind of ['season', 'ytd', 'rolling_12', 'all_time', 'custom'] as const) {
        built.push([`board ${metric} ${kind}`, boardExplainer(metric, kind)]);
      }
    }
    for (const metric of Object.keys(METRIC_COPY) as Metric[]) {
      for (const scope of ['windowed', 'all-time', undefined] as const) {
        built.push([`explorer ${metric} ${String(scope)}`, explorerExplainer(metric, scope)]);
      }
    }
    for (const key of ['rec-events', 'rec-streaks', 'rec-highest']) {
      built.push([key, recordsExplainer(key, { asOf: '2026-01-04' })]);
    }
    for (const key of ['race-bars', 'race-bump'] as const) {
      for (const mode of ['rolling_12', 'season', 'ytd'] as const) {
        built.push([`${key} ${mode}`, raceExplainer(key, mode)]);
      }
    }
    const problems = built.flatMap(([name, explainer]) =>
      missingTerms(explainer).map((id) => `${name}: add '${id}' to terms`),
    );
    expect(problems).toEqual([]);
  });

  it('skips a term the explainer opts out of', () => {
    const bare: Explainer = { what: 'Your percentile on the day.', computed: ['x'] };
    expect(missingTerms({ ...bare, noTerms: ['percentile'] })).toEqual([]);
  });
});
