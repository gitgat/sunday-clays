import { Smartphone } from 'lucide-react';
import {
  CLAYSMASHER_BUTTON_ENABLED,
  CLAYSMASHER_LINK_MODE,
  claysmasherSchemeUrl,
  claysmasherWebUrl,
} from '../links';
import type { ClaySmasherLinkMode } from '../links';

/** components/ui/Button's tonal look for an <a> (Button renders a <button> only). */
const BUTTON_CLASS =
  'inline-flex min-h-11 min-w-11 self-start items-center justify-center gap-2 rounded-button border border-outline-variant bg-elevated px-4 text-sm font-medium text-text transition-colors hover:border-outline';

/**
 * Spec §3.1, §4.2: a plain same-tab <a> (no target, no window.open), so the phone treats the tap as
 * a universal link / App Link and opens ClaySmasher when it is installed; without the app the
 * claysmasher.com page opens and Back returns here. Hidden while the flag is off (spec §11).
 */
export function ImportIntoClaySmasher({
  shooterId,
  enabled = CLAYSMASHER_BUTTON_ENABLED,
  mode = CLAYSMASHER_LINK_MODE,
}: {
  shooterId: number;
  enabled?: boolean;
  mode?: ClaySmasherLinkMode;
}) {
  if (!enabled) return null;
  const button = (href: string) => (
    <a href={href} className={BUTTON_CLASS}>
      <Smartphone aria-hidden="true" className="size-4" />
      Import into ClaySmasher
    </a>
  );
  if (mode === 'universal') return button(claysmasherWebUrl(shooterId));
  return (
    <div className="flex flex-col items-start self-start">
      {button(claysmasherSchemeUrl(shooterId))}
      <a
        href={claysmasherWebUrl(shooterId)}
        className="inline-flex min-h-11 items-center text-sm text-text-muted underline"
      >
        Don’t have ClaySmasher?
      </a>
    </div>
  );
}
