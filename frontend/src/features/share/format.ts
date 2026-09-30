const INT = new Intl.NumberFormat('en-US');
const FULL_DAY = new Intl.DateTimeFormat('en-US', {
  weekday: 'short',
  month: 'short',
  day: 'numeric',
  year: 'numeric',
  timeZone: 'UTC',
});

export function formatInt(value: number): string {
  return INT.format(value);
}

/** "Sun, Sep 13, 2026". Parsed and formatted in UTC so the day never shifts. */
export function formatFullDay(iso: string): string {
  return FULL_DAY.format(new Date(`${iso}T00:00:00Z`));
}
