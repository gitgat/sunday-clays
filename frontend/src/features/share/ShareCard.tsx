import { Share2 } from 'lucide-react';
import { useRef, useState, type ReactNode } from 'react';
import { shareElementAsImage } from '../../lib/share';

type Status = 'idle' | 'busy' | 'done' | 'failed';

const MESSAGES: Record<Status, string> = {
  idle: '',
  busy: 'Preparing image…',
  done: 'Image ready.',
  failed: 'Could not create the image.',
};

/**
 * Wraps a card and adds a "Share image" button that renders exactly the wrapped card to a PNG
 * through `lib/share.ts` (Web Share API with the file when the browser can, else a download).
 * The image is made in the browser; nothing is sent to a server.
 */
export function ShareCard({
  filename,
  name,
  compact = false,
  children,
}: {
  filename: string;
  /** Appended to the button's accessible name when several cards share a page. */
  name?: string;
  /** An icon-only 44 px button beside the card instead of a labelled button under it. */
  compact?: boolean;
  children: ReactNode;
}) {
  const cardRef = useRef<HTMLDivElement>(null);
  const [status, setStatus] = useState<Status>('idle');

  async function share() {
    setStatus('busy');
    try {
      const outcome: unknown = await shareElementAsImage(
        cardRef.current as HTMLDivElement,
        filename,
      );
      setStatus(outcome === 'cancelled' ? 'idle' : 'done');
    } catch {
      setStatus('failed');
    }
  }

  const button = (
    // aria-label rather than a visually hidden span: the name then starts with the visible
    // text (WCAG 2.5.3) and is computed the same in every browser.
    <button
      type="button"
      aria-label={name === undefined ? 'Share image' : `Share image: ${name}`}
      onClick={() => void share()}
      disabled={status === 'busy'}
      className={`inline-flex min-h-11 items-center justify-center gap-2 rounded-button border border-outline-variant disabled:opacity-60 ${compact ? 'min-w-11' : 'px-4'}`}
    >
      <Share2 aria-hidden="true" className="size-4" />
      {compact ? null : 'Share image'}
    </button>
  );
  // A polite live line, not role="status": pages wait for "no status left" to know they have
  // finished loading, and an empty status on every card would hold them up. Beside a compact
  // button only a failure is worth showing; progress is left to screen readers.
  const message = (
    <span
      aria-live="polite"
      className={
        compact
          ? status === 'failed'
            ? 'max-w-24 text-xs text-text-muted'
            : 'sr-only'
          : 'text-sm text-text-muted'
      }
    >
      {MESSAGES[status]}
    </span>
  );

  if (compact) {
    return (
      <div className="flex min-w-0 items-start gap-2">
        <div ref={cardRef} className="min-w-0 flex-1">
          {children}
        </div>
        <div className="flex flex-col items-center gap-1">
          {button}
          {message}
        </div>
      </div>
    );
  }
  return (
    <div className="flex min-w-0 flex-col gap-2">
      <div ref={cardRef}>{children}</div>
      <div className="flex flex-wrap items-center gap-3">
        {button}
        {message}
      </div>
    </div>
  );
}
