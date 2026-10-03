import { ordinal } from '../home/format';
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

/** "A", "A and B", "A, B and C" */
function joinNames(names: readonly string[]): string {
  if (names.length <= 1) return names.join('');
  return `${names.slice(0, -1).join(', ')} and ${names.slice(-1).join('')}`;
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
  /** Plain text writes the lines without "- " (the podium); Markdown always lists them. */
  plainBullets: boolean;
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

/** Plain text and Markdown of one Sunday's recap (Plan 19 §3.3.3). Names are only podium, PBs,
 * trophies and first-timers: positive or neutral facts (R2). */
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
    if (r.podium.length > 0) {
      sections.push({
        heading: 'Podium (best round of the day)',
        plainBullets: false,
        lines: r.podium.map(
          (p) =>
            `${p.tied ? 'Tied ' : ''}${ordinal(p.place)}: ${joinNames(p.names)} — ${String(p.score)}`,
        ),
      });
    }
    if (r.pbs.length > 0) {
      sections.push({
        heading: 'New personal bests',
        plainBullets: true,
        lines: r.pbs.map(
          (p) => `${p.display_name}: ${String(p.score)} (was ${String(p.previous)})`,
        ),
      });
    }
  }
  const trophyLines = [
    ...r.trophies.map((t) => `${t.display_name}: ${t.items.join(', ')}`),
    ...r.club_milestones.map((m) => `Club: ${m}`),
  ];
  if (trophyLines.length > 0) {
    sections.push({ heading: 'Milestones and trophies', plainBullets: true, lines: trophyLines });
  }
  if (r.first_timers.length > 0) {
    sections.push({
      heading: 'Welcome to our first-timers',
      plainBullets: true,
      lines: [...r.first_timers],
    });
  }
  const title = `Sunday Clays · ${longDay(r.event_date)}`;
  const labelLine =
    special && r.label !== null
      ? `${r.label} (special shoot, ${String(r.target_total)} targets)`
      : null;

  const text = [
    [title, ...(labelLine === null ? [] : [labelLine])].join('\n'),
    intro.join('\n'),
    ...sections.map((s) =>
      [s.heading, ...s.lines.map((l) => (s.plainBullets ? `- ${l}` : l))].join('\n'),
    ),
    `See every score: ${r.link}`,
  ].join('\n\n');

  const markdown = [
    [`**${md(title)}**`, ...(labelLine === null ? [] : [md(labelLine)])].join('\n\n'),
    intro.map(md).join('\n\n'),
    ...sections.map((s) =>
      [`**${md(s.heading)}**`, ...s.lines.map((l) => `- ${md(l)}`)].join('\n'),
    ),
    `[See every score](${r.link})`,
  ].join('\n\n');

  return { text, markdown };
}
