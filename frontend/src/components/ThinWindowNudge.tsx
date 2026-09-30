import type { ReactNode } from 'react';
import { inWindow, useWindowChoice } from '../lib/timeWindowChoice';
import { WidenWindowButtons } from './WidenWindowButtons';

/** Fewer scored Sundays than this in the window is "thin": patterns need more to show. */
export const THIN_WINDOW_SUNDAYS = 12;

export function isThinWindow(sundays: number): boolean {
  return sundays < THIN_WINDOW_SUNDAYS;
}

/**
 * The plain-words note a thin (or empty) window gets instead of a silent, sparse chart: the count,
 * the period, why it matters, and one-tap 12M and All buttons that widen the header window. Draws
 * nothing once the window has enough Sundays. The page's own charts stay put underneath. A `note`,
 * not a `status`: it is part of the settled page, not a loading message.
 */
export function ThinWindowNudge({
  sundays,
  need = 'Weather patterns need more.',
  message,
  action,
  label,
}: {
  /** Scored Sundays inside the window. */
  sundays: number;
  /** The closing sentence: what needs more Sundays. */
  need?: string;
  /** The page's own whole sentence in place of the Sunday count ("No station sheets in ..."). */
  message?: string;
  /** The page's own button in place of 12M and All, for a cause the window does not explain. */
  action?: ReactNode;
  /** An accessible name for the note, when the page has other notes beside it. */
  label?: string;
}) {
  const [window] = useWindowChoice();
  if (!isThinWindow(sundays)) return null;
  const where = inWindow(window);
  const count =
    sundays === 0 ? 'No Sundays' : `Only ${sundays} ${sundays === 1 ? 'Sunday' : 'Sundays'}`;
  return (
    <div
      role="note"
      aria-label={label}
      className="flex min-w-0 flex-col gap-2 rounded-card border border-outline-variant bg-elevated p-3 sm:flex-row sm:items-center"
    >
      <p className="min-w-0 flex-1 break-words text-sm text-text">
        {message ?? `${count} ${where}. ${need}`}
      </p>
      {action !== undefined ? (
        <div className="flex flex-wrap gap-2">{action}</div>
      ) : (
        <WidenWindowButtons />
      )}
    </div>
  );
}
