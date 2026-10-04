import { describe, expect, it } from 'vitest';
import { allStrings, BANNED_WORDS } from '../../test/language';
import { sourceLiterals } from '../../test/sourceLiterals';

const sources = import.meta.glob<string>(['./**/*.{ts,tsx}', '!./**/*.test.{ts,tsx}'], {
  query: '?raw',
  import: 'default',
  eager: true,
});
const PRONOUNS = /\b(he|she|his|her|him|hers|himself|herself)\b/i;

describe('club-events copy (§5.8)', () => {
  it('never uses he, she, his, her, him, hers, himself or herself anywhere in the source', () => {
    expect(Object.keys(sources).length).toBeGreaterThan(5);
    for (const [file, text] of Object.entries(sources)) {
      expect(text, file).not.toMatch(PRONOUNS);
    }
  });

  // The owner's "class" rule too: Plan 19's BANNED_WORDS on every string literal and JSX text
  // (a raw-source scan cannot, since every className would trip it).
  it('never uses a banned word, "class" included, in any string or JSX text', () => {
    expect(Object.keys(sources).length).toBeGreaterThan(5);
    for (const [file, text] of Object.entries(sources)) {
      for (const literal of allStrings(sourceLiterals(file, text))) {
        expect(literal, file).not.toMatch(BANNED_WORDS);
      }
    }
  });
});
