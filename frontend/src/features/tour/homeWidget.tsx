import { useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'react-router';
import { useFeature } from '../../lib/features';
import type { HomeWidget } from '../home/widgets';
import { markTourDone, useTourDone } from './state';
import { TOUR_STEPS } from './steps';
import { TourDialog } from './TourDialog';

/** The Home h1 (Plan 19 §3.2.1: focus returns here when the tour closes). */
export const HOME_TITLE_ID = 'home-title';
/** Open once the latest-Sunday card is in the DOM, or after this long at most. */
const READY_WAIT_MS = 1500;
const POLL_MS = 100;

/** Renders nothing until it opens the tour; never a visible card (no hero-slot node). */
function TourWidget() {
  const { visible, preview } = useFeature('tour_glossary');
  const [params, setParams] = useSearchParams();
  const asked = params.get('tour') === '1';
  const done = useTourDone();
  const [open, setOpen] = useState(false);
  const wanted = visible && !open && (asked || !done);

  useEffect(() => {
    if (!wanted) return undefined;
    const started = Date.now();
    const timer = window.setInterval(() => {
      const ready = document.querySelector('[data-tour="sunday"]') !== null;
      if (!ready && Date.now() - started < READY_WAIT_MS) return;
      window.clearInterval(timer);
      setOpen(true);
      if (asked) {
        setParams(
          (previous) => {
            const next = new URLSearchParams(previous);
            next.delete('tour');
            return next;
          },
          { replace: true }, // a reload does not reopen it
        );
      }
    }, POLL_MS);
    return () => window.clearInterval(timer);
  }, [wanted, asked, setParams]);

  // Focus goes back to the Home title after the dialog has unmounted and the page is no longer
  // inert (an inert element cannot take focus).
  const wasOpen = useRef(false);
  useEffect(() => {
    if (!open && wasOpen.current) document.getElementById(HOME_TITLE_ID)?.focus();
    wasOpen.current = open;
  }, [open]);

  if (!open) return null;
  const close = () => {
    markTourDone();
    setOpen(false);
  };
  return <TourDialog steps={TOUR_STEPS} preview={preview} onClose={close} />;
}

export const homeWidget: HomeWidget = {
  id: 'tour',
  order: -10,
  slot: 'hero',
  Component: TourWidget,
};
