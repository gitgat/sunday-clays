import { formatShortDate } from '../../lib/format';
import type { TimeWindow, WindowRange } from '../../lib/timeWindow';
import { windowTagText } from '../../lib/windowText';
import { slugify } from '../share/filenames';
import type { ShooterSummary } from './api';

export type SummaryLine = [label: string, value: string, extra: string];

/** The card's lines; a 0 value or a streak below 2 is left out, never shown as 0 (D19). */
export function summaryLines(s: ShooterSummary): SummaryLine[] {
  const special =
    s.special_sundays === 0
      ? ''
      : `(${String(s.special_sundays)} special shoot${s.special_sundays === 1 ? '' : 's'})`;
  const lines: SummaryLine[] = [['Sundays shot', String(s.sundays), special]];
  if (s.rounds > 0 && s.average !== null) {
    lines.push(['Rounds · Average', `${String(s.rounds)} · ${s.average.toFixed(1)}`, '']);
  }
  if (s.rounds > 0 && s.best !== null) {
    lines.push([
      'Best round',
      `${String(s.best.score)} · ${formatShortDate(s.best.event_date)}`,
      '',
    ]);
  }
  if (s.pbs_set > 0) lines.push(['Personal bests', String(s.pbs_set), '']);
  if (s.trophies > 0) {
    const names = s.trophy_names.join(', ');
    lines.push([
      'Trophies earned',
      String(s.trophies),
      s.trophies > s.trophy_names.length ? `${names}, …` : names,
    ]);
  }
  if (s.longest_streak >= 2) {
    lines.push(['Longest streak', `${String(s.longest_streak)} Sundays in a row`, '']);
  }
  return lines;
}

/** "Last 3 months · Jul 6 – Sep 27", "All time · through Sep 27, 2026", or a custom window's dates. */
export function windowLine(window: TimeWindow, range: WindowRange): string {
  return windowTagText(window, range);
}

export function summaryFilename(name: string, from: string | null, to: string): string {
  return `sunday-clays-${slugify(name)}-${from ?? 'all'}-to-${to}.png`;
}
