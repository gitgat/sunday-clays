import { useState } from 'react';
import { useMeta, useTimeWindow } from '../../lib/timeWindow';
import { customWindow, isCustomWindow } from '../../lib/timeWindowChoice';
import { formatDate } from '../../lib/format';
import { useIsDesktop } from '../../lib/useMediaQuery';
import { Button } from '../ui/Button';
import { DATE_INPUT_CLASS, RangeAlert } from '../ui/DateField';
import { Sheet } from '../ui/Sheet';

function CustomWindowForm({ onClose }: { onClose: () => void }) {
  const { window, range, setWindow } = useTimeWindow();
  const meta = useMeta();
  const first = meta.data?.first_event_date ?? undefined;
  const last = meta.data?.last_score_date ?? undefined;
  // What the viewer typed, or (until they type) the range now in force.
  const [typedStart, setTypedStart] = useState<string | null>(null);
  const [typedEnd, setTypedEnd] = useState<string | null>(null);
  const start = typedStart ?? range?.from ?? first ?? '';
  const end = typedEnd ?? range?.to ?? '';
  const reversed = start !== '' && end !== '' && start > end;
  const canApply = start !== '' && end !== '' && !reversed;

  return (
    <form
      className="flex flex-col gap-3"
      onSubmit={(event) => {
        event.preventDefault();
        if (!canApply) return;
        setWindow(customWindow(start, end));
        onClose();
      }}
    >
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <label className="flex flex-col gap-1 text-xs text-text-muted">
          Start date
          <input
            type="date"
            value={start}
            min={first}
            max={last}
            onChange={(event) => setTypedStart(event.target.value)}
            className={DATE_INPUT_CLASS}
          />
        </label>
        <label className="flex flex-col gap-1 text-xs text-text-muted">
          End date
          <input
            type="date"
            value={end}
            min={first}
            max={last}
            onChange={(event) => setTypedEnd(event.target.value)}
            className={DATE_INPUT_CLASS}
          />
        </label>
      </div>
      {reversed && <RangeAlert />}
      <p className="text-sm text-text-muted">
        Charts and stats that follow the time window use these dates. The presets (8W, 3M, 6M, 12M,
        YTD) count back from the latest scored Sunday
        {last === undefined ? '' : `, ${formatDate(last)}`}, not from today.
      </p>
      <div className="flex flex-wrap justify-end gap-2">
        {isCustomWindow(window) && (
          <Button
            variant="ghost"
            className="mr-auto"
            onClick={() => {
              setWindow('8w');
              onClose();
            }}
          >
            Back to last 8 weeks
          </Button>
        )}
        <Button variant="ghost" onClick={onClose}>
          Cancel
        </Button>
        <Button type="submit" disabled={!canApply}>
          Apply
        </Button>
      </div>
    </form>
  );
}

/**
 * The Custom range of the global time window: two dates, applied together to `?w=start..end`.
 * A bottom sheet on a phone, a centred dialog on desktop. The form mounts only while open, so it
 * starts from the range in force each time.
 */
export function CustomWindowSheet({ open, onClose }: { open: boolean; onClose: () => void }) {
  const isDesktop = useIsDesktop();
  return (
    <Sheet
      open={open}
      onClose={onClose}
      title="Custom dates"
      placement={isDesktop ? 'center' : 'bottom'}
      size="auto"
    >
      <CustomWindowForm onClose={onClose} />
    </Sheet>
  );
}
