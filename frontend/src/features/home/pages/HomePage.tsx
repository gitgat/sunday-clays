import { useState } from 'react';
import { getMe } from '../../../lib/me';
import { ClubPulse } from '../components/ClubPulse';
import { LatestEventCard } from '../components/LatestEventCard';
import { MePanel } from '../components/MePanel';
import { WidgetSlot } from '../components/WidgetSlot';
import { homeWidgets } from '../widgets';
import type { HomeWidget } from '../widgets';

export function HomePage({ widgets = homeWidgets }: { widgets?: HomeWidget[] }) {
  const [meId, setMeId] = useState<number | null>(() => getMe());
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-medium">Sunday Clays</h1>
      <WidgetSlot slot="hero" widgets={widgets} meId={meId} />
      <div className="grid gap-4 lg:grid-cols-3">
        <div className="flex min-w-0 flex-col gap-4 lg:col-span-2">
          <LatestEventCard />
          <ClubPulse />
          <WidgetSlot slot="main" widgets={widgets} meId={meId} />
        </div>
        {/* Named apart from the "Your panel" card inside it: landmark names stay unique. */}
        <aside aria-label="Personal" className="flex min-w-0 flex-col gap-4">
          <MePanel meId={meId} onCleared={() => setMeId(null)} widgets={widgets} />
        </aside>
      </div>
    </div>
  );
}
