import { useAnalyticsRange } from '../api';
import { BumpsCard } from '../components/BumpsCard';
import { PageKindsCard } from '../components/PageKindsCard';
import { UptakeCard } from '../components/UptakeCard';
import { VisitorsCard } from '../components/VisitorsCard';

/** Admin Analytics (Plan 16): anonymous site usage over the header's time window, to today. */
export function AnalyticsPage() {
  const { range, tag } = useAnalyticsRange();
  return (
    <div className="flex min-w-0 flex-col gap-4">
      <h1 className="text-2xl font-medium">Analytics</h1>
      <p className="min-w-0 text-sm text-text-muted">
        {tag}. Signed-in visitors only: admin visits are never counted, and nothing here says who
        anyone is.
      </p>
      <VisitorsCard range={range} />
      <PageKindsCard range={range} />
      <BumpsCard range={range} />
      <UptakeCard range={range} />
    </div>
  );
}
