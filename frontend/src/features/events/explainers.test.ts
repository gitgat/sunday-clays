import { describe, expect, it } from 'vitest';
import { eventExplainers } from './explainers';

const sources = import.meta.glob(['./**/*.tsx', '!./**/*.test.tsx'], {
  query: '?raw',
  import: 'default',
  eager: true,
}) as Record<string, string>;

/** Every text an explainer shows, with its key for the failure message. */
function texts(): [string, string][] {
  return Object.entries(eventExplainers).flatMap(([key, e]) => [
    [key, e.what] as [string, string],
    ...(e.read ?? []).map((t): [string, string] => [key, t]),
    ...e.computed.map((t): [string, string] => [key, t]),
  ]);
}

describe('event explainers', () => {
  it('has an entry for every ChartFrame urlKey in the feature', () => {
    const keys = Object.values(sources).flatMap((src) =>
      [...src.matchAll(/urlKey="([^"]+)"/g)].map((m) => m[1] ?? ''),
    );
    expect(keys.length).toBeGreaterThan(0);
    for (const key of keys) expect(eventExplainers, key).toHaveProperty(key);
  });

  it('has an entry for every explainer the feature wires in', () => {
    const wired = Object.values(sources).flatMap((src) =>
      [...src.matchAll(/eventExplainers\.(\w+)/g)].map((m) => m[1] ?? ''),
    );
    expect(new Set(wired)).toEqual(new Set(Object.keys(eventExplainers)));
  });

  it('uses neutral pronouns, says Sunday and never says class', () => {
    for (const [key, text] of texts()) {
      expect(text, key).not.toMatch(/\b(he|she|his|her|hers|him)\b/i);
      expect(text, key).not.toMatch(/\bclass(es)?\b/i);
      expect(text, key).not.toMatch(/\bevents?\b/i);
    }
  });

  it('keeps each explainer short and gives every one a "how it is worked out"', () => {
    const totals = new Map<string, number>();
    for (const [key, text] of texts()) {
      totals.set(key, (totals.get(key) ?? 0) + text.split(/\s+/).length);
    }
    for (const [key, words] of totals) expect(words, key).toBeLessThanOrEqual(95);
    for (const [key, e] of Object.entries(eventExplainers)) {
      expect(e.computed.length, key).toBeGreaterThan(0);
    }
  });

  it('tags the calendar as one year (the year arrows set its period)', () => {
    expect(eventExplainers.calendar.scope).toBe('year');
  });
});
