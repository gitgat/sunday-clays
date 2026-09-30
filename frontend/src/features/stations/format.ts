export function pct(value: number | null): string {
  return value === null ? '—' : `${(value * 100).toFixed(2)}%`;
}

export function signedPoints(value: number): string {
  const points = value * 100;
  return `${points > 0 ? '+' : ''}${points.toFixed(2)} pts`;
}

/** A fraction as a percentage rounded to 2 dp (chart Table and CSV rows show 2 dp); null stays null. */
export function percentValue(value: number | null): number | null {
  return value === null ? null : Math.round(value * 10_000) / 100;
}
