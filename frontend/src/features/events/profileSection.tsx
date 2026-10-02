import type { ProfileSection } from '../shooters/sections';
import { SpecialShootsCard } from './components/SpecialShootsCard';

/** C10 profile section (Plan 17): the shooter's special shoots, after the weather card. */
export const profileSection: ProfileSection = {
  id: 'special',
  title: 'Special shoots',
  order: 65,
  bare: true,
  Component: SpecialShootsCard,
};
