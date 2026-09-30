import { Navigate } from 'react-router';
import { EmptyState } from '../../../components/ui/EmptyState';
import { useRoundTypeLink } from '../../../lib/roundTypes';
import { useYirClub } from '../api';

/** /yir: open the latest year that has scores. */
export function YirIndexPage() {
  const query = useYirClub(new Date().getFullYear());
  const latest = query.data?.years.at(-1);
  const target = useRoundTypeLink(`/yir/${latest ?? ''}`);
  if (latest !== undefined) return <Navigate to={target} replace />;
  return (
    <main className="mx-auto grid w-full min-w-0 max-w-5xl grid-cols-1 gap-4 p-4">
      <h1 className="text-2xl font-bold">Year in Review</h1>
      {query.isPending ? (
        <p role="status">Loading Year in Review…</p>
      ) : query.isError ? (
        <p role="alert">Could not load Year in Review.</p>
      ) : (
        <EmptyState title="No scores have been imported yet." />
      )}
    </main>
  );
}
