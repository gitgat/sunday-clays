import { useWindowChoice } from '../lib/timeWindowChoice';
import { Button } from './ui/Button';

/**
 * One-tap 12M and All buttons that widen the header window: 12M unless the window is already 12M
 * or All; All (accessible name "Show all time") unless it is already All. Nothing when neither
 * applies.
 */
export function WidenWindowButtons() {
  const [window, setWindow] = useWindowChoice();
  const widen12 = window !== '12m' && window !== 'all';
  const widenAll = window !== 'all';
  if (!widen12 && !widenAll) return null;
  return (
    <div className="flex flex-wrap gap-2">
      {widen12 && (
        <Button
          variant="tonal"
          aria-label="Show the last 12 months"
          onClick={() => setWindow('12m')}
        >
          12M
        </Button>
      )}
      {widenAll && (
        <Button variant="tonal" aria-label="Show all time" onClick={() => setWindow('all')}>
          All
        </Button>
      )}
    </div>
  );
}
