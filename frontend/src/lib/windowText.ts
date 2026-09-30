import { formatDate, formatShortDate } from './format';
import {
  isCustomWindow,
  WINDOW_LABELS,
  windowLabel,
  type TimeWindow,
  type WindowRange,
} from './timeWindowChoice';

/** "Aug 3 – Sep 27" (years only when the two dates fall in different years). */
export function rangeText(range: WindowRange): string {
  if (range.from === null) return `through ${formatDate(range.to)}`;
  return range.from.slice(0, 4) === range.to.slice(0, 4)
    ? `${formatShortDate(range.from)} – ${formatShortDate(range.to)}`
    : `${formatDate(range.from)} – ${formatDate(range.to)}`;
}

/**
 * The name of a window with its dates, as every window tag shows it: "Last 8 weeks · Aug 3 – Sep 27".
 * A custom window is its dates alone; before the range is known it is the bare name.
 */
export function windowTagText(window: TimeWindow, range: WindowRange | null): string {
  if (isCustomWindow(window)) return windowLabel(window);
  return range === null ? WINDOW_LABELS[window] : `${WINDOW_LABELS[window]} · ${rangeText(range)}`;
}

/** Lower-case name for running text: "the last 8 weeks (Aug 3 – Sep 27)". */
export function windowPhrase(window: TimeWindow, range: WindowRange | null): string {
  if (isCustomWindow(window)) return windowLabel(window);
  const name = WINDOW_LABELS[window].replace(/^Last/, 'the last').replace(/^This/, 'this');
  return range === null || range.from === null
    ? name.toLowerCase()
    : `${name.toLowerCase()} (${rangeText(range)})`;
}
