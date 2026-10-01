import { describe, expect, it } from 'vitest';
import { homeExplainers } from './explainers';

const sources = import.meta.glob(['./**/*.tsx', '!./**/*.test.tsx'], {
  query: '?raw',
  import: 'default',
  eager: true,
}) as Record<string, string>;

function texts(): [string, string][] {
  return Object.entries(homeExplainers).flatMap(([key, e]) => [
    [key, e.what] as [string, string],
    ...(e.read ?? []).map((t): [string, string] => [key, t]),
    ...e.computed.map((t): [string, string] => [key, t]),
  ]);
}

describe('home explainers', () => {
  it('says fullscreen and the CSV cover every Sunday on record', () => {
    expect(homeExplainers.pulse.read?.join(' ')).toContain(
      'Fullscreen and the CSV download cover every Sunday on record.',
    );
  });

  it('has an entry for every ChartFrame urlKey in the feature', () => {
    const keys = Object.values(sources).flatMap((src) =>
      [...src.matchAll(/urlKey="([^"]+)"/g)].map((m) => m[1] ?? ''),
    );
    expect(keys.length).toBeGreaterThan(0);
    for (const key of keys) expect(homeExplainers, key).toHaveProperty(key);
  });

  it('has an entry for every explainer the feature wires in, and wires in every entry', () => {
    const wired = Object.values(sources).flatMap((src) =>
      [...src.matchAll(/homeExplainers\.(\w+)/g)].map((m) => m[1] ?? ''),
    );
    expect(new Set(wired)).toEqual(new Set(Object.keys(homeExplainers)));
  });

  it('uses neutral pronouns, says Sunday and never says class', () => {
    for (const [key, text] of texts()) {
      expect(text, key).not.toMatch(/\b(he|she|his|her|hers|him)\b/i);
      expect(text, key).not.toMatch(/\bclass(es)?\b/i);
      expect(text, key).not.toMatch(/\bevents?\b/i);
    }
  });

  it('keeps each explainer short', () => {
    const totals = new Map<string, number>();
    for (const [key, text] of texts()) {
      totals.set(key, (totals.get(key) ?? 0) + text.split(/\s+/).length);
    }
    for (const [key, words] of totals) expect(words, key).toBeLessThanOrEqual(95);
  });

  it('tags the chart’s default explainer with the time window', () => {
    expect(homeExplainers.pulse.scope).toBe('windowed');
  });

  it('leaves the Sheet’s fixed 8-week club numbers untagged: the header window does not apply', () => {
    for (const key of [
      'pulseSheet',
      'pulseHeldSheet',
      'pulseTurnoutSheet',
      'pulseHighSheet',
    ] as const) {
      expect(homeExplainers[key].scope, key).toBeUndefined();
    }
  });
});
