import { AppShell } from '../../../components/layout/AppShell';
import { useSession } from '../api';
import { AccountPanel } from './AccountPanel';

/** The AppShell layout for the signed-in session (rendered inside RequireRole). */
export function SessionShell() {
  const { session } = useSession();
  const role = session?.role ?? 'viewer';
  return <AppShell isAdmin={role === 'admin'} account={<AccountPanel role={role} />} />;
}
