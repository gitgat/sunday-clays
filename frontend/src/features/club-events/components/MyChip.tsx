import { chipText } from '../format';
import { useMyRow } from './useMyRow';

/**
 * "You're in" / "Waitlist #2" when this device holds a sign-up for the event. Summaries carry no
 * positions, so the event's own roster is read, only for events this device signed up for.
 */
export function MyChip({ eventId }: { eventId: number }) {
  const { row } = useMyRow(eventId);
  if (row === undefined) return null;
  return (
    <span className="rounded-button border border-accent px-2 text-xs text-text">
      {chipText(row)}
    </span>
  );
}
