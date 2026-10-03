import { useQuery } from '@tanstack/react-query';
import { api, unwrap } from '../api/client';
import type { components } from '../api/schema';
import { useSession, type Role } from '../features/auth/api';

/**
 * A launch-switch key (Plan 19 D23), from the generated API schema. `page_cache` (Plan 19 T11) is an infrastructure switch that
 * `/api/features` never lists, so it is excluded here; until T11 the Exclude is a no-op.
 */
export type FeatureKey = Exclude<components['schemas']['FeatureSwitchOut']['key'], 'page_cache'>;

export const FEATURES_QUERY_KEY = ['/api/features'] as const;

/**
 * `on`: the switch is on for everyone. `visible`: this viewer sees the feature (on, or an admin
 * previewing it). `preview`: an admin sees it while it is off. `settled`: the switches are known;
 * code that acts on "off" (the PWA unregister, D16) checks `settled && !on`.
 */
export interface FeatureState {
  visible: boolean;
  preview: boolean;
  on: boolean;
  settled: boolean;
}

const UNKNOWN: FeatureState = { visible: false, preview: false, on: false, settled: false };

export function featureState(
  switches: Readonly<Record<string, boolean>> | undefined,
  role: Role | null,
  key: FeatureKey,
): FeatureState {
  if (switches === undefined) return UNKNOWN;
  const on = switches[key] === true;
  const admin = role === 'admin';
  return { on, visible: on || admin, preview: !on && admin, settled: true };
}

/** GET /api/features, only once a session exists (never on /login, never a 401 redirect). */
export function useFeatures() {
  const { session } = useSession();
  return useQuery({
    queryKey: FEATURES_QUERY_KEY,
    queryFn: async (): Promise<Record<string, boolean>> =>
      (await unwrap(api.GET('/api/features'))).switches as Record<string, boolean>,
    staleTime: 60_000,
    refetchOnWindowFocus: true,
    enabled: session !== null,
  });
}

export function useFeature(key: FeatureKey): FeatureState {
  const { session } = useSession();
  const query = useFeatures();
  return featureState(query.isSuccess ? query.data : undefined, session?.role ?? null, key);
}
