import { useEffect, useState } from 'react';
import type { QuerySpec } from '../../../components/charts/explore';
import { Chip } from '../../../components/ui/Chip';
import { formatShortDate } from '../../../lib/format';
import { RangeSlider, Slider } from '../../../components/ui/Slider';
import { Toggle } from '../../../components/ui/Toggle';
import {
  GAUGES,
  RANGE_FILTERS,
  STATUSES,
  type RangeFilter,
  type useExplorerState,
} from '../urlState';

type State = ReturnType<typeof useExplorerState>;

/** "09-27" → "Sep 27" (a leap year, so 02-29 reads too); anything else is shown as typed. */
function monthDay(mmdd: string): string {
  const text = formatShortDate(`2024-${mmdd}`);
  return text === '—' ? mmdd : text;
}

const STATUS_LABELS: Record<(typeof STATUSES)[number], string> = {
  member: 'Member',
  guest: 'Guest',
  deceased: 'Deceased',
};

/** How long a slider must rest before its value reaches the URL and the query runs again. */
export const SETTLE_MS = 300;

type SliderValue = number | readonly [number, number] | null;

interface Draft<T> {
  value: T;
  /** The URL's value when the draft started. */
  base: T;
}

/**
 * Still to be written: the URL holds the value the draft started from, and they differ. A draft
 * that is not unsettled is finished, and useSettledValue drops it.
 */
function unsettled<T extends SliderValue>(draft: Draft<T> | null, value: T): draft is Draft<T> {
  return (
    draft !== null &&
    Object.is(draft.base, value) &&
    JSON.stringify(draft.value) !== JSON.stringify(value)
  );
}

/**
 * A slider's value that follows every step at once but reaches `commit` (the URL, and so the
 * query) only once it has rested for SETTLE_MS, so a drag or a run of arrow key presses runs one
 * query instead of one per step.
 *
 * - A draft is kept only while the URL still holds the value it started from. Once the URL moves
 *   (its own commit lands, or Back or a link brings a new value), or the draft comes back to the
 *   URL's value, the draft is dropped for good, so a later return to that starting value never
 *   brings back its thumb or commits it again. Unmounting cancels it.
 * - Any other URL change re-arms the timer with the newest `commit`, because a useUrlState setter
 *   writes over the URL it last rendered and an older one would undo that change.
 * - A write that lands between this commit and its render drops it; the URL then still holds the
 *   draft's starting value, so the draft commits again once settled.
 */
function useSettledValue<T extends SliderValue>(
  value: T,
  commit: (next: T) => void,
): [T, (next: T) => void] {
  const [draft, setDraft] = useState<Draft<T> | null>(null);
  // Dropped while rendering (React's pattern for resetting state when an input changes), so the
  // finished draft never reaches the screen and a render React discards takes the reset with it.
  if (draft !== null && !unsettled(draft, value)) setDraft(null);
  useEffect(() => {
    if (!unsettled(draft, value)) return undefined;
    const timer = setTimeout(() => commit(draft.value), SETTLE_MS);
    return () => clearTimeout(timer);
  }, [draft, value, commit]);
  return [
    unsettled(draft, value) ? draft.value : value,
    (next) => setDraft({ value: next, base: value }),
  ];
}

function SettledRangeSlider({
  filter,
  state,
}: {
  filter: RangeFilter;
  state: State['ranges'][RangeFilter];
}) {
  const { label, min, max, step, unit } = RANGE_FILTERS[filter];
  const [value, change] = useSettledValue(...state);
  return (
    <RangeSlider
      label={label}
      min={min}
      max={max}
      step={step}
      value={value ?? [min, max]}
      format={(n) => `${n} ${unit}`}
      onChange={([lo, hi]) => change(lo === min && hi === max ? null : [lo, hi])}
    />
  );
}

function SettledMinRounds({ value, commit }: { value: number; commit: (next: number) => void }) {
  const [shown, change] = useSettledValue(value, commit);
  return (
    <Slider label="Minimum rounds per shooter" min={0} max={50} value={shown} onChange={change} />
  );
}

function toggled<T>(list: readonly T[], value: T): T[] {
  return list.includes(value) ? list.filter((v) => v !== value) : [...list, value];
}

/** Count of active filters, for the collapsed "Filters (n)" summary (dates are the header's window). */
export function activeFilterCount(spec: QuerySpec): number {
  const f = spec.filters;
  return [
    f.shooter_ids.length > 0,
    f.statuses.length > 0,
    f.gauges.length > 0,
    f.temp_f,
    f.gust_mph,
    f.precip_in,
    f.min_rounds > 0,
    f.best_round_only,
    f.min_score !== null && f.min_score !== undefined,
    f.ytd !== null && f.ytd !== undefined,
  ].filter(Boolean).length;
}

export function FilterControls({ spec, ranges, set }: Pick<State, 'spec' | 'ranges' | 'set'>) {
  const f = spec.filters;
  const statuses = f.statuses.filter((s): s is (typeof STATUSES)[number] =>
    (STATUSES as readonly string[]).includes(s),
  );
  const gauges = f.gauges.filter((g): g is (typeof GAUGES)[number] =>
    (GAUGES as readonly string[]).includes(g),
  );
  return (
    <div className="flex flex-col gap-4">
      <div role="group" aria-label="Status" className="flex flex-wrap gap-2">
        {STATUSES.map((s) => (
          <Chip
            key={s}
            selected={statuses.includes(s)}
            onClick={() => set.statuses(toggled(statuses, s))}
          >
            {STATUS_LABELS[s]}
          </Chip>
        ))}
      </div>
      <div role="group" aria-label="Gauge" className="flex flex-wrap gap-2">
        {GAUGES.map((g) => (
          <Chip
            key={g}
            selected={gauges.includes(g)}
            onClick={() => set.gauges(toggled(gauges, g))}
          >
            {g === 'unspecified' ? 'Not recorded' : g}
          </Chip>
        ))}
      </div>
      {f.shooter_ids.length > 0 && (
        <div>
          <Chip onRemove={() => set.shooterIds([])} removeLabel="Clear shooter filter">
            {f.shooter_ids.length === 1 ? '1 shooter' : `${f.shooter_ids.length} shooters`}
          </Chip>
        </div>
      )}
      {((f.min_score ?? null) !== null || (f.ytd ?? null) !== null) && (
        <div className="flex flex-wrap gap-2">
          {f.min_score !== null && f.min_score !== undefined && (
            <Chip onRemove={() => set.minScore(null)} removeLabel="Clear minimum score">
              {`Rounds of ${String(f.min_score)} or better`}
            </Chip>
          )}
          {f.ytd !== null && f.ytd !== undefined && (
            <Chip onRemove={() => set.ytd(null)} removeLabel="Clear year to date">
              {`Each year to ${monthDay(f.ytd)}`}
            </Chip>
          )}
        </div>
      )}
      {(Object.keys(RANGE_FILTERS) as RangeFilter[]).map((key) => (
        <SettledRangeSlider key={key} filter={key} state={ranges[key]} />
      ))}
      <SettledMinRounds value={f.min_rounds} commit={set.minRounds} />
      <Toggle label="Best round only" checked={f.best_round_only} onChange={set.bestOnly} />
    </div>
  );
}
