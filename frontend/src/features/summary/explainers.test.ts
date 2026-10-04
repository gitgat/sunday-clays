import { describe, expect, it } from 'vitest';
import { allStrings, BANNED_WORDS } from '../../test/language';
import { explainers } from './explainers';

describe('summary explainers', () => {
  it('has the summary-card entry with its scope and terms', () => {
    expect(explainers['summary-card']?.scope).toBe('windowed');
    expect(explainers['summary-card']?.terms).toEqual([
      'special-shoot',
      'personal-best',
      'streak',
      'round-types',
      'time-window', // "the chosen time window" matches T5's trigger; T5 and T7 are both wave 3
    ]);
  });

  it('uses no banned word', () => {
    for (const text of allStrings(explainers)) expect(text).not.toMatch(BANNED_WORDS);
  });
});
