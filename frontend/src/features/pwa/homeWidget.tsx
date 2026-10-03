import { useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router';
import { AdminPreviewBadge } from '../../components/ui/AdminPreviewBadge';
import { Card } from '../../components/ui/Card';
import { useFeature } from '../../lib/features';
import {
  dismissInstall,
  isIosSafari,
  promptInstall,
  useInstallDismissed,
  useInstallPrompt,
} from '../../lib/installPrompt';
import { getMe } from '../../lib/me';
import { useIsTouch, useMediaQuery } from '../../lib/useMediaQuery';
import type { HomeWidget } from '../home/widgets';
import { useTourDone } from '../tour/state';
import { ANDROID_BODY, GOT_IT, INSTALL, IOS_BODY, NOT_NOW, TIP_TITLE } from './copy';

export const LAUNCHED_KEY = 'sc.pwa.launched';
const STANDALONE = '(display-mode: standalone)';
const BUTTON = 'inline-flex min-h-11 items-center justify-center rounded-button px-4 text-sm';

/** An installed app opens on the viewer's own page, once per session (§3.4 launch behaviour). */
function useLaunchRedirect(pwaVisible: boolean): void {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  useEffect(() => {
    if (!pwaVisible || !window.matchMedia(STANDALONE).matches || pathname !== '/') return;
    try {
      if (sessionStorage.getItem(LAUNCHED_KEY) !== null) return;
      const me = getMe();
      if (me === null) return;
      void navigate(`/shooters/${String(me)}`, { replace: true });
      sessionStorage.setItem(LAUNCHED_KEY, '1');
    } catch {
      // storage blocked: stay on Home
    }
  }, [navigate, pathname, pwaVisible]);
}

/** Always mounts (the launch redirect runs first), then renders the install tip or nothing. */
function InstallTip() {
  const { visible } = useFeature('pwa');
  useLaunchRedirect(visible);
  const tour = useFeature('tour_glossary');
  const tourDone = useTourDone();
  const touch = useIsTouch();
  const standalone = useMediaQuery(STANDALONE);
  const dismissed = useInstallDismissed();
  const prompt = useInstallPrompt();
  const ios = isIosSafari();
  const show =
    visible &&
    touch &&
    !standalone &&
    !dismissed &&
    (tourDone || !tour.visible) &&
    (prompt !== null || ios);
  if (!show) return null;
  return (
    <Card
      title={
        <span className="inline-flex flex-wrap items-center gap-2">
          {TIP_TITLE}
          <AdminPreviewBadge feature="pwa" />
        </span>
      }
    >
      <div className="flex flex-col gap-3">
        <p>{prompt !== null ? ANDROID_BODY : IOS_BODY}</p>
        <div className="flex flex-wrap gap-2">
          {prompt !== null ? (
            <>
              <button
                type="button"
                className={`${BUTTON} bg-primary text-text`}
                onClick={() => void promptInstall()}
              >
                {INSTALL}
              </button>
              <button
                type="button"
                className={`${BUTTON} border border-outline-variant`}
                onClick={dismissInstall}
              >
                {NOT_NOW}
              </button>
            </>
          ) : (
            <button
              type="button"
              className={`${BUTTON} border border-outline-variant`}
              onClick={dismissInstall}
            >
              {GOT_IT}
            </button>
          )}
        </div>
      </div>
    </Card>
  );
}

export const homeWidget: HomeWidget = {
  id: 'install',
  order: 90,
  slot: 'main',
  Component: InstallTip,
};
