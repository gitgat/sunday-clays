import type { ProfileSection } from '../shooters/sections';
import { TrophyCase } from './TrophyCase';

export const profileSection: ProfileSection = {
  id: 'trophy-case',
  title: 'Trophy Case',
  order: 60,
  Component: TrophyCase,
};
