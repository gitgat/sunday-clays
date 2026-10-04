import { describe, expect, it } from 'vitest';
import { allStrings, BANNED_WORDS } from './language';

describe('BANNED_WORDS', () => {
  it('catches a banned word (the check is not vacuous)', () => {
    expect('Her best round').toMatch(BANNED_WORDS);
    expect('top of the class').toMatch(BANNED_WORDS);
    expect('Classes of shooter').toMatch(BANNED_WORDS);
  });

  it('leaves similar words alone', () => {
    expect('The hero shot there, then headed home').not.toMatch(BANNED_WORDS);
  });
});

describe('allStrings', () => {
  it('collects strings from nested arrays and objects and ignores the rest', () => {
    expect(allStrings({ a: 'x', b: ['y', { c: 'z' }], d: 4, e: null })).toEqual(['x', 'y', 'z']);
  });
});
