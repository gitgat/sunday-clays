import type { ReactNode } from 'react';
import { NotFoundView } from '../app/ErrorBoundary';
import { useFeature, useFeatures, type FeatureKey } from '../lib/features';

/**
 * Wraps a gated page (Plan 19 D21): a viewer with the switch off sees "Page not found", an admin
 * sees the page (the page shows its own AdminPreviewBadge). Nothing renders until the switches
 * are known, so a page never flashes in and then out.
 */
export function FeatureGate({ feature, children }: { feature: FeatureKey; children: ReactNode }) {
  const state = useFeature(feature);
  const query = useFeatures();
  if (query.isError) {
    return <p role="alert">Could not load this page. Reload to try again.</p>;
  }
  if (!state.settled) return null;
  if (!state.visible) return <NotFoundView />;
  return <>{children}</>;
}
