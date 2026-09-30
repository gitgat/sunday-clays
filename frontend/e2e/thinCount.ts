/** The nudge's opening words for a count of scored Sundays: "No Sundays", "Only 1 Sunday", "Only 7 Sundays". */
export function thinCount(n: number): string {
  if (n === 0) return 'No Sundays';
  return `Only ${String(n)} ${n === 1 ? 'Sunday' : 'Sundays'}`;
}
