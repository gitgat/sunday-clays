import { describe, expect, it } from 'vitest';
import { allStrings, BANNED_WORDS } from '../../test/language';
import * as copy from './copy';

describe('install tip copy', () => {
  it('uses no banned word', () => {
    for (const text of allStrings(Object.values(copy))) expect(text).not.toMatch(BANNED_WORDS);
  });
});
