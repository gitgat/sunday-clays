import type { components } from '../../api/schema';

export type ThrownOut = components['schemas']['ThrownOutOut'];

/** Mirrors backend `domain/thrown_out.py`; the two must return identical text. */
export const SUNDAY_THROWN_OUT = 'A station was thrown out this Sunday';

/** Same text as the server's `templates.THROWN_OUT_RECAP_HOW`. */
export const THROWN_OUT_RECAP_LINE =
  'A station was thrown out this Sunday. Its results count; its scores stay out of averages and PBs.';

export function thrownOutPhrase(items: readonly ThrownOut[]): string {
  const stations = items.filter((i) => i.station_label !== null);
  const [first] = stations;
  if (!first) return SUNDAY_THROWN_OUT;
  if (stations.length === 1) {
    const base = `Station ${first.station_label} was thrown out`;
    return first.credited
      ? `${base}; everyone was credited ${first.target_count}/${first.target_count}`
      : base;
  }
  const labels = stations.map((s) => s.station_label);
  const last = labels[labels.length - 1];
  const head = labels.slice(0, -1).join(', ');
  const base = `Stations ${head} and ${last} were thrown out`;
  return stations.every((s) => s.credited) ? `${base}; everyone was credited in full` : base;
}

export function thrownOutBanner(items: readonly ThrownOut[]): string {
  return `${thrownOutPhrase(items)}. Today's results and standings count, marked *. These scores are left out of averages, PBs and station stats.`;
}

export function excludedNote(n: number): string | null {
  return n === 0 ? null : `${n} round${n === 1 ? '' : 's'} marked * not in the average`;
}
