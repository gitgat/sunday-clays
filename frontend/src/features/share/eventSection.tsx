import { useEvent } from '../events/api';
import type { EventSection } from '../events/sections';
import { EventShareCard } from './components/EventShareCard';
import { eventFilename } from './filenames';
import { ShareCard } from './ShareCard';

function ShareEventSection({ date }: { date: string }) {
  const query = useEvent(date);
  return (
    <section aria-label="Shareable results card" className="flex min-w-0 flex-col gap-2">
      {query.isPending ? (
        <p role="status">Loading…</p>
      ) : query.isError ? (
        <p role="alert">Could not load this Sunday.</p>
      ) : (
        <ShareCard filename={eventFilename(date)}>
          <EventShareCard event={query.data} />
        </ShareCard>
      )}
    </section>
  );
}

/** C10 event section: a shareable results image of the Sunday. */
export const eventSection: EventSection = {
  id: 'share',
  title: 'Share',
  order: 95,
  Component: ShareEventSection,
};
