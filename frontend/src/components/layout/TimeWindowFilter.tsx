import { useId, useState } from 'react';
import {
  CUSTOM_SHORT_LABEL,
  TIME_WINDOWS,
  WINDOW_LABELS,
  WINDOW_SHORT_LABELS,
  isCustomWindow,
  useWindowChoice,
  windowLabel,
  parseCustomWindow,
  type TimeWindowPreset,
} from '../../lib/timeWindowChoice';
import { formatShortDate } from '../../lib/format';
import { rangeText } from '../../lib/windowText';
import { cx } from '../ui/cx';
import { CustomWindowSheet } from './CustomWindowSheet';

/**
 * A custom range as the phone select's text: "Aug 3 – Sep 27" inside one year; across years the
 * days go ("Aug '25 – Sep '26") so it still fits the top bar at 390 px. The title has it in full.
 */
function customText(from: string, to: string): string {
  if (from.slice(0, 4) === to.slice(0, 4)) return rangeText({ from, to });
  const monthYear = (iso: string) =>
    `${formatShortDate(iso).split(' ')[0] ?? ''} '${iso.slice(2, 4)}`;
  return `${monthYear(from)} – ${monthYear(to)}`;
}

const CUSTOM_HINT = 'Pick your own start and end dates';

/**
 * The global time window (`?w=`, default last 8 weeks); the default is never written. The desktop
 * content header shows a segmented control of 44 px buttons; the phone top bar shows one compact 44 px select
 * with short labels (8W, 3M, 6M, 12M, YTD, All, Custom) so it stays on one row of the sticky header.
 * Custom opens a sheet for a start and an end date (`?w=start..end`).
 */
export function TimeWindowFilter({ variant = 'segmented' }: { variant?: 'segmented' | 'select' }) {
  const [selected, setSelected] = useWindowChoice();
  const [sheetOpen, setSheetOpen] = useState(false);
  const descriptionId = useId();
  const custom = isCustomWindow(selected);
  const label = windowLabel(selected);
  // A custom range is the selected text, so phones (no hover) see its dates.
  const dates = custom ? parseCustomWindow(selected) : null;
  const selectText = dates === null ? 'Custom…' : customText(dates.from, dates.to);
  const sheet = <CustomWindowSheet open={sheetOpen} onClose={() => setSheetOpen(false)} />;
  if (variant === 'select') {
    return (
      <span className="inline-flex shrink-0">
        <select
          aria-label="Time window"
          aria-describedby={`${descriptionId}-selected`}
          title={label}
          value={custom ? 'custom' : selected}
          onChange={(event) => {
            const next = event.target.value;
            // Re-choosing the selected option fires no change event, so a custom window offers "edit".
            if (next === 'custom' || next === 'edit') setSheetOpen(true);
            else setSelected(next as TimeWindowPreset);
          }}
          className={cx(
            'min-h-11 rounded-button border border-outline-variant bg-surface px-0.5 text-sm text-text',
            custom ? 'w-auto max-w-[10.5rem]' : 'w-[5.5rem]',
          )}
        >
          {TIME_WINDOWS.map((w) => (
            // Short text keeps the phone top bar on one row; the full wording stays for screen readers.
            <option key={w} value={w} aria-label={WINDOW_LABELS[w]}>
              {WINDOW_SHORT_LABELS[w]}
            </option>
          ))}
          <option value="custom" aria-label="Custom dates">
            {selectText}
          </option>
          {custom && <option value="edit">Change dates…</option>}
        </select>
        <span id={`${descriptionId}-selected`} className="sr-only">
          {label}
        </span>
        {sheet}
      </span>
    );
  }
  return (
    <div role="group" aria-label="Time window" className="flex flex-wrap items-center gap-1">
      {TIME_WINDOWS.map((w) => (
        <span key={w} className="contents">
          <button
            type="button"
            aria-pressed={w === selected}
            aria-describedby={`${descriptionId}-${w}`}
            title={WINDOW_LABELS[w]}
            onClick={() => setSelected(w)}
            className={cx(
              'inline-flex min-h-11 min-w-11 items-center justify-center rounded-button border px-3 text-sm',
              w === selected
                ? 'border-accent bg-accent/15 font-medium text-text'
                : 'border-outline-variant text-text-muted hover:text-text',
            )}
          >
            {WINDOW_SHORT_LABELS[w]}
          </button>
          <span id={`${descriptionId}-${w}`} className="sr-only">
            {WINDOW_LABELS[w]}
          </span>
        </span>
      ))}
      <button
        type="button"
        aria-haspopup="dialog"
        aria-pressed={custom}
        aria-describedby={`${descriptionId}-custom`}
        onClick={() => setSheetOpen(true)}
        className={cx(
          'inline-flex min-h-11 min-w-11 items-center justify-center rounded-button border px-3 text-sm',
          custom
            ? 'border-accent bg-accent/15 font-medium text-text'
            : 'border-outline-variant text-text-muted hover:text-text',
        )}
      >
        {CUSTOM_SHORT_LABEL}
      </button>
      <span id={`${descriptionId}-custom`} className="sr-only">
        {custom ? label : CUSTOM_HINT}
      </span>
      {sheet}
    </div>
  );
}
