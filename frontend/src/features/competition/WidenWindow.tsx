import { useWindowChoice, type TimeWindowPreset } from '../../lib/timeWindowChoice';
import { cx } from '../../components/ui/cx';

const OPTIONS: readonly { value: TimeWindowPreset; label: string }[] = [
  { value: '12m', label: '12M' },
  { value: 'all', label: 'All' },
];

const BUTTON =
  'inline-flex min-h-11 min-w-11 items-center justify-center rounded-button border border-accent px-4 text-sm font-medium';

/**
 * One-tap 12M and All buttons that widen the time window (`?w=`). A button for the window already
 * chosen is left out, and nothing renders when both would be pointless (the window is All time).
 * Local to the Leaderboards, Records and Race pages; each page words the message around it.
 */
export function WidenWindow({ className }: { className?: string }) {
  const [timeWindow, setWindow] = useWindowChoice();
  // From All time there is nothing wider to offer; otherwise leave out the window already chosen.
  if (timeWindow === 'all') return null;
  const options = OPTIONS.filter((o) => o.value !== timeWindow);
  return (
    <div
      role="group"
      aria-label="Widen the window"
      className={cx('flex flex-wrap gap-2', className)}
    >
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          onClick={() => {
            setWindow(o.value);
          }}
          className={BUTTON}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}
