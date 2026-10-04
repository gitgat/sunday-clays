import type { ShooterListItem } from '../shooters/api';

export const PICKER_LIMIT = 8;

function words(text: string): string[] {
  return text.toLowerCase().replace(/,/g, ' ').split(/\s+/).filter(Boolean);
}

/** Every typed word starts some word of the name: "ike had" finds "Hadley, Ike". */
export function matchesName(query: string, name: string): boolean {
  const wanted = words(query);
  if (wanted.length === 0) return false;
  const have = words(name);
  return wanted.every((part) => have.some((word) => word.startsWith(part)));
}

/** The directory minus deceased shooters (§4 live shooters; the API already lists profiles only). */
export function pickable(list: readonly ShooterListItem[]): ShooterListItem[] {
  return list.filter((s) => s.status !== 'deceased');
}

export function searchShooters(
  list: readonly ShooterListItem[],
  query: string,
  limit: number = PICKER_LIMIT,
): ShooterListItem[] {
  return pickable(list)
    .filter((s) => matchesName(query, s.display_name))
    .slice(0, limit);
}
