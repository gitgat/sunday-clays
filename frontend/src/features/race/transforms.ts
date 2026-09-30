import type { LeaderboardFrame, TabularData } from '../../components/charts/types';
import type { HistoryFrame } from './api';

/**
 * One chart name per shooter across ALL frames: a display name held by more than one shooter_id
 * anywhere in the race becomes `<name> #<id>` in every frame, so raceOption's per-frame
 * de-duplication never renames a bar mid-race.
 */
export function racerNames(frames: readonly HistoryFrame[]): ReadonlyMap<number, string> {
  const idsByName = new Map<string, Set<number>>();
  for (const frame of frames) {
    for (const r of frame.rows) {
      const ids = idsByName.get(r.display_name) ?? new Set<number>();
      ids.add(r.shooter_id);
      idsByName.set(r.display_name, ids);
    }
  }
  const names = new Map<number, string>();
  for (const [name, ids] of idsByName) {
    for (const id of ids) names.set(id, ids.size > 1 ? `${name} #${String(id)}` : name);
  }
  return names;
}

/** A LeaderboardHistoryOut frame as Plan 07's typed race/bump builder input (D17; rows keep the API order). */
export function toLeaderboardFrame(
  frame: HistoryFrame,
  names: ReadonlyMap<number, string>,
): LeaderboardFrame {
  return {
    date: frame.event_date,
    rows: frame.rows.map((r) => ({
      id: r.shooter_id,
      name: names.get(r.shooter_id) ?? r.display_name,
      value: r.value,
      rank: r.rank,
    })),
  };
}

/** One frame of the race as a bar table for ChartFrame's table/CSV: shooter → value (already ordered by the API). */
export function frameTable(
  frame: HistoryFrame | undefined,
  valueLabel: string,
  names?: ReadonlyMap<number, string>,
): TabularData {
  return {
    columns: [
      { key: 'display_name', label: 'Shooter', type: 'string' },
      { key: 'value', label: valueLabel, type: 'number' },
    ],
    // shooter_id is not a column: it lets an insight's `s:{id}` find the bar (Plan 12 hlLabels).
    rows: (frame?.rows ?? []).map((row) => ({
      display_name: names?.get(row.shooter_id) ?? row.display_name,
      value: row.value,
      shooter_id: row.shooter_id,
    })),
  };
}

/** Every frame's top-N as long rows for the bump chart's table/CSV: event date × shooter → rank. */
export function bumpTable(
  frames: readonly HistoryFrame[],
  names?: ReadonlyMap<number, string>,
): TabularData {
  return {
    columns: [
      { key: 'event_date', label: 'Event', type: 'date' },
      { key: 'display_name', label: 'Shooter', type: 'string' },
      { key: 'rank', label: 'Rank', type: 'int' },
    ],
    rows: frames.flatMap((frame) =>
      frame.rows.map((row) => ({
        event_date: frame.event_date,
        display_name: names?.get(row.shooter_id) ?? row.display_name,
        rank: row.rank,
      })),
    ),
  };
}
