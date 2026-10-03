import { useFeature, type FeatureKey } from '../../lib/features';

export const ADMIN_PREVIEW_HINT = 'Only admins can see this until it is turned on in Features.';

/** "Admin preview" pill beside a gated feature's title, only while an admin previews it. */
export function AdminPreviewBadge({ feature }: { feature: FeatureKey }) {
  const { preview } = useFeature(feature);
  if (!preview) return null;
  return (
    <span className="inline-flex items-center rounded-button border border-accent px-2 py-0.5 text-xs font-medium text-text">
      Admin preview
      <span className="sr-only"> {ADMIN_PREVIEW_HINT}</span>
    </span>
  );
}
