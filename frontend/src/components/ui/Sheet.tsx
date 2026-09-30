import { X } from 'lucide-react';
import { useEffect, useId, useRef, type KeyboardEvent, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { cx } from './cx';

export interface SheetProps {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  /** 'bottom' slides up from the bottom edge (mobile); 'center' is a centered dialog (desktop). */
  placement?: 'bottom' | 'center';
  /** 'full' uses (almost) the whole viewport, e.g. fullscreen charts. */
  size?: 'auto' | 'full';
}

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

/** Wraps Tab at either end of the dialog, including Shift+Tab from the panel itself. */
function trapTab(event: KeyboardEvent<HTMLDivElement>) {
  const items = [...event.currentTarget.querySelectorAll<HTMLElement>(FOCUSABLE)];
  const index = items.findIndex((el) => el === document.activeElement);
  const atEdge = event.shiftKey ? index <= 0 : index === items.length - 1;
  if (!atEdge) return;
  event.preventDefault();
  items.at(event.shiftKey ? -1 : 0)?.focus();
}

/** Makes every other child of <body> inert; returns the undo (only for elements it changed). */
function inertOthers(keep: Element | null): () => void {
  const changed = [...document.body.children].filter(
    (el) => el !== keep && !el.hasAttribute('inert'),
  );
  for (const el of changed) el.setAttribute('inert', '');
  return () => {
    for (const el of changed) el.removeAttribute('inert');
  };
}

export function Sheet({
  open,
  onClose,
  title,
  children,
  placement = 'bottom',
  size = 'auto',
}: SheetProps) {
  const titleId = useId();
  const overlayRef = useRef<HTMLDivElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const restoreInert = inertOthers(overlayRef.current);
    panelRef.current?.focus();
    return () => {
      // Un-inert first: an inert opener cannot take focus back.
      restoreInert();
      document.body.style.overflow = overflow;
      previous?.focus();
    };
  }, [open]);

  if (!open) return null;

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === 'Escape') {
      event.stopPropagation();
      onClose();
    } else if (event.key === 'Tab') {
      trapTab(event);
    }
  };

  return createPortal(
    <div
      ref={overlayRef}
      className={cx(
        'fixed inset-0 z-50 flex',
        placement === 'bottom' ? 'items-end' : 'items-center justify-center p-6',
      )}
    >
      <div
        data-testid="sheet-backdrop"
        aria-hidden="true"
        className="absolute inset-0 bg-black/60"
        onClick={onClose}
      />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        onKeyDown={onKeyDown}
        className={cx(
          'relative flex max-h-full w-full flex-col bg-elevated text-text shadow-xl outline-none',
          placement === 'bottom' ? 'rounded-t-sheet' : 'max-w-5xl rounded-sheet',
          size === 'full' && (placement === 'bottom' ? 'h-[95dvh]' : 'h-[90dvh]'),
        )}
      >
        <header className="flex items-center justify-between gap-2 border-b border-outline-variant px-4 py-2">
          <h2 id={titleId} className="text-base font-medium">
            {title}
          </h2>
          <button
            type="button"
            aria-label="Close"
            onClick={onClose}
            className="inline-flex size-11 items-center justify-center rounded-full text-text-muted hover:bg-surface hover:text-text"
          >
            <X aria-hidden="true" className="size-5" />
          </button>
        </header>
        <div className="min-h-0 flex-1 overflow-auto p-4">{children}</div>
      </div>
    </div>,
    document.body,
  );
}
