import { useBumpToggle, type BumpCounts, type BumpState, type BumpsKey } from './api';

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
}

/** 🤜🤛 and the count. Nobody is ever shown who bumped; you can bump an insight about yourself. */
export function BumpButton({
  queryKey,
  insightKey,
  deviceId,
  state,
  noteId,
  counts,
}: BumpButtonProps) {
  if (deviceId === null) {
    return (
      <button
        type="button"
        disabled
        aria-label={label(state)}
        aria-describedby={noteId}
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
    />
  );
}

function LiveBumpButton({
  queryKey,
  insightKey,
  deviceId,
  state,
  counts,
}: {
  queryKey: BumpsKey;
  insightKey: string;
  deviceId: string;
  state: BumpState | undefined;
  counts: BumpCounts | undefined;
}) {
  const { send, failed } = useBumpToggle(queryKey, deviceId, insightKey, counts);
  const bumped = state?.bumped ?? false;
  return (
    <span className="inline-flex flex-wrap items-center gap-2">
      <button
        type="button"
        aria-pressed={bumped}
        aria-label={label(state)}
        onClick={() => send(!bumped)}
        className={`${BUTTON} ${bumped ? 'border-accent bg-primary' : 'border-outline-variant'}`}
      >
        <Face state={state} />
      </button>
      {failed && (
        <span role="alert" className="text-sm text-text-muted">
          Couldn’t send that bump
        </span>
      )}
    </span>
  );
}
