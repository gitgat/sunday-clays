import type { ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router';
import { Button } from '../../../components/ui/Button';
import { EmptyState } from '../../../components/ui/EmptyState';
import { Skeleton } from '../../../components/ui/Skeleton';
import { useSession, type Role } from '../api';

/**
 * Renders children only for a session with `role` (admin ⊇ viewer). No session → /login with
 * `next` built from pathname + search (C10). A viewer on an admin page sees "Admins only".
 */
export function RequireRole({ role = 'viewer', children }: { role?: Role; children: ReactNode }) {
  const { session, isPending, error, refetch } = useSession();
  const location = useLocation();

  if (isPending) {
    return <Skeleton label="Checking your session" lines={4} className="mx-auto max-w-md p-8" />;
  }
  // Only a failed check with no known session blocks the page: a failed background refresh
  // (reconnect, a stale remount) keeps the cached role instead of unmounting the whole shell.
  if (error && !session) {
    return (
      <EmptyState
        title="Can't reach the server"
        description="Check your connection and try again."
        action={<Button onClick={() => void refetch()}>Try again</Button>}
      />
    );
  }
  if (!session) {
    const next = encodeURIComponent(location.pathname + location.search);
    return <Navigate to={`/login?next=${next}`} replace />;
  }
  if (role === 'admin' && session.role !== 'admin') {
    return (
      <EmptyState
        title="Admins only"
        description="Log out and log in with the admin password to open this page."
      />
    );
  }
  return children;
}
