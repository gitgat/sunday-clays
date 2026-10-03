import { describe, expect, it } from 'vitest';
import { allStrings, BANNED_WORDS } from '../../test/language';
import { GLOSSARY_TERMS, termById } from './terms';

describe('glossary terms', () => {
  it('has the 15 terms of the spec, sorted by id', () => {
    const ids = GLOSSARY_TERMS.map((t) => t.id);
    expect(ids).toHaveLength(15);
    expect(ids).toEqual([...ids].sort());
  });

  it('gives every term a unique id that is a valid anchor', () => {
    const ids = GLOSSARY_TERMS.map((t) => t.id);
    expect(new Set(ids).size).toBe(ids.length);
    for (const id of ids) expect(id).toMatch(/^[a-z][a-z-]*[a-z]$/);
  });

  it('looks a term up by id', () => {
    expect(termById('percentile').term).toBe('Percentile');
    expect(termById('held-sunday').term).toBe('Sunday with full results');
  });

  it('uses no banned word', () => {
    for (const text of allStrings(GLOSSARY_TERMS)) expect(text).not.toMatch(BANNED_WORDS);
  });

  it('catches a banned word (the check is not vacuous)', () => {
    expect('Her best round').toMatch(BANNED_WORDS);
    expect('top of the class').toMatch(BANNED_WORDS);
  });
});
