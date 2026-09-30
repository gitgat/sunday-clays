import { formatDate } from '../../lib/format';
import {
  isCustomWindow,
  parseCustomWindow,
  WINDOW_LABELS,
  type TimeWindow,
} from '../../lib/timeWindowChoice';

/** Aug 3, 2026 → Aug 3 (the year is dropped only when both ends share it). */
function shortDate(iso: string): string {
  return formatDate(iso).replace(/, \d{4}$/, '');
}

/**
 * "Aug 3 – Sep 27" when both dates fall in the year of `latest` (the latest scored Sunday, so the year
 * is understood); otherwise both years are spelled out: "Sep 29, 2025 – Sep 27, 2026", "Jan 7, 2024 – Dec 29, 2024".
 */
export function datesText(start: string, end: string, latest: string | null = null): string {
  const year = latest?.slice(0, 4);
  return start.slice(0, 4) === year && end.slice(0, 4) === year
    ? `${shortDate(start)} – ${shortDate(end)}`
    : `${formatDate(start)} – ${formatDate(end)}`;
}

/** "Last 8 weeks · Aug 3 – Sep 27"; a custom window is its dates alone. */
export function windowTag(
  window: TimeWindow,
  start: string,
  end: string,
  latest: string | null,
): string {
  const dates = datesText(start, end, latest);
  return isCustomWindow(window) ? dates : `${WINDOW_LABELS[window]} · ${dates}`;
}

const IN_WORDS = {
  '8w': 'the last 8 weeks',
  '3m': 'the last 3 months',
  '6m': 'the last 6 months',
  '12m': 'the last 12 months',
  ytd: 'this year so far',
  all: 'all time',
} as const;

/** "the last 8 weeks", "this year so far", "Aug 3 – Sep 27": for "Only 7 Sundays in ...". */
export function windowInWords(window: TimeWindow): string {
  if (!isCustomWindow(window)) return IN_WORDS[window];
  const dates = parseCustomWindow(window);
  return dates === null ? 'these dates' : datesText(dates.from, dates.to);
}

/** "Only 7 Sundays in the last 8 weeks." / "No Sundays with scores in the last 8 weeks." */
export function sundaysNote(count: number, window: TimeWindow): string {
  const where = windowInWords(window);
  if (count === 0) return `No Sundays with scores in ${where}.`;
  return `Only ${String(count)} Sunday${count === 1 ? '' : 's'} in ${where}.`;
}

/** A window with fewer scored Sundays than this reads as thin. */
export const THIN_SUNDAYS = 4;
