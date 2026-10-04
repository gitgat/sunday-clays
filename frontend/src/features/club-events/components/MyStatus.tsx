import { Button } from '../../../components/ui/Button';
import type { ClubEventSummary, RosterRow } from '../api';
import { onFileAfterRace, PROMOTED, statusLine } from '../format';

/** This device's sign-up: going or its waitlist place, and how to cancel it (§5.8). */
export function MyStatus({
  row,
  promoted,
  onFileName,
  canCancel,
  onCancel,
  event,
}: {
  row: RosterRow;
  promoted: boolean;
  onFileName: string | null;
  canCancel: boolean;
  onCancel: () => void;
  event: Pick<ClubEventSummary, 'upcoming' | 'state'>;
}) {
  return (
    <section
      aria-label="Your sign-up"
      className="flex flex-col gap-2 rounded-card border border-accent bg-elevated p-4 text-text"
    >
      {promoted && <p className="font-medium">{PROMOTED}</p>}
      <p>{statusLine(row, event)}</p>
      {onFileName !== null && (
        <p className="text-sm text-text-muted">{onFileAfterRace(onFileName)}</p>
      )}
      {canCancel && (
        <div>
          <Button variant="tonal" onClick={onCancel}>
            Cancel my spot
          </Button>
        </div>
      )}
    </section>
  );
}
