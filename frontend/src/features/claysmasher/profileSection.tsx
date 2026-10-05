import type { ProfileSection } from '../shooters/sections';
import { ExportScores } from './components/ExportScores';

/** C10 profile section: the "Export my scores" button under the hero (bare: no card). */
export const profileSection: ProfileSection = {
  id: 'claysmasher-export',
  title: 'Export my scores',
  order: 5,
  placement: 'top',
  bare: true,
  Component: ExportScores,
};
