import type { ReactNode } from 'react';
import { Button } from '../../../components/ui/Button';
import { Sheet } from '../../../components/ui/Sheet';
import { useIsDesktop } from '../../../lib/useMediaQuery';

/** A yes/no step before a destructive or irreversible organizer action. */
export function ConfirmSheet({
  open,
  title,
  children,
  confirm,
  busy,
  onConfirm,
  onClose,
}: {
  open: boolean;
  title: string;
  children: ReactNode;
  confirm: string;
  busy: boolean;
  onConfirm: () => void;
  onClose: () => void;
}) {
  const isDesktop = useIsDesktop();
  return (
    <Sheet open={open} onClose={onClose} title={title} placement={isDesktop ? 'center' : 'bottom'}>
      <div className="flex max-w-md flex-col gap-3">
        {children}
        <div className="flex flex-wrap gap-2">
          <Button variant="danger" loading={busy} onClick={onConfirm}>
            {confirm}
          </Button>
          <Button variant="ghost" onClick={onClose}>
            Keep it
          </Button>
        </div>
      </div>
    </Sheet>
  );
}
