import { describe, expect, it } from 'vitest';
import { allStrings, BANNED_WORDS, OUTSIDER_BANNED } from '../../test/language';
import { escapeMarkdown, formatRecap, recapFilename } from './format';
import { regularRecap, specialRecap } from './mocks';

const REGULAR_TEXT = `Sunday Clays · Sunday, September 27, 2026

Turnout: 24 came out and 27 rounds were shot.

This week
- Scores up 3 Sundays straight for Alvin McGinnis: 33, 36, then 46.
- A friendly Sunday: scores ran about 3 targets over a typical Sunday for this crowd. The middle score was 40.

Milestones
- Wylie Marsden has now broken 4,000 targets on Sundays: 4,018 in all.
- Preston Abernathy: Clays Broken - 1,000
- Pat Kim: Clays Broken - 1,000
- Club: 7,500 rounds shot all time!`;

const REGULAR_MARKDOWN = `**Sunday Clays · Sunday, September 27, 2026**

Turnout: 24 came out and 27 rounds were shot.

**This week**
- Scores up 3 Sundays straight for Alvin McGinnis: 33, 36, then 46.
- A friendly Sunday: scores ran about 3 targets over a typical Sunday for this crowd. The middle score was 40.

**Milestones**
- Wylie Marsden has now broken 4,000 targets on Sundays: 4,018 in all.
- Preston Abernathy: Clays Broken - 1,000
- Pat Kim: Clays Broken - 1,000
- Club: 7,500 rounds shot all time!`;

const SPECIAL_TEXT = `Sunday Clays · Sunday, September 20, 2026
3-Bird Shoot (special shoot, 60 targets)

40 shooters came out.
3-Bird Shoot trophy: 12 earned it for the first time today. 58 shooters hold it now.
Top score: 55 of 60.

Milestones
- Ike Hadley: Clays Broken - 500`;

const SPECIAL_MARKDOWN = `**Sunday Clays · Sunday, September 20, 2026**

3-Bird Shoot (special shoot, 60 targets)

40 shooters came out.

3-Bird Shoot trophy: 12 earned it for the first time today. 58 shooters hold it now.

Top score: 55 of 60.

**Milestones**
- Ike Hadley: Clays Broken - 500`;

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
    const bare = { ...regularRecap, head_count: null, insights: [], milestones: [] };
    const text = formatRecap(bare).text;
    expect(text).toContain('Turnout: 23 shooters and 27 rounds were shot.');
    expect(text).not.toContain('This week');
    expect(text).not.toContain('Milestones');
    expect(formatRecap(bare).markdown).not.toContain('Milestones');
  });

  it('carries nothing the club newsletter covers, and no link', () => {
    for (const r of [regularRecap, specialRecap]) {
      for (const out of Object.values(formatRecap(r))) {
        expect(out).not.toMatch(/podium|personal best|first-timer|See every score|https?:/i);
      }
    }
    expect(Object.keys(regularRecap)).not.toEqual(
      expect.arrayContaining(['podium', 'pbs', 'first_timers', 'trophies']),
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

  it('orders turnout, This week, Milestones, and hides This week when empty', () => {
    const text = formatRecap(regularRecap).text;
    expect(text.indexOf('Turnout:')).toBeLessThan(text.indexOf('This week'));
    expect(text.indexOf('This week')).toBeLessThan(text.indexOf('Milestones'));
    const none = formatRecap({ ...regularRecap, insights: [] });
    expect(none.text).not.toContain('This week');
    expect(none.markdown).not.toContain('This week');
  });

  it('a special shoot lists its insights right after the intro too', () => {
    const text = formatRecap({ ...specialRecap, insights: ['A friendly Sunday.'] }).text;
    expect(text).toContain(
      'Top score: 55 of 60.\n\nThis week\n- A friendly Sunday.\n\nMilestones\n- Ike Hadley',
    );
  });

  it('escapes Markdown characters in a milestone line', () => {
    const md = formatRecap({ ...regularRecap, milestones: ['A_B: *Big* [one]'] }).markdown;
    expect(md).toContain('- A\\_B: \\*Big\\* \\[one\\]');
  });

  it('escapes Markdown characters in an insight sentence', () => {
    const md = formatRecap({ ...regularRecap, insights: ['Shot *48* [club] record'] }).markdown;
    expect(md).toContain('- Shot \\*48\\* \\[club\\] record');
  });

  it('every line stands alone: nothing only a site visitor would understand (R3)', () => {
    const outputs = [regularRecap, specialRecap].flatMap((r) => Object.values(formatRecap(r)));
    for (const text of allStrings(outputs)) expect(text).not.toMatch(OUTSIDER_BANNED);
    expect(OUTSIDER_BANNED.test('Well above their usual for a day like this')).toBe(true);
    for (const bad of ['Your best', 'a Silver trophy', 'Tap here', 'See the chart', 'Level 3'])
      expect(OUTSIDER_BANNED.test(bad)).toBe(true);
    expect(OUTSIDER_BANNED.test('Welcome back after a long break')).toBe(false);
  });

  it('uses no banned word in any golden', () => {
    const outputs = [regularRecap, specialRecap].flatMap((r) => Object.values(formatRecap(r)));
    for (const text of allStrings(outputs)) expect(text).not.toMatch(BANNED_WORDS);
  });

  it('says "1 round was" and leaves out a special shoot top score nobody has', () => {
    const one = { ...regularRecap, rounds: 1 };
    expect(formatRecap(one).text).toContain('and 1 round was shot.');
    const noTop = { ...specialRecap, top_score: null };
    expect(formatRecap(noTop).text).not.toContain('Top score');
  });

  it('special, Markdown: the title, label and intro lines are separate paragraphs', () => {
    expect(formatRecap(specialRecap).markdown).toBe(SPECIAL_MARKDOWN);
  });
});
