import { Button } from '../../../components/ui/Button';
import { clearMe } from '../../../lib/me';
import { MePanel } from '../../home/components/MePanel';
import type { HomeWidget } from '../../home/widgets';
import { WhichOneAreYou } from './WhichOneAreYou';

/**
 * The rail's personal slot (Plan 14): the viewer's last result, totals and next trophy once
 * "me" is set; "Which one are you?" until then; nothing once this browser said "skip".
 */
export function YourSunday({
  meId,
  skipped,
  widgets,
  onPicked,
  onCleared,
  onSkipped,
}: {
  meId: number | null;
  skipped: boolean;
  widgets: HomeWidget[];
  onPicked: (id: number) => void;
  onCleared: () => void;
  onSkipped: () => void;
}) {
  if (meId === null) {
    return skipped ? null : <WhichOneAreYou onPicked={onPicked} onSkipped={onSkipped} />;
  }
  return (
    <MePanel
      meId={meId}
      title="Your Sunday"
      actions={
        <Button
          variant="ghost"
          onClick={() => {
            clearMe();
            onCleared();
          }}
        >
          Not me
        </Button>
      }
      onCleared={onCleared}
      widgets={widgets}
    />
  );
}
