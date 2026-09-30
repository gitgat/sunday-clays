import type { ReactNode } from 'react';
import { Button } from '../../components/ui/Button';
import { formatShortDate } from '../../lib/format';
import type { EraSel } from './api';

export function ToggleButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={`min-h-11 min-w-11 rounded-button border px-4 ${active ? 'border-accent bg-primary text-text' : 'border-outline-variant text-text-muted'}`}
    >
      {children}
    </button>
  );
}

/** The nudge's "All setups" button: the empty result is the setup choice's doing, not the window's. */
export function AllSetupsButton({ onClick }: { onClick: () => void }) {
  return (
    <Button variant="tonal" aria-label="Show all setups" onClick={onClick}>
      All setups
    </Button>
  );
}

/**
 * Which station setups count: each station since its latest reset, or every setup it has had.
 * Shared by the page and the profile. `resetDate` is the newest reset on or before today.
 */
export function EraToggle({
  era,
  onChange,
  resetDate = null,
}: {
  era: EraSel;
  onChange: (next: EraSel) => void;
  resetDate?: string | null;
}) {
  return (
    <div className="flex min-w-0 flex-col gap-1">
      <div role="group" aria-label="Station setups" className="flex flex-wrap gap-2">
        <ToggleButton
          active={era === 'current'}
          onClick={() => {
            onChange('current');
          }}
        >
          {resetDate === null
            ? 'Since last reset'
            : `Since last reset (${formatShortDate(resetDate)})`}
        </ToggleButton>
        <ToggleButton
          active={era === 'all'}
          onClick={() => {
            onChange('all');
          }}
        >
          All setups
        </ToggleButton>
      </div>
      {resetDate !== null && (
        <p className="text-sm text-text-muted">
          Each station counts from its own latest reset; {formatShortDate(resetDate)} is the most
          recent one.
        </p>
      )}
    </div>
  );
}
