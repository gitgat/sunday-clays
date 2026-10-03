import { useEffect, useRef, useState } from 'react';
import { getMe, isMeSkipped } from '../../../lib/me';
import { ClubPulse } from '../components/ClubPulse';
import { LatestEventCard } from '../components/LatestEventCard';
import { MePanel } from '../components/MePanel';
import { WhichOneAreYou } from '../components/WhichOneAreYou';
import { WidgetSlot } from '../components/WidgetSlot';
import { homeWidgets } from '../widgets';
import type { HomeWidget } from '../widgets';

export function HomePage({ widgets = homeWidgets }: { widgets?: HomeWidget[] }) {
  const [meId, setMeId] = useState<number | null>(() => getMe());
  const [skipped, setSkipped] = useState(isMeSkipped);
  const asking = meId === null && !skipped;
  // Which card the personal slot holds: the question, the prompt, or a shooter's panel.
  const slot = asking ? 'ask' : String(meId);
  const personal = useRef<HTMLElement>(null);
  const before = useRef(slot);
  // A pick, a skip or "Not me" swaps the card that held focus: carry on at the new card's heading.
  useEffect(() => {
    if (before.current === slot) return;
    before.current = slot;
    const heading = personal.current?.querySelector<HTMLElement>('h2');
    if (heading === null || heading === undefined) return;
    heading.tabIndex = -1;
    heading.classList.add('focus:outline-none');
    heading.focus();
  }, [slot]);
  return (
    <div className="flex flex-col gap-4">
      {/* tabIndex -1: the tour returns focus here without adding a Tab stop (Plan 19). */}
      <h1 id="home-title" tabIndex={-1} className="text-2xl font-medium focus:outline-none">
        Sunday Clays
      </h1>
      <WidgetSlot slot="hero" widgets={widgets} meId={meId} />
      <div className="grid gap-4 lg:grid-cols-3">
        <div className="flex min-w-0 flex-col gap-4 lg:col-span-2">
          <LatestEventCard />
          <ClubPulse />
          <WidgetSlot slot="main" widgets={widgets} meId={meId} />
        </div>
        {/* Named apart from the "Your panel" card inside it: landmark names stay unique. */}
        <aside
          ref={personal}
          aria-label="Personal"
          data-tour="you"
          className="flex min-w-0 flex-col gap-4"
        >
          {asking ? (
            <WhichOneAreYou onPicked={setMeId} onSkipped={() => setSkipped(true)} />
          ) : (
            <MePanel meId={meId} onCleared={() => setMeId(null)} widgets={widgets} />
          )}
        </aside>
      </div>
    </div>
  );
}
