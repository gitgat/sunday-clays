import { describe, expect, it } from 'vitest';
import { analyticsExplainers } from './explainers';

const sources = import.meta.glob(['./**/*.tsx', '!./**/*.test.tsx'], {
  query: '?raw',
  import: 'default',
  eager: true,
}) as Record<string, string>;

function texts(): [string, string][] {
  return Object.entries(analyticsExplainers).flatMap(([key, e]) => [
    [key, e.what] as [string, string],
    ...(e.read ?? []).map((t): [string, string] => [key, t]),
    ...e.computed.map((t): [string, string] => [key, t]),
  ]);
}

describe('analytics explainers', () => {
  it('has an entry for every ChartFrame urlKey in the feature, and uses every entry', () => {
    const keys = Object.values(sources).flatMap((src) =>
      [...src.matchAll(/urlKey="([^"]+)"/g)].map((m) => m[1] ?? ''),
    );
    expect(new Set(keys)).toEqual(new Set(['visitors', 'pages', 'bumps', 'uptake']));
    const wired = Object.values(sources).flatMap((src) =>
      [...src.matchAll(/analyticsExplainers\.(\w+)/g)].map((m) => m[1] ?? ''),
    );
    expect(new Set(wired)).toEqual(new Set(Object.keys(analyticsExplainers)));
  });

  it('says fullscreen and the CSV cover everything on record', () => {
    for (const [key, e] of Object.entries(analyticsExplainers)) {
      expect(e.read?.join(' '), key).toMatch(/Fullscreen and the CSV download cover every/);
    }
  });

  it('uses neutral pronouns, says Sunday and never says class', () => {
    for (const [key, text] of texts()) {
      expect(text, key).not.toMatch(/\b(he|she|his|her|hers|him)\b/i);
      expect(text, key).not.toMatch(/\bclass(es)?\b/i);
      expect(text, key).not.toMatch(/\bevents?\b/i);
    }
  });

  it('says where every chart starts and ends, and that weeks begin on Monday', () => {
    const all = (key: keyof typeof analyticsExplainers) => {
      const e = analyticsExplainers[key] as { what: string; read?: string[]; computed: string[] };
      return [e.what, ...(e.read ?? []), ...e.computed].join(' ');
    };
    for (const key of ['visitors', 'pages', 'bumps', 'uptake'] as const) {
      expect(all(key), key).toMatch(/first day the site has any/i);
      expect(all(key), key).toMatch(/today/i);
    }
    expect(all('visitors')).toMatch(/Monday/);
    expect(all('uptake')).toMatch(/Monday/);
    expect(all('bumps')).toMatch(/headline/i);
  });

  it('says admin bumps count, and keeps "never counted" for visits only', () => {
    const all = (key: keyof typeof analyticsExplainers) => {
      const e = analyticsExplainers[key] as { what: string; read?: string[]; computed: string[] };
      return [e.what, ...(e.read ?? []), ...e.computed].join(' ');
    };
    expect(all('bumps')).toMatch(/everyone.*admins included/i);
    expect(all('bumps')).not.toMatch(/never counted/i);
    expect(all('visitors')).toMatch(/Admin visits .* never counted/);
    expect(all('pages')).toMatch(/Admin visits are never counted/);
  });

  it('keeps each explainer short', () => {
    const totals = new Map<string, number>();
    for (const [key, text] of texts()) {
      totals.set(key, (totals.get(key) ?? 0) + text.split(/\s+/).length);
    }
    for (const [key, words] of totals) expect(words, key).toBeLessThanOrEqual(95);
  });
});
