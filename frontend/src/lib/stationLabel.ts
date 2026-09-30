/**
 * Station labels: "7" and "7A" are two stations. A label sorts by its leading number, then by its
 * letter: 4, 5, 6, 7, 7A, 8 (the API already sends them in this order; charts that regroup rows
 * sort with `compareStations`).
 */
const LABEL = /^(\d{1,2})([A-Z]?)$/;

/** One integer that orders labels: 7 → 700, 7A → 701. Anything else sorts last. */
export function stationRank(label: string): number {
  const match = LABEL.exec(label);
  if (match === null) return Number.MAX_SAFE_INTEGER;
  const [, digits = '', letter = ''] = match;
  return Number(digits) * 100 + (letter === '' ? 0 : letter.charCodeAt(0) - 64);
}

export function compareStations(a: string, b: string): number {
  return stationRank(a) - stationRank(b) || a.localeCompare(b);
}
