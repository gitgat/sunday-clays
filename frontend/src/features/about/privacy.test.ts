import { describe, expect, it } from 'vitest';
import { allStrings, BANNED_WORDS } from '../../test/language';
import { LINK_PREVIEWS_LINE, PRIVACY } from './pages/AboutPage';

describe('About privacy points', () => {
  it('say what link previews show, and never names or scores', () => {
    expect(LINK_PREVIEWS_LINE).toBe(
      'Links shared in chat apps show only the club name, and for a Sunday its date, how many shot and the round type. Never names or scores.',
    );
    expect(PRIVACY).not.toContain(LINK_PREVIEWS_LINE); // only behind its switch
  });

  it('use no banned word', () => {
    for (const text of allStrings([...PRIVACY, LINK_PREVIEWS_LINE])) {
      expect(text).not.toMatch(BANNED_WORDS);
    }
  });
});
