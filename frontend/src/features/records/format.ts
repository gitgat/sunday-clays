import type { TabularRow } from '../../components/charts/types';

type ShooterValue = { shooter_id: number; display_name: string; value: number };

/** Each row with its chart label: a display name held by two shooters (e.g. first-name-only guests) gets `#<id>`. */
function labelled(rows: readonly ShooterValue[]): { label: string; row: ShooterValue }[] {
  const names = rows.map((row) => row.display_name);
  return rows.map((row) => ({
    label:
      names.indexOf(row.display_name) === names.lastIndexOf(row.display_name)
        ? row.display_name
        : `${row.display_name} #${String(row.shooter_id)}`,
    row,
  }));
}

/**
 * Bar-chart rows. `barOption` keeps one category per distinct label, so a display name held by two shooters is
 * charted as `<name> #<id>`, and each row carries its `shooter_id` (not a column) for the table drill link, as Plan 07's `race.ts` does (Plan 07 D18).
 */
export function chartRows(rows: readonly ShooterValue[]): TabularRow[] {
  return labelled(rows).map(({ label, row }) => ({
    display_name: label,
    value: row.value,
    shooter_id: row.shooter_id,
  }));
}

/** Chart label (as `chartRows` writes it) → shooter id, so a bar or a table row can link to its shooter. */
export function labelIds(rows: readonly ShooterValue[]): Map<string, number> {
  return new Map(labelled(rows).map(({ label, row }) => [label, row.shooter_id]));
}

export function formatEventDate(iso: string): string {
  return new Date(`${iso}T00:00:00Z`).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    timeZone: 'UTC',
  });
}

export function formatSigned(value: number): string {
  return `${value > 0 ? '+' : ''}${value.toFixed(1)}`;
}

export function formatRating(value: number): string {
  return value.toFixed(1);
}
