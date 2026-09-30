const STAMP = new Intl.DateTimeFormat('en-US', {
  dateStyle: 'medium',
  timeStyle: 'short',
  timeZone: 'America/Los_Angeles',
});
const DAY = new Intl.DateTimeFormat('en-US', {
  month: 'short',
  day: 'numeric',
  year: 'numeric',
  timeZone: 'UTC',
});

const STATUS_LABELS: Record<string, string> = {
  pending: 'Pending',
  committed: 'Committed',
  discarded: 'Discarded',
  rolled_back: 'Rolled back',
};
const KIND_LABELS: Record<string, string> = {
  scores: 'Scores workbook',
  stations: 'Station workbook',
};

/** timestamptz (UTC) → club wall-clock time. */
export function formatTimestamp(iso: string | null): string {
  return iso === null ? '—' : STAMP.format(new Date(iso));
}

export function formatDay(iso: string): string {
  return DAY.format(new Date(`${iso}T00:00:00Z`));
}

export function dateList(dates: string[]): string {
  return dates.length === 0 ? '—' : dates.map(formatDay).join(', ');
}

export function statusLabel(status: string): string {
  return STATUS_LABELS[status] ?? status;
}

export function kindLabel(kind: string): string {
  return KIND_LABELS[kind] ?? kind;
}
