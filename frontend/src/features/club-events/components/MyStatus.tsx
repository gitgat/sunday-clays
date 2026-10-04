import { useEffect, useRef } from 'react';
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
  focusOnMount = false,
}: {
  row: RosterRow;
  promoted: boolean;
  onFileName: string | null;
  canCancel: boolean;
  onCancel: () => void;
  event: Pick<ClubEventSummary, 'upcoming' | 'state'>;
  /** Focus this section when it first appears (right after this device signed up). */
  focusOnMount?: boolean;
}) {
  const ref = useRef<HTMLElement>(null);
  useEffect(() => {
    if (focusOnMount) ref.current?.focus();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return (
    <section
      ref={ref}
      tabIndex={-1}
      aria-label="Your sign-up"
      className="flex flex-col gap-2 rounded-card outline-none border border-accent bg-elevated p-4 text-text"
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
