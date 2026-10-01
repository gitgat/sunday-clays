import { Link2 } from 'lucide-react';
import { useState } from 'react';
import { shareLink } from '../../../lib/share';
import { formatDay, formatScore } from '../../home/format';
import type { SheetIssue } from '../api';

const MESSAGES = { idle: '', copied: 'Link copied.', failed: 'Could not share the link.' } as const;

/** "The Sunday Sheet, Sep 27, 2026: 23 shooters, field median 39, top score 49, 13 trophies." */
export function sheetShareText(issue: SheetIssue): string {
  const n = issue.numbers;
  const shooters = `${String(n.shooters)} ${n.shooters === 1 ? 'shooter' : 'shooters'}`;
  return (
    `The Sunday Sheet, ${formatDay(issue.masthead.date)}: ${shooters}, ` +
    `field median ${formatScore(n.median)}, top score ${formatScore(n.top_score)}, ` +
    `${String(n.trophies)} ${n.trophies === 1 ? 'trophy' : 'trophies'}.`
  );
}

/**
 * Shares this issue's `/sheet/{date}` link with the four numbers as text (the site stays behind
 * its password, so there is no preview image), or copies them when the browser cannot share.
 */
export function ShareSheetButton({ issue }: { issue: SheetIssue }) {
  const [status, setStatus] = useState<keyof typeof MESSAGES>('idle');
  async function share() {
    const url = new URL(`/sheet/${issue.masthead.date}`, window.location.origin).toString();
    try {
      const outcome = await shareLink({
        title: 'The Sunday Sheet',
        text: sheetShareText(issue),
        url,
      });
      setStatus(outcome === 'copied' ? 'copied' : 'idle');
    } catch {
      setStatus('failed');
    }
  }
  return (
    <span className="inline-flex items-center gap-2">
      <button
        type="button"
        onClick={() => void share()}
        className="inline-flex min-h-11 items-center gap-2 rounded-button px-2 underline underline-offset-2"
      >
        <Link2 aria-hidden="true" className="size-4" />
        Share this Sheet
      </button>
      {/* A polite live line, not role="status": pages wait for "no status left" to be settled. */}
      <span aria-live="polite" className="text-sm text-text-muted">
        {MESSAGES[status]}
      </span>
    </span>
  );
}
