import { describe, expect, it } from 'vitest';
import { allStrings, BANNED_WORDS } from '../../test/language';
import { sourceLiterals } from '../../test/sourceLiterals';
import { CONTACT_SOURCES } from './form';

const PRONOUNS = /\b(he|she|his|her|him|hers|himself|herself)\b/i;
const sources = import.meta.glob(['./**/*.{ts,tsx}', '!./**/*.test.{ts,tsx}'], {
  eager: true,
  query: '?raw',
  import: 'default',
}) as Record<string, string>;

describe('admin club-events copy (§5.8)', () => {
  it('uses no pronoun anywhere in the raw source outside comments', () => {
    const files = Object.entries(sources);
    expect(files.length).toBeGreaterThan(4);
    for (const [file, text] of files) {
      const code = text.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '');
      expect(PRONOUNS.test(code), file).toBe(false);
    }
  });

  it('uses no banned word, "class" included, in any string or JSX text', () => {
    const files = Object.entries(sources);
    expect(files.length).toBeGreaterThan(4);
    for (const [file, text] of files) {
      for (const literal of sourceLiterals(file, text)) {
        expect(BANNED_WORDS.test(literal), `${file}: ${literal}`).toBe(false);
      }
    }
    for (const text of allStrings(CONTACT_SOURCES)) expect(BANNED_WORDS.test(text)).toBe(false);
  });
});
