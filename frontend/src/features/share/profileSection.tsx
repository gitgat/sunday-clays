import { useShooter } from '../shooters/api';
import type { ProfileSection } from '../shooters/sections';
import { ProfileShareCard } from './components/ProfileShareCard';
import { profileFilename } from './filenames';
import { ShareCard } from './ShareCard';

function ShareProfileSection({ shooterId }: { shooterId: number }) {
  // Lifetime numbers (no window), following the global round-type filter like the page does.
  const query = useShooter(shooterId, null);
  return (
    <section aria-label="Shareable profile card" className="flex min-w-0 flex-col gap-2">
      {query.isPending ? (
        <p role="status">Loading…</p>
      ) : query.isError ? (
        <p role="alert">Could not load this shooter.</p>
      ) : (
        <ShareCard filename={profileFilename(query.data.display_name)}>
          <ProfileShareCard shooter={query.data} />
        </ShareCard>
      )}
    </section>
  );
}

/** C10 profile section: a shareable personal best and odometer image. */
export const profileSection: ProfileSection = {
  id: 'share',
  title: 'Share',
  order: 95,
  Component: ShareProfileSection,
};
