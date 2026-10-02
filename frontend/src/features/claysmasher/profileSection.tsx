import type { ProfileSection } from '../shooters/sections';
import { ImportIntoClaySmasher } from './components/ImportIntoClaySmasher';

/** C10 profile section: the "Import into ClaySmasher" button under the hero (bare: no card). */
export const profileSection: ProfileSection = {
  id: 'claysmasher',
  title: 'ClaySmasher',
  order: 5,
  placement: 'top',
  bare: true,
  Component: ImportIntoClaySmasher,
};
