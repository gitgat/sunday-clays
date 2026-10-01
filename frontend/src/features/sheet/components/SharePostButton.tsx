import { Share2 } from 'lucide-react';
import { useRef, useState } from 'react';
import { createPortal, flushSync } from 'react-dom';
import { shareElementAsImage } from '../../../lib/share';
import { segmentsText } from '../../insights/segments';
import { sheetPostFilename } from '../../share/filenames';
import type { SheetPost } from '../api';
import { PostShareCard } from './PostShareCard';

/**
 * Shares one post as a branded image (lib/share: the Web Share API, else a download). The card is
 * rendered off screen only while the image is made.
 */
export function SharePostButton({ post, date }: { post: SheetPost; date: string }) {
  const cardRef = useRef<HTMLDivElement>(null);
  const [rendering, setRendering] = useState(false);
  const [status, setStatus] = useState<'idle' | 'busy' | 'failed'>('idle');

  async function share() {
    setStatus('busy');
    flushSync(() => setRendering(true));
    try {
      const card = cardRef.current;
      if (card === null) throw new Error('The share card did not render');
      await shareElementAsImage(card, sheetPostFilename(date, segmentsText(post.headline)));
      setStatus('idle');
    } catch {
      setStatus('failed');
    } finally {
      setRendering(false);
    }
  }

  return (
    <>
      <button
        type="button"
        aria-label="Share image"
        onClick={() => void share()}
        disabled={status === 'busy'}
        className="inline-flex min-h-11 min-w-11 items-center justify-center gap-2 rounded-button px-3 text-sm text-text-muted hover:text-text disabled:opacity-60"
      >
        <Share2 aria-hidden="true" className="size-4" />
        Share
      </button>
      {status === 'failed' && (
        <span role="alert" className="text-sm text-text-muted">
          Could not create the image.
        </span>
      )}
      {rendering &&
        createPortal(
          <div aria-hidden="true" className="pointer-events-none fixed top-0 left-[-10000px]">
            <div ref={cardRef}>
              <PostShareCard post={post} date={date} />
            </div>
          </div>,
          document.body,
        )}
    </>
  );
}
