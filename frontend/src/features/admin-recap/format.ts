import type { Recap } from './api';

const LONG = new Intl.DateTimeFormat('en-US', {
  weekday: 'long',
  month: 'long',
  day: 'numeric',
  year: 'numeric',
  timeZone: 'UTC',
});

/** Sunday, September 27, 2026 */
function longDay(iso: string): string {
  return LONG.format(new Date(`${iso}T00:00:00Z`));
}

function shooters(n: number): string {
  return n === 1 ? '1 shooter' : `${String(n)} shooters`;
}

export function escapeMarkdown(text: string): string {
  return text.replace(/([*_`[\]])/g, '\\$1').replace(/^([#>])/gm, '\\$1');
}

export function recapFilename(date: string): string {
  return `sunday-clays-recap-${date}.png`;
}

interface Section {
  heading: string;
  lines: string[];
}

function threeBirdLine(r: Recap): string | null {
  const holders = r.three_bird_holders;
  const fresh = r.three_bird_new;
  if (holders === null || holders === 0 || fresh === null) return null;
  if (fresh === holders) return `3-Bird Shoot trophy: ${shooters(holders)} earned it today.`;
  if (fresh === 0) return `3-Bird Shoot trophy: ${shooters(holders)} hold it now.`;
  return `3-Bird Shoot trophy: ${String(fresh)} earned it for the first time today. ${shooters(holders)} hold it now.`;
}

function rounds(n: number): string {
  return n === 1 ? '1 round was' : `${String(n)} rounds were`;
}

/** Plain text and Markdown of one Sunday's recap, built to complement the club newsletter (owner,
 * 2026-10-05): podium, personal bests and new shooters are the newsletter's, so this carries the
 * turnout, "This week" and "Milestones". Names are only in the server's sentences and lines:
 * positive or neutral facts. Every line stands alone for a reader who never visits the site. */
export function formatRecap(r: Recap): { text: string; markdown: string } {
  const special = r.kind === 'special';
  const intro: string[] = [];
  const md = (s: string) => escapeMarkdown(s);
  const sections: Section[] = [];
  if (special) {
    const count = r.head_count ?? r.shooters;
    intro.push(`${shooters(count)} came out.`);
    const trophy = threeBirdLine(r);
    if (trophy !== null) intro.push(trophy);
    if (r.top_score !== null)
      intro.push(`Top score: ${String(r.top_score)} of ${String(r.target_total)}.`);
  } else {
    const who = r.head_count === null ? shooters(r.shooters) : `${String(r.head_count)} came out`;
    intro.push(`Turnout: ${who} and ${rounds(r.rounds)} shot.`);
  }
  if (r.insights.length > 0) sections.push({ heading: 'This week', lines: [...r.insights] });
  if (r.milestones.length > 0) sections.push({ heading: 'Milestones', lines: [...r.milestones] });
  const title = `Sunday Clays · ${longDay(r.event_date)}`;
  const labelLine =
    special && r.label !== null
      ? `${r.label} (special shoot, ${String(r.target_total)} targets)`
      : null;

  const text = [
    [title, ...(labelLine === null ? [] : [labelLine])].join('\n'),
    intro.join('\n'),
    ...sections.map((s) => [s.heading, ...s.lines.map((l) => `- ${l}`)].join('\n')),
  ].join('\n\n');

  const markdown = [
    [`**${md(title)}**`, ...(labelLine === null ? [] : [md(labelLine)])].join('\n\n'),
    intro.map(md).join('\n\n'),
    ...sections.map((s) =>
      [`**${md(s.heading)}**`, ...s.lines.map((l) => `- ${md(l)}`)].join('\n'),
    ),
  ].join('\n\n');

  return { text, markdown };
}
