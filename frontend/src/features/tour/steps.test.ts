import { describe, expect, it } from 'vitest';
import { allStrings, BANNED_WORDS } from '../../test/language';
import { TOUR_STEPS } from './steps';

describe('tour steps', () => {
  it('has the five steps of the spec, in order', () => {
    expect(TOUR_STEPS.map((s) => [s.target, s.title])).toEqual([
      ['sunday', 'The latest Sunday'],
      ['you', 'Which one are you?'],
      ['insights', 'Insights and fist bumps'],
      ['trophies', 'Trophies'],
      ['window', 'Time window'],
    ]);
  });

  it('uses no banned word', () => {
    for (const text of allStrings(TOUR_STEPS)) expect(text).not.toMatch(BANNED_WORDS);
  });
});
