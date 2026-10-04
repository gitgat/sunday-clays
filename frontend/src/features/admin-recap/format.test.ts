import { describe, expect, it } from 'vitest';
import { allStrings, BANNED_WORDS } from '../../test/language';
import { escapeMarkdown, formatRecap, recapFilename } from './format';
import { regularRecap, specialRecap } from './mocks';

const REGULAR_TEXT = `Sunday Clays · Sunday, September 27, 2026

Turnout: 24 came out and 27 rounds were shot.

Podium (best round of the day)
Tied 1st: Finnegan, Stanton and Stockton, Ethan — 49
3rd: Devlin, Sid — 47

New personal bests
- Kaplan, Noel: 45 (was 43)

Milestones and trophies
- Abernathy, Preston: Events Attended — Silver
- Club: 350,000 clays thrown

Welcome to our first-timers
- Kim, Pat

See every score: https://sundayclays.claysmasher.com/l/events/2026-09-27`;

const REGULAR_MARKDOWN = `**Sunday Clays · Sunday, September 27, 2026**

Turnout: 24 came out and 27 rounds were shot.

**Podium (best round of the day)**
- Tied 1st: Finnegan, Stanton and Stockton, Ethan — 49
- 3rd: Devlin, Sid — 47

**New personal bests**
- Kaplan, Noel: 45 (was 43)

**Milestones and trophies**
- Abernathy, Preston: Events Attended — Silver
- Club: 350,000 clays thrown

**Welcome to our first-timers**
- Kim, Pat

[See every score](https://sundayclays.claysmasher.com/l/events/2026-09-27)`;

const SPECIAL_TEXT = `Sunday Clays · Sunday, September 20, 2026
3-Bird Shoot (special shoot, 60 targets)

40 shooters came out.
3-Bird Shoot trophy: 12 earned it for the first time today. 58 shooters hold it now.
Top score: 55 of 60.

Welcome to our first-timers
- Kim, Pat

See every score: https://sundayclays.claysmasher.com/l/events/2026-09-20`;

const SPECIAL_MARKDOWN = `**Sunday Clays · Sunday, September 20, 2026**

3-Bird Shoot (special shoot, 60 targets)

40 shooters came out.

3-Bird Shoot trophy: 12 earned it for the first time today. 58 shooters hold it now.

Top score: 55 of 60.

**Welcome to our first-timers**
- Kim, Pat

[See every score](https://sundayclays.claysmasher.com/l/events/2026-09-20)`;

describe('recap formatting', () => {
  it('regular, plain text', () => expect(formatRecap(regularRecap).text).toBe(REGULAR_TEXT));
  it('regular, Markdown', () => expect(formatRecap(regularRecap).markdown).toBe(REGULAR_MARKDOWN));
  it('special, plain text', () => expect(formatRecap(specialRecap).text).toBe(SPECIAL_TEXT));

  it('a later 3-bird shoot where nobody is new, and the first one on record', () => {
    expect(formatRecap({ ...specialRecap, three_bird_new: 0 }).text).toContain(
      '3-Bird Shoot trophy: 58 shooters hold it now.',
    );
    expect(
      formatRecap({ ...specialRecap, three_bird_new: 40, three_bird_holders: 40 }).text,
    ).toContain('3-Bird Shoot trophy: 40 shooters earned it today.');
    expect(
      formatRecap({ ...specialRecap, three_bird_new: 1, three_bird_holders: 1 }).text,
    ).toContain('3-Bird Shoot trophy: 1 shooter earned it today.');
  });

  it('a Turkey Shoot has no trophy line and is otherwise unchanged', () => {
    const turkey = {
      ...specialRecap,
      label: 'Turkey Shoot',
      three_bird_new: null,
      three_bird_holders: null,
    };
    expect(formatRecap(turkey).text).toBe(
      SPECIAL_TEXT.replace('3-Bird Shoot (special', 'Turkey Shoot (special').replace(
        '3-Bird Shoot trophy: 12 earned it for the first time today. 58 shooters hold it now.\n',
        '',
      ),
    );
  });

  it('omits empty sections with their headings, and uses the shooter count without a head count', () => {
    const bare = {
      ...regularRecap,
      head_count: null,
      pbs: [],
      trophies: [],
      club_milestones: [],
      first_timers: [],
    };
    const text = formatRecap(bare).text;
    expect(text).toContain('Turnout: 23 shooters and 27 rounds were shot.');
    for (const heading of [
      'New personal bests',
      'Milestones and trophies',
      'Welcome to our first-timers',
    ]) {
      expect(text).not.toContain(heading);
    }
  });

  it('one shooter, and five tied for third', () => {
    const one = {
      ...regularRecap,
      podium: [{ place: 1 as const, tied: false, score: 44, names: ['Hadley, Ike'] }],
    };
    expect(formatRecap(one).text).toContain(
      'Podium (best round of the day)\n1st: Hadley, Ike — 44\n',
    );
    const five = ['A, One', 'B, Two', 'C, Three', 'D, Four', 'E, Five'];
    const tied = {
      ...regularRecap,
      podium: [{ place: 3 as const, tied: true, score: 44, names: five }],
    };
    expect(formatRecap(tied).text).toContain(
      'Tied 3rd: A, One, B, Two, C, Three, D, Four and E, Five — 44',
    );
  });

  it('escapes backticks and a leading # or > in a label', () => {
    expect(escapeMarkdown('`code`')).toBe('\\`code\\`');
    expect(escapeMarkdown('# Big')).toBe('\\# Big');
    expect(escapeMarkdown('> Big')).toBe('\\> Big');
    expect(escapeMarkdown('Big # shoot')).toBe('Big # shoot');
  });

  it('escapes Markdown characters in a label', () => {
    expect(escapeMarkdown('*Big* [shoot]_x')).toBe('\\*Big\\* \\[shoot\\]\\_x');
    const odd = {
      ...specialRecap,
      label: '*Big* Shoot',
      three_bird_new: null,
      three_bird_holders: null,
    };
    expect(formatRecap(odd).markdown).toContain('\\*Big\\* Shoot (special shoot, 60 targets)');
  });

  it('names the image file by date', () => {
    expect(recapFilename('2026-09-27')).toBe('sunday-clays-recap-2026-09-27.png');
  });

  it('uses no banned word in any golden', () => {
    const outputs = [regularRecap, specialRecap].flatMap((r) => Object.values(formatRecap(r)));
    for (const text of allStrings(outputs)) expect(text).not.toMatch(BANNED_WORDS);
  });

  it('says "1 round was" and leaves out a special shoot top score nobody has', () => {
    const one = { ...regularRecap, rounds: 1, podium: [] };
    expect(formatRecap(one).text).toContain('and 1 round was shot.');
    expect(formatRecap(one).text).not.toContain('Podium');
    const noTop = { ...specialRecap, top_score: null };
    expect(formatRecap(noTop).text).not.toContain('Top score');
  });

  it('special, Markdown: the title, label and intro lines are separate paragraphs', () => {
    expect(formatRecap(specialRecap).markdown).toBe(SPECIAL_MARKDOWN);
  });
});
