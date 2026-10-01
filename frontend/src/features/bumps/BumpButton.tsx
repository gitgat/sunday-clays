import { useEffect } from 'react';
import { useBumpToggle, type BumpCounts, type BumpState, type BumpsKey } from './api';

export const BUMP_FAILED = 'Couldn’t send that bump';
const FIST = '🤜🤛';
const BUTTON =
  'inline-flex min-h-11 min-w-11 items-center justify-center gap-2 rounded-button border px-3 text-sm tabular-nums transition-colors disabled:cursor-not-allowed disabled:opacity-60';

function label(state: BumpState | undefined): string {
  const n = state?.bumps ?? 0;
  return `Fist bump, ${String(n)} ${n === 1 ? 'bump' : 'bumps'}`;
}

function Face({ state }: { state: BumpState | undefined }) {
  return (
    <>
      <span aria-hidden="true">{FIST}</span>
      <span aria-hidden="true">{state?.bumps ?? 0}</span>
    </>
  );
}

export interface BumpButtonProps {
  /** The counts query this button reads and writes (its section's BumpsProvider). */
  queryKey: BumpsKey;
  insightKey: string;
  /** Null when this browser cannot remember a device id: the count shows, the button is off. */
  deviceId: string | null;
  state: BumpState | undefined;
  /** The id of the note that says why bumps are off. */
  noteId: string;
  /** Every count the section has on screen: seeds a tap while a new key set loads. */
  counts?: BumpCounts;
  /** The section's shared live region: told once when a bump fails, and cleared on the next tap. */
  announce?: (message: string) => void;
  /** The id of the insight's headline, so a screen reader hears what is being bumped. */
  describedBy?: string;
}

/** 🤜🤛 and the count. Nobody is ever shown who bumped; you can bump an insight about yourself. */
export function BumpButton({
  queryKey,
  insightKey,
  deviceId,
  state,
  noteId,
  counts,
  announce,
  describedBy,
}: BumpButtonProps) {
  if (deviceId === null) {
    return (
      <button
        type="button"
        disabled
        aria-label={label(state)}
        aria-describedby={describedBy === undefined ? noteId : `${noteId} ${describedBy}`}
        className={`${BUTTON} border-outline-variant`}
      >
        <Face state={state} />
      </button>
    );
  }
  return (
    <LiveBumpButton
      queryKey={queryKey}
      insightKey={insightKey}
      deviceId={deviceId}
      state={state}
      counts={counts}
      announce={announce}
      describedBy={describedBy}
    />
  );
}

function LiveBumpButton({
  queryKey,
  insightKey,
  deviceId,
  state,
  counts,
  announce,
  describedBy,
}: {
  queryKey: BumpsKey;
  insightKey: string;
  deviceId: string;
  state: BumpState | undefined;
  counts: BumpCounts | undefined;
  announce: ((message: string) => void) | undefined;
  describedBy: string | undefined;
}) {
  const { send, failed } = useBumpToggle(queryKey, deviceId, insightKey, counts);
  const bumped = state?.bumped ?? false;
  useEffect(() => {
    if (failed) announce?.(BUMP_FAILED);
  }, [failed, announce]);
  return (
    <span className="inline-flex flex-wrap items-center gap-2">
      <button
        type="button"
        aria-pressed={bumped}
        aria-label={label(state)}
        aria-describedby={describedBy}
        onClick={() => {
          announce?.('');
          send(!bumped);
        }}
        className={`${BUTTON} ${bumped ? 'border-accent bg-primary' : 'border-outline-variant'}`}
      >
        <Face state={state} />
      </button>
      {failed && <span className="text-sm text-text-muted">{BUMP_FAILED}</span>}
    </span>
  );
}
