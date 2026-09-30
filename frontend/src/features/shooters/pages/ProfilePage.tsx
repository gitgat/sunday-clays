import { lazy, Suspense } from 'react';
import { useParams } from 'react-router';
import { ApiError } from '../../../api/errors';
import { EmptyState } from '../../../components/ui/EmptyState';
import { Skeleton } from '../../../components/ui/Skeleton';
import { useTimeWindow } from '../../../lib/timeWindow';
import { useShooter } from '../api';
import { InsightsCard } from '../components/InsightsCard';
import { OdometerStrip } from '../components/OdometerStrip';
import { PbTable } from '../components/PbTable';
import { ProfileHero } from '../components/ProfileHero';
import { ProfileSections } from '../components/ProfileSections';
import { profileSections, sectionsAt } from '../sections';
import type { ProfileSection } from '../sections';

// ECharts is the heaviest chunk: the hero, odometer and insights render before it loads.
const ProfileCharts = lazy(async () => ({
  default: (await import('../components/ProfileCharts')).ProfileCharts,
}));

export function ProfilePage({ sections = profileSections }: { sections?: ProfileSection[] }) {
  const { id: idParam = '' } = useParams();
  const id = Number(idParam);
  const { range } = useTimeWindow();
  const shooter = useShooter(id, range);

  if (!Number.isInteger(id) || id <= 0) {
    return (
      <EmptyState
        title="Shooter not found"
        description="Pick someone from the shooters directory."
      />
    );
  }
  if (shooter.isPending) return <Skeleton className="h-96" />;
  if (shooter.isError) {
    return shooter.error instanceof ApiError && shooter.error.status === 404 ? (
      <EmptyState
        title="Shooter not found"
        description="They may have been merged into another name."
      />
    ) : (
      <EmptyState title="Couldn't load this shooter" description={shooter.error.message} />
    );
  }
  return (
    <div className="flex flex-col gap-4">
      <ProfileHero shooter={shooter.data} isPlaceholderData={shooter.isPlaceholderData} />
      <OdometerStrip odometer={shooter.data.odometer} />
      <ProfileSections shooterId={id} sections={sectionsAt(sections, 'top')} />
      <InsightsCard shooterId={id} deceased={shooter.data.deceased} />
      <Suspense fallback={<Skeleton label="Loading charts" className="h-64" />}>
        <ProfileCharts shooterId={id} />
      </Suspense>
      <PbTable shooterId={id} pbs={shooter.data.pbs} />
      <ProfileSections shooterId={id} sections={sectionsAt(sections, 'bottom')} />
    </div>
  );
}
