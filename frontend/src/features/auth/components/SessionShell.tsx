import { AppShell } from '../../../components/layout/AppShell';
import { featureState, useFeatures, type FeatureKey } from '../../../lib/features';
import { usePageViewBeacon } from '../../pageviews/beacon';
import { useSession } from '../api';
import { AccountPanel } from './AccountPanel';

/**
 * The AppShell layout for the signed-in session (rendered inside RequireRole). It also sends the
 * anonymous page-view beacon on every page change (Plan 16; router.tsx is closed to edits), and
 * hides nav items whose launch switch is off for this viewer (Plan 19 D21).
 */
export function SessionShell() {
  const { session } = useSession();
  usePageViewBeacon(session?.role ?? null);
  const features = useFeatures();
  const role = session?.role ?? 'viewer';
  const switches = features.data;
  const featureVisible = (key: FeatureKey) => featureState(switches, role, key).visible;
  return (
    <AppShell
      isAdmin={role === 'admin'}
      account={<AccountPanel role={role} />}
      featureVisible={featureVisible}
    />
  );
}
