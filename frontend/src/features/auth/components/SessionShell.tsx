import { AppShell } from '../../../components/layout/AppShell';
import { usePageViewBeacon } from '../../pageviews/beacon';
import { useSession } from '../api';
import { AccountPanel } from './AccountPanel';

/**
 * The AppShell layout for the signed-in session (rendered inside RequireRole). It also sends the
 * anonymous page-view beacon on every page change (Plan 16; router.tsx is closed to edits).
 */
export function SessionShell() {
  const { session } = useSession();
  usePageViewBeacon(session?.role ?? null);
  const role = session?.role ?? 'viewer';
  return <AppShell isAdmin={role === 'admin'} account={<AccountPanel role={role} />} />;
}
