import { useClubEvent, type RosterRow } from '../api';
import { useDeviceSignups, type DeviceSignup } from '../tokens';

/**
 * This device's row on an event's roster (the first when several), found by matching the stored
 * registration ids against the roster, not by the token alone. Asks only for an event this device
 * holds a token for. `pending` is true while that roster is still loading.
 */
export function useMyRow(eventId: number): {
  mine: DeviceSignup[];
  row: RosterRow | undefined;
  pending: boolean;
} {
  const mine = useDeviceSignups().filter((s) => s.eventId === eventId);
  const detail = useClubEvent(mine.length > 0 ? eventId : 0);
  const row = detail.data?.roster.find((r) =>
    mine.some((s) => s.registrationId === r.registration_id),
  );
  return { mine, row, pending: mine.length > 0 && detail.isPending };
}
