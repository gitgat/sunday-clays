import type { ProfileSection } from '../shooters/sections';
import { ProfileOutlook } from './components/ProfileOutlook';

/** C10 profile section: the shooter's own expectation for next Sunday. */
export const profileSection: ProfileSection = {
  id: 'next-sunday',
  title: 'Next Sunday',
  order: 20,
  Component: ProfileOutlook,
};
