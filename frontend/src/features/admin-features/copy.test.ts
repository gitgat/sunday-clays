import { describe, expect, it } from 'vitest';
import { allStrings, BANNED_WORDS } from '../../test/language';
import { changedText, FEATURES_INTRO } from './copy';
import { featureSwitches } from './mocks';

describe('Features page copy', () => {
  it('formats the change date and the never-changed case', () => {
    expect(changedText('2026-10-02')).toBe('Changed Oct 2, 2026');
    expect(changedText(null)).toBe('Never changed');
  });

  it('uses no banned word in the intro, labels and descriptions', () => {
    const texts = [
      FEATURES_INTRO,
      ...allStrings(featureSwitches.map(({ label, description }) => ({ label, description }))),
    ];
    for (const text of texts) expect(text).not.toMatch(BANNED_WORDS);
  });
});
