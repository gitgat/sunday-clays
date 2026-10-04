import { useClubEvent } from '../api';
import { chipText } from '../format';
import { useDeviceSignups } from '../tokens';

/**
 * "You're in" / "Waitlist #2" when this device holds a sign-up for the event. Summaries carry no
 * positions, so the event's own roster is read, only for events this device signed up for.
 */
export function MyChip({ eventId }: { eventId: number }) {
  const mine = useDeviceSignups().filter((s) => s.eventId === eventId);
  const detail = useClubEvent(mine.length > 0 ? eventId : 0);
  const row = detail.data?.roster.find((r) =>
    mine.some((s) => s.registrationId === r.registration_id),
  );
  if (row === undefined) return null;
  return (
    <span className="rounded-button border border-accent px-2 text-xs text-text">
      {chipText(row)}
    </span>
  );
}
