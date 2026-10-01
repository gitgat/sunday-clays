import { useBumpToggle, type BumpState } from '../api';

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
  date: string;
  postKey: string;
  /** Null when this browser cannot remember a device id: the count shows, the button is off. */
  deviceId: string | null;
  state: BumpState | undefined;
  /** The id of the note that says why bumps are off. */
  noteId: string;
}

/** 🤜🤛 and the count. Nobody is ever shown who bumped; you can bump a post about yourself. */
export function BumpButton({ date, postKey, deviceId, state, noteId }: BumpButtonProps) {
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
  return <LiveBumpButton date={date} postKey={postKey} deviceId={deviceId} state={state} />;
}

function LiveBumpButton({
  date,
  postKey,
  deviceId,
  state,
}: {
  date: string;
  postKey: string;
  deviceId: string;
  state: BumpState | undefined;
}) {
  const { send, failed } = useBumpToggle(date, deviceId, postKey);
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
