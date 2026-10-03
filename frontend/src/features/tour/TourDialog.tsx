import { useEffect, useId, useRef, useState, type KeyboardEvent } from 'react';
import { createPortal } from 'react-dom';
import { ADMIN_PREVIEW_HINT } from '../../components/ui/AdminPreviewBadge';
import { cx } from '../../components/ui/cx';
import { inertOthers, trapTab } from '../../components/ui/Sheet';
import { useMediaQuery } from '../../lib/useMediaQuery';
import type { TourStep } from './steps';
import { firstVisible, PHONE_QUERY, REDUCED_MOTION_QUERY } from './target';

const RING_PAD = 4;
const BUTTON =
  'inline-flex min-h-11 min-w-11 items-center justify-center rounded-button px-4 text-sm';

/** The target's box, kept up to date on resize and scroll (rAF-throttled); null when missing. */
function useTargetBox(id: string, reduced: boolean): DOMRect | null {
  const [state, setState] = useState<{ id: string; box: DOMRect | null } | null>(null);
  useEffect(() => {
    const el = firstVisible(id);
    let frame = requestAnimationFrame(() =>
      setState({ id, box: el?.getBoundingClientRect() ?? null }),
    );
    if (el === null) return () => cancelAnimationFrame(frame);
    el.scrollIntoView({ block: 'center', behavior: reduced ? 'auto' : 'smooth' });
    const update = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => setState({ id, box: el.getBoundingClientRect() }));
    };
    const observer = new ResizeObserver(update);
    observer.observe(el);
    window.addEventListener('scroll', update, true);
    window.addEventListener('resize', update);
    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      window.removeEventListener('scroll', update, true);
      window.removeEventListener('resize', update);
    };
  }, [id, reduced]);
  return state?.id === id ? state.box : null;
}

export function TourDialog({
  steps,
  preview,
  onClose,
}: {
  steps: readonly TourStep[];
  preview: boolean;
  onClose: () => void;
}) {
  const [index, setIndex] = useState(0);
  const step = steps[index] as TourStep;
  const last = index === steps.length - 1;
  const reduced = useMediaQuery(REDUCED_MOTION_QUERY);
  const phone = useMediaQuery(PHONE_QUERY);
  const box = useTargetBox(step.target, reduced);
  const titleId = useId();
  const bodyId = useId();
  const rootRef = useRef<HTMLDivElement>(null);
  const titleRef = useRef<HTMLHeadingElement>(null);

  useEffect(() => inertOthers(rootRef.current), []);
  useEffect(() => titleRef.current?.focus(), [index]);

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === 'Escape') {
      event.stopPropagation();
      onClose();
    } else if (event.key === 'Tab') {
      trapTab(event);
    }
  };

  const placement = phone
    ? 'inset-x-4 bottom-20'
    : box === null
      ? 'left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2'
      : '';
  const beside =
    !phone && box !== null
      ? {
          left: Math.max(16, Math.min(box.right + 16, window.innerWidth - 376)),
          top: Math.max(16, Math.min(box.top, window.innerHeight - 280)),
        }
      : undefined;

  return createPortal(
    <div ref={rootRef}>
      <div aria-hidden="true" className="fixed inset-0 z-40 bg-black/60" />
      {box !== null && (
        <div
          aria-hidden="true"
          data-testid="tour-ring"
          className={cx(
            'pointer-events-none fixed z-40 rounded-card border-[3px] border-accent',
            !reduced && 'transition-all duration-200',
          )}
          style={{
            top: box.top - RING_PAD,
            left: box.left - RING_PAD,
            width: box.width + 2 * RING_PAD,
            height: box.height + 2 * RING_PAD,
          }}
        />
      )}
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={bodyId}
        onKeyDown={onKeyDown}
        style={beside}
        className={cx(
          'fixed z-50 flex flex-col gap-3 rounded-card bg-elevated p-4 text-text shadow-xl sm:w-[360px]',
          placement,
        )}
      >
        <header className="flex flex-wrap items-center justify-between gap-2">
          <h2
            id={titleId}
            ref={titleRef}
            tabIndex={-1}
            className="text-base font-medium focus:outline-none"
          >
            {step.title}
          </h2>
          {preview && (
            <span
              title={ADMIN_PREVIEW_HINT}
              aria-description={ADMIN_PREVIEW_HINT}
              className="rounded-button border border-accent px-2 py-0.5 text-xs font-medium text-accent"
            >
              Admin preview
            </span>
          )}
        </header>
        <p id={bodyId} className="text-sm text-text-muted">
          {step.body}
        </p>
        <p className="text-xs text-text-muted">{`Step ${String(index + 1)} of ${String(steps.length)}`}</p>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <button
            type="button"
            onClick={onClose}
            className={cx(BUTTON, 'text-text-muted underline')}
          >
            Skip tour
          </button>
          <div className="flex gap-2">
            {index > 0 && (
              <button
                type="button"
                onClick={() => setIndex(index - 1)}
                className={cx(BUTTON, 'border border-outline-variant')}
              >
                Back
              </button>
            )}
            <button
              type="button"
              onClick={() => (last ? onClose() : setIndex(index + 1))}
              className={cx(BUTTON, 'bg-primary text-text')}
            >
              {last ? 'Done' : 'Next'}
            </button>
          </div>
        </div>
      </div>
    </div>,
    document.body,
  );
}
