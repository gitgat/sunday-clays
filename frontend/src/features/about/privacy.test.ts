import { describe, expect, it } from 'vitest';
import { allStrings, BANNED_WORDS } from '../../test/language';
import { BACKUP_RETENTION_SENTENCE, LINK_PREVIEWS_LINE, privacyLines } from './privacy';

const KEEP =
  'If you sign up for a club event, we keep your name and the email you give us so organizers can reach you.';
const EMAILS =
  'Only organizers see emails. We never show them on the site and never send email from it. Sign-ups are deleted 30 days after the event; an email saved for a shooter stays for quicker sign-ups until an organizer removes it or it goes two years unused. Nightly backups that still hold deleted data are themselves deleted within about two months.';
const IP =
  'Fist bumps and visit counts are anonymous. They use a random ID your browser makes up, never tied to a name. We don’t store IP addresses for any of it';

describe('About privacy points (Plan 19 §4, Plan 20 §5.7.6)', () => {
  it('lists the five standing points in order, with "No ads" last', () => {
    expect(privacyLines(false).map((line) => line.text)).toEqual([
      'No accounts. There are no logins beyond the club’s shared password.',
      'Browsing the site collects nothing about you: no name, no email. The site processes the club’s score sheets and analyses them.',
      '“Which one are you?” is remembered on your device and never sent anywhere.',
      `${IP}.`,
      'No ads, no third-party trackers.',
    ]);
  });

  it('adds the two sign-up lines after the second line while club events are visible', () => {
    const lines = privacyLines(true);
    expect(lines.slice(2, 4)).toEqual([
      { text: KEEP, feature: 'events' },
      { text: EMAILS, feature: 'events' },
    ]);
    expect(lines).toHaveLength(7);
    expect(lines.map((line) => line.text)).toContain(`${IP}, sign-ups included.`);
    expect(lines[3]?.text).toContain(BACKUP_RETENTION_SENTENCE);
    expect(lines.at(-1)?.text).toBe('No ads, no third-party trackers.');
  });

  it('say what link previews show, and never names or scores (Plan 19), outside privacyLines', () => {
    expect(LINK_PREVIEWS_LINE).toBe(
      'Links shared in chat apps show only the club name, and for a Sunday its date (or a special shoot’s title), how many shot and the round type. Never shooter names or scores.',
    );
    expect(privacyLines(true).map((line) => line.text)).not.toContain(LINK_PREVIEWS_LINE);
  });

  it('use no banned word ("class" and every pronoun included)', () => {
    for (const text of allStrings([...privacyLines(true), LINK_PREVIEWS_LINE])) {
      expect(text).not.toMatch(BANNED_WORDS);
    }
  });
});
