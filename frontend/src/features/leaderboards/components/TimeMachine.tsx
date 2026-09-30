import { formatEventDate, snapIndex } from '../labels';

export interface TimeMachineProps {
  /** Every has_scores event date, ascending (LeaderboardOut.event_dates). */
  dates: readonly string[];
  /** Selected as_of; null means "latest". */
  asOf: string | null;
  onChange: (asOf: string | null) => void;
}

const STEP =
  'inline-flex min-h-11 min-w-11 items-center justify-center rounded-button border border-outline-variant px-3 text-accent disabled:opacity-40';

/**
 * "Board as of": moves the end of the board's window to a Sunday. A slider for a long jump and step
 * buttons for one Sunday at a time (a phone slider cannot land on a specific date); the last Sunday is
 * the same as "Latest", which clears the date.
 */
export function TimeMachine({ dates, asOf, onChange }: TimeMachineProps) {
  const index = snapIndex(dates, asOf);
  const first = dates[0];
  const shown = dates[index];
  if (first === undefined || shown === undefined) return null;
  const last = dates.length - 1;
  // The thumb parks on the last event at or before as_of, but the label names the date actually queried.
  const labelDate = asOf ?? shown;
  const moveTo = (to: number) => {
    // Landing on the last Sunday is the latest board: the date is cleared so the link stays "latest".
    onChange(to >= last ? null : (dates[to] as string));
  };
  return (
    <div className="flex flex-col gap-2 rounded-card bg-elevated p-3">
      <div className="flex items-center justify-between gap-2">
        <label htmlFor="leaderboard-as-of" className="text-sm text-text-muted">
          Board as of
        </label>
        <output htmlFor="leaderboard-as-of" className="font-medium">
          {asOf === null ? 'Latest' : formatEventDate(labelDate)}
        </output>
      </div>
      <input
        id="leaderboard-as-of"
        type="range"
        min={0}
        max={last}
        step={1}
        value={index}
        aria-valuetext={formatEventDate(labelDate)}
        onChange={(event) => {
          moveTo(Number(event.currentTarget.value));
        }}
        className="min-h-11 w-full accent-primary"
      />
      <div className="flex items-center justify-between gap-2 text-xs text-text-muted">
        <span>{formatEventDate(first)}</span>
        <span className="flex items-center gap-2">
          <button
            type="button"
            aria-label="Previous Sunday"
            disabled={index === 0}
            onClick={() => {
              moveTo(index - 1);
            }}
            className={STEP}
          >
            ◀
          </button>
          <button
            type="button"
            aria-label="Next Sunday"
            disabled={asOf === null}
            onClick={() => {
              moveTo(index + 1);
            }}
            className={STEP}
          >
            ▶
          </button>
          <button
            type="button"
            onClick={() => {
              onChange(null);
            }}
            disabled={asOf === null}
            className={`${STEP} text-sm`}
          >
            Latest
          </button>
        </span>
      </div>
    </div>
  );
}
