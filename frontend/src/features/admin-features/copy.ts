import { formatDate } from '../../lib/format';

export const FEATURES_INTRO =
  'Turn a finished feature on for everyone. While a switch is off, only admins see the feature, marked “Admin preview”. Changes reach everyone within a minute. No redeploy needed.';

/** "Changed Oct 2, 2026" from the club-timezone date (D26), or "Never changed". */
export function changedText(updatedOn: string | null): string {
  return updatedOn === null ? 'Never changed' : `Changed ${formatDate(updatedOn)}`;
}
