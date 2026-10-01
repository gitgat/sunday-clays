import { describe, expect, it } from 'vitest';
import { sheetExplainers } from './explainers';

const sources = import.meta.glob(['./**/*.tsx', '!./**/*.test.tsx'], {
  query: '?raw',
  import: 'default',
  eager: true,
}) as Record<string, string>;

function texts(): [string, string][] {
  return Object.entries(sheetExplainers).flatMap(([key, e]) => [
    [key, e.what] as [string, string],
    ...(e.read ?? []).map((t): [string, string] => [key, t]),
    ...e.computed.map((t): [string, string] => [key, t]),
  ]);
}

describe('sheet explainers', () => {
  it('has an entry for every explainer the feature wires in, and wires in every entry', () => {
    const wired = Object.values(sources).flatMap((src) =>
      [...src.matchAll(/sheetExplainers\.(\w+)/g)].map((m) => m[1] ?? ''),
    );
    expect(new Set(wired)).toEqual(new Set(Object.keys(sheetExplainers)));
  });

  it('uses neutral pronouns, says Sunday and never says class', () => {
    for (const [key, text] of texts()) {
      expect(text, key).not.toMatch(/\b(he|she|his|her|hers|him)\b/i);
      expect(text, key).not.toMatch(/\bclass(es)?\b/i);
      expect(text, key).not.toMatch(/\bevents?\b/i);
    }
  });

  it('says the numbers and look-backs ignore the time filter', () => {
    for (const e of Object.values(sheetExplainers)) {
      expect(e.computed.join(' ')).toContain('time filters do not apply');
      expect(e.scope).toBeUndefined();
    }
  });
});
